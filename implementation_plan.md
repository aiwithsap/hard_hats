# Safety / Violation Video Analytics Demo (YOLOv11) — Implementation Plan

## Goal
Build a **Python demo** that:
- Ingests either **webcam** or a **video file**
- Runs **YOLOv11** inference (PPE hardhat compliance or zone/line violation)
- Renders results as **green/red person boxes**
- Displays output in a **browser** (MJPEG stream) so Docker works cleanly across platforms
- (Optional) Saves an annotated MP4 for later playback

This is a demo/experiment: keep it small, readable, and easy to run.

---

## Behavior Modes (switchable)
### Mode A — PPE (Hardhat compliance)
- Detect: `Person`, `Hardhat`, `NO-Hardhat` (via a YOLOv11 PPE-trained weights file)
- For each `Person`, compute a simple **head region** (top ~35% of the person box)
- If `NO-Hardhat` overlaps head region ⇒ **RED**
- Else if `Hardhat` overlaps ⇒ **GREEN**
- Else ⇒ **GRAY/UNKNOWN** (optional, or treat as red for strict compliance)

### Mode B — Restricted Zone / Line Violation
- Detect `Person`
- Define a polygon **zone** (or a line) in config
- If person centroid enters polygon (or crosses line) ⇒ **RED**
- Else ⇒ **GREEN**
- Works well for generic “people walking” videos.

---

## Deliverables
1. Dockerized demo runnable with **docker compose**
2. Auto-downloader for a few **open demo videos** + weights
3. Single command to start demo and open browser stream

---

## Repository Layout
```
safety_demo/
  app/
    main.py                 # starts pipeline + MJPEG server
    vision.py               # inference + rendering helpers
    config.py               # config parsing (zone polygon, thresholds)
  tools/
    download_assets.py      # downloads demo videos + model weights
  data/
    videos/                 # downloaded demo MP4s
    weights/                # YOLOv11 PPE weights (.pt)
    output/                 # optional annotated outputs
    config/
      demo_zone.json        # polygon/line config for zone mode
  docker/
    Dockerfile
  docker-compose.yml
  requirements.txt
  README.md                 # 10 lines: how to run
```

---

## Core Design (simple + stable)
### Pipeline
1. Video source:
   - webcam (Linux): `/dev/video0`
   - video file: `/app/data/videos/<file>.mp4`
2. Frame loop:
   - read frame
   - run YOLO predict
   - apply mode logic (PPE/zone)
   - overlay boxes + text
3. Output:
   - MJPEG stream at `http://localhost:8000/`
   - optional MP4 writer to `data/output/`

### Why MJPEG for display
GUI windows (OpenCV `imshow`) are painful in Docker (X11/Wayland/Windows). MJPEG makes the demo **portable**: any laptop can view in a browser.

---

## Config
### `data/config/demo_zone.json`
Example:
```json
{
  "mode": "zone",
  "source": "data/videos/office_corridor.mp4",
  "zone_polygon": [[50,50],[600,50],[600,400],[50,400]],
  "imgsz": 640,
  "conf": 0.25,
  "save_output": false
}
```

For PPE mode, set `"mode": "ppe"` and provide `"weights": "data/weights/best_yolo11s_ppe.pt"`.

---

## Assets: download from the web (no manual hunting)
### `tools/download_assets.py`
- Downloads 2–3 public demo clips (Pexels) into `data/videos/`
- Downloads YOLOv11 PPE weights into `data/weights/`
- The developer should implement URLs as constants; if a URL ever changes, only this file needs edits.

**Important:** keep “demo assets” separate from the code so developers can swap videos/weights quickly.

---

## Implementation Details

### 1) `requirements.txt`
Keep minimal:
- `ultralytics`
- `opencv-python-headless` (headless inside Docker)
- `numpy`
- `flask` (MJPEG server)

### 2) `app/main.py` (entrypoint)
Responsibilities:
- Parse args / config JSON
- Open source (webcam or file)
- Load YOLO weights
- Start Flask server:
  - `/` serves a tiny HTML page with `<img src="/stream">`
  - `/stream` yields multipart MJPEG frames
- Main loop updates the latest annotated frame shared with the server

CLI arguments (minimum):
- `--mode {ppe,zone}`
- `--source <0 or path>`
- `--weights <path>`
- `--conf 0.25`
- `--imgsz 640`
- `--save-output true|false`

### 3) `app/vision.py`
Key functions:
- `infer(frame) -> detections`
- `annotate_ppe(frame, detections) -> frame`
- `annotate_zone(frame, detections, polygon) -> frame`
- helper `head_region(person_box, frac=0.35)`
- helper `iou(boxA, boxB)`
- helper `point_in_poly(centroid, polygon)`

### 4) (Optional) Tracking
Skip for v1. Tracking adds complexity. If needed, add `model.track(...)` with ByteTrack later.

---

## Docker

### `docker/Dockerfile`
Requirements:
- Python 3.11 slim
- System libs for OpenCV headless:
  - `libgl1`, `libglib2.0-0` (common minimum)
- Copy code
- Install requirements
- Default command runs Flask MJPEG server demo

Example Dockerfile:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app/ /app/app
COPY tools/ /app/tools
COPY data/ /app/data

EXPOSE 8000

CMD ["python", "-m", "app.main", "--config", "data/config/demo_zone.json"]
```

### `docker-compose.yml`
Two common run modes:

#### A) Video-file mode (portable, no webcam)
```yaml
services:
  demo:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
```

#### B) Webcam mode (Linux hosts)
Add device mapping:
```yaml
services:
  demo:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    devices:
      - "/dev/video0:/dev/video0"
```

Notes:
- Webcam-in-Docker is easiest on Linux.
- On Windows/Mac, prefer **video-file mode** for the demo.

---

## Runbook (developer-facing)

### 1) First run: download demo assets
From host (recommended):
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python tools/download_assets.py
```

Or inside Docker (optional):
```bash
docker compose run --rm demo python tools/download_assets.py
```

### 2) Start the demo
```bash
docker compose up --build
```

### 3) View output
Open:
- `http://localhost:8000/`

### 4) Switch modes
Edit `data/config/demo_zone.json`:
- Set `"mode": "ppe"` or `"zone"`
- Set `"source"` to a downloaded video
- Set `"weights"` for PPE mode

---

## Acceptance Criteria (demo-level)
- `docker compose up --build` starts without errors
- Browser shows live annotated frames
- PPE mode:
  - People get boxes, and helmet/no-helmet labeling is visible
- Zone mode:
  - Polygon is drawn; entering marks person red
- Runs at “good enough” speed on a laptop (even 8–15 FPS is fine)

---

## Common Pitfalls / Notes
- If PPE weights are missing or wrong dataset: PPE mode will fail silently (no helmet classes). Ensure the weights match expected labels.
- If video is 4K, inference may be slow: downscale or set `imgsz=640`.
- If webcam access fails in Docker on non-Linux hosts: use video-file mode.

---

## Next (optional) Enhancements
Keep out of v1 unless requested:
- Person tracking IDs + line-crossing counters
- Event logging (CSV/SQLite)
- Saving violation snapshots
- Simple UI overlay: counts + timestamps
