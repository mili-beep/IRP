"""Build the three figures embedded in report/final_report.md from saved runs."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def metric(run: Path, model: str, name: str) -> float:
    rows = pd.read_csv(run / "metrics_summary.csv")
    selected = rows.loc[(rows["model"] == model) & (rows["metric"] == name), "mean"]
    if len(selected) != 1:
        raise ValueError(f"Expected one {model}/{name} in {run}, found {len(selected)}")
    return float(selected.iloc[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p01", type=Path, required=True)
    parser.add_argument("--d01", type=Path, required=True)
    parser.add_argument("--d03", type=Path, required=True)
    parser.add_argument("--d07", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("report/figures"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    for name in ("normal_modes_by_hour.png", "normal_modes_pca.png"):
        source = args.p01 / "figures" / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, args.output / name)

    runs = [args.d01, args.d03, args.d07]
    models = ["statistical", "supervised", "xgboost"]
    labels = ["D01 Statistical", "D03 Histogram", "D07 XGBoost"]
    f1 = [metric(run, model, "f1") for run, model in zip(runs, models)]
    false_minutes = [metric(run, model, "false_alarms_per_day") for run, model in zip(runs, models)]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    x = range(3)
    axes[0].bar(x, f1, color="#24628a")
    axes[0].set_ylim(0, 1.08)
    axes[0].set_ylabel("Mean fold F1 (higher is better)")
    axes[1].bar(x, false_minutes, color="#ac5738")
    axes[1].set_ylim(0, max(false_minutes) * 1.20)
    axes[1].set_ylabel("Flagged normal minutes/day (lower is better)")
    for axis, values, fmt in zip(axes, (f1, false_minutes), (".5f", ".3f")):
        axis.set_xticks(list(x), labels, rotation=12, ha="right")
        for index, value in enumerate(values):
            axis.annotate(format(value, fmt), (index, value), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9)
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Scenario-holdout detection: score and normal-row burden")
    fig.savefig(args.output / "detection_comparison.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
