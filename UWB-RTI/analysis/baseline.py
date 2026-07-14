from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


LINKS = ["A-B", "A-C", "A-D", "B-C", "B-D", "C-D"]


def build_baseline(input_csv: Path, output_csv: Path) -> pd.DataFrame:
    frame = pd.read_csv(input_csv)
    baseline = (
        frame[frame["link"].isin(LINKS)]
        .groupby("link", as_index=False)
        .agg(range_mean=("range", "mean"), rx_mean=("rx_power", "mean"), fp_mean=("fp_power", "mean"))
    )
    baseline.to_csv(output_csv, index=False)
    return baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a six-link empty-room RTI baseline.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("baseline.csv"))
    args = parser.parse_args()
    print(build_baseline(args.input_csv, args.output))


if __name__ == "__main__":
    main()

