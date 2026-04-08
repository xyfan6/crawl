"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-08

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table(
        "crawled_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("surface_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content_body", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("authors_json", JSONB(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("lang", sa.Text(), nullable=True, server_default="en"),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.Column("engagement", JSONB(), nullable=True),
        sa.Column("doi", sa.Text(), nullable=True),
        sa.Column("journal", sa.Text(), nullable=True),
        sa.Column("open_access", sa.Boolean(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),  # vector(1536) via raw SQL below
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_crawled_items_url"),
    )

    # Add vector column properly
    op.execute("ALTER TABLE crawled_items ALTER COLUMN embedding TYPE vector(1536) USING NULL")

    op.create_index("idx_source_time", "crawled_items", ["source", "collected_at"])
    op.create_index("idx_surface_time", "crawled_items", ["surface_key", "collected_at"])
    op.execute(
        "CREATE UNIQUE INDEX idx_doi ON crawled_items(doi) WHERE doi IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_embedding ON crawled_items "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "surfaces",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("poll_interval_sec", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("max_items_per_run", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("config_json", JSONB(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cursor", sa.Text(), nullable=True),
        sa.Column("last_status", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_run_count", sa.Integer(), nullable=True),
        sa.Column("consecutive_fails", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "http_cache",
        sa.Column("url_hash", sa.Text(), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("url_hash"),
    )


def downgrade() -> None:
    op.drop_table("http_cache")
    op.drop_table("surfaces")
    op.drop_table("crawled_items")
