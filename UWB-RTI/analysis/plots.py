from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_ranges(input_csv: Path, output_png: Path) -> None:
    frame = pd.read_csv(input_csv)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    pivot = frame.pivot_table(index="timestamp", columns="link", values="range", aggfunc="last")
    axis = pivot.plot(figsize=(10, 5), linewidth=1.5)
    axis.set_ylabel("Range (m)")
    axis.set_xlabel("Time")
    axis.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_png, dpi=150)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot RTI link ranges from a recording CSV.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("ranges.png"))
    args = parser.parse_args()
    plot_ranges(args.input_csv, args.output)


if __name__ == "__main__":
    main()

