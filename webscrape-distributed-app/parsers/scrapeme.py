from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import (
    urldefrag,
    urljoin,
    urlsplit,
)

from bs4 import BeautifulSoup


Product = dict[str, str | None]


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """
    Structured data extracted from one HTML page.
    """

    title: str | None
    products: list[Product]
    discovered_urls: list[str]


class ScrapeMeParser:
    """
    Parse product listing pages from scrapeme.live.
    """

    def parse(
        self,
        page_url: str,
        html: str,
    ) -> ParsedPage:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        title_node = soup.select_one("title")

        return ParsedPage(
            title=(
                title_node.get_text(
                    " ",
                    strip=True,
                )
                if title_node is not None
                else None
            ),
            products=self._extract_products(
                page_url,
                soup,
            ),
            discovered_urls=(
                self._extract_pagination_links(
                    page_url,
                    soup,
                )
            ),
        )

    @staticmethod
    def _extract_products(
        page_url: str,
        soup: BeautifulSoup,
    ) -> list[Product]:
        products: list[Product] = []

        for product_node in soup.select(
            "li.product"
        ):
            name_node = product_node.select_one(
                "h2"
            )

            price_node = product_node.select_one(
                ".price .amount, .amount"
            )

            id_node = product_node.select_one(
                "[data-product_id]"
            )

            link_node = product_node.select_one(
                "a.woocommerce-LoopProduct-link[href], "
                "a[href]"
            )

            if name_node is None:
                continue

            raw_product_id = (
                id_node.get("data-product_id")
                if id_node is not None
                else None
            )

            product_id = (
                str(raw_product_id)
                if raw_product_id is not None
                else None
            )

            raw_href = (
                link_node.get("href")
                if link_node is not None
                else None
            )

            product_url = (
                urljoin(page_url, raw_href)
                if isinstance(raw_href, str)
                else None
            )

            products.append(
                {
                    "id": product_id,
                    "name": name_node.get_text(
                        " ",
                        strip=True,
                    ),
                    "price": (
                        price_node.get_text(
                            " ",
                            strip=True,
                        )
                        if price_node is not None
                        else None
                    ),
                    "url": product_url,
                }
            )

        return products

    @staticmethod
    def _extract_pagination_links(
        page_url: str,
        soup: BeautifulSoup,
    ) -> list[str]:
        page_hostname = (
            urlsplit(page_url).hostname or ""
        ).lower()

        discovered_urls: set[str] = set()

        for anchor in soup.select(
            "a.page-numbers[href]"
        ):
            raw_href = anchor.get("href")

            if not isinstance(raw_href, str):
                continue

            absolute_url = urljoin(
                page_url,
                raw_href,
            )

            normalized_url, _ = urldefrag(
                absolute_url
            )

            parsed_url = urlsplit(
                normalized_url
            )

            if parsed_url.scheme not in {
                "http",
                "https",
            }:
                continue

            if (
                parsed_url.hostname or ""
            ).lower() != page_hostname:
                continue

            if "/shop/page/" not in parsed_url.path:
                continue

            discovered_urls.add(
                normalized_url
            )

        return sorted(discovered_urls)
