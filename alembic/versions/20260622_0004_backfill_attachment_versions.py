"""backfill attachment versions

Revision ID: 20260622_0004
Revises: 20260622_0003
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op

revision = "20260622_0004"
down_revision = "20260622_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO attachment_versions (
            attachment_id,
            announcement_id,
            site_id,
            run_id,
            version_no,
            name,
            safe_name,
            source_url,
            final_url,
            local_path,
            file_size,
            file_hash,
            file_updated_at,
            downloaded_at,
            download_status,
            change_type,
            created_at,
            updated_at
        )
        SELECT
            a.id,
            a.announcement_id,
            a.site_id,
            a.run_id,
            1,
            a.name,
            a.safe_name,
            a.source_url,
            a.final_url,
            a.local_path,
            a.file_size,
            a.file_hash,
            a.file_updated_at,
            a.downloaded_at,
            a.download_status,
            'attachment_added',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM attachments a
        WHERE a.download_status = 'success'
          AND a.local_path IS NOT NULL
          AND a.file_hash IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM attachment_versions av
              WHERE av.attachment_id = a.id
          )
        """
    )


def downgrade() -> None:
    pass
