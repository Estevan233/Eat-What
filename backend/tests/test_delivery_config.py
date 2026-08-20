"""Static delivery checks for the CloudBase container contract."""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_app_container_does_not_run_schema_changes_on_startup() -> None:
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    cmd_line = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))

    assert "uvicorn" in cmd_line
    assert "alembic" not in cmd_line
    assert "seed-all" not in cmd_line


def test_release_script_owns_migration_and_seed() -> None:
    script = (BACKEND_ROOT / "scripts" / "release.sh").read_text(encoding="utf-8")

    assert "alembic upgrade head" in script
    assert "eat-what seed-all" in script
    assert "uvicorn" not in script
