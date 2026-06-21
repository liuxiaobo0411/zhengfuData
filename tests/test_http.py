from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from app.services.crawler.http import normalize_request_url


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
