"""Cross-catalog report and review manifest tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_catalog_report_distinguishes_draft_from_approved() -> None:
    report = BACKEND_ROOT / "data" / "candidate-catalog-report-test.json"
    env = os.environ.copy()
    env.setdefault("JWT_SECRET", "x" * 32)
    result = subprocess.run(
        [
            sys.executable,
            str(BACKEND_ROOT / "scripts" / "validate_candidate_catalog.py"),
            "--external-path",
            str(BACKEND_ROOT / "data" / "external_dining_seed.json"),
            "--allow-draft",
            "--report",
            str(report),
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        summary = json.loads(report.read_text(encoding="utf-8"))
    finally:
        report.unlink(missing_ok=True)
    assert summary["food"]["rows"] == 205
    assert summary["external"]["rows"] == 57
    assert summary["external"]["draft"] == 57
    assert summary["approved_total"] == 0
    assert summary["catalog_total"] == 205
    assert summary["cross_catalog_exact_name_overlap"] == 0


def test_review_manifest_preserves_draft_and_source_evidence() -> None:
    output = BACKEND_ROOT / "data" / "candidate-review-test.csv"
    result = subprocess.run(
        [
            sys.executable,
            str(BACKEND_ROOT / "scripts" / "build_candidate_review_manifest.py"),
            "--output",
            str(output),
        ],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        assert result.returncode == 0, result.stdout + result.stderr
        lines = output.read_text(encoding="utf-8").splitlines()
    finally:
        output.unlink(missing_ok=True)
    assert len(lines) == 58
    assert all("draft" in line for line in lines[1:])
