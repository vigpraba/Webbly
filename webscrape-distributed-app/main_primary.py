from __future__ import annotations

import json
import time

from repository import CrawlRepository
from tasks_primary import crawl_page


START_URL = "https://scrapeme.live/shop/"

# Keep this small while learning.
MAX_PAGES = 8

RUN_TIMEOUT_SECONDS = 180


def main() -> None:
    repository = CrawlRepository()

    # Verify Python can reach crawler Redis DB 2.
    repository.client.ping()

    print(f"VIGNESH-TEST:{repository.client.info()}")
    run_id = repository.create_run(
        start_url=START_URL,
        max_pages=MAX_PAGES,
    )

    claim_result = repository.claim_url(
        run_id,
        START_URL,
    )

    if claim_result != "claimed":
        raise RuntimeError(
            "Could not claim the starting URL"
        )

    print("Starting distributed crawl")
    print("--------------------------")
    print(f"Run ID: {run_id}")
    print(f"Start URL: {START_URL}")
    print(f"Maximum pages: {MAX_PAGES}")
    print()

    try:
        initial_task = crawl_page.delay(
            run_id,
            START_URL,
        )
    except Exception as error:
        repository.mark_failed(
            run_id,
            START_URL,
            (
                f"Could not publish initial task: "
                f"{type(error).__name__}: {error}"
            ),
        )

        print(
            f"Could not publish the initial task: "
            f"{error}"
        )
        return

    print(
        f"Initial Celery task ID: "
        f"{initial_task.id}"
    )
    print("Waiting for the crawl to complete...")
    print()

    deadline = (
        time.monotonic()
        + RUN_TIMEOUT_SECONDS
    )

    previous_snapshot: tuple | None = None

    while True:
        summary = repository.get_summary(
            run_id
        )

        snapshot = (
            summary["state"],
            summary["scheduled"],
            summary["pending"],
            summary["visited"],
            summary["failed"],
            summary["product_count"],
        )

        if snapshot != previous_snapshot:
            print(
                f"state={summary['state']} | "
                f"scheduled={summary['scheduled']} | "
                f"pending={summary['pending']} | "
                f"visited={summary['visited']} | "
                f"failed={summary['failed']} | "
                f"products={summary['product_count']}"
            )

            previous_snapshot = snapshot

        if summary["state"] == "complete":
            break

        if time.monotonic() >= deadline:
            print()
            print(
                "The crawl did not finish within "
                f"{RUN_TIMEOUT_SECONDS} seconds."
            )
            print(
                "Check both Celery worker terminals "
                "for errors."
            )
            return

        time.sleep(1)

    print()
    print("Crawl complete")
    print("--------------")
    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        )
    )

    sample_products = (
        repository.get_products(
            run_id,
            limit=5,
        )
    )

    print()
    print("Sample products")
    print("---------------")
    print(
        json.dumps(
            sample_products,
            indent=2,
            ensure_ascii=False,
        )
    )

    errors = repository.get_errors(
        run_id,
        limit=5,
    )

    if errors:
        print()
        print("Crawl errors")
        print("------------")
        print(
            json.dumps(
                errors,
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
