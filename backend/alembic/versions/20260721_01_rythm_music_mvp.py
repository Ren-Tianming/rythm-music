"""Add RyThM Music genre, generation, and publishing fields.

Revision ID: 20260721_01
Revises: 20260529_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_01"
down_revision: str | None = "20260529_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("song_analyses", sa.Column("genre", sa.String(100), nullable=True))
    op.add_column("song_analyses", sa.Column("genre_confidence", sa.Numeric(6, 5), nullable=True))
    op.add_column(
        "song_analyses",
        sa.Column("genre_model_status", sa.String(30), server_default="NOT_CONFIGURED", nullable=False),
    )
    op.add_column("song_analyses", sa.Column("genre_model_version", sa.String(100), nullable=True))
    op.add_column("song_analyses", sa.Column("lyrics", sa.Text(), nullable=True))
    op.add_column(
        "song_analyses",
        sa.Column("lyrics_status", sa.String(30), server_default="NOT_CONFIGURED", nullable=False),
    )
    op.add_column("song_analyses", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column(
        "song_analyses",
        sa.Column("ai_summary_source", sa.String(30), server_default="LOCAL", nullable=False),
    )

    op.create_table(
        "generated_tracks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("instrumental", sa.Boolean(), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_job_id", sa.String(160), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("audio_url", sa.String(1000), nullable=True),
        sa.Column("points_cost", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_tracks_user_created", "generated_tracks", ["user_id", "created_at"])

    op.create_table(
        "published_works",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("generation_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cover_gradient", sa.String(80), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("likes_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generated_tracks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_id", name="uq_published_work_generation"),
    )
    op.create_index(
        "ix_published_works_public_created", "published_works", ["is_public", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_published_works_public_created", table_name="published_works")
    op.drop_table("published_works")
    op.drop_index("ix_generated_tracks_user_created", table_name="generated_tracks")
    op.drop_table("generated_tracks")
    for column in (
        "ai_summary_source",
        "ai_summary",
        "lyrics_status",
        "lyrics",
        "genre_model_version",
        "genre_model_status",
        "genre_confidence",
        "genre",
    ):
        op.drop_column("song_analyses", column)
