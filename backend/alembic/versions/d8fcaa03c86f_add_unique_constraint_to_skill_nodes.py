"""add unique constraint to skill_nodes

Revision ID: d8fcaa03c86f
Revises: f2a560c8fba2
Create Date: 2026-06-14 14:42:55.096386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8fcaa03c86f'
down_revision: Union[str, None] = 'f2a560c8fba2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_skill_nodes_developer_skill",
        "skill_nodes",
        ["developer_id", "skill_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_skill_nodes_developer_skill",
        "skill_nodes",
        type_="unique",
    )