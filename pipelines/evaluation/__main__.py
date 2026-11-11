"""CLI: python -m pipelines.evaluation [--source DIR] [--out FILE]

Scores the anomaly detector on the loaded warehouse against the injected scenarios and
writes the result as JSON (docs/evaluation/anomaly_detection.json by default).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.db.session import build_engine
from backend.app.repositories.warehouse import account_month_frame
from pipelines.evaluation.anomaly_detection import evaluate, load_scenarios

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate anomaly detection.")
    parser.add_argument("--source", type=Path, default=REPO_ROOT / "data" / "synthetic")
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "docs" / "evaluation" / "anomaly_detection.json"
    )
    args = parser.parse_args()

    with Session(build_engine()) as session:
        history = account_month_frame(session, [])
    result = evaluate(history, load_scenarios(args.source))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        f"Series: {result['series_evaluated']}  cells: {result['cells_evaluated']}  "
        f"primary cells: {result['primary_cells']}  threshold: |z| > {result['z_threshold']}"
    )
    print(f"{'scenario':<42}{'primary':>8}{'flagged':>9}{'material':>10}{'recall':>8}")
    for scenario in result["scenarios"]:
        label = f"{scenario['id']} {scenario['name']}"[:41]
        recall = scenario["cell_recall"]
        print(
            f"{label:<42}{scenario['primary_cells']:>8}{scenario['primary_flagged']:>9}"
            f"{scenario['primary_flagged_material']:>10}{recall:>8.0%}"
        )
    for name in ("all_flags", "material_flags"):
        block = result[name]
        print(
            f"{name}: {block['flagged_cells']} flagged = {block['flagged_primary']} primary + "
            f"{block['flagged_derived']} derived + {block['flagged_unexplained']} unexplained | "
            f"recall {block['cell_recall']:.1%}  precision {block['precision']:.1%}"
        )
    print(
        f"Scenarios detected: {result['scenarios_detected']}/{result['scenarios_total']} "
        f"(material: {result['scenarios_detected_material']}/{result['scenarios_total']})"
    )
    print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
