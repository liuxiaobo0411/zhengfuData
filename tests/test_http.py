from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx

from app.models import SiteSection
from app.services.crawler.http import fetch_url, fetch_url_with_curl, normalize_request_url
from app.services.crawler.types import FetchedPage


def test_normalize_request_url_encodes_chinese_query_values():
    url = (
        "https://www.mohurd.gov.cn/api-gateway/download?"
        "fileUrl=abc%2Fdef%2Bg%3D%3D&fileName=住房城乡建设部 关于通知-文字版.docx"
    )

    normalized = normalize_request_url(url)

    assert "fileName=住房" not in normalized
    assert "%E4%BD%8F%E6%88%BF" in normalized
    assert "fileUrl=abc%2Fdef%2Bg%3D%3D" in normalized
    assert parse_qs(urlsplit(normalized).query)["fileName"] == [
        "住房城乡建设部 关于通知-文字版.docx"
    ]


def test_normalize_request_url_encodes_non_ascii_path():
    normalized = normalize_request_url("https://example.gov.cn/附件/通知.pdf?x=1")

    assert normalized == "https://example.gov.cn/%E9%99%84%E4%BB%B6/%E9%80%9A%E7%9F%A5.pdf?x=1"


def test_fetch_url_waits_with_backoff_between_retry_attempts(monkeypatch):
    section = SiteSection(
        name="测试栏目",
        url="https://example.gov.cn/list.html",
        crawler_strategy="http_with_retry",
        request_timeout=5,
        retry_times=2,
        request_interval_seconds=2,
    )
    sleeps: list[int] = []

    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("timeout")

    def fake_sleep(seconds: int):
        sleeps.append(seconds)

    def fake_curl(url: str, section: SiteSection, timeout: int):
        return FetchedPage(
            url=url,
            final_url=url,
            body=b"ok",
            text="ok",
            content_type="text/html",
        )

    monkeypatch.setattr("app.services.crawler.http.httpx.get", fake_get)
    monkeypatch.setattr("app.services.crawler.http.time.sleep", fake_sleep)
    monkeypatch.setattr("app.services.crawler.http.fetch_url_with_curl", fake_curl)

    page = fetch_url("https://example.gov.cn/list.html", section)

    assert page.text == "ok"
    assert sleeps == [2, 4]


def test_fetch_url_with_curl_sets_process_and_connect_timeouts(monkeypatch, tmp_path):
    section = SiteSection(
        name="测试栏目",
        url="https://example.gov.cn/list.html",
        request_timeout=60,
    )
    captured: dict[str, object] = {}

    def fake_run(command, check, capture_output, text, timeout):
        output_path = command[command.index("-o") + 1]
        tmp_path.joinpath("seen").write_text(output_path, encoding="utf-8")
        with open(output_path, "wb") as file:
            file.write(b"ok")
        captured.update(
            {
                "command": command,
                "check": check,
                "capture_output": capture_output,
                "text": text,
                "timeout": timeout,
            }
        )

        class Result:
            stdout = "https://example.gov.cn/file.pdf\napplication/pdf"

        return Result()

    monkeypatch.setattr("app.services.crawler.http.subprocess.run", fake_run)

    page = fetch_url_with_curl("https://example.gov.cn/file.pdf", section, timeout=60)

    command = captured["command"]
    assert page.body == b"ok"
    assert captured["timeout"] == 65
    assert command[command.index("--max-time") + 1] == "60"
    assert command[command.index("--connect-timeout") + 1] == "15"
