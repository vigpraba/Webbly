from __future__ import annotations

from collectors.requests_collector import (
    RequestsCollector,
)
from parsers.scrapeme import ScrapeMeParser


def crawl_once(url: str) -> dict:
    """
    Collect and parse exactly one page.

    This function keeps the result format expected by
    tasks.py, so tasks.py does not need to change.
    """
    collector = RequestsCollector()
    parser = ScrapeMeParser()

    collected_page = collector.collect(url)

    parsed_page = parser.parse(
        page_url=collected_page.final_url,
        html=collected_page.html,
    )

    return {
        "requested_url": (
            collected_page.requested_url
        ),
        "final_url": collected_page.final_url,
        "status_code": (
            collected_page.status_code
        ),
        "title": parsed_page.title,
        "product_count": len(
            parsed_page.products
        ),
        "products": parsed_page.products,

        # Keep this key name because tasks.py currently
        # expects page_result["pagination_links"].
        "pagination_links": (
            parsed_page.discovered_urls
        ),
    }
