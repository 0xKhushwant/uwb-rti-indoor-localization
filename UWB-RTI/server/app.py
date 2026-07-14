from __future__ import annotations

import csv
import socket
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file


NODE_NAMES = ("A", "B", "C", "D")
LINK_NAMES = ("A-B", "A-C", "A-D", "B-C", "B-D", "C-D")
OFFLINE_AFTER_SECONDS = 4.0
HTTP_PORT = 5000
DISCOVERY_PORT = 50505
DISCOVERY_REQUEST = b"RTI_DISCOVER"
CSV_COLUMNS = ("timestamp", "source", "target", "link", "range", "rx_power", "fp_power", "wifi_rssi")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
state_lock = Lock()
recording = False
csv_path = DATA_DIR / "rti_latest.csv"


@dataclass
class BoardStatus:
    node: str
    ip: str = ""
    wifi_rssi: int | None = None
    last_seen: str = ""
    age: float | None = None
    online: bool = False


@dataclass
class LinkStatus:
    link: str
    source: str
    target: str
    range: float | None = None
    rx_power: float | None = None
    fp_power: float | None = None
    wifi_rssi: int | None = None
    timestamp: int | None = None
    server_time: str = ""
    age: float | None = None


boards: dict[str, BoardStatus] = {name: BoardStatus(node=name) for name in NODE_NAMES}
links: dict[str, LinkStatus] = {
    name: LinkStatus(link=name, source=name[0], target=name[2]) for name in LINK_NAMES
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="milliseconds")


def parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ensure_csv_header(path: Path) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(CSV_COLUMNS)


def csv_row(sample: LinkStatus) -> list[Any]:
    return [
        sample.server_time,
        sample.source,
        sample.target,
        sample.link,
        sample.range,
        sample.rx_power,
        sample.fp_power,
        sample.wifi_rssi,
    ]


def refresh_ages() -> None:
    now = utc_now()
    for board in boards.values():
        if not board.last_seen:
            board.online = False
            board.age = None
            continue
        seen = datetime.fromisoformat(board.last_seen)
        board.age = max(0.0, (now - seen).total_seconds())
        board.online = board.age <= OFFLINE_AFTER_SECONDS

    for link in links.values():
        if not link.server_time:
            link.age = None
            continue
        seen = datetime.fromisoformat(link.server_time)
        link.age = max(0.0, (now - seen).total_seconds())


def update_board(source: str, data: dict[str, Any]) -> None:
    board = boards.setdefault(source, BoardStatus(node=source))
    board.ip = request.remote_addr or board.ip
    board.wifi_rssi = parse_int(data.get("wifi_rssi"))
    board.last_seen = iso_now()
    board.online = True
    board.age = 0.0


def update_link(data: dict[str, Any]) -> LinkStatus | None:
    source = str(data.get("source", "")).strip().upper()
    target = str(data.get("target", "")).strip().upper()
    link_name = str(data.get("link") or f"{source}-{target}").strip().upper()
    if link_name not in LINK_NAMES:
        return None

    sample = links[link_name]
    sample.source = source
    sample.target = target
    sample.range = parse_float(data.get("range"))
    sample.rx_power = parse_float(data.get("rx_power"))
    sample.fp_power = parse_float(data.get("fp_power"))
    sample.wifi_rssi = parse_int(data.get("wifi_rssi"))
    sample.timestamp = parse_int(data.get("timestamp"))
    sample.server_time = iso_now()
    sample.age = 0.0
    return sample


def local_ipv4_addresses() -> list[str]:
    addresses = {"127.0.0.1"}
    hostname = socket.gethostname()
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addresses.add(info[4][0])
    except socket.gaierror:
        addresses.add("127.0.0.1")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        addresses.add("127.0.0.1")

    return sorted(addresses)


def udp_discovery_server() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
        print(f"RTI UDP discovery listening on 0.0.0.0:{DISCOVERY_PORT}")

        while True:
            message, sender = sock.recvfrom(256)
            if message.strip() != DISCOVERY_REQUEST:
                continue

            server_ip = sender[0]
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                    probe.connect((sender[0], sender[1]))
                    server_ip = probe.getsockname()[0]
            except OSError:
                server_ip = local_ipv4_addresses()[-1]

            response = f"RTI_SERVER http://{server_ip}:{HTTP_PORT}/api/ingest".encode("ascii")
            sock.sendto(response, sender)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    with state_lock:
        refresh_ages()
        return jsonify(
            recording=recording,
            boards=[asdict(boards[name]) for name in NODE_NAMES],
            links=[asdict(links[name]) for name in LINK_NAMES],
        )


@app.post("/api/ingest")
def api_ingest():
    data = request.get_json(silent=True) or {}
    source = str(data.get("source") or data.get("node") or "").strip().upper()
    if source not in NODE_NAMES:
        return jsonify(ok=False, error="unknown source"), 400

    with state_lock:
        update_board(source, data)
        sample = None
        if data.get("type") != "heartbeat" and data.get("target"):
            sample = update_link(data)
            if sample is None:
                return jsonify(ok=False, error="unknown link"), 400
            if recording:
                ensure_csv_header(csv_path)
                with csv_path.open("a", newline="", encoding="utf-8") as handle:
                    csv.writer(handle).writerow(csv_row(sample))

    return jsonify(ok=True)


@app.post("/api/record/start")
def api_record_start():
    global recording, csv_path
    with state_lock:
        csv_path = DATA_DIR / f"rti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        ensure_csv_header(csv_path)
        recording = True
    return jsonify(ok=True, recording=True, file=csv_path.name)


@app.post("/api/record/stop")
def api_record_stop():
    global recording
    with state_lock:
        recording = False
    return jsonify(ok=True, recording=False)


@app.get("/api/download")
def api_download():
    ensure_csv_header(csv_path)
    return send_file(csv_path, mimetype="text/csv", as_attachment=True, download_name=csv_path.name)


if __name__ == "__main__":
    print("RTI Dashboard URLs:")
    for address in local_ipv4_addresses():
        print(f"  http://{address}:{HTTP_PORT}")
    Thread(target=udp_discovery_server, daemon=True).start()
    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)
