from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

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
    request_url = normalize_request_url(url)
    retries = max(0, section.retry_times if section.crawler_strategy == "http_with_retry" else 0)
    headers = section_headers(section)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = httpx.get(
                request_url,
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
                headers=dict(response.headers),
            )
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < retries:
                wait_for_retry(section, attempt)
    if last_error is not None:
        return fetch_url_with_curl(url, section, timeout or section.request_timeout)
    raise RuntimeError("request failed without error")


def fetch_browser_rendered_page(
    url: str,
    section: SiteSection,
    timeout: int | None = None,
) -> FetchedPage:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "browser_rendered 策略需要安装 Playwright："
            'python -m pip install ".[browser]" && python -m playwright install chromium'
        ) from exc

    request_url = normalize_request_url(url)
    headers = section_headers(section)
    timeout_ms = max(1, timeout or section.request_timeout) * 1000
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(extra_http_headers=headers)
                page.goto(request_url, wait_until="networkidle", timeout=timeout_ms)
                body = page.content().encode("utf-8")
                return FetchedPage(
                    url=url,
                    final_url=page.url,
                    body=body,
                    text=body.decode("utf-8"),
                    content_type="text/html; charset=utf-8",
                    headers={},
                )
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise RuntimeError(f"browser_rendered 页面渲染失败：{exc}") from exc


def add_query_params(url: str, params: dict[str, str]) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params)}"


def fetch_url_with_curl(url: str, section: SiteSection, timeout: int) -> FetchedPage:
    headers = section_headers(section)
    request_url = normalize_request_url(url)
    with tempfile.NamedTemporaryFile(delete=False) as body_file:
        body_path = Path(body_file.name)
    try:
        command = [
            "curl",
            "--compressed",
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout),
            "-o",
            str(body_path),
            "-w",
            "%{url_effective}\n%{content_type}",
        ]
        for key, value in headers.items():
            if key.lower() == "user-agent":
                command.extend(["-A", value])
            else:
                command.extend(["-H", f"{key}: {value}"])
        command.append(request_url)
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        output_lines = result.stdout.splitlines()
        final_url = output_lines[0] if output_lines else url
        content_type = output_lines[1] if len(output_lines) > 1 else ""
        body = body_path.read_bytes()
        return FetchedPage(
            url=url,
            final_url=final_url,
            body=body,
            text=decode_body(body, content_type),
            content_type=content_type,
        )
    finally:
        body_path.unlink(missing_ok=True)


def wait_for_retry(section: SiteSection, attempt: int) -> None:
    interval = max(0, section.request_interval_seconds or 0)
    if interval:
        time.sleep(interval * (attempt + 1))


def decode_body(body: bytes, content_type: str) -> str:
    encodings = ["utf-8", "gb18030"]
    if "charset=" in content_type:
        encodings.insert(0, content_type.rsplit("charset=", 1)[-1].split(";")[0].strip())
    for encoding in encodings:
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def normalize_request_url(url: str) -> str:
    """Encode non-ASCII URL parts before handing them to httpx or curl."""
    parts = urlsplit(url)
    query = urlencode(parse_qsl(parts.query, keep_blank_values=True), doseq=True)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            quote(parts.path, safe="/%"),
            query,
            quote(parts.fragment, safe=""),
        )
    )
