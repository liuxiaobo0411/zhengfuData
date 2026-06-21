"""create core business tables

Revision ID: 20260621_0001
Revises:
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260621_0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("homepage_url", sa.String(length=1000), nullable=False),
        sa.Column("organization", sa.String(length=200), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_sites_slug", "sites", ["slug"], unique=True)

    op.create_table(
        "site_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column(
            "item_type",
            sa.String(length=64),
            nullable=False,
            server_default="qualification_notice",
        ),
        sa.Column("crawl_method", sa.String(length=64), nullable=False, server_default="http"),
        sa.Column(
            "crawler_strategy",
            sa.String(length=64),
            nullable=False,
            server_default="http_static",
        ),
        sa.Column(
            "schedule_cron",
            sa.String(length=64),
            nullable=False,
            server_default="0 9 * * *",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("download_attachments", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("save_snapshot", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("request_timeout", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("retry_times", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("request_interval_seconds", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("request_headers", sa.Text(), nullable=True),
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_items_per_run", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "stop_when_seen_existing_count",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
        sa.Column("crawl_date_window_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allow_full_crawl", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("list_selector", sa.String(length=500), nullable=True),
        sa.Column("title_selector", sa.String(length=500), nullable=True),
        sa.Column("date_selector", sa.String(length=500), nullable=True),
        sa.Column("detail_url_selector", sa.String(length=500), nullable=True),
        sa.Column("content_selector", sa.String(length=500), nullable=True),
        sa.Column("attachment_selector", sa.String(length=500), nullable=True),
        sa.Column("pagination_rule", sa.Text(), nullable=True),
        sa.Column("custom_adapter", sa.String(length=120), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("site_id", "url", name="uq_site_sections_site_url"),
    )
    op.create_index("ix_site_sections_site_id", "site_sections", ["site_id"])

    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_no", sa.String(length=64), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("total_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_changed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attachment_added_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attachment_changed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attachment_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attachment_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered_by", sa.String(length=64), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_crawl_runs_run_no", "crawl_runs", ["run_no"], unique=True)

    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("site_sections.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("crawl_runs.id"), nullable=True),
        sa.Column("identity_key", sa.String(length=255), nullable=False),
        sa.Column("identity_strategy", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("final_url", sa.String(length=1000), nullable=True),
        sa.Column("raw_published_at", sa.String(length=120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_page_updated_at", sa.String(length=120), nullable=True),
        sa.Column("page_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("attachments_hash", sa.String(length=128), nullable=True),
        sa.Column("snapshot_path", sa.String(length=1000), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("section_id", "identity_key", name="uq_announcements_section_identity"),
    )
    op.create_index("ix_announcements_site_id", "announcements", ["site_id"])
    op.create_index("ix_announcements_section_id", "announcements", ["section_id"])
    op.create_index("ix_announcements_run_id", "announcements", ["run_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "announcement_id",
            sa.Integer(),
            sa.ForeignKey("announcements.id"),
            nullable=False,
        ),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("crawl_runs.id"), nullable=True),
        sa.Column("attachment_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("safe_name", sa.String(length=500), nullable=False),
        sa.Column("file_ext", sa.String(length=32), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("final_url", sa.String(length=1000), nullable=True),
        sa.Column("local_path", sa.String(length=1000), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("file_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "download_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("announcement_id", "attachment_key", name="uq_attachments_item_key"),
    )
    op.create_index("ix_attachments_site_id", "attachments", ["site_id"])
    op.create_index("ix_attachments_run_id", "attachments", ["run_id"])

    op.create_table(
        "change_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "announcement_id",
            sa.Integer(),
            sa.ForeignKey("announcements.id"),
            nullable=True,
        ),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id"), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("site_sections.id"), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("crawl_runs.id"), nullable=True),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("old_hash", sa.String(length=128), nullable=True),
        sa.Column("new_hash", sa.String(length=128), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_change_logs_announcement_id", "change_logs", ["announcement_id"])
    op.create_index("ix_change_logs_attachment_id", "change_logs", ["attachment_id"])
    op.create_index("ix_change_logs_site_id", "change_logs", ["site_id"])
    op.create_index("ix_change_logs_section_id", "change_logs", ["section_id"])
    op.create_index("ix_change_logs_run_id", "change_logs", ["run_id"])


def downgrade() -> None:
    op.drop_table("change_logs")
    op.drop_table("attachments")
    op.drop_table("announcements")
    op.drop_table("crawl_runs")
    op.drop_table("site_sections")
    op.drop_table("sites")
    op.drop_table("users")
