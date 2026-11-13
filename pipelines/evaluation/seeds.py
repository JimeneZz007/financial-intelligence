"""CLI: python -m pipelines.evaluation.seeds [--seeds N] [--out FILE]

Evaluates the anomaly detector on several independent realisations of the synthetic data.

The reference evaluation (``python -m pipelines.evaluation``) uses one seed, and one of
the detector's conditions (the minimum deviation of one percentage point) was added after
looking at that seed. This script measures how much the results depend on that particular
realisation: for each seed it regenerates the extracts, loads them with the real ETL into
the *test* database and scores the detector with the same, unchanged thresholds.

Seeds other than the project seed were never used to choose a threshold, so their results
are a held-out check of the post-hoc adjustment. The scenarios are the same in every
realisation; only the random noise differs. The warehouse used by the application is never
touched.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.session import build_engine
from backend.app.repositories.warehouse import account_month_frame
from pipelines.etl.runner import run_pipeline
from pipelines.evaluation.anomaly_detection import evaluate, load_scenarios
from pipelines.generate import config as generator_config
from pipelines.generate.dataset import build_dataset, write_dataset

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "docs" / "evaluation" / "anomaly_detection_seeds.json"
DEFAULT_SEEDS = 20

METRICS = (
    "material_recall",
    "material_precision",
    "material_strict_precision",
    "all_recall",
    "all_precision",
    "scenarios_detected_material",
)


def seed_list(count: int, first: int = generator_config.SEED) -> list[int]:
    """The project seed followed by consecutive seeds, fixed before looking at results."""
    if count < 1:
        raise ValueError("At least one seed is required.")
    return [first + offset for offset in range(count)]


def seed_metrics(seed: int, result: dict[str, Any]) -> dict[str, Any]:
    """The figures of one evaluation that are compared across seeds."""
    material = result["material_flags"]
    flagged = material["flagged_cells"]
    return {
        "seed": seed,
        "material_flags": flagged,
        "material_recall": material["cell_recall"],
        "material_precision": material["precision"],
        # Only primary cells count as hits; derived cells are treated as errors.
        "material_strict_precision": (material["flagged_primary"] / flagged) if flagged else None,
        "all_recall": result["all_flags"]["cell_recall"],
        "all_precision": result["all_flags"]["precision"],
        "scenarios_detected_material": result["scenarios_detected_material"],
        "scenario_recall": {s["id"]: s["cell_recall"] for s in result["scenarios"]},
    }


def _describe(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "stdev": statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
    }


def summarise(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    """Distribution of every metric across seeds, with and without the project seed."""
    if not per_seed:
        raise ValueError("No seed results to summarise.")
    project_seed = generator_config.SEED

    def block(rows: list[dict[str, Any]]) -> dict[str, Any]:
        metrics = {
            name: _describe([float(row[name]) for row in rows if row[name] is not None])
            for name in METRICS
        }
        scenario_ids = sorted({key for row in rows for key in row["scenario_recall"]})
        scenarios = {
            scenario_id: _describe(
                [
                    float(row["scenario_recall"][scenario_id])
                    for row in rows
                    if row["scenario_recall"].get(scenario_id) is not None
                ]
            )
            for scenario_id in scenario_ids
        }
        return {"seeds": len(rows), "metrics": metrics, "scenario_recall": scenarios}

    held_out = [row for row in per_seed if row["seed"] != project_seed]
    return {
        "all_seeds": block(per_seed),
        "held_out_seeds": block(held_out) if held_out else None,
    }


def _migrated_test_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url(settings.postgres_test_db)
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")
    return build_engine(url)


def evaluate_seed(engine: Engine, seed: int) -> dict[str, Any]:  # pragma: no cover - slow
    """Generate, load and evaluate one realisation of the data."""
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory)
        write_dataset(build_dataset(seed), source, seed)
        summary = run_pipeline(engine, source)
        if not summary.succeeded:
            raise RuntimeError(f"ETL failed for seed {seed}: {summary.error_message}")
        with Session(engine) as session:
            history = account_month_frame(session, [])
        return seed_metrics(seed, evaluate(history, load_scenarios(source)))


def main() -> None:  # pragma: no cover - command-line entry point
    parser = argparse.ArgumentParser(description="Evaluate the detector over several seeds.")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    engine = _migrated_test_engine()
    per_seed = []
    for seed in seed_list(args.seeds):
        row = evaluate_seed(engine, seed)
        per_seed.append(row)
        print(
            f"seed {seed}: material recall {row['material_recall']:.1%}  "
            f"precision {row['material_precision']:.1%}  "
            f"strict {row['material_strict_precision']:.1%}  "
            f"scenarios {row['scenarios_detected_material']}/9"
        )
    engine.dispose()

    summary = summarise(per_seed)
    result: dict[str, Any] = {
        "description": (
            "Anomaly detector evaluated on independent realisations of the synthetic data. "
            "Thresholds are unchanged; only the random noise differs between seeds."
        ),
        "project_seed": generator_config.SEED,
        "seeds": seed_list(args.seeds),
        "summary": summary,
        "per_seed": per_seed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    held_out = summary["held_out_seeds"]
    if held_out:
        metrics = held_out["metrics"]
        print(f"Held-out seeds: {held_out['seeds']}")
        for name in METRICS:
            stats = metrics[name]
            print(
                f"  {name:<30} mean {stats['mean']:.3f}  "
                f"range {stats['min']:.3f}-{stats['max']:.3f}"
            )
    print(f"Written to {args.out}")


if __name__ == "__main__":  # pragma: no cover
    main()
