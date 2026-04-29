"""Add adfs_sub to users

Revision ID: a1b2c3d4e5f6
Revises: 62ca44ae1def
Create Date: 2026-04-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '62ca44ae1def'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('adfs_sub', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_adfs_sub'), 'users', ['adfs_sub'], unique=True)
    # hashed_password теперь nullable — пользователи AD FS входят без пароля
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=False)
    op.drop_index(op.f('ix_users_adfs_sub'), table_name='users')
    op.drop_column('users', 'adfs_sub')
