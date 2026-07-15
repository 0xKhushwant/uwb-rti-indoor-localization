from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


LINKS = ["A-B", "A-C", "A-D", "B-C", "B-D", "C-D"]


def label_for(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^rti_\d{8}_\d{6}$", "", stem)
    stem = stem.strip("_ ")
    return stem or path.stem


def read_trimmed(path: Path, trim_seconds: float) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty:
        return frame

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    start = frame["timestamp"].min() + pd.Timedelta(seconds=trim_seconds)
    end = frame["timestamp"].max() - pd.Timedelta(seconds=trim_seconds)
    return frame[(frame["timestamp"] >= start) & (frame["timestamp"] <= end)].copy()


def per_link_stats(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["link", "samples", "range_mean", "range_std", "rx_mean", "rx_std", "fp_mean"])

    return (
        frame[frame["link"].isin(LINKS)]
        .groupby("link", as_index=False)
        .agg(
            samples=("rx_power", "size"),
            range_mean=("range", "mean"),
            range_std=("range", "std"),
            rx_mean=("rx_power", "mean"),
            rx_std=("rx_power", "std"),
            fp_mean=("fp_power", "mean"),
        )
    )


def ordered_stats(stats: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"link": LINKS}).merge(stats, on="link", how="left")


def build_summary(data_dir: Path, output_dir: Path, baseline_name: str, trim_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = data_dir / baseline_name
    baseline = read_trimmed(baseline_path, trim_seconds)
    baseline.to_csv(output_dir / "empty_room.trimmed.csv", index=False)

    baseline_stats = ordered_stats(per_link_stats(baseline))
    baseline_stats.to_csv(output_dir / "baseline_trimmed.csv", index=False)

    baseline_rx = baseline_stats.set_index("link")["rx_mean"]
    trial_rows = []
    matrix_rows = []

    trial_files = [
        path
        for path in sorted(data_dir.glob("*.csv"))
        if path.name != baseline_name
        and not path.name.startswith("rti_")
        and path.stat().st_size > 64
    ]

    for trial_path in trial_files:
        label = label_for(trial_path)
        trimmed = read_trimmed(trial_path, trim_seconds)
        trimmed.to_csv(output_dir / f"{trial_path.stem}.trimmed.csv", index=False)

        stats = ordered_stats(per_link_stats(trimmed))
        stats["trial"] = label
        stats["attenuation_db"] = stats["link"].map(baseline_rx) - stats["rx_mean"]
        stats["range_delta_m"] = stats["range_mean"] - stats["link"].map(
            baseline_stats.set_index("link")["range_mean"]
        )
        matrix_rows.extend(stats.to_dict("records"))

        duration = (
            (trimmed["timestamp"].max() - trimmed["timestamp"].min()).total_seconds()
            if not trimmed.empty
            else 0.0
        )
        strongest = stats.sort_values("attenuation_db", ascending=False).head(3)
        trial_rows.append(
            {
                "trial": label,
                "file": trial_path.name,
                "trimmed_samples": len(trimmed),
                "trimmed_duration_s": round(duration, 3),
                "strongest_links": ", ".join(
                    f"{row.link}:{row.attenuation_db:.2f}dB"
                    for row in strongest.itertuples()
                    if pd.notna(row.attenuation_db)
                ),
            }
        )

    matrix = pd.DataFrame(matrix_rows)
    if not matrix.empty:
        matrix = matrix[
            [
                "trial",
                "link",
                "samples",
                "rx_mean",
                "rx_std",
                "attenuation_db",
                "range_mean",
                "range_delta_m",
                "fp_mean",
            ]
        ]
    matrix.to_csv(output_dir / "attenuation_by_trial.csv", index=False)
    pd.DataFrame(trial_rows).to_csv(output_dir / "trial_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trim RTI recordings and compute baseline attenuation summaries.")
    parser.add_argument("--data-dir", type=Path, default=Path("UWB-RTI/server/data"))
    parser.add_argument("--output-dir", type=Path, default=Path("UWB-RTI/server/data/processed"))
    parser.add_argument("--baseline", default="empty_room.csv")
    parser.add_argument("--trim-seconds", type=float, default=1.0)
    args = parser.parse_args()

    build_summary(args.data_dir, args.output_dir, args.baseline, args.trim_seconds)


if __name__ == "__main__":
    main()
