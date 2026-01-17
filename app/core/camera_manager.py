"""Camera manager for multi-camera orchestration."""

import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from ..models.camera import Camera, CameraStatus
from ..config import get_config
from ..vision import load_model, infer, annotate_frame
from .frame_buffer import FrameBuffer
from .event_processor import get_event_processor


class CameraManager:
    """
    Manages multiple camera threads and shared resources.

    Responsibilities:
    - Load camera configurations
    - Spawn/manage camera processing threads
    - Share YOLO model across cameras
    - Provide access to camera streams and status
    """

    def __init__(self, config_path: str = "data/config/cameras.json"):
        self.config_path = Path(config_path)
        self._cameras: Dict[str, Camera] = {}
        self._buffers: Dict[str, FrameBuffer] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._model = None
        self._model_lock = threading.Lock()
        self._running = False

    def load_cameras(self) -> List[Camera]:
        """Load camera configurations from JSON file."""
        if not self.config_path.exists():
            # Create default camera config
            self._create_default_config()

        with open(self.config_path) as f:
            config = json.load(f)

        cameras = []
        for cam_data in config.get("cameras", []):
            camera = Camera.from_dict(cam_data)
            self._cameras[camera.id] = camera
            self._buffers[camera.id] = FrameBuffer()
            cameras.append(camera)

        return cameras

    def _create_default_config(self):
        """Create default camera configuration for demo."""
        default_config = {
            "cameras": [
                {
                    "id": "cam-001",
                    "name": "Warehouse Zone A",
                    "zone": "Warehouse",
                    "source": "data/videos/construction_workers.mp4",
                    "position_x": 25,
                    "position_y": 30,
                    "start_offset": 0,
                    "playback_speed": 1.0,
                },
                {
                    "id": "cam-002",
                    "name": "Production Line 1",
                    "zone": "Production",
                    "source": "data/videos/construction_workers.mp4",
                    "position_x": 60,
                    "position_y": 45,
                    "start_offset": 120,
                    "playback_speed": 1.0,
                    "mirror": True,
                },
                {
                    "id": "cam-003",
                    "name": "Main Entrance",
                    "zone": "Common",
                    "source": "data/videos/construction_workers.mp4",
                    "position_x": 85,
                    "position_y": 20,
                    "start_offset": 240,
                    "playback_speed": 0.8,
                },
                {
                    "id": "cam-004",
                    "name": "Loading Dock",
                    "zone": "Warehouse",
                    "source": "data/videos/construction_workers.mp4",
                    "position_x": 40,
                    "position_y": 75,
                    "start_offset": 60,
                    "playback_speed": 1.2,
                    "hue_shift": 10,
                },
            ]
        }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(default_config, f, indent=2)

    def _get_model(self):
        """Get the shared YOLO model (lazy loading)."""
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    config = get_config()
                    print(f"[CameraManager] Loading YOLO model from: {config.weights}")
                    self._model = load_model(config.weights)
        return self._model

    def start(self):
        """Start all camera processing threads."""
        if self._running:
            return

        self._running = True
        self.load_cameras()

        # Pre-load model
        self._get_model()

        # Start threads for each camera
        for camera_id, camera in self._cameras.items():
            self._start_camera_thread(camera)

        print(f"[CameraManager] Started {len(self._cameras)} camera threads")

    def stop(self):
        """Stop all camera processing threads."""
        self._running = False

        # Signal all threads to stop
        for stop_event in self._stop_events.values():
            stop_event.set()

        # Wait for threads to finish
        for thread in self._threads.values():
            thread.join(timeout=5.0)

        self._threads.clear()
        self._stop_events.clear()
        print("[CameraManager] All camera threads stopped")

    def _start_camera_thread(self, camera: Camera):
        """Start processing thread for a single camera."""
        stop_event = threading.Event()
        self._stop_events[camera.id] = stop_event

        thread = threading.Thread(
            target=self._camera_processing_loop,
            args=(camera, stop_event),
            daemon=True,
            name=f"camera-{camera.id}",
        )
        self._threads[camera.id] = thread
        thread.start()

        camera.status = CameraStatus.ACTIVE

    def _camera_processing_loop(self, camera: Camera, stop_event: threading.Event):
        """Main processing loop for a single camera."""
        config = get_config()
        model = self._get_model()
        buffer = self._buffers[camera.id]
        event_processor = get_event_processor()

        # Open video source
        source = camera.source
        if source.isdigit():
            source = int(source)

        print(f"[{camera.id}] Opening video source: {source}")
        cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            camera.status = CameraStatus.ERROR
            camera.last_error = f"Failed to open video source: {source}"
            print(f"[{camera.id}] ERROR: {camera.last_error}")
            self._show_error_frame(buffer, camera)
            return

        # Set start offset if specified
        if camera.start_offset > 0:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(camera.start_offset * fps))

        # Get video properties
        fps_target = (cap.get(cv2.CAP_PROP_FPS) or 30) * camera.playback_speed
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        frame_times = []
        frame_number = 0

        while not stop_event.is_set():
            start_time = time.time()

            ret, frame = cap.read()
            if not ret:
                # Loop video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_number += 1

            # Apply demo mode transforms
            frame = self._apply_transforms(frame, camera)

            # Run inference
            detections = infer(model, frame, conf=config.conf, imgsz=config.imgsz)

            # Process events (violations)
            event_processor.process_detections(
                camera=camera,
                frame=frame,
                detections=detections,
                frame_number=frame_number,
            )

            # Annotate frame
            annotated = annotate_frame(
                frame,
                detections,
                mode=config.mode,
                polygon=config.zone_polygon if config.mode == "zone" else None,
            )

            # Calculate FPS
            elapsed = time.time() - start_time
            frame_times.append(elapsed)
            if len(frame_times) > 30:
                frame_times.pop(0)
            avg_time = sum(frame_times) / len(frame_times)
            current_fps = 1.0 / avg_time if avg_time > 0 else 0

            # Add camera overlay
            self._add_camera_overlay(annotated, camera, current_fps, config.mode)

            # Update buffer
            buffer.update(
                frame=annotated,
                fps=current_fps,
                detections=detections,
                frame_number=frame_number,
            )

            # Update camera stats
            camera.fps = current_fps
            camera.frame_count = frame_number
            camera.last_detection_count = len(detections)

            # Limit processing rate
            sleep_time = max(0, (1.0 / fps_target) - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time * 0.5)

        cap.release()
        camera.status = CameraStatus.INACTIVE

    def _apply_transforms(self, frame: np.ndarray, camera: Camera) -> np.ndarray:
        """Apply demo mode visual transforms."""
        # Mirror if configured
        if camera.mirror:
            frame = cv2.flip(frame, 1)

        # Apply hue shift for visual diversity
        if camera.hue_shift != 0:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hsv[:, :, 0] = (hsv[:, :, 0].astype(int) + camera.hue_shift) % 180
            frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # Brightness adjustment
        if camera.brightness != 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=camera.brightness, beta=0)

        return frame

    def _add_camera_overlay(
        self,
        frame: np.ndarray,
        camera: Camera,
        fps: float,
        mode: str,
    ):
        """Add camera info overlay to frame."""
        # Camera name and zone tag
        cv2.putText(
            frame,
            f"{camera.name}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),  # Cyan color
            2,
        )

        # Zone tag
        zone_colors = {
            "Warehouse": (255, 165, 0),   # Orange
            "Production": (0, 255, 0),     # Green
            "Common": (0, 255, 255),       # Yellow
            "Secure": (0, 0, 255),         # Red
        }
        zone_color = zone_colors.get(camera.zone, (255, 255, 255))
        cv2.putText(
            frame,
            camera.zone,
            (10, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            zone_color,
            1,
        )

        # FPS and mode (bottom right)
        h = frame.shape[0]
        cv2.putText(
            frame,
            f"FPS: {fps:.1f} | {mode.upper()}",
            (10, h - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

    def _show_error_frame(self, buffer: FrameBuffer, camera: Camera):
        """Show error frame in buffer."""
        error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            error_frame,
            f"Camera Error: {camera.name}",
            (50, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )
        cv2.putText(
            error_frame,
            str(camera.last_error or "Unknown error"),
            (50, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )
        buffer.update(error_frame, 0)

    # Public API

    def get_cameras(self) -> List[Camera]:
        """Get list of all cameras."""
        return list(self._cameras.values())

    def get_camera(self, camera_id: str) -> Optional[Camera]:
        """Get camera by ID."""
        return self._cameras.get(camera_id)

    def get_buffer(self, camera_id: str) -> Optional[FrameBuffer]:
        """Get frame buffer for camera."""
        return self._buffers.get(camera_id)

    def get_frame(self, camera_id: str) -> Optional[Tuple[np.ndarray, float]]:
        """Get current frame and FPS for camera."""
        buffer = self._buffers.get(camera_id)
        if buffer:
            return buffer.get()
        return None, 0.0

    def get_active_count(self) -> int:
        """Get count of active cameras."""
        return sum(
            1 for c in self._cameras.values()
            if c.status == CameraStatus.ACTIVE
        )

    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running


# Global camera manager instance
camera_manager: Optional[CameraManager] = None


def get_camera_manager() -> CameraManager:
    """Get or create the global camera manager."""
    global camera_manager
    if camera_manager is None:
        camera_manager = CameraManager()
    return camera_manager
