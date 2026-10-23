"""baseline schema

Revision ID: 0001
Revises:
Create Date: 2026-10-23 13:44:58.055323
"""
from typing import Sequence, Union

import pgvector.sqlalchemy.vector
import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Adoption of databases that predate Alembic: the pre-Alembic app created the three RAG
# tables with create_all (identical definitions to the models), so existing tables are
# skipped rather than failing the baseline. Everything else is created normally.
_preexisting: set[str] = set()


def _create_table(name, *columns, **kw):
    if name in _preexisting:
        return
    op.create_table(name, *columns, **kw)


def _create_index(index_name, table_name, columns, **kw):
    if table_name in _preexisting:
        return
    op.create_index(index_name, table_name, columns, **kw)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _preexisting.update(sa.inspect(bind).get_table_names())
    _create_table('circuit_breakers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('dependency', sa.String(), nullable=False),
    sa.Column('state', sa.String(), nullable=True),
    sa.Column('failure_count', sa.Integer(), nullable=True),
    sa.Column('success_count', sa.Integer(), nullable=True),
    sa.Column('last_failure_at', sa.DateTime(), nullable=True),
    sa.Column('last_state_change_at', sa.DateTime(), nullable=True),
    sa.Column('failure_threshold', sa.Integer(), nullable=True),
    sa.Column('cooldown_seconds', sa.Integer(), nullable=True),
    sa.Column('half_open_max_calls', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dependency')
    )
    _create_table('compliance_documents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('category', sa.String(), nullable=False),
    sa.Column('jurisdiction', sa.String(), nullable=True),
    sa.Column('effective_date', sa.DateTime(), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('precedent_decisions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('case_summary', sa.Text(), nullable=False),
    sa.Column('decision', sa.String(), nullable=False),
    sa.Column('reasoning', sa.Text(), nullable=True),
    sa.Column('risk_factors', sa.JSON(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('sanctions_entries',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('program', sa.String(), nullable=True),
    sa.Column('country', sa.String(), nullable=True),
    sa.Column('aliases', sa.JSON(), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('first_name', sa.String(), nullable=False),
    sa.Column('last_name', sa.String(), nullable=False),
    sa.Column('company', sa.String(), nullable=True),
    sa.Column('plan', sa.String(), nullable=True),
    sa.Column('total_credits', sa.Integer(), nullable=True),
    sa.Column('used_credits', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_verified', sa.Boolean(), nullable=True),
    sa.Column('is_trial', sa.Boolean(), nullable=True),
    sa.Column('trial_expires_at', sa.DateTime(), nullable=True),
    sa.Column('billing_cycle_start', sa.DateTime(), nullable=True),
    sa.Column('billing_cycle_end', sa.DateTime(), nullable=True),
    sa.Column('pending_plan_change', sa.String(), nullable=True),
    sa.Column('timezone', sa.String(), nullable=True),
    sa.Column('saved_card_last4', sa.String(), nullable=True),
    sa.Column('saved_card_expiry', sa.String(), nullable=True),
    sa.Column('saved_card_holder', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    _create_table('account_baselines',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('account_id', sa.String(), nullable=False),
    sa.Column('avg_amount', sa.Float(), nullable=True),
    sa.Column('avg_frequency_per_day', sa.Float(), nullable=True),
    sa.Column('max_amount', sa.Float(), nullable=True),
    sa.Column('min_amount', sa.Float(), nullable=True),
    sa.Column('std_dev_amount', sa.Float(), nullable=True),
    sa.Column('typical_countries', sa.JSON(), nullable=True),
    sa.Column('typical_payees', sa.JSON(), nullable=True),
    sa.Column('typical_tx_types', sa.JSON(), nullable=True),
    sa.Column('first_transaction_at', sa.DateTime(), nullable=True),
    sa.Column('last_transaction_at', sa.DateTime(), nullable=True),
    sa.Column('history_days', sa.Integer(), nullable=True),
    sa.Column('total_transactions', sa.Integer(), nullable=True),
    sa.Column('is_cold_start', sa.Boolean(), nullable=True),
    sa.Column('last_computed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('api_keys',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('key_hash', sa.String(), nullable=False),
    sa.Column('key_prefix', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_hash')
    )
    _create_table('audit_logs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=True),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('resource_type', sa.String(), nullable=True),
    sa.Column('resource_id', sa.String(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.Column('ip_address', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('notification_preferences',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('email_blocked_tx', sa.Boolean(), nullable=True),
    sa.Column('email_new_cases', sa.Boolean(), nullable=True),
    sa.Column('email_daily_summary', sa.Boolean(), nullable=True),
    sa.Column('email_weekly_report', sa.Boolean(), nullable=True),
    sa.Column('email_system_downtime', sa.Boolean(), nullable=True),
    sa.Column('email_credit_alerts', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    _create_table('notifications',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.Column('link', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('rule_configs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('rule_id', sa.String(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('custom_parameters', sa.JSON(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=True),
    sa.Column('effective_from', sa.DateTime(), nullable=True),
    sa.Column('effective_to', sa.DateTime(), nullable=True),
    sa.Column('hit_count', sa.Integer(), nullable=True),
    sa.Column('last_hit_at', sa.DateTime(), nullable=True),
    sa.Column('false_positive_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('transactions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('idempotency_key', sa.String(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('currency', sa.String(), nullable=True),
    sa.Column('transaction_type', sa.String(), nullable=False),
    sa.Column('sender_name', sa.String(), nullable=False),
    sa.Column('receiver_name', sa.String(), nullable=False),
    sa.Column('destination_country', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('risk_score', sa.Float(), nullable=True),
    sa.Column('credit_tier', sa.String(), nullable=True),
    sa.Column('credits_consumed', sa.Float(), nullable=True),
    sa.Column('rule_results', sa.JSON(), nullable=True),
    sa.Column('behavioral_score', sa.Float(), nullable=True),
    sa.Column('ml_classification', sa.String(), nullable=True),
    sa.Column('ml_confidence', sa.Float(), nullable=True),
    sa.Column('total_latency_ms', sa.Float(), nullable=True),
    sa.Column('pipeline_stages', sa.JSON(), nullable=True),
    sa.Column('rag_context', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index(op.f('ix_transactions_idempotency_key'), 'transactions', ['idempotency_key'], unique=True)
    _create_table('webhook_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=True),
    sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('next_retry_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('delivered_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('cases',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('transaction_id', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('priority', sa.String(), nullable=True),
    sa.Column('severity', sa.String(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('assigned_to', sa.String(), nullable=True),
    sa.Column('sla_deadline', sa.DateTime(), nullable=True),
    sa.Column('escalated_at', sa.DateTime(), nullable=True),
    sa.Column('escalated_by', sa.String(), nullable=True),
    sa.Column('escalation_reason', sa.Text(), nullable=True),
    sa.Column('resolution', sa.String(), nullable=True),
    sa.Column('resolution_summary', sa.Text(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('case_comments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('case_notes',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('filings',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('filing_type', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('deadline', sa.DateTime(), nullable=True),
    sa.Column('narrative', sa.Text(), nullable=True),
    sa.Column('structured_data', sa.JSON(), nullable=True),
    sa.Column('reference_number', sa.String(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('submitted_by', sa.String(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(), nullable=True),
    sa.Column('confirmed_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('filings')
    op.drop_table('case_notes')
    op.drop_table('case_comments')
    op.drop_table('cases')
    op.drop_table('webhook_events')
    op.drop_index(op.f('ix_transactions_idempotency_key'), table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('rule_configs')
    op.drop_table('notifications')
    op.drop_table('notification_preferences')
    op.drop_table('audit_logs')
    op.drop_table('api_keys')
    op.drop_table('account_baselines')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('sanctions_entries')
    op.drop_table('precedent_decisions')
    op.drop_table('compliance_documents')
    op.drop_table('circuit_breakers')
