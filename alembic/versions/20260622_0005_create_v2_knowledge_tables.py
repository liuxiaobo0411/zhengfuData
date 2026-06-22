"""create v2 knowledge tables

Revision ID: 20260622_0005
Revises: 20260622_0004
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260622_0005"
down_revision = "20260622_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_texts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id"), nullable=False),
        sa.Column(
            "attachment_version_id",
            sa.Integer(),
            sa.ForeignKey("attachment_versions.id"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="attachment"),
        sa.Column("parser_name", sa.String(length=120), nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("text_hash", sa.String(length=128), nullable=True),
        sa.Column("text_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
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
            "attachment_version_id",
            name="uq_document_texts_attachment_version",
        ),
    )
    op.create_index("ix_document_texts_attachment_id", "document_texts", ["attachment_id"])
    op.create_index(
        "ix_document_texts_attachment_version_id",
        "document_texts",
        ["attachment_version_id"],
    )
    op.create_index("ix_document_texts_status", "document_texts", ["status"])

    op.create_table(
        "search_index",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("backend_path", sa.String(length=1000), nullable=True),
        sa.Column("site_name", sa.String(length=200), nullable=True),
        sa.Column("section_name", sa.String(length=200), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_search_index_entity"),
    )
    op.create_index("ix_search_index_entity", "search_index", ["entity_type", "entity_id"])
    op.create_index("ix_search_index_published_at", "search_index", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_search_index_published_at", table_name="search_index")
    op.drop_index("ix_search_index_entity", table_name="search_index")
    op.drop_table("search_index")
    op.drop_index("ix_document_texts_status", table_name="document_texts")
    op.drop_index("ix_document_texts_attachment_version_id", table_name="document_texts")
    op.drop_index("ix_document_texts_attachment_id", table_name="document_texts")
    op.drop_table("document_texts")
