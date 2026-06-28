"""create v3 qualification tables

Revision ID: 20260628_0006
Revises: 20260622_0005
Create Date: 2026-06-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260628_0006"
down_revision = "20260622_0005"
branch_labels = None
depends_on = None


def timestamp_columns() -> list[sa.Column]:
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
        "qualification_standards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("level", sa.String(length=64), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("authority", sa.String(length=200), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_document_title", sa.String(length=500), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("code", name="uq_qualification_standards_code"),
    )
    op.create_index("ix_qualification_standards_code", "qualification_standards", ["code"])
    op.create_index("ix_qualification_standards_name", "qualification_standards", ["name"])

    op.create_table(
        "qualification_standard_conditions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "standard_id",
            sa.Integer(),
            sa.ForeignKey("qualification_standards.id"),
            nullable=False,
        ),
        sa.Column("condition_type", sa.String(length=64), nullable=False, server_default="other"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=True),
        sa.Column("metric_value", sa.String(length=120), nullable=True),
        sa.Column("metric_unit", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *timestamp_columns(),
    )
    op.create_index(
        "ix_qualification_standard_conditions_standard_id",
        "qualification_standard_conditions",
        ["standard_id"],
    )

    op.create_table(
        "enterprises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unified_social_credit_code", sa.String(length=64), nullable=True),
        sa.Column("legal_representative", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("registered_capital", sa.String(length=120), nullable=True),
        sa.Column("contact_name", sa.String(length=120), nullable=True),
        sa.Column("contact_phone", sa.String(length=120), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("name", name="uq_enterprises_name"),
        sa.UniqueConstraint(
            "unified_social_credit_code",
            name="uq_enterprises_unified_social_credit_code",
        ),
    )
    op.create_index("ix_enterprises_name", "enterprises", ["name"])
    op.create_index(
        "ix_enterprises_unified_social_credit_code",
        "enterprises",
        ["unified_social_credit_code"],
    )

    op.create_table(
        "enterprise_qualifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column(
            "standard_id",
            sa.Integer(),
            sa.ForeignKey("qualification_standards.id"),
            nullable=True,
        ),
        sa.Column("qualification_name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("level", sa.String(length=64), nullable=True),
        sa.Column("certificate_no", sa.String(length=120), nullable=True),
        sa.Column("issuing_authority", sa.String(length=200), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
    )
    op.create_index(
        "ix_enterprise_qualifications_enterprise_id",
        "enterprise_qualifications",
        ["enterprise_id"],
    )
    op.create_index(
        "ix_enterprise_qualifications_standard_id",
        "enterprise_qualifications",
        ["standard_id"],
    )

    op.create_table(
        "enterprise_personnel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("id_number_masked", sa.String(length=64), nullable=True),
        sa.Column("role_type", sa.String(length=120), nullable=True),
        sa.Column("certificate_name", sa.String(length=200), nullable=True),
        sa.Column("certificate_no", sa.String(length=120), nullable=True),
        sa.Column("specialty", sa.String(length=120), nullable=True),
        sa.Column("level", sa.String(length=64), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
    )
    op.create_index(
        "ix_enterprise_personnel_enterprise_id",
        "enterprise_personnel",
        ["enterprise_id"],
    )

    op.create_table(
        "enterprise_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("project_type", sa.String(length=120), nullable=True),
        sa.Column("contract_amount", sa.String(length=120), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("source_document", sa.String(length=500), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
    )
    op.create_index(
        "ix_enterprise_projects_enterprise_id",
        "enterprise_projects",
        ["enterprise_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_enterprise_projects_enterprise_id", table_name="enterprise_projects")
    op.drop_table("enterprise_projects")
    op.drop_index("ix_enterprise_personnel_enterprise_id", table_name="enterprise_personnel")
    op.drop_table("enterprise_personnel")
    op.drop_index(
        "ix_enterprise_qualifications_standard_id",
        table_name="enterprise_qualifications",
    )
    op.drop_index(
        "ix_enterprise_qualifications_enterprise_id",
        table_name="enterprise_qualifications",
    )
    op.drop_table("enterprise_qualifications")
    op.drop_index("ix_enterprises_unified_social_credit_code", table_name="enterprises")
    op.drop_index("ix_enterprises_name", table_name="enterprises")
    op.drop_table("enterprises")
    op.drop_index(
        "ix_qualification_standard_conditions_standard_id",
        table_name="qualification_standard_conditions",
    )
    op.drop_table("qualification_standard_conditions")
    op.drop_index("ix_qualification_standards_name", table_name="qualification_standards")
    op.drop_index("ix_qualification_standards_code", table_name="qualification_standards")
    op.drop_table("qualification_standards")
