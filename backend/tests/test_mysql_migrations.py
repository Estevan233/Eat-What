"""MySQL DDL smoke tests that do not require a live database."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(
    database_url: str,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "test",
            "DEBUG": "false",
            "DATABASE_URL": database_url,
            "JWT_SECRET": "x" * 32,
            "WX_APPID": "wx-test",
            "CLOUDBASE_ENV_ID": "cloud-test",
        }
    )

    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _compile_alembic_sql(
    database_url: str,
    revision: str = "head",
    *,
    command: str = "upgrade",
) -> subprocess.CompletedProcess[str]:
    return _run_alembic(database_url, command, revision, "--sql")


def test_all_alembic_revisions_compile_for_mysql() -> None:
    result = _compile_alembic_sql(
        "mysql+pymysql://user:pass@db.example/eat_what?charset=utf8mb4",
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE foods" in result.stdout
    assert "TEXT" in result.stdout
    assert "request_id VARCHAR(64) NOT NULL" in result.stdout
    assert "uq_recommendation_events_request_id" in result.stdout
    assert "account_kind VARCHAR(16)" in result.stdout
    assert "account_status VARCHAR(16)" in result.stdout
    assert "merged_into_user_id INTEGER" in result.stdout
    assert "merge_started_at DATETIME" in result.stdout
    assert "merged_at DATETIME" in result.stdout
    assert "openid LIKE 'guest:%'" in result.stdout
    assert "ix_users_account_kind_status" in result.stdout
    assert "ix_users_merged_into_user_id" in result.stdout
    assert "fk_users_merged_into_user_id_users" in result.stdout


def test_account_merge_revision_compiles_for_sqlite() -> None:
    result = _compile_alembic_sql(
        "sqlite:///./migration-offline.db",
        "20260820_06:head",
    )

    assert result.returncode == 0, result.stderr
    assert "account_kind VARCHAR(16)" in result.stdout
    assert "account_status VARCHAR(16)" in result.stdout
    assert "merged_into_user_id INTEGER" in result.stdout
    assert "openid LIKE 'guest:%'" in result.stdout
    assert "ix_users_account_kind_status" in result.stdout
    assert "ix_users_merged_into_user_id" in result.stdout


def test_account_merge_mysql_downgrade_drops_foreign_key_before_index() -> None:
    result = _compile_alembic_sql(
        "mysql+pymysql://user:pass@db.example/eat_what?charset=utf8mb4",
        "20260828_07:20260820_06",
        command="downgrade",
    )

    assert result.returncode == 0, result.stderr
    foreign_key_drop = (
        "ALTER TABLE users DROP FOREIGN KEY fk_users_merged_into_user_id_users"
    )
    merged_index_drop = "DROP INDEX ix_users_merged_into_user_id ON users"
    assert foreign_key_drop in result.stdout
    assert merged_index_drop in result.stdout
    assert result.stdout.index(foreign_key_drop) < result.stdout.index(merged_index_drop)


def test_account_merge_revision_round_trips_on_sqlite(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'account-merge-roundtrip.db'}"

    upgrade = _run_alembic(database_url, "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr

    downgrade = _run_alembic(database_url, "downgrade", "20260820_06")
    assert downgrade.returncode == 0, downgrade.stderr

    reupgrade = _run_alembic(database_url, "upgrade", "head")
    assert reupgrade.returncode == 0, reupgrade.stderr


def test_user_model_declares_account_merge_indexes_and_self_foreign_key() -> None:
    table = User.__table__
    index_names = {index.name for index in table.indexes}

    assert "ix_users_account_kind_status" in index_names
    assert "ix_users_merged_into_user_id" in index_names
    assert {
        (foreign_key.parent.name, foreign_key.target_fullname)
        for foreign_key in table.foreign_keys
    } >= {("merged_into_user_id", "users.id")}
