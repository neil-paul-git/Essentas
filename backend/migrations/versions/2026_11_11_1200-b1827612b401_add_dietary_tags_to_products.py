"""add dietary tags to products

Revision ID: b1827612b401
Revises: 8f7277af9cda
Create Date: 2026-11-11 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b1827612b401'
down_revision: str | Sequence[str] | None = '8f7277af9cda'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ('allergens', 'traces', 'ingredients_analysis', 'labels')


def upgrade() -> None:
    """Upgrade schema."""
    # server_default '[]' lets NOT NULL columns be added to a table that already has rows.
    with op.batch_alter_table('products', schema=None) as batch_op:
        for name in _COLUMNS:
            batch_op.add_column(sa.Column(name, sa.JSON(), server_default='[]', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('products', schema=None) as batch_op:
        for name in reversed(_COLUMNS):
            batch_op.drop_column(name)
