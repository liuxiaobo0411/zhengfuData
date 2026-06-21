from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FetchedPage:
    url: str
    final_url: str
    body: bytes
    text: str
    content_type: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedAttachment:
    name: str
    url: str


@dataclass(frozen=True)
class ParsedAnnouncement:
    title: str
    source_url: str
    raw_published_at: str | None = None
    content: str | None = None
    attachments: list[ParsedAttachment] = field(default_factory=list)
