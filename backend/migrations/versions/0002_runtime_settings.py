"""runtime settings and feature flags (S1.4)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of the values that were code literals before S1.4. Do not import app code here:
# later changes to the defaults must not rewrite history.
SEED_SETTINGS = {
    "rules.threshold.wire": 10000.0,
    "rules.threshold.international": 50000.0,
    "behavioral.trigger.cold_start": 0.5,
    "behavioral.trigger.warm": 0.65,
    "risk.weights": {
        "rules": 0.5,
        "behavioral": 0.3,
        "model": 0.2
    },
    "decision.bands": {
        "block": 0.8,
        "block_if_rule": 0.6,
        "flag": 0.5,
        "review": 0.3
    },
    "billing.credit_cost": {
        "rule_only": 0.2,
        "behavioral": 0.5,
        "full_ml": 1.0
    },
    "billing.credit_packs": {
        "10000": 9,
        "50000": 39,
        "200000": 129
    },
    "billing.plans": [
        {
            "id": "starter",
            "name": "Starter",
            "price_monthly": 29,
            "included_credits": 15000,
            "features": [
                "Up to 15,000 credits/mo",
                "Rule + behavioral screening",
                "Email support",
                "1 API key"
            ]
        },
        {
            "id": "growth",
            "name": "Growth",
            "price_monthly": 99,
            "included_credits": 60000,
            "features": [
                "Up to 60,000 credits/mo",
                "Full ML pipeline",
                "Case management",
                "Priority support"
            ]
        },
        {
            "id": "pro",
            "name": "Pro",
            "price_monthly": 299,
            "included_credits": 250000,
            "features": [
                "Up to 250,000 credits/mo",
                "Everything in Growth",
                "SAR/STR filing",
                "Dedicated CSM"
            ]
        },
        {
            "id": "enterprise",
            "name": "Enterprise",
            "price_monthly": None,
            "included_credits": None,
            "features": [
                "Unlimited credits",
                "On-premise / VPC",
                "SSO + audit export",
                "99.9% uptime SLA"
            ]
        }
    ]
}

SEED_FLAGS = {
    "screening.behavioral": True,
    "screening.ml": True,
    "screening.rag": True
}


def upgrade() -> None:
    settings = op.create_table(
        "settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("key", "scope"),
    )
    flags = op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("key", "scope"),
    )
    now = datetime.utcnow()
    op.bulk_insert(settings, [
        {"key": k, "scope": "global", "value": v, "updated_by": None, "updated_at": now} for k, v in SEED_SETTINGS.items()
    ])
    op.bulk_insert(flags, [
        {"key": k, "scope": "global", "enabled": v, "updated_by": None, "updated_at": now} for k, v in SEED_FLAGS.items()
    ])


def downgrade() -> None:
    op.drop_table("feature_flags")
    op.drop_table("settings")
