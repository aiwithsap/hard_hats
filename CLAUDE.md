# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Docker (recommended - turnkey)
docker compose up --build        # First run (downloads model + video)
docker compose up                # Subsequent runs
docker compose down              # Stop

# Local development
pip install -r requirements.txt
python -m app.main               # Run with defaults
python -m app.main --mode zone --conf 0.3  # With CLI overrides
```

## Architecture

**Threading Model**: Flask web server (main thread) + video processing (background thread) with thread-safe `FrameBuffer` for frame sharing.

**Core Pipeline**:
1. `app/main.py` - Flask MJPEG server at port 8123, asset auto-download, video capture loop
2. `app/vision.py` - YOLOv11 inference (`infer()`), PPE annotation (`annotate_ppe()`), zone annotation (`annotate_zone()`)
3. `app/config.py` - Configuration hierarchy: defaults → JSON (`data/config/default.json`) → CLI args

**Detection Modes**:
- **PPE Mode**: Checks head region (top 30% of person box) for Hardhat/NO-Hardhat overlap using IoU
- **Zone Mode**: Checks if person centroid falls inside polygon using `cv2.pointPolygonTest`

**YOLO Classes** (from `yihong1120/Construction-Hazard-Detection-YOLO11`):
- 0: Hardhat, 2: NO-Hardhat, 5: Person, 7: Safety Vest, 4: NO-Safety Vest

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | Flask server, video loop, asset download |
| `app/vision.py` | YOLO inference + annotation logic |
| `app/config.py` | Config dataclass, CLI parsing, class constants |
| `data/config/default.json` | Runtime configuration |
| `tools/download_assets.py` | Hugging Face model + video downloader |

## Configuration

Edit `data/config/default.json` or pass CLI flags:
- `mode`: "ppe" or "zone"
- `source`: video path or "0" for webcam
- `conf`: confidence threshold (0.25 default)
- `imgsz`: inference size (640 default)
- `zone_polygon`: [[x,y], ...] for zone mode

## Performance Notes

- **CPU-only** by default (~174ms/frame, ~5.7 FPS on typical cloud CPU)
- At 0.5 FPS target: supports ~11 concurrent camera streams per CPU
- GPU requires CUDA base image + nvidia runtime in docker-compose
