"""Redesign api_keys: remove user_id FK, add description

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Убираем FK на users и колонку user_id
    op.drop_constraint('api_keys_user_id_fkey', 'api_keys', type_='foreignkey')
    op.drop_column('api_keys', 'user_id')
    # Убираем label, добавляем description
    op.drop_column('api_keys', 'label')
    op.add_column('api_keys', sa.Column('description', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('api_keys', 'description')
    op.add_column('api_keys', sa.Column('label', sa.String(), nullable=True))
    op.add_column('api_keys', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('api_keys_user_id_fkey', 'api_keys', 'users', ['user_id'], ['id'])
