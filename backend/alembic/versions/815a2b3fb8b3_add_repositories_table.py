"""add repositories table

Revision ID: 815a2b3fb8b3
Revises: d8fcaa03c86f
Create Date: 2026-06-17 12:07:07.859440
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "815a2b3fb8b3"
down_revision: Union[str, None] = "d8fcaa03c86f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_language", sa.String(50), nullable=True),
        sa.Column("topics", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("stars", sa.Integer(), nullable=True),
        sa.Column("forks", sa.Integer(), nullable=True),
        sa.Column("open_issues", sa.Integer(), nullable=True),
        sa.Column("last_commit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_contributing_guide", sa.Boolean(), nullable=True),
        sa.Column("has_code_of_conduct", sa.Boolean(), nullable=True),
        sa.Column("newcomer_friendliness", sa.Float(), nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_id"),
        sa.UniqueConstraint("full_name"),
    )
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])
    op.create_index("ix_repositories_language", "repositories", ["primary_language"])


def downgrade() -> None:
    op.drop_index("ix_repositories_language", table_name="repositories")
    op.drop_index("ix_repositories_full_name", table_name="repositories")
    op.drop_table("repositories")