"""Alembic environment: one metadata (app.database.Base) covering all tables."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import app.db_models  # noqa: F401  (registers every model on Base.metadata)
from app.database import DATABASE_URL, Base

# Its own engine: migrations need owner rights, and app.database.engine drops to the RLS-bound
# application role (which the migrations themselves create).
engine = create_engine(DATABASE_URL)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
