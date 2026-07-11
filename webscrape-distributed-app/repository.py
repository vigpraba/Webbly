from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

import redis


ClaimResult = Literal["claimed", "seen", "limit"]


def utc_now() -> str:
    """Return the current time as an ISO-8601 UTC string."""
    return datetime.now(timezone.utc).isoformat()


# Atomically:
# 1. Check whether the URL was already seen.
# 2. Check the maximum-page limit.
# 3. Add the URL to the seen set.
# 4. Increment scheduled and pending counters.
# 5. Mark the URL as queued.
CLAIM_URL_SCRIPT = """
local seen_key = KEYS[1]
local url_status_key = KEYS[2]
local meta_key = KEYS[3]

local url = ARGV[1]

if redis.call("SISMEMBER", seen_key, url) == 1 then
    return 0
end

local max_pages = tonumber(
    redis.call("HGET", meta_key, "max_pages") or "0"
)

local scheduled = tonumber(
    redis.call("HGET", meta_key, "scheduled") or "0"
)

if max_pages <= 0 then
    return -2
end

if scheduled >= max_pages then
    return -1
end

redis.call("SADD", seen_key, url)
redis.call("HSET", url_status_key, url, "queued")
redis.call("HINCRBY", meta_key, "scheduled", 1)
redis.call("HINCRBY", meta_key, "pending", 1)

return 1
"""


MARK_RUNNING_SCRIPT = """
local url_status_key = KEYS[1]
local url = ARGV[1]

local current_status = redis.call(
    "HGET",
    url_status_key,
    url
)

if not current_status then
    return 0
end

if current_status == "visited"
    or current_status == "failed" then
    return 0
end

redis.call(
    "HSET",
    url_status_key,
    url,
    "running"
)

return 1
"""


MARK_RETRYING_SCRIPT = """
local url_status_key = KEYS[1]
local url = ARGV[1]

local current_status = redis.call(
    "HGET",
    url_status_key,
    url
)

if not current_status then
    return 0
end

if current_status == "visited"
    or current_status == "failed" then
    return 0
end

redis.call(
    "HSET",
    url_status_key,
    url,
    "retrying"
)

return 1
"""


# Atomically mark one URL as terminal.
#
# A terminal URL is either:
# - visited successfully
# - failed permanently
#
# The pending counter is decremented only once.
MARK_TERMINAL_SCRIPT = """
local url_status_key = KEYS[1]
local meta_key = KEYS[2]

local url = ARGV[1]
local final_status = ARGV[2]
local counter_field = ARGV[3]
local finished_at = ARGV[4]

local current_status = redis.call(
    "HGET",
    url_status_key,
    url
)

local pending = tonumber(
    redis.call("HGET", meta_key, "pending") or "0"
)

if not current_status then
    return {-1, pending}
end

if current_status == "visited"
    or current_status == "failed" then
    return {0, pending}
end

redis.call(
    "HSET",
    url_status_key,
    url,
    final_status
)

redis.call(
    "HINCRBY",
    meta_key,
    counter_field,
    1
)

pending = redis.call(
    "HINCRBY",
    meta_key,
    "pending",
    -1
)

if pending <= 0 then
    pending = 0

    redis.call(
        "HSET",
        meta_key,
        "pending",
        0
    )

    redis.call(
        "HSET",
        meta_key,
        "state",
        "complete"
    )

    redis.call(
        "HSET",
        meta_key,
        "finished_at",
        finished_at
    )
end

return {1, pending}
"""


