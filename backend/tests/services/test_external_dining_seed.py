"""B0 external candidate seed build, validation and import tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from app.services import external_dining_seed

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _build_seed(tmp_path: Path) -> Path:
    output = tmp_path / "external.json"
    env = os.environ.copy()
    env.setdefault("JWT_SECRET", "x" * 32)
    result = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "build_external_dining_seed.py"), "--output", str(output)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return output


def test_b0_builder_preserves_57_legacy_rules(tmp_path: Path) -> None:
    output = _build_seed(tmp_path)
    rows = json.loads(output.read_text(encoding="utf-8"))
    assert len(rows) == 57
    assert len({row["catalog_key"] for row in rows}) == 57
    assert len({row["legacy_key"] for row in rows}) == 57
    assert {row["review_status"] for row in rows} == {"draft"}


def test_b0_seed_passes_draft_validator(tmp_path: Path) -> None:
    output = _build_seed(tmp_path)
    result = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "validate_external_dining_seed.py"), "--path", str(output), "--allow-draft"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_draft_seed_requires_explicit_import_flag(session, tmp_path: Path) -> None:
    output = _build_seed(tmp_path)
    assert external_dining_seed.import_seed(session, output) == 0
    assert external_dining_seed.import_seed(session, output, include_drafts=True) == 57
    assert external_dining_seed.import_seed(session, output, include_drafts=True) == 57
    assert len(external_dining_seed._rows(session)) == 57
