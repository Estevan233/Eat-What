"""MySQL DDL smoke tests that do not require a live database."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_all_alembic_revisions_compile_for_mysql() -> None:
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "test",
            "DEBUG": "false",
            "DATABASE_URL": "mysql+pymysql://user:pass@db.example/eat_what?charset=utf8mb4",
            "JWT_SECRET": "x" * 32,
            "WX_APPID": "wx-test",
            "CLOUDBASE_ENV_ID": "cloud-test",
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE foods" in result.stdout
    assert "TEXT" in result.stdout
    assert "request_id VARCHAR(64) NOT NULL" in result.stdout
    assert "uq_recommendation_events_request_id" in result.stdout
