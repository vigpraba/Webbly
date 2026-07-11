from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from redis import Redis


ROBOT_USER_AGENT = "DistributedCrawlerTutorial"

HTTP_USER_AGENT = (
    "DistributedCrawlerTutorial/1.0 "
    "(educational local crawler)"
)

DEFAULT_DELAY_SECONDS = 1.0
ROBOTS_CACHE_SECONDS = 3600


@dataclass(frozen=True, slots=True)
class RobotsDecision:
    """
    Result of checking robots.txt for one URL.
    """

    allowed: bool
    delay_seconds: float
    robots_url: str


class RobotsPolicy:
    """
    Download, parse, and temporarily cache robots.txt files.

    The cache belongs to one worker process. That is sufficient
    for this basic implementation.
    """

    def __init__(
        self,
        robot_user_agent: str = ROBOT_USER_AGENT,
        default_delay_seconds: float = (
            DEFAULT_DELAY_SECONDS
        ),
        cache_seconds: int = ROBOTS_CACHE_SECONDS,
    ) -> None:
        self.robot_user_agent = robot_user_agent
        self.default_delay_seconds = (
            default_delay_seconds
        )
        self.cache_seconds = cache_seconds

        self._cache: dict[
            str,
            tuple[float, RobotFileParser],
        ] = {}

    def check(self, url: str) -> RobotsDecision:
        parsed_url = urlsplit(url)

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise ValueError(
                f"Invalid HTTP URL: {url}"
            )

        origin = (
            f"{parsed_url.scheme}://"
            f"{parsed_url.netloc}"
        )

        robots_url = f"{origin}/robots.txt"

        parser = self._get_parser(
            origin=origin,
            robots_url=robots_url,
        )

        delay = parser.crawl_delay(
            self.robot_user_agent
        )

        if delay is None:
            delay = parser.crawl_delay("*")

        if delay is None:
            delay = self.default_delay_seconds

        return RobotsDecision(
            allowed=parser.can_fetch(
                self.robot_user_agent,
                url,
            ),
            delay_seconds=max(
                0.0,
                float(delay),
            ),
            robots_url=robots_url,
        )

    def _get_parser(
        self,
        origin: str,
        robots_url: str,
    ) -> RobotFileParser:
        now = time.monotonic()

        cached = self._cache.get(origin)

        if cached is not None:
            expires_at, parser = cached

            if expires_at > now:
                return parser

        response = requests.get(
            robots_url,
            headers={
                "User-Agent": HTTP_USER_AGENT,
                "Accept": "text/plain,*/*",
            },
            timeout=(5, 10),
        )

        parser = RobotFileParser()
        parser.set_url(robots_url)

        if response.status_code == 200:
            parser.parse(
                response.text.splitlines()
            )

        elif response.status_code in {401, 403}:
            # Basic conservative behavior:
            # inaccessible robots.txt means crawl nothing.
            parser.parse(
                [
                    "User-agent: *",
                    "Disallow: /",
                ]
            )

        elif (
            response.status_code == 429
            or response.status_code >= 500
        ):
            # Temporary server errors should be retried
            # by the Celery task.
            response.raise_for_status()

        else:
            # 404 and other non-temporary responses:
            # treat as no robots restrictions.
            parser.parse([])

        self._cache[origin] = (
            now + self.cache_seconds,
            parser,
        )

        return parser


class SharedDomainDelay:
    """
    Ensure workers do not all request the same domain at once.

    Redis stores a short-lived key for each hostname.
    Only one worker can create the key at a time.
    """

    def __init__(
        self,
        redis_client: Redis,
    ) -> None:
        self.redis_client = redis_client

    def wait(
        self,
        url: str,
        delay_seconds: float,
    ) -> float:
        """
        Wait until this worker obtains the next domain slot.

        Returns the approximate number of seconds spent waiting.
        """
        if delay_seconds <= 0:
            return 0.0

        hostname = (
            urlsplit(url).hostname
            or "unknown-host"
        ).lower()

        redis_key = (
            f"crawler:domain-delay:"
            f"{{{hostname}}}"
        )

        delay_milliseconds = max(
            1,
            round(delay_seconds * 1000),
        )

        started_at = time.monotonic()

        while True:
            acquired = self.redis_client.set(
                redis_key,
                "reserved",
                nx=True,
                px=delay_milliseconds,
            )

            if acquired:
                break

            remaining_milliseconds = (
                self.redis_client.pttl(
                    redis_key
                )
            )

            if remaining_milliseconds > 0:
                sleep_seconds = (
                    remaining_milliseconds
                    / 1000
                )
            else:
                sleep_seconds = 0.05

            time.sleep(
                max(0.05, sleep_seconds)
            )

        return time.monotonic() - started_at
