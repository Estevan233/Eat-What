"""Build a review log from the candidate seed without inventing approvals."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

DEFAULT_SEED = Path(__file__).resolve().parent.parent / "data" / "external_dining_seed.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "candidate_review_manifest.csv"

FIELDS = (
    "catalog_key",
    "dish_name",
    "candidate_kind",
    "anchor_food",
    "continuity_score",
    "source_url",
    "source_type",
    "source_checked_at",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "review_notes",
)


def build_manifest(seed_path: Path) -> list[dict[str, object]]:
    raw: object = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("candidate seed 顶层必须是 list")
    rows: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("candidate seed 含非 object 记录")
        rows.append(
            {
                "catalog_key": item.get("catalog_key", ""),
                "dish_name": item.get("dish_name", ""),
                "candidate_kind": "external",
                "anchor_food": item.get("anchor_food", ""),
                "continuity_score": item.get("continuity_score", "pending"),
                "source_url": item.get("source_url", ""),
                "source_type": item.get("source_type", ""),
                "source_checked_at": item.get("source_checked_at", ""),
                "review_status": item.get("review_status", "draft"),
                "reviewed_by": item.get("reviewed_by", ""),
                "reviewed_at": item.get("reviewed_at", ""),
                "review_notes": item.get("review_notes", ""),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = build_manifest(args.seed)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    statuses = sorted({str(row["review_status"]) for row in rows})
    print(
        f"candidate_review_manifest_ok rows={len(rows)} statuses={','.join(statuses)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
