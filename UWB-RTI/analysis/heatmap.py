from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


LINKS = ["A-B", "A-C", "A-D", "B-C", "B-D", "C-D"]


def attenuation_matrix(samples_csv: Path, baseline_csv: Path) -> pd.DataFrame:
    samples = pd.read_csv(samples_csv)
    baseline = pd.read_csv(baseline_csv).set_index("link")
    latest = samples[samples["link"].isin(LINKS)].groupby("link").tail(1).set_index("link")
    rows = []
    for link in LINKS:
        rx_now = float(latest.loc[link, "rx_power"]) if link in latest.index else np.nan
        rx_base = float(baseline.loc[link, "rx_mean"]) if link in baseline.index else np.nan
        rows.append({"link": link, "attenuation_db": rx_base - rx_now})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute the current six-link attenuation vector.")
    parser.add_argument("samples_csv", type=Path)
    parser.add_argument("baseline_csv", type=Path)
    args = parser.parse_args()
    print(attenuation_matrix(args.samples_csv, args.baseline_csv))


if __name__ == "__main__":
    main()

