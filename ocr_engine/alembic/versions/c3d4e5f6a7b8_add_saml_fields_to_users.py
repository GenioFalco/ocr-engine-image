"""Add SAML fields to users

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-29 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Убираем старое поле adfs_sub если есть
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS adfs_sub")

    # Добавляем новые поля
    op.add_column('users', sa.Column('saml_nameid', sa.String(), nullable=True))
    op.add_column('users', sa.Column('display_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('department', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_saml_nameid'), 'users', ['saml_nameid'], unique=True)

    # hashed_password nullable — SAML пользователи входят без пароля
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=False)
    op.drop_index(op.f('ix_users_saml_nameid'), table_name='users')
    op.drop_column('users', 'department')
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'saml_nameid')
