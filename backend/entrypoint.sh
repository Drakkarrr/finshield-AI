#!/bin/sh
set -e
# Schema is owned by Alembic: bring the database to head before serving traffic.
alembic upgrade head
exec "$@"
