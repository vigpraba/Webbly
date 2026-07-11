from __future__ import annotations

from typing import Any

import requests
from celery import Celery

from crawler import crawl_once
from repository import CrawlRepository
from safety import (
    RobotsPolicy,
    SharedDomainDelay,
)


app = Celery(
    "tasks",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/1",
)


app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
)


_repository: CrawlRepository | None = None
_robots_policy: RobotsPolicy | None = None


def get_repository() -> CrawlRepository:
    global _repository

    if _repository is None:
        _repository = CrawlRepository()

    return _repository


def get_robots_policy() -> RobotsPolicy:
    global _robots_policy

    if _robots_policy is None:
        _robots_policy = RobotsPolicy()

    return _robots_policy


@app.task(
    bind=True,
    name="tasks.crawl_page",
    max_retries=3,
    ignore_result=True,
)
def crawl_page(
    self,
    run_id: str,
    url: str,
) -> dict[str, Any]:
    repository = get_repository()
    robots_policy = get_robots_policy()

    worker_name = (
        self.request.hostname
        or "unknown-worker"
    )

    if not repository.mark_running(
        run_id,
        url,
    ):
        return {
            "run_id": run_id,
            "url": url,
            "status": "already-terminal",
        }

    try:
        # 1. Check robots.txt.
        robots_decision = (
            robots_policy.check(url)
        )

        if not robots_decision.allowed:
            pending = repository.mark_failed(
                run_id,
                url,
                (
                    "Blocked by robots.txt: "
                    f"{robots_decision.robots_url}"
                ),
            )

            print(
                f"[{worker_name}] "
                f"Robots denied: {url} | "
                f"pending={pending}",
                flush=True,
            )

            return {
                "run_id": run_id,
                "url": url,
                "status": "robots-denied",
                "pending": pending,
            }

        # 2. Coordinate the request delay through Redis.
        rate_limiter = SharedDomainDelay(
            repository.client
        )

        waited_seconds = rate_limiter.wait(
            url=url,
            delay_seconds=(
                robots_decision.delay_seconds
            ),
        )

        print(
            f"[{worker_name}] "
            f"Starting: {url} | "
            f"rate_wait={waited_seconds:.2f}s",
            flush=True,
        )

        # 3. Download and parse one page.
        page_result = crawl_once(url)

        new_product_count = (
            repository.store_products(
                run_id=run_id,
                source_page=(
                    page_result["final_url"]
                ),
                products=(
                    page_result["products"]
                ),
            )
        )

        scheduled_children = 0

        # 4. Claim and publish child URLs.
        for child_url in page_result[
            "pagination_links"
        ]:
            claim_result = (
                repository.claim_url(
                    run_id,
                    child_url,
                )
            )

            if claim_result != "claimed":
                continue

            try:
                crawl_page.delay(
                    run_id,
                    child_url,
                )
            except Exception as publish_error:
                repository.mark_failed(
                    run_id,
                    child_url,
                    (
                        "Could not publish task: "
                        f"{type(publish_error).__name__}: "
                        f"{publish_error}"
                    ),
                )
            else:
                scheduled_children += 1

        # Children are scheduled before the parent is completed.
        pending = repository.mark_visited(
            run_id,
            url,
        )

        print(
            f"[{worker_name}] "
            f"Completed: {url} | "
            f"products="
            f"{page_result['product_count']} | "
            f"new_products="
            f"{new_product_count} | "
            f"children="
            f"{scheduled_children} | "
            f"pending={pending}",
            flush=True,
        )

        return {
            "run_id": run_id,
            "url": url,
            "status": "visited",
            "pending": pending,
        }

    except requests.RequestException as error:
        maximum_retries = int(
            self.max_retries or 0
        )

        if (
            self.request.retries
            < maximum_retries
        ):
            repository.mark_retrying(
                run_id,
                url,
            )

            countdown = min(
                2 ** (
                    self.request.retries + 1
                ),
                30,
            )

            print(
                f"[{worker_name}] "
                f"Temporary failure: {url} | "
                f"retry_in={countdown}s | "
                f"error={error}",
                flush=True,
            )

            raise self.retry(
                exc=error,
                countdown=countdown,
            )

        pending = repository.mark_failed(
            run_id,
            url,
            (
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        print(
            f"[{worker_name}] "
            f"Retries exhausted: {url} | "
            f"pending={pending}",
            flush=True,
        )

        raise

    except Exception as error:
        # Permanent HTTP errors, parsing errors,
        # and unexpected programming errors arrive here.
        pending = repository.mark_failed(
            run_id,
            url,
            (
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        print(
            f"[{worker_name}] "
            f"Permanent failure: {url} | "
            f"pending={pending} | "
            f"error={error}",
            flush=True,
        )

        raise
