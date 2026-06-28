from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Site(TimestampMixin, Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(200))
    region: Mapped[str | None] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(32))

    sections: Mapped[list[SiteSection]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )


class SiteSection(TimestampMixin, Base):
    __tablename__ = "site_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    item_type: Mapped[str] = mapped_column(
        String(64), default="qualification_notice", nullable=False
    )
    crawl_method: Mapped[str] = mapped_column(String(64), default="http", nullable=False)
    crawler_strategy: Mapped[str] = mapped_column(String(64), default="http_static", nullable=False)
    schedule_cron: Mapped[str] = mapped_column(String(64), default="0 9 * * *", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    download_attachments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    save_snapshot: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    request_timeout: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    retry_times: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    request_interval_seconds: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    request_headers: Mapped[str | None] = mapped_column(Text)
    max_pages: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_items_per_run: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    stop_when_seen_existing_count: Mapped[int] = mapped_column(
        Integer,
        default=20,
        nullable=False,
    )
    crawl_date_window_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    allow_full_crawl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    list_selector: Mapped[str | None] = mapped_column(String(500))
    title_selector: Mapped[str | None] = mapped_column(String(500))
    date_selector: Mapped[str | None] = mapped_column(String(500))
    detail_url_selector: Mapped[str | None] = mapped_column(String(500))
    content_selector: Mapped[str | None] = mapped_column(String(500))
    attachment_selector: Mapped[str | None] = mapped_column(String(500))
    pagination_rule: Mapped[str | None] = mapped_column(Text)
    custom_adapter: Mapped[str | None] = mapped_column(String(120))
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(32))
    last_error: Mapped[str | None] = mapped_column(Text)

    site: Mapped[Site] = relationship(back_populates="sections")

    __table_args__ = (UniqueConstraint("site_id", "url", name="uq_site_sections_site_url"),)


class CrawlRun(TimestampMixin, Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_no: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    run_type: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    total_sections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_sections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_sections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discovered_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_changed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attachment_added_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attachment_changed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attachment_success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attachment_failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triggered_by: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(Text)


class Announcement(TimestampMixin, Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("site_sections.id"), nullable=False, index=True
    )
    run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), index=True)
    identity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(1000))
    raw_published_at: Mapped[str | None] = mapped_column(String(120))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_page_updated_at: Mapped[str | None] = mapped_column(String(120))
    page_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    content_summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    attachments_hash: Mapped[str | None] = mapped_column(String(128))
    snapshot_path: Mapped[str | None] = mapped_column(String(1000))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("section_id", "identity_key", name="uq_announcements_section_identity"),
    )


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("announcements.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), index=True)
    attachment_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_ext: Mapped[str | None] = mapped_column(String(32))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(1000))
    local_path: Mapped[str | None] = mapped_column(String(1000))
    file_size: Mapped[int | None] = mapped_column(Integer)
    file_hash: Mapped[str | None] = mapped_column(String(128))
    file_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    download_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("announcement_id", "attachment_key", name="uq_attachments_item_key"),
    )


class AttachmentVersion(TimestampMixin, Base):
    __tablename__ = "attachment_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachments.id"), nullable=False, index=True
    )
    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("announcements.id"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(1000))
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    file_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    download_status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "attachment_id",
            "version_no",
            name="uq_attachment_versions_attachment_version",
        ),
    )


class DocumentText(TimestampMixin, Base):
    __tablename__ = "document_texts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachments.id"), nullable=False, index=True
    )
    attachment_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachment_versions.id"),
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(64), default="attachment", nullable=False)
    parser_name: Mapped[str | None] = mapped_column(String(120))
    parser_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    text_hash: Mapped[str | None] = mapped_column(String(128))
    text_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "attachment_version_id",
            name="uq_document_texts_attachment_version",
        ),
    )


class SearchIndex(TimestampMixin, Base):
    __tablename__ = "search_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    backend_path: Mapped[str | None] = mapped_column(String(1000))
    site_name: Mapped[str | None] = mapped_column(String(200))
    section_name: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_search_index_entity"),)


