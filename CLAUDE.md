# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Local dev (multi-service: Postgres + Redis + web + worker)
docker compose -f docker-compose.dev.yml up --build
docker compose -f docker-compose.dev.yml down

# Legacy single-container demo (monolith)
docker compose up --build
docker compose down

# Local dev without Docker (web service)
pip install -r requirements-web.txt
uvicorn app.web.main:app --host 0.0.0.0 --port 8123

# Local dev without Docker (worker service)
pip install -r requirements-worker-new.txt
python -m app.worker.main
```

## Architecture

**Services**
- Web service: FastAPI API/auth/SSE/MJPEG proxy, serves embedded dashboard. Uses Postgres + Redis.
- Worker service: RTSP/file capture + YOLO inference, publishes annotated JPEG frames to Redis, writes events to Postgres.
- Shared library: models, repositories, Redis helpers, encryption (`app/shared`).

**Data Flow**
1. Worker reads frames from camera/source.
2. Worker runs YOLO at `target_fps`, caches last detections, annotates each streamed frame with cached boxes.
3. Worker publishes JPEG frames and metadata to Redis (`frames:{camera_id}`, `camera_meta:{camera_id}`).
4. Web streams MJPEG from Redis at `/api/v1/stream/{camera_id}` and serves SSE at `/api/v1/sse/events`.

**Inference vs Stream FPS**
- `target_fps` controls inference cadence, not video playback.
- Stream FPS is derived from the capture FPS (fallback 15) and should remain smooth even when `target_fps` is low.

**YOLO Classes** (from `yihong1120/Construction-Hazard-Detection-YOLO11`):
- 0: Hardhat, 2: NO-Hardhat, 5: Person, 7: Safety Vest, 4: NO-Safety Vest

## Key Files

| File | Purpose |
|------|---------|
| `app/web/main.py` | FastAPI web service entry |
| `app/web/api/v1/*` | REST API, auth, stream, SSE |
| `app/web/dashboard.py` | Embedded dashboard HTML |
| `app/worker/main.py` | Worker entry |
| `app/worker/camera_manager.py` | Capture/inference/stream loop |
| `app/worker/vision.py` | YOLO load/infer/annotate |
| `app/shared/*` | DB models, repos, Redis helpers |

## Configuration

Environment (web + worker):
- `DATABASE_URL`, `REDIS_URL`
- `SECRET_KEY` (web), `ENCRYPTION_KEY` (web/worker)
- `WEIGHTS_PATH` (worker, default `data/weights/best_yolo11s.pt`, auto-download if missing)

Per-camera settings (DB via API):
- `target_fps` (YOLO cadence)
- `inference_width/height` (YOLO input size)
- `source_type`, `rtsp_url`, `placeholder_video`

## Performance Notes

- CPU-only by default; low `target_fps` is intentional to save CPU.
- Stream FPS is decoupled from inference, so video should remain smooth.
- To use more CPU, increase `target_fps`, add cameras, or run more worker replicas.
