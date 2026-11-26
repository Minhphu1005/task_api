#!/bin/sh
set -e

echo "Running Alembic database migrations..."
alembic upgrade head

echo "Starting TaskHub API server..."
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
