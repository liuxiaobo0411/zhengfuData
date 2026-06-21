from __future__ import annotations

import json

import httpx

from app.models import SiteSection
from app.services.crawler.types import FetchedPage

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)


def section_headers(section: SiteSection) -> dict[str, str]:
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if section.request_headers:
        parsed = json.loads(section.request_headers)
        if not isinstance(parsed, dict):
            raise ValueError("request_headers must be a JSON object")
        headers.update({str(key): str(value) for key, value in parsed.items()})
    return headers


def fetch_url(url: str, section: SiteSection, timeout: int | None = None) -> FetchedPage:
    retries = max(0, section.retry_times if section.crawler_strategy == "http_with_retry" else 0)
    headers = section_headers(section)
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            response = httpx.get(
                url,
                follow_redirects=True,
                headers=headers,
                timeout=timeout or section.request_timeout,
            )
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            return FetchedPage(
                url=url,
                final_url=str(response.url),
                body=response.content,
                text=response.text,
                content_type=response.headers.get("content-type", ""),
            )
        except httpx.HTTPError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("request failed without error")
