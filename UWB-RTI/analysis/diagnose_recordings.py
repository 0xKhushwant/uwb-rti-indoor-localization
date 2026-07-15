from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


LINKS = ["A-B", "A-C", "A-D", "B-C", "B-D", "C-D"]


def read_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


def diagnose_file(path: Path) -> list[dict]:
    frame = read_frame(path)
    rows = []
    if frame.empty:
        return [
            {
                "file": path.name,
                "link": link,
                "samples": 0,
                "duration_s": 0.0,
                "samples_per_min": 0.0,
                "rx_mean": None,
                "rx_std": None,
                "range_mean": None,
                "range_std": None,
                "max_gap_s": None,
            }
            for link in LINKS
        ]

    duration_s = max(1e-9, (frame["timestamp"].max() - frame["timestamp"].min()).total_seconds())
    for link in LINKS:
        link_frame = frame[frame["link"] == link].sort_values("timestamp")
        gaps = link_frame["timestamp"].diff().dt.total_seconds().dropna()
        rows.append(
            {
                "file": path.name,
                "link": link,
                "samples": len(link_frame),
                "duration_s": round(duration_s, 3),
                "samples_per_min": round(len(link_frame) / duration_s * 60.0, 2),
                "rx_mean": link_frame["rx_power"].mean() if not link_frame.empty else None,
                "rx_std": link_frame["rx_power"].std() if len(link_frame) > 1 else None,
                "range_mean": link_frame["range"].mean() if not link_frame.empty else None,
                "range_std": link_frame["range"].std() if len(link_frame) > 1 else None,
                "max_gap_s": gaps.max() if not gaps.empty else None,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose RTI recording health by link.")
    parser.add_argument("--data-dir", type=Path, default=Path("UWB-RTI/server/data"))
    parser.add_argument("--output", type=Path, default=Path("UWB-RTI/server/data/processed_trim5/link_health.csv"))
    args = parser.parse_args()

    files = [
        args.data_dir / "empty_room.csv",
        args.data_dir / "standing_20cm_in_front_of_board_B.csv",
        args.data_dir / "standing_in_front_of_boardA_20cm.csv",
        args.data_dir / "standing_20cm_in_front_of boardD.csv",
        args.data_dir / "standing_in_front_of_board_C_20cm.csv",
        args.data_dir / "walking_between_A_and_C_continusoly_back_and_froth.csv",
    ]
    rows = []
    for path in files:
        if path.exists():
            rows.extend(diagnose_file(path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
