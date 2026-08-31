#!/bin/sh
set -eu

database_backend="${DATABASE_BACKEND:-sqlalchemy}"

# CloudBase REST is the production runtime path.  It intentionally has no
# DATABASE_URL, and the HTTP gateway cannot execute Alembic DDL.  Schema
# migrations must therefore be applied explicitly through the CloudBase SQL
# console/MCP before deployment; never make a REST release fail by trying to
# open a SQLAlchemy connection here.
if [ "$database_backend" = "cloudbase_rest" ]; then
  echo "CloudBase REST backend detected; skipping Alembic DDL."
else
  echo "Applying database migrations..."
  alembic upgrade head
fi

echo "Importing idempotent food and recipe seeds..."
eat-what seed-all
if [ "$database_backend" = "cloudbase_rest" ]; then
  echo "Verifying CloudBase HTTP gateway read contract after seed import..."
  python /app/scripts/verify_cloudbase_rdb.py
fi

echo "Database release tasks completed."
