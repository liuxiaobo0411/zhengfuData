"""create attachment versions

Revision ID: 20260622_0003
Revises: 20260621_0002
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260622_0003"
down_revision = "20260621_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachment_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id"), nullable=False),
        sa.Column(
            "announcement_id",
            sa.Integer(),
            sa.ForeignKey("announcements.id"),
            nullable=False,
        ),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("crawl_runs.id"), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("safe_name", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("final_url", sa.String(length=1000), nullable=True),
        sa.Column("local_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("file_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "download_status",
            sa.String(length=32),
            nullable=False,
            server_default="success",
        ),
        sa.Column("change_type", sa.String(length=64), nullable=False),
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
        sa.UniqueConstraint(
            "attachment_id",
            "version_no",
            name="uq_attachment_versions_attachment_version",
        ),
    )
    op.create_index(
        "ix_attachment_versions_attachment_id",
        "attachment_versions",
        ["attachment_id"],
    )
    op.create_index(
        "ix_attachment_versions_announcement_id",
        "attachment_versions",
        ["announcement_id"],
    )
    op.create_index("ix_attachment_versions_site_id", "attachment_versions", ["site_id"])
    op.create_index("ix_attachment_versions_run_id", "attachment_versions", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_attachment_versions_run_id", table_name="attachment_versions")
    op.drop_index("ix_attachment_versions_site_id", table_name="attachment_versions")
    op.drop_index("ix_attachment_versions_announcement_id", table_name="attachment_versions")
    op.drop_index("ix_attachment_versions_attachment_id", table_name="attachment_versions")
    op.drop_table("attachment_versions")