class CrawlRepository:
    """
    Store crawl state and extracted products in Redis.

    Redis database usage:

        DB 0: Celery task broker
        DB 1: Celery task results
        DB 2: crawler state and extracted products
    """

    def __init__(
        self,
        redis_url: str | None = None,
    ) -> None:
        self.redis_url = redis_url or os.getenv(
            "CRAWLER_REDIS_URL",
            "redis://127.0.0.1:6379/2",
        )

        self.client = redis.Redis.from_url(
            self.redis_url,
            decode_responses=True,
        )

    @staticmethod
    def _keys(run_id: str) -> dict[str, str]:
        # Braces keep related keys grouped together if Redis
        # Cluster is used later.
        prefix = f"crawl:{{{run_id}}}"

        return {
            "meta": f"{prefix}:meta",
            "seen": f"{prefix}:seen",
            "url_status": f"{prefix}:url-status",
            "products": f"{prefix}:products",
            "errors": f"{prefix}:errors",
        }

    def create_run(
        self,
        start_url: str,
        max_pages: int,
    ) -> str:
        if max_pages < 1:
            raise ValueError(
                "max_pages must be at least 1"
            )

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%SZ")

        run_id = (
            f"{timestamp}-{uuid4().hex[:8]}"
        )

        keys = self._keys(run_id)

        self.client.hset(
            keys["meta"],
            mapping={
                "run_id": run_id,
                "start_url": start_url,
                "max_pages": max_pages,
                "state": "running",
                "created_at": utc_now(),
                "scheduled": 0,
                "pending": 0,
                "visited": 0,
                "failed": 0,
            },
        )

        return run_id

    def claim_url(
        self,
        run_id: str,
        url: str,
    ) -> ClaimResult:
        """
        Attempt to reserve a URL for this crawl.

        Returns:
            claimed: URL was new and reserved
            seen: URL was already scheduled
            limit: maximum-page limit was reached
        """
        keys = self._keys(run_id)

        result = int(
            self.client.eval(
                CLAIM_URL_SCRIPT,
                3,
                keys["seen"],
                keys["url_status"],
                keys["meta"],
                url,
            )
        )

        if result == 1:
            return "claimed"

        if result == 0:
            return "seen"

        if result == -1:
            return "limit"

        raise RuntimeError(
            f"Unable to claim URL for run {run_id}"
        )

    def mark_running(
        self,
        run_id: str,
        url: str,
    ) -> bool:
        keys = self._keys(run_id)

        result = self.client.eval(
            MARK_RUNNING_SCRIPT,
            1,
            keys["url_status"],
            url,
        )

        return int(result) == 1

    def mark_retrying(
        self,
        run_id: str,
        url: str,
    ) -> bool:
        keys = self._keys(run_id)

        result = self.client.eval(
            MARK_RETRYING_SCRIPT,
            1,
            keys["url_status"],
            url,
        )

        return int(result) == 1

    def _mark_terminal(
        self,
        run_id: str,
        url: str,
        final_status: str,
        counter_field: str,
    ) -> tuple[bool, int]:
        keys = self._keys(run_id)

        result = self.client.eval(
            MARK_TERMINAL_SCRIPT,
            2,
            keys["url_status"],
            keys["meta"],
            url,
            final_status,
            counter_field,
            utc_now(),
        )

        changed = int(result[0]) == 1
        pending = int(result[1])

        return changed, pending

    def mark_visited(
        self,
        run_id: str,
        url: str,
    ) -> int:
        _, pending = self._mark_terminal(
            run_id=run_id,
            url=url,
            final_status="visited",
            counter_field="visited",
        )

        return pending

    def mark_failed(
        self,
        run_id: str,
        url: str,
        error: str,
    ) -> int:
        keys = self._keys(run_id)

        changed, pending = self._mark_terminal(
            run_id=run_id,
            url=url,
            final_status="failed",
            counter_field="failed",
        )

        if changed:
            self.client.hset(
                keys["errors"],
                url,
                error[:2000],
            )

        return pending

    def store_products(
        self,
        run_id: str,
        source_page: str,
        products: list[dict],
    ) -> int:
        """
        Store products in a Redis hash.

        The product URL or product ID is used as a stable key,
        preventing the same product from being stored repeatedly.
        """
        if not products:
            return 0

        keys = self._keys(run_id)
        pipeline = self.client.pipeline(
            transaction=False
        )

        for product in products:
            stored_product = {
                **product,
                "source_page": source_page,
            }

            identity = (
                product.get("url")
                or (
                    f"id:{product['id']}"
                    if product.get("id")
                    else None
                )
            )

            if identity is None:
                serialized = json.dumps(
                    stored_product,
                    sort_keys=True,
                    ensure_ascii=False,
                )

                identity = hashlib.sha256(
                    serialized.encode("utf-8")
                ).hexdigest()

            pipeline.hset(
                keys["products"],
                identity,
                json.dumps(
                    stored_product,
                    ensure_ascii=False,
                ),
            )

        results = pipeline.execute()

        # HSET returns 1 for a new hash field and 0 when an
        # existing field was updated.
        return sum(int(value) for value in results)

    def get_summary(
        self,
        run_id: str,
    ) -> dict:
        keys = self._keys(run_id)
        summary = self.client.hgetall(
            keys["meta"]
        )

        if not summary:
            raise KeyError(
                f"Crawl run does not exist: {run_id}"
            )

        integer_fields = (
            "max_pages",
            "scheduled",
            "pending",
            "visited",
            "failed",
        )

        for field in integer_fields:
            summary[field] = int(
                summary.get(field, 0)
            )

        summary["product_count"] = (
            self.client.hlen(keys["products"])
        )

        return summary

    def get_products(
        self,
        run_id: str,
        limit: int | None = None,
    ) -> list[dict]:
        keys = self._keys(run_id)

        products = [
            json.loads(value)
            for value in self.client.hvals(
                keys["products"]
            )
        ]

        products.sort(
            key=lambda product: (
                str(product.get("source_page", "")),
                str(product.get("name", "")),
            )
        )

        if limit is not None:
            return products[:limit]

        return products

    def get_errors(
        self,
        run_id: str,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        keys = self._keys(run_id)

        errors = [
            {
                "url": url,
                "error": error,
            }
            for url, error in self.client.hgetall(
                keys["errors"]
            ).items()
        ]

        errors.sort(
            key=lambda item: item["url"]
        )

        return errors[:limit]
