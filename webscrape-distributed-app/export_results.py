from __future__ import annotations

import argparse
import json
from pathlib import Path

from repository import CrawlRepository


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export one distributed crawl run "
            "to JSON."
        )
    )

    parser.add_argument(
        "--run-id",
        required=True,
        help="Run ID printed by main.py",
    )

    parser.add_argument(
        "--output",
        help=(
            "Output filename. Defaults to "
            "results/<run-id>.json"
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    repository = CrawlRepository()

    run_id = arguments.run_id

    summary = repository.get_summary(
        run_id
    )

    products = repository.get_products(
        run_id
    )

    errors = repository.get_errors(
        run_id,
        limit=10_000,
    )

    output_path = Path(
        arguments.output
        or f"results/{run_id}.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "summary": summary,
        "products": products,
        "errors": errors,
    }

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Exported run: {run_id}")
    print(f"Products: {len(products)}")
    print(f"Errors: {len(errors)}")
    print(
        f"Output: {output_path.resolve()}"
    )


if __name__ == "__main__":
    main()
