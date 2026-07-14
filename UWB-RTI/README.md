# UWB RTI Research Platform

This project converts four Makerfabs ESP32 UWB-X1 MAX boards into a distributed
six-link Radio Tomographic Imaging data collection platform. All boards run the
same firmware; only `NODE_NAME` changes between A, B, C, and D.

## Hardware

- 4 x Makerfabs ESP32 UWB-X1 MAX boards with DW1000
- Phone hotspot for WiFi
- Windows laptop running Flask at `172.22.244.47:5000`

The Makerfabs board wiring is used as shipped:

- DW1000 reset: GPIO 27
- DW1000 chip select: GPIO 4
- DW1000 IRQ: GPIO 34
- SPI SCK/MISO/MOSI: GPIO 18/19/23

## TDMA Schedule

The firmware uses an 8000 ms cycle. The longer slots give the Makerfabs
`DW1000Ranging` discovery and range handshake enough time to settle after role
changes.

| Time | Initiator | Reported links |
| --- | --- | --- |
| 0-2000 ms | A | A-B, A-C, A-D |
| 2000-4000 ms | B | B-C, B-D |
| 4000-6000 ms | C | C-D |
| 6000-8000 ms | none | all boards listen |

Only one node is a tag initiator in each active slot. Other boards run as
anchors/listeners. The firmware filters reports so the server receives the six
unique RTI links.

## Firmware Setup

1. Install Arduino IDE or Arduino CLI with ESP32 board support.
2. Install the Makerfabs `DW1000Ranging` library. Keep the original driver API;
   this project does not rewrite the DW1000 driver.
3. Open `firmware/RTINode.ino`.
4. Edit `firmware/config.h` and set one board identity:

   ```cpp
   #define NODE_NAME "A"
   ```

5. Flash board A, then repeat with `"B"`, `"C"`, and `"D"`.
6. Copy `firmware/RTINode/secrets.example.h` to
   `firmware/RTINode/secrets.h`, then add the phone hotspot credentials.
   `secrets.h` is intentionally ignored by Git so passwords stay local.
7. The boards discover the Flask server automatically over UDP port `50505`.
   `SERVER_FALLBACK_URL` in `firmware/config.h` is used only if discovery is
   blocked by firewall or hotspot isolation:

   ```cpp
   #define SERVER_FALLBACK_URL "http://10.255.226.47:5000/api/ingest"
   ```

## Server Setup

From PowerShell:

```powershell
cd "C:\Users\Khushwant\Documents\Projects\Indoor Localization\RTI\UWB-RTI\server"
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open the dashboard at:

```text
http://172.22.244.47:5000
```

If the laptop IP changes, restart `python app.py`. The boards will rediscover
the server without reflashing. If discovery does not work, allow UDP port
`50505` and TCP port `5000` through Windows Defender Firewall for the active
Python executable.

## Dashboard

The dashboard shows:

- Board status for A, B, C, and D
- Green online state when a heartbeat was received in the last 4 seconds
- Red offline state when heartbeats stop
- Six RTI links with range, RX power, FP power, and age
- Start Recording, Stop Recording, and Download CSV controls

## JSON Ingest Format

Each successful range event posts:

```json
{
  "source": "A",
  "target": "B",
  "link": "A-B",
  "range": 2.91,
  "rx_power": -81.4,
  "fp_power": -84.2,
  "wifi_rssi": -51,
  "timestamp": 123456,
  "online": true
}
```

Heartbeat packets are sent once per second and use the same `/api/ingest`
endpoint with `"type": "heartbeat"`.

## CSV Format

Recordings are saved in `server/data/` with columns:

```text
timestamp,source,target,link,range,rx_power,fp_power,wifi_rssi
```

## Analysis

Install analysis dependencies when needed:

```powershell
pip install pandas numpy matplotlib
```

Create an empty-room baseline:

```powershell
python analysis\baseline.py server\data\rti_YYYYMMDD_HHMMSS.csv -o baseline.csv
```

Compute the current attenuation vector:

```powershell
python analysis\heatmap.py server\data\rti_YYYYMMDD_HHMMSS.csv baseline.csv
```

Plot recorded ranges:

```powershell
python analysis\plots.py server\data\rti_YYYYMMDD_HHMMSS.csv -o ranges.png
```

The analysis code is intentionally organized around the six-link matrix so RTI
image reconstruction can be added directly on top of `A-B`, `A-C`, `A-D`,
`B-C`, `B-D`, and `C-D`.
