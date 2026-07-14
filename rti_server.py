from flask import Flask, request, jsonify, send_file, render_template_string
from pathlib import Path
from threading import Lock
from datetime import datetime
import os
import csv

app = Flask(__name__)

lock = Lock()
latest_boards = {}
latest_links = {}
recording = False
csv_path = Path("rti_data.csv")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_board_status(last_seen_str):
    try:
        last_seen = datetime.strptime(
            last_seen_str,
            "%Y-%m-%d %H:%M:%S"
        )

        age = (
            datetime.now() - last_seen
        ).total_seconds()

        if age < 15:
            return "🟢 ONLINE"
        elif age < 45:
            return "🟡 STALE"
        else:
            return "🔴 OFFLINE"

    except:
        return "❓ UNKNOWN"
    
def ensure_csv():
    if not csv_path.exists():
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["server_time", "node", "peer", "range_m", "rx_power_dbm", "device_millis", "ip"])


@app.get("/")
def index():
    html = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>UWB RTI Dashboard</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 20px; background:#f7f7f7; }
        .row { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
        .card { background:white; padding:16px; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.08); }
        button, a.btn { border:0; padding:10px 14px; border-radius:10px; cursor:pointer; text-decoration:none; display:inline-block; }
        button { background:#111; color:white; }
        a.btn { background:#e5e5e5; color:#111; }
        table { border-collapse: collapse; width:100%; }
        th, td { border-bottom:1px solid #ddd; padding:8px; text-align:left; }
        th { background:#fafafa; }
        .small { color:#555; font-size: 13px; }
        .on { color: #0a7; font-weight: bold; }
        .off { color: #c33; font-weight: bold; }
      </style>
    </head>
    <body>
      <h2>UWB / RTI Dashboard</h2>
      <div class="row">
        <div class="card">
          <div>Status: <span id="rec" class="off">OFF</span></div>
          <div class="small">Hotspot connected boards will appear below.</div>
          <div style="margin-top:10px;">
            <button onclick="post('/api/record/start')">Start Recording</button>
            <button onclick="post('/api/record/stop')">Stop Recording</button>
            <a class="btn" href="/api/download">Download CSV</a>
          </div>
        </div>
      </div>

      <div class="row">
        <div class="card" style="flex:1; min-width:320px;">
          <h3>Board Status</h3>
          <table>
            <thead>
              <tr>
              <th>Node</th>
              <th>Status</th>
              <th>Type</th>
              <th>IP</th>
              <th>WiFi RSSI</th>
              <th>Last Seen</th>
              </tr>
            </thead>
            <tbody id="boards"></tbody>
          </table>
        </div>

        <div class="card" style="flex:1; min-width:320px;">
          <h3>Latest Links</h3>
          <table>
            <thead>
              <tr><th>Link</th><th>Range (m)</th><th>RX (dBm)</th><th>Last Seen</th></tr>
            </thead>
            <tbody id="links"></tbody>
          </table>
        </div>
      </div>

      <script>
        async function post(url) {
          await fetch(url, {method:'POST'});
          await refresh();
        }

        async function refresh() {
          const r = await fetch('/api/latest');
          const j = await r.json();

          document.getElementById('rec').textContent = j.recording ? 'ON' : 'OFF';
          document.getElementById('rec').className = j.recording ? 'on' : 'off';

          const boards = j.boards || [];
          const links = j.links || [];

          document.getElementById('boards').innerHTML = boards.map(x => `
            <tr>
              <td>${x.node || ''}</td>
              <td>${x.status || ''}</td>
              <td>${x.type || ''}</td>
              <td>${x.ip || ''}</td>
              <td>${x.wifi_rssi ?? ''}</td>
              <td>${x.last_seen || ''}</td>
            </tr>
          `).join('');

          document.getElementById('links').innerHTML = links.map(x => `
            <tr>
              <td>${x.link || ''}</td>
              <td>${x.range_m ?? ''}</td>
              <td>${x.rx_power_dbm ?? ''}</td>
              <td>${x.last_seen || ''}</td>
            </tr>
          `).join('');
        }

        refresh();
        setInterval(refresh, 1000);
      </script>
    </body>
    </html>
    """
    return render_template_string(html)


@app.post("/api/record/start")
def record_start():

    global recording
    global csv_path

    with lock:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        csv_path = Path(
            f"rti_{timestamp}.csv"
        )

        recording = True
        ensure_csv()

    return jsonify(
        ok=True,
        recording=True
    )


@app.post("/api/record/stop")
def record_stop():
    global recording
    with lock:
        recording = False
    return jsonify(ok=True, recording=False)


@app.get("/api/latest")
def api_latest():
    with lock:

        boards = []

        for board in latest_boards.values():
            b = board.copy()
            b["status"] = get_board_status(
                board["last_seen"]
            )
            boards.append(b)

        links = list(latest_links.values())

        boards.sort(
            key=lambda x: x.get("node", "")
        )

        links.sort(
            key=lambda x: x.get("link", "")
        )

        return jsonify(
            recording=recording,
            boards=boards,
            links=links
        )


@app.post("/api/ingest")
def ingest():
    global latest_boards, latest_links
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    node = str(data.get("node", "?")).strip().upper()
    typ = str(data.get("type", "ranging")).strip().lower()
    ip = str(data.get("ip", request.remote_addr or "")).strip()

    entry = {
        "node": node,
        "type": typ,
        "ip": ip,
        "wifi_rssi": data.get("wifi_rssi", ""),
        "last_seen": now_str(),
    }

    with lock:
        if typ == "heartbeat":
            latest_boards[node] = entry
        else:
            peer = str(data.get("peer", "")).strip().upper()
            link = f"{node}->{peer}" if peer else node
            entry.update({
                "peer": peer,
                "range_m": data.get("range", ""),
                "rx_power_dbm": data.get("rx", ""),
                "link": link,
                "device_millis": data.get("millis", ""),
            })
            latest_links[link] = entry
            latest_boards[node] = {
                "node": node,
                "type": "ranging",
                "ip": ip,
                "wifi_rssi": data.get("wifi_rssi", ""),
                "last_seen": now_str(),
            }

            if recording and peer:
                ensure_csv()
                with csv_path.open("a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow([
                        now_str(),
                        node,
                        peer,
                        data.get("range", ""),
                        data.get("rx", ""),
                        data.get("millis", ""),
                        ip
                    ])

    return jsonify(ok=True)


@app.get("/api/download")
def download():

    full_path = os.path.abspath(
        str(csv_path)
    )

    if not os.path.exists(full_path):
        return jsonify(
            error="CSV file not found"
        ), 404

    return send_file(
        full_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name=os.path.basename(
            full_path
        )
    )


if __name__ == "__main__":
    print("Open the dashboard at: http://172.22.244.47:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)