#!/bin/sh
set -eu

echo "Applying database migrations..."
alembic upgrade head

echo "Importing idempotent food and recipe seeds..."
eat-what seed-all

echo "Database release tasks completed."