class ChangeLog(TimestampMixin, Base):
    __tablename__ = "change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    announcement_id: Mapped[int | None] = mapped_column(ForeignKey("announcements.id"), index=True)
    attachment_id: Mapped[int | None] = mapped_column(ForeignKey("attachments.id"), index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("site_sections.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    old_hash: Mapped[str | None] = mapped_column(String(128))
    new_hash: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(String(1000))


class NotificationLog(TimestampMixin, Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="openclaw", nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    request_url: Mapped[str | None] = mapped_column(String(1000))
    request_payload: Mapped[str | None] = mapped_column(Text)
    response_status_code: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QualificationStandard(TimestampMixin, Base):
    __tablename__ = "qualification_standards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    level: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(100))
    authority: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_document_title: Mapped[str | None] = mapped_column(String(500))
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)

    conditions: Mapped[list[QualificationStandardCondition]] = relationship(
        back_populates="standard",
        cascade="all, delete-orphan",
        order_by="QualificationStandardCondition.sort_order",
    )


class QualificationStandardCondition(TimestampMixin, Base):
    __tablename__ = "qualification_standard_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    standard_id: Mapped[int] = mapped_column(
        ForeignKey("qualification_standards.id"),
        nullable=False,
        index=True,
    )
    condition_type: Mapped[str] = mapped_column(String(64), default="other", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    metric_name: Mapped[str | None] = mapped_column(String(120))
    metric_value: Mapped[str | None] = mapped_column(String(120))
    metric_unit: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    standard: Mapped[QualificationStandard] = relationship(back_populates="conditions")


class Enterprise(TimestampMixin, Base):
    __tablename__ = "enterprises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    unified_social_credit_code: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    legal_representative: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(100))
    registered_capital: Mapped[str | None] = mapped_column(String(120))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    qualifications: Mapped[list[EnterpriseQualification]] = relationship(
        back_populates="enterprise",
        cascade="all, delete-orphan",
    )
    personnel: Mapped[list[EnterprisePersonnel]] = relationship(
        back_populates="enterprise",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list[EnterpriseProject]] = relationship(
        back_populates="enterprise",
        cascade="all, delete-orphan",
    )


class EnterpriseQualification(TimestampMixin, Base):
    __tablename__ = "enterprise_qualifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enterprise_id: Mapped[int] = mapped_column(
        ForeignKey("enterprises.id"),
        nullable=False,
        index=True,
    )
    standard_id: Mapped[int | None] = mapped_column(
        ForeignKey("qualification_standards.id"),
        index=True,
    )
    qualification_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    level: Mapped[str | None] = mapped_column(String(64))
    certificate_no: Mapped[str | None] = mapped_column(String(120))
    issuing_authority: Mapped[str | None] = mapped_column(String(200))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    enterprise: Mapped[Enterprise] = relationship(back_populates="qualifications")
    standard: Mapped[QualificationStandard | None] = relationship()


class EnterprisePersonnel(TimestampMixin, Base):
    __tablename__ = "enterprise_personnel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enterprise_id: Mapped[int] = mapped_column(
        ForeignKey("enterprises.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    id_number_masked: Mapped[str | None] = mapped_column(String(64))
    role_type: Mapped[str | None] = mapped_column(String(120))
    certificate_name: Mapped[str | None] = mapped_column(String(200))
    certificate_no: Mapped[str | None] = mapped_column(String(120))
    specialty: Mapped[str | None] = mapped_column(String(120))
    level: Mapped[str | None] = mapped_column(String(64))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    enterprise: Mapped[Enterprise] = relationship(back_populates="personnel")


class EnterpriseProject(TimestampMixin, Base):
    __tablename__ = "enterprise_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enterprise_id: Mapped[int] = mapped_column(
        ForeignKey("enterprises.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(120))
    contract_amount: Mapped[str | None] = mapped_column(String(120))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[str | None] = mapped_column(String(120))
    source_document: Mapped[str | None] = mapped_column(String(500))
    remark: Mapped[str | None] = mapped_column(Text)

    enterprise: Mapped[Enterprise] = relationship(back_populates="projects")
