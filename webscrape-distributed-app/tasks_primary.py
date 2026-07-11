from __future__ import annotations

from typing import Any

import requests
from celery import Celery

from crawler_primary import crawl_once
from repository import CrawlRepository


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

    # Reduce how many additional long-running crawl tasks
    # each process reserves in advance.
    worker_prefetch_multiplier=1,

    timezone="UTC",
    enable_utc=True,
)


_repository: CrawlRepository | None = None


def get_repository() -> CrawlRepository:
    """
    Lazily create one repository object in each worker process.
    """
    global _repository

    if _repository is None:
        _repository = CrawlRepository()

    return _repository


@app.task(
    bind=True,
    name="tasks.crawl_page",
    max_retries=3,

    # Crawl state is stored in Redis DB 2, so we do not need
    # every task result duplicated in Celery's result backend.
    ignore_result=True,
)
def crawl_page(
    self,
    run_id: str,
    url: str,
) -> dict[str, Any]:
    """
    Crawl one URL and schedule newly discovered URLs.
    """
    repository = get_repository()

    task_id = self.request.id
    worker_name = (
        self.request.hostname
        or "unknown-worker"
    )

    # A duplicate/redelivered task that is already terminal
    # should not decrement counters or repeat work.
    if not repository.mark_running(
        run_id,
        url,
    ):
        print(
            f"[{worker_name}] Skipping already-terminal "
            f"URL: {url}",
            flush=True,
        )

        return {
            "run_id": run_id,
            "url": url,
            "status": "already-terminal",
        }

    print(
        f"[{worker_name}] Starting: {url}",
        flush=True,
    )

    try:
        page_result = crawl_once(url)

        new_product_count = (
            repository.store_products(
                run_id=run_id,
                source_page=page_result["final_url"],
                products=page_result["products"],
            )
        )

        scheduled_children = 0
        duplicate_children = 0
        limited_children = 0
        publish_failures = 0

        for child_url in page_result[
            "pagination_links"
        ]:
            claim_result = repository.claim_url(
                run_id,
                child_url,
            )

            if claim_result == "seen":
                duplicate_children += 1
                continue

            if claim_result == "limit":
                limited_children += 1
                continue

            # This worker is now also acting as a producer.
            try:
                crawl_page.delay(
                    run_id,
                    child_url,
                )
            except Exception as publish_error:
                publish_failures += 1

                repository.mark_failed(
                    run_id,
                    child_url,
                    (
                        "Could not publish Celery task: "
                        f"{type(publish_error).__name__}: "
                        f"{publish_error}"
                    ),
                )

                print(
                    f"[{worker_name}] Could not publish "
                    f"{child_url}: {publish_error}",
                    flush=True,
                )
            else:
                scheduled_children += 1

        pending = repository.mark_visited(
            run_id,
            url,
        )

        print(
            f"[{worker_name}] Completed: {url} | "
            f"products={page_result['product_count']} | "
            f"new_products={new_product_count} | "
            f"children={scheduled_children} | "
            f"pending={pending}",
            flush=True,
        )

        return {
            "run_id": run_id,
            "task_id": task_id,
            "worker": worker_name,
            "url": url,
            "status": "visited",
            "products_found": (
                page_result["product_count"]
            ),
            "new_products": new_product_count,
            "scheduled_children": (
                scheduled_children
            ),
            "duplicate_children": (
                duplicate_children
            ),
            "limited_children": limited_children,
            "publish_failures": publish_failures,
            "pending": pending,
        }

    except requests.RequestException as error:
        maximum_retries = int(
            self.max_retries or 0
        )

        if self.request.retries < maximum_retries:
            repository.mark_retrying(
                run_id,
                url,
            )

            countdown = min(
                2 ** (self.request.retries + 1),
                30,
            )

            print(
                f"[{worker_name}] Temporary request "
                f"failure for {url}. "
                f"Retrying in {countdown} seconds: "
                f"{error}",
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
            f"[{worker_name}] Permanently failed: "
            f"{url} | pending={pending}",
            flush=True,
        )

        raise

    except Exception as error:
        pending = repository.mark_failed(
            run_id,
            url,
            (
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        print(
            f"[{worker_name}] Failed: {url} | "
            f"pending={pending} | error={error}",
            flush=True,
        )

        raise
