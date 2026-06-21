from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from app.models import SiteSection
from app.services.crawler.types import ParsedAnnouncement, ParsedAttachment

FILE_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".wps"}


def parse_date_text(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.search(r"(20\d{2})[-年./](\d{1,2})[-月./](\d{1,2})", value)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    return datetime(year, month, day)


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def parse_list_page(html: str, base_url: str, section: SiteSection) -> list[ParsedAnnouncement]:
    soup = BeautifulSoup(html, "html.parser")
    if section.list_selector:
        return parse_configured_list(soup, base_url, section)
    return parse_fallback_list(soup, base_url)


def parse_json_page(text: str, base_url: str, section: SiteSection) -> list[ParsedAnnouncement]:
    payload = json.loads(text)
    rows = extract_json_rows(payload)
    records: list[ParsedAnnouncement] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        title = first_json_value(
            row,
            ["title", "name", "fappContent", "fentName", "content", "noticeTitle"],
        )
        if not title:
            continue
        source_url = first_json_value(row, ["url", "source_url", "link", "detailUrl"])
        row_id = first_json_value(row, ["id", "fid", "uuid", "code"]) or str(index)
        date_text = first_json_value(
            row,
            ["published_at", "publishDate", "date", "ftime", "created_at"],
        )
        if source_url:
            source_url_value = urljoin(base_url, source_url)
        else:
            source_url_value = f"{base_url}#row-{row_id}"
        records.append(
            ParsedAnnouncement(
                title=normalize_text(title),
                source_url=source_url_value,
                raw_published_at=date_text,
                content=json.dumps(row, ensure_ascii=False, sort_keys=True),
            )
        )
    return dedupe_records(records[: section.max_items_per_run])


def extract_json_rows(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "list", "records", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return extract_json_rows(data)
    return []


def first_json_value(row: dict[str, object], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def parse_configured_list(
    soup: BeautifulSoup,
    base_url: str,
    section: SiteSection,
) -> list[ParsedAnnouncement]:
    records: list[ParsedAnnouncement] = []
    for node in soup.select(section.list_selector):
        title_node = (
            first_selected(node, section.title_selector) if section.title_selector else None
        )
        link_node = (
            first_selected(node, section.detail_url_selector)
            if section.detail_url_selector
            else None
        )
        if link_node is None:
            link_node = node if is_anchor(node) else node.find("a", href=True)
        if link_node is None or not is_anchor(link_node):
            continue
        title = normalize_text(title_node.get_text(" ", strip=True) if title_node else "")
        title = title or normalize_text(link_node.get_text(" ", strip=True))
        href = str(link_node.get("href") or "").strip()
        if not title or not href or href.startswith(("javascript:", "#")):
            continue
        date_text = None
        if section.date_selector:
            date_node = first_selected(node, section.date_selector)
            date_text = normalize_text(date_node.get_text(" ", strip=True)) if date_node else None
        date_text = date_text or normalize_text(node.get_text(" ", strip=True))
        records.append(
            ParsedAnnouncement(
                title=title,
                source_url=urljoin(base_url, href),
                raw_published_at=date_text,
            )
        )
    return dedupe_records(records)


def parse_fallback_list(soup: BeautifulSoup, base_url: str) -> list[ParsedAnnouncement]:
    records: list[ParsedAnnouncement] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        title = normalize_text(anchor.get_text(" ", strip=True) or str(anchor.get("title") or ""))
        if not href or not title or href.startswith(("javascript:", "#")):
            continue
        parent = anchor.find_parent("li") or anchor.parent
        text = normalize_text(parent.get_text(" ", strip=True) if parent else title)
        records.append(
            ParsedAnnouncement(
                title=title,
                source_url=urljoin(base_url, href),
                raw_published_at=text,
            )
        )
    return dedupe_records(records)


def parse_detail_page(
    html: str,
    final_url: str,
    section: SiteSection,
) -> tuple[str, list[ParsedAttachment]]:
    soup = BeautifulSoup(html, "html.parser")
    content_node = soup.select_one(section.content_selector) if section.content_selector else None
    if content_node is None:
        content_node = soup.find("body") or soup
    content = normalize_text(content_node.get_text(" ", strip=True))
    attachments = extract_attachments(soup, final_url, section)
    return content, attachments


def extract_attachments(
    soup: BeautifulSoup,
    base_url: str,
    section: SiteSection,
) -> list[ParsedAttachment]:
    anchors = (
        soup.select(section.attachment_selector)
        if section.attachment_selector
        else soup.find_all("a", href=True)
    )
    results: list[ParsedAttachment] = []
    seen: set[str] = set()
    for anchor in anchors:
        if not is_anchor(anchor):
            continue
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "#")):
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url in seen or not looks_like_attachment(absolute_url, anchor):
            continue
        seen.add(absolute_url)
        label = normalize_text(
            anchor.get_text(" ", strip=True) or str(anchor.get("title") or "附件")
        )
        results.append(ParsedAttachment(name=label or "附件", url=absolute_url))
    return results


def looks_like_attachment(url: str, anchor: Tag) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    suffix = "." + path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    label = normalize_text(anchor.get_text(" ", strip=True))
    return (
        suffix in FILE_EXTENSIONS
        or "附件" in label
        or "下载" in label
        or "file" in parsed.query.lower()
        or "/attach" in path
        or "/download" in path
    )


def first_selected(node: Tag, selector: str | None) -> Tag | None:
    if not selector:
        return None
    selected = node.select_one(selector)
    return selected if isinstance(selected, Tag) else None


def is_anchor(node: object) -> bool:
    return isinstance(node, Tag) and node.name == "a" and node.has_attr("href")


def dedupe_records(records: list[ParsedAnnouncement]) -> list[ParsedAnnouncement]:
    unique: dict[str, ParsedAnnouncement] = {}
    for record in records:
        unique[record.source_url] = record
    return list(unique.values())
