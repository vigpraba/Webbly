from __future__ import annotations

from dataclasses import dataclass

import requests

from safety import HTTP_USER_AGENT


RETRYABLE_STATUS_CODES = {
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}


class RetryableHttpError(
    requests.HTTPError
):
    """
    An HTTP error that may succeed when retried later.
    """


class PermanentHttpError(RuntimeError):
    """
    An HTTP error that should not normally be retried.
    """


@dataclass(frozen=True, slots=True)
class CollectedPage:
    requested_url: str
    final_url: str
    status_code: int
    html: str


class RequestsCollector:
    """
    Download server-rendered HTML using Requests.
    """

    def __init__(
        self,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
    ) -> None:
        self.timeout = (
            connect_timeout,
            read_timeout,
        )

        self.headers = {
            "User-Agent": HTTP_USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml"
            ),
        }

    def collect(
        self,
        url: str,
    ) -> CollectedPage:
        response = requests.get(
            url,
            headers=self.headers,
            timeout=self.timeout,
            allow_redirects=True,
        )

        status_code = response.status_code

        if status_code in RETRYABLE_STATUS_CODES:
            raise RetryableHttpError(
                (
                    f"Temporary HTTP "
                    f"{status_code} for {url}"
                ),
                response=response,
            )

        if status_code >= 400:
            raise PermanentHttpError(
                (
                    f"Permanent HTTP "
                    f"{status_code} for {url}"
                )
            )

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        if "text/html" not in content_type:
            raise PermanentHttpError(
                (
                    f"Expected HTML from {url}, "
                    f"but received "
                    f"{content_type!r}"
                )
            )

        return CollectedPage(
            requested_url=url,
            final_url=response.url,
            status_code=status_code,
            html=response.text,
        )
