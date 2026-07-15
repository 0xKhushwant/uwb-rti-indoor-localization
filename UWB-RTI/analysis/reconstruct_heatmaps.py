from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


LINKS = ["A-B", "A-C", "A-D", "B-C", "B-D", "C-D"]
INCH_TO_METER = 0.0254


def load_geometry(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def link_nodes(link: str) -> tuple[str, str]:
    source, target = link.split("-")
    return source, target


def node_xy_m(geometry: dict, node: str) -> np.ndarray:
    point = geometry["nodes"][node]
    return np.array([point["x"] * INCH_TO_METER, point["y"] * INCH_TO_METER], dtype=float)


def reconstruct_trial(
    trial_frame: pd.DataFrame,
    geometry: dict,
    grid_step_m: float,
    ellipse_width_m: float,
) -> pd.DataFrame:
    room = geometry["room"]
    width_m = room["width"] * INCH_TO_METER
    height_m = room["height"] * INCH_TO_METER

    xs = np.arange(0.0, width_m + grid_step_m * 0.5, grid_step_m)
    ys = np.arange(0.0, height_m + grid_step_m * 0.5, grid_step_m)

    rows = []
    usable = trial_frame.dropna(subset=["attenuation_db"])
    usable = usable[usable["attenuation_db"] > 0.0]

    for y in ys:
        for x in xs:
            pixel = np.array([x, y], dtype=float)
            weighted_sum = 0.0
            total_weight = 0.0

            for sample in usable.itertuples(index=False):
                a_name, b_name = link_nodes(sample.link)
                a = node_xy_m(geometry, a_name)
                b = node_xy_m(geometry, b_name)
                link_len = float(np.linalg.norm(a - b))
                excess_path = float(np.linalg.norm(pixel - a) + np.linalg.norm(pixel - b) - link_len)
                if excess_path > ellipse_width_m:
                    continue

                # Pixels close to the direct link path get the most weight; pixels
                # near the edge of the ellipse taper smoothly to zero.
                taper = 1.0 - (excess_path / ellipse_width_m)
                weight = max(0.0, taper) / math.sqrt(max(link_len, 1e-6))
                weighted_sum += weight * float(sample.attenuation_db)
                total_weight += weight

            value = weighted_sum / total_weight if total_weight > 0.0 else 0.0
            rows.append({"x_m": x, "y_m": y, "attenuation_score": value})

    frame = pd.DataFrame(rows)
    max_value = frame["attenuation_score"].max()
    frame["normalized"] = frame["attenuation_score"] / max_value if max_value > 0 else 0.0
    return frame


def build_heatmaps(
    processed_dir: Path,
    geometry_path: Path,
    output_dir: Path,
    grid_step_m: float,
    ellipse_width_m: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    geometry = load_geometry(geometry_path)
    attenuation = pd.read_csv(processed_dir / "attenuation_by_trial.csv")

    manifest_rows = []
    for trial, trial_frame in attenuation.groupby("trial", sort=False):
        heatmap = reconstruct_trial(trial_frame, geometry, grid_step_m, ellipse_width_m)
        safe_name = (
            trial.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("/", "_")
            .replace("__", "_")
        )
        output_path = output_dir / f"{safe_name}.heatmap.csv"
        heatmap.to_csv(output_path, index=False)

        peak = heatmap.sort_values("attenuation_score", ascending=False).head(1).iloc[0]
        manifest_rows.append(
            {
                "trial": trial,
                "heatmap_file": output_path.name,
                "peak_x_m": peak["x_m"],
                "peak_y_m": peak["y_m"],
                "peak_score": peak["attenuation_score"],
                "grid_step_m": grid_step_m,
                "ellipse_width_m": ellipse_width_m,
            }
        )

    pd.DataFrame(manifest_rows).to_csv(output_dir / "heatmap_manifest.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build first-pass RTI heatmaps from processed attenuation data.")
    parser.add_argument("--processed-dir", type=Path, default=Path("UWB-RTI/server/data/processed_trim5"))
    parser.add_argument("--geometry", type=Path, default=Path("UWB-RTI/analysis/setup_geometry.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("UWB-RTI/server/data/processed_trim5/heatmaps"))
    parser.add_argument("--grid-step-m", type=float, default=0.05)
    parser.add_argument("--ellipse-width-m", type=float, default=0.45)
    args = parser.parse_args()

    build_heatmaps(args.processed_dir, args.geometry, args.output_dir, args.grid_step_m, args.ellipse_width_m)


if __name__ == "__main__":
    main()
