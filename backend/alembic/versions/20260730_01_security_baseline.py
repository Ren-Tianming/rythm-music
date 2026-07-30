"""Add password recovery, consent, audit, and locale security baseline.

Revision ID: 20260730_01
Revises: 20260728_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_01"
down_revision: str | None = "20260728_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.String(length=10),
            nullable=False,
            server_default="zh-CN",
        ),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("locale", server_default=None)

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_password_reset_user_expires",
        "password_reset_tokens",
        ["user_id", "expires_at"],
    )

    op.create_table(
        "user_consents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("document_version", sa.String(length=40), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("consented_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "document_type",
            "document_version",
            name="uq_user_consents_document_version",
        ),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("metadata_redacted", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_event_created",
        "audit_logs",
        ["event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_event_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("user_consents")
    op.drop_index(
        "ix_password_reset_user_expires",
        table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "locale")
