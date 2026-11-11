"""CLI: python -m pipelines.generate [--out DIR] [--seed N]"""

from __future__ import annotations

import argparse
from pathlib import Path

from pipelines.generate import config as cfg
from pipelines.generate.dataset import build_dataset, write_dataset

DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic source extracts.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="output directory")
    parser.add_argument("--seed", type=int, default=cfg.SEED, help="random seed")
    args = parser.parse_args()

    manifest = write_dataset(build_dataset(args.seed), args.out, args.seed)
    print(f"Synthetic dataset written to {args.out} (seed {manifest['seed']})")
    for name, info in manifest["files"].items():
        print(f"  {name:<26} {info['rows']:>8,} rows")
    totals = manifest["control_totals"]["sales_transactions"]
    print(f"  clean net sales: {totals['net_sales_amount']:,.2f} {cfg.CURRENCY}")


if __name__ == "__main__":
    main()
