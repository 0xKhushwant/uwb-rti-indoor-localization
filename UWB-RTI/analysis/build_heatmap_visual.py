from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
VIS_PATH = Path(
    r"C:\Users\Khushwant\.codex\visualizations\2026\07\15\019f6342-d1ae-7b51-81b4-8e6050f1c62b\rti-room-heatmaps.html"
)
PROCESSED = ROOT / "UWB-RTI" / "server" / "data" / "processed_trim5"
HEATMAPS = PROCESSED / "heatmaps"
GEOMETRY = ROOT / "UWB-RTI" / "analysis" / "setup_geometry.json"
INCH_TO_METER = 0.0254


def build_data() -> dict:
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    manifest = pd.read_csv(HEATMAPS / "heatmap_manifest.csv")

    trials = []
    for row in manifest.to_dict("records"):
        heatmap = pd.read_csv(HEATMAPS / row["heatmap_file"])
        heatmap = heatmap.iloc[::2][["x_m", "y_m", "normalized"]].round(3)
        trials.append(
            {
                "trial": row["trial"],
                "peak_x_m": round(row["peak_x_m"], 3),
                "peak_y_m": round(row["peak_y_m"], 3),
                "peak_score": round(row["peak_score"], 3),
                "points": heatmap.to_dict("records"),
            }
        )

    return {
        "room": {
            "width_m": round(geometry["room"]["width"] * INCH_TO_METER, 3),
            "height_m": round(geometry["room"]["height"] * INCH_TO_METER, 3),
        },
        "nodes": {
            name: {
                "x_m": round(point["x"] * INCH_TO_METER, 3),
                "y_m": round(point["y"] * INCH_TO_METER, 3),
            }
            for name, point in geometry["nodes"].items()
        },
        "trials": trials,
    }


def main() -> None:
    data = json.dumps(build_data(), separators=(",", ":"))
    VIS_PATH.write_text(
        f"""<div id="rti-room-heatmaps" style="display:grid;gap:12px;width:100%;">
  <style>
    #rti-room-heatmaps .viz-controls{{align-items:end}}
    #rti-room-heatmaps .stage{{display:grid;gap:10px}}
    #rti-room-heatmaps canvas{{width:100%;max-width:760px;aspect-ratio:1.1;border:1px solid var(--border);background:var(--background)}}
    #rti-room-heatmaps .meta{{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted-foreground)}}
  </style>
  <div class="viz-controls">
    <label class="form-label">Trial
      <select class="form-select" id="rti-heatmap-trial"></select>
    </label>
  </div>
  <div class="stage">
    <canvas id="rti-heatmap-canvas" width="760" height="680" role="img" aria-label="Top down RTI heatmap of the measured room"></canvas>
    <div class="meta text-small" id="rti-heatmap-meta"></div>
  </div>
  <script>
    (() => {{
      const data = {data};
      const root = document.getElementById("rti-room-heatmaps");
      const select = root.querySelector("#rti-heatmap-trial");
      const canvas = root.querySelector("#rti-heatmap-canvas");
      const meta = root.querySelector("#rti-heatmap-meta");
      const ctx = canvas.getContext("2d");
      data.trials.forEach((trial, i) => {{
        const option = document.createElement("option");
        option.value = String(i);
        option.textContent = trial.trial.replaceAll("_", " ");
        select.appendChild(option);
      }});
      const sx = (x) => 54 + x / data.room.width_m * 650;
      const sy = (y) => 626 - y / data.room.height_m * 560;
      function color(v) {{
        const a = Math.max(0, Math.min(1, v));
        return "rgba(224, 74, 55, " + (0.05 + a * 0.72) + ")";
      }}
      function draw() {{
        const trial = data.trials[Number(select.value || 0)];
        const styles = getComputedStyle(root);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = styles.getPropertyValue("--border").trim() || "#999";
        ctx.lineWidth = 2;
        ctx.strokeRect(54, 66, 650, 560);
        trial.points.forEach((p) => {{
          ctx.fillStyle = color(p.normalized);
          ctx.fillRect(sx(p.x_m) - 4, sy(p.y_m) - 4, 8, 8);
        }});
        ctx.strokeStyle = "rgba(120,120,120,0.55)";
        ctx.lineWidth = 1;
        [["A","B"],["A","C"],["A","D"],["B","C"],["B","D"],["C","D"]].forEach(([a,b]) => {{
          ctx.beginPath();
          ctx.moveTo(sx(data.nodes[a].x_m), sy(data.nodes[a].y_m));
          ctx.lineTo(sx(data.nodes[b].x_m), sy(data.nodes[b].y_m));
          ctx.stroke();
        }});
        Object.entries(data.nodes).forEach(([name,p]) => {{
          ctx.beginPath();
          ctx.fillStyle = styles.getPropertyValue("--primary").trim() || "#222";
          ctx.arc(sx(p.x_m), sy(p.y_m), 8, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = styles.getPropertyValue("--primary-foreground").trim() || "#fff";
          ctx.font = "500 12px sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(name, sx(p.x_m), sy(p.y_m));
        }});
        ctx.beginPath();
        ctx.strokeStyle = styles.getPropertyValue("--foreground").trim() || "#111";
        ctx.lineWidth = 3;
        ctx.arc(sx(trial.peak_x_m), sy(trial.peak_y_m), 12, 0, Math.PI * 2);
        ctx.stroke();
        meta.textContent = "Peak: x=" + trial.peak_x_m + " m, y=" + trial.peak_y_m +
          " m, score=" + trial.peak_score + " dB. Room: " + data.room.width_m +
          " m x " + data.room.height_m + " m.";
      }}
      select.addEventListener("change", draw);
      draw();
    }})();
  </script>
</div>
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
