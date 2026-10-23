#!/bin/sh
set -e
# Schema is owned by Alembic: bring the database to head before serving traffic.
alembic upgrade head
# Idempotent: seed/re-embed RAG, import list data on first run (never fails the start).
python -m scripts.bootstrap
exec "$@"
