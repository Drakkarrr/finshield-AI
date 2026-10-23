"""add_risk_model_versions_table

Revision ID: 40c3dd896fc7
Revises: e103d6a40c89
Create Date: 2026-10-23 23:16:45.566807
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '40c3dd896fc7'
down_revision: Union[str, None] = 'e103d6a40c89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'risk_model_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model_type', sa.String(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='development'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('shadow_of', sa.String(), nullable=True),
        sa.Column('shadow_percentage', sa.Float(), nullable=True, server_default=sa.text('0.0')),
        sa.Column('training_data_summary', sa.Text(), nullable=True),
        sa.Column('performance_metrics', sa.JSON(), nullable=True),
        sa.Column('limitations', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('deprecated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version'),
        sa.ForeignKeyConstraint(['shadow_of'], ['risk_model_versions.version']),
    )
    op.create_index(op.f('ix_risk_model_versions_version'), 'risk_model_versions', ['version'], unique=True)
    op.create_index(op.f('ix_risk_model_versions_status'), 'risk_model_versions', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_risk_model_versions_status'), table_name='risk_model_versions')
    op.drop_index(op.f('ix_risk_model_versions_version'), table_name='risk_model_versions')
    op.drop_table('risk_model_versions')
