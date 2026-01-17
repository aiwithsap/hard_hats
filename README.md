# Safety Video Analytics Demo

PPE compliance and zone violation detection using YOLOv11.

## Quick Start

```bash
docker compose up --build
```

Open http://localhost:8123

## Features

- **PPE Mode**: Detects hardhats, safety vests, masks
  - Green box = Compliant (wearing PPE)
  - Red box = Violation (missing PPE)
  - Yellow box = Unknown/Uncertain

- **Zone Mode**: Detects people in restricted areas
  - Green box = Outside zone (safe)
  - Red box = Inside zone (violation)

## Configuration

Edit `data/config/default.json`:

```json
{
  "mode": "ppe",
  "source": "data/videos/construction_workers.mp4",
  "weights": "data/weights/best_yolo11s.pt",
  "zone_polygon": [[100, 100], [500, 100], [500, 400], [100, 400]],
  "imgsz": 640,
  "conf": 0.25
}
```

### Options

| Field | Description |
|-------|-------------|
| `mode` | `"ppe"` or `"zone"` |
| `source` | Video file path or `"0"` for webcam |
| `weights` | Path to YOLO weights |
| `zone_polygon` | List of [x,y] points defining restricted zone |
| `imgsz` | Inference image size (640 recommended) |
| `conf` | Confidence threshold (0.0-1.0) |

## Model

Uses [Construction-Hazard-Detection-YOLO11](https://huggingface.co/yihong1120/Construction-Hazard-Detection-YOLO11) with 11 classes:

- Hardhat, NO-Hardhat
- Safety Vest, NO-Safety Vest
- Mask, NO-Mask
- Person, Vehicle, Machinery
- Safety Cone, Utility Pole

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run (downloads assets automatically)
python -m app.main

# With options
python -m app.main --mode zone --conf 0.3
```

## Webcam (Linux only)

Uncomment the `devices` section in `docker-compose.yml`:

```yaml
devices:
  - "/dev/video0:/dev/video0"
```

Then set `"source": "0"` in config.
