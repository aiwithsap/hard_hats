"""Multi-camera orchestration with database-backed configuration."""

import asyncio
from typing import Dict, Optional, List, Any
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import cv2
import numpy as np

from ..shared.db.database import async_session_factory
from ..shared.db.models import Camera, CameraStatus, SourceType, DetectionMode
from ..shared.db.repositories.cameras import GlobalCameraRepository
from ..shared.redis.pubsub import get_frame_publisher, get_event_publisher
from .config import config
from .rtsp_handler import get_rtsp_handler, RTSPHandler, get_test_pattern_capture
from .vision import get_model, infer, annotate_frame
from .frame_publisher import FrameProcessor
from .event_processor import EventProcessor


class CameraState(Enum):
    """Camera processing state."""
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class CameraContext:
    """Runtime context for a camera."""
    camera_id: UUID
    organization_id: UUID
    name: str
    source_type: SourceType
    rtsp_url: Optional[str]
    credentials_encrypted: Optional[str]
    placeholder_video: Optional[str]
    use_placeholder: bool
    inference_width: int
    inference_height: int
    target_fps: float
    detection_mode: DetectionMode
    zone_polygon: Optional[List[List[int]]]
    confidence_threshold: float
    inference_enabled: bool = True

    # Runtime state
    state: CameraState = CameraState.IDLE
    cap: Optional[cv2.VideoCapture] = None
    error_message: Optional[str] = None
    frames_processed: int = 0
    last_frame_time: float = 0
    last_infer_time: float = 0.0
    last_detections: List[Dict[str, Any]] = field(default_factory=list)
    infer_in_flight: bool = False
    infer_task: Optional[asyncio.Task] = None
    fps_ema: float = 0.0
    infer_fps_ema: float = 0.0
    task: Optional[asyncio.Task] = None


class CameraManager:
    """
    Manages multiple camera streams with database-backed configuration.

    Features:
    - Loads camera configurations from database
    - Manages RTSP connections with retry logic
    - Coordinates frame processing and publishing
    - Handles graceful shutdown
    """

    def __init__(self):
        self.cameras: Dict[UUID, CameraContext] = {}
        self.rtsp_handler: Optional[RTSPHandler] = None
        self.frame_publisher = None
        self.event_publisher = None
        self.frame_processor: Optional[FrameProcessor] = None
        self.event_processor: Optional[EventProcessor] = None
        self.model = None
        self._running = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the camera manager."""
        print("[CAMERA_MANAGER] Initializing...")

        # Load YOLO model
        print("[CAMERA_MANAGER] Loading YOLO model...")
        self.model = get_model()

        # Initialize handlers
        self.rtsp_handler = get_rtsp_handler()
        self.frame_publisher = await get_frame_publisher()
        self.event_publisher = await get_event_publisher()

        # Initialize processors
        self.frame_processor = FrameProcessor(self.frame_publisher)
        self.event_processor = EventProcessor(self.event_publisher)

        print("[CAMERA_MANAGER] Initialization complete")

    async def start(self) -> None:
        """Start the camera manager."""
        if self._running:
            return

        self._running = True
        print("[CAMERA_MANAGER] Starting...")

        # Load cameras from database
        await self.refresh_cameras()

        # Start refresh task
        self._refresh_task = asyncio.create_task(self._refresh_loop())

        print("[CAMERA_MANAGER] Started")

    async def stop(self) -> None:
        """Stop the camera manager."""
        if not self._running:
            return

        self._running = False
        print("[CAMERA_MANAGER] Stopping...")

        # Cancel refresh task
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        # Stop all cameras
        async with self._lock:
            for camera_id in list(self.cameras.keys()):
                await self._stop_camera(camera_id)

        # Close Redis connections
        if self.frame_publisher:
            await self.frame_publisher.close()
        if self.event_publisher:
            await self.event_publisher.close()

        print("[CAMERA_MANAGER] Stopped")

    async def refresh_cameras(self) -> None:
        """Refresh camera list from database."""
        print("[CAMERA_MANAGER] Refreshing cameras from database...")

        async with async_session_factory() as session:
            repo = GlobalCameraRepository(session)
            db_cameras = await repo.get_active_cameras()

        async with self._lock:
            # Get current camera IDs
            current_ids = set(self.cameras.keys())
            new_ids = {c.id for c in db_cameras}

            # Stop removed cameras
            for camera_id in current_ids - new_ids:
                print(f"[CAMERA_MANAGER] Removing camera: {camera_id}")
                await self._stop_camera(camera_id)

            # Add or update cameras
            for db_camera in db_cameras:
                if db_camera.id in current_ids:
                    # Update existing camera if config changed
                    await self._update_camera(db_camera)
                else:
                    # Add new camera
                    print(f"[CAMERA_MANAGER] Adding camera: {db_camera.name}")
                    await self._add_camera(db_camera)

        print(f"[CAMERA_MANAGER] Managing {len(self.cameras)} cameras")

    async def _add_camera(self, db_camera: Camera) -> None:
        """Add a new camera to management."""
        # Get zone polygon (stored as JSON in database, automatically parsed)
        zone_polygon = db_camera.zone_polygon

        # Clamp inference size to max 400x400 for faster CPU processing
        inference_width = min(db_camera.inference_width, 400)
        inference_height = min(db_camera.inference_height, 400)
        # Respect user's FPS setting (0.5 FPS is intentional to save compute)
        target_fps = db_camera.target_fps

        context = CameraContext(
            camera_id=db_camera.id,
            organization_id=db_camera.organization_id,
            name=db_camera.name,
            source_type=db_camera.source_type,
            rtsp_url=db_camera.rtsp_url,
            credentials_encrypted=db_camera.credentials_encrypted,
            placeholder_video=db_camera.placeholder_video,
            use_placeholder=db_camera.use_placeholder,
            inference_width=inference_width,
            inference_height=inference_height,
            target_fps=target_fps,
            detection_mode=db_camera.detection_mode,
            zone_polygon=zone_polygon,
            confidence_threshold=db_camera.confidence_threshold,
            inference_enabled=db_camera.inference_enabled,
        )

        self.cameras[db_camera.id] = context

        # Start processing task
        context.task = asyncio.create_task(
            self._process_camera(context)
        )

    async def _update_camera(self, db_camera: Camera) -> None:
        """Update camera configuration if changed."""
        context = self.cameras.get(db_camera.id)
        if not context:
            return

        # Check if source changed (requires reconnection)
        source_changed = (
            context.rtsp_url != db_camera.rtsp_url or
            context.credentials_encrypted != db_camera.credentials_encrypted or
            context.use_placeholder != db_camera.use_placeholder or
            context.placeholder_video != db_camera.placeholder_video
        )

        if source_changed:
            # Restart camera with new config
            await self._stop_camera(db_camera.id)
            await self._add_camera(db_camera)
        else:
            # Update in-place settings
            context.target_fps = db_camera.target_fps
            context.inference_width = db_camera.inference_width
            context.inference_height = db_camera.inference_height
            context.confidence_threshold = db_camera.confidence_threshold
            context.detection_mode = db_camera.detection_mode
            context.inference_enabled = db_camera.inference_enabled

            if db_camera.zone_polygon is not None:
                context.zone_polygon = db_camera.zone_polygon

    async def _stop_camera(self, camera_id: UUID) -> None:
        """Stop a camera's processing."""
        context = self.cameras.pop(camera_id, None)
        if not context:
            return

        context.state = CameraState.STOPPED

        # Cancel task
        if context.task:
            context.task.cancel()
            try:
                await context.task
            except asyncio.CancelledError:
                pass

        # Cancel inference task
        if context.infer_task:
            context.infer_task.cancel()
            try:
                await context.infer_task
            except asyncio.CancelledError:
                pass

        # Release capture
        if context.cap:
            context.cap.release()
            context.cap = None

        # Update database status
        await self._update_camera_status(
            camera_id, CameraStatus.offline, "Stopped"
        )

    async def _process_camera(self, context: CameraContext) -> None:
        """Main processing loop for a camera."""
        camera_id = context.camera_id

        try:
            # Connect to source
            context.state = CameraState.CONNECTING
            await self._update_camera_status(
                camera_id, CameraStatus.connecting, None
            )

            cap, error = await self._connect_camera(context)

            if error:
                context.state = CameraState.ERROR
                context.error_message = error
                await self._update_camera_status(
                    camera_id, CameraStatus.error, error
                )
                return

            context.cap = cap
            context.state = CameraState.STREAMING
            await self._update_camera_status(
                camera_id, CameraStatus.online, None
            )

            # Initialize inference timing so first inference can calculate EMA
            # Without this, last_infer_time=0 causes first EMA calculation to be skipped
            context.last_infer_time = asyncio.get_event_loop().time()

            def get_stream_fps(capture: cv2.VideoCapture) -> float:
                fps = capture.get(cv2.CAP_PROP_FPS)
                if not fps or fps < 1.0:
                    return 15.0
                return fps

            stream_fps = get_stream_fps(cap)
            stream_interval = 1.0 / stream_fps

            print(
                f"[CAMERA:{context.name}] Started streaming at "
                f"{stream_fps:.1f} FPS (inference {context.target_fps} FPS)"
            )

            while self._running and context.state == CameraState.STREAMING:
                loop_start = asyncio.get_event_loop().time()

                # Read frame
                ret, frame = cap.read()

                if not ret or frame is None:
                    # Try to reconnect
                    print(f"[CAMERA:{context.name}] Frame read failed, reconnecting...")
                    cap.release()

                    cap, error = await self._connect_camera(context)
                    if error:
                        context.state = CameraState.ERROR
                        context.error_message = error
                        await self._update_camera_status(
                            camera_id, CameraStatus.error, error
                        )
                        break

                    context.cap = cap
                    stream_fps = get_stream_fps(cap)
                    stream_interval = 1.0 / stream_fps
                    continue

                # Resize for inference
                if frame.shape[1] != context.inference_width or frame.shape[0] != context.inference_height:
                    frame = cv2.resize(
                        frame,
                        (context.inference_width, context.inference_height)
                    )

                infer_interval = 1.0 / max(context.target_fps, 0.1)
                should_infer = (loop_start - context.last_infer_time) >= infer_interval

                if should_infer and not context.infer_in_flight and context.inference_enabled:
                    context.infer_in_flight = True
                    frame_for_infer = frame.copy()
                    context.infer_task = asyncio.create_task(
                        self._run_inference(context, frame_for_infer)
                    )

                detections = context.last_detections if context.inference_enabled else []
                detection_count = len(detections)

                # Annotate frame
                polygon = context.zone_polygon if context.detection_mode == DetectionMode.zone else None
                annotated = annotate_frame(
                    frame.copy(),
                    detections,
                    mode=context.detection_mode.value,
                    polygon=polygon,
                )

                # Add "AI Disabled" overlay when inference is off
                if not context.inference_enabled:
                    h, w = annotated.shape[:2]
                    text = "AI Disabled"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = min(w, h) / 400.0  # Scale based on frame size
                    thickness = max(1, int(font_scale * 2))
                    (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
                    x = (w - text_w) // 2
                    y = (h + text_h) // 2
                    # Draw shadow for better visibility
                    cv2.putText(annotated, text, (x + 2, y + 2), font, font_scale, (0, 0, 0), thickness + 1)
                    cv2.putText(annotated, text, (x, y), font, font_scale, (128, 128, 128), thickness)

                # Calculate FPS (exponential moving average)
                fps = 0.0
                prev_time = context.last_frame_time
                context.last_frame_time = loop_start
                if prev_time > 0:
                    delta = max(loop_start - prev_time, 1e-6)
                    instant_fps = 1.0 / delta
                    if context.fps_ema <= 0:
                        context.fps_ema = instant_fps
                    else:
                        context.fps_ema = (context.fps_ema * 0.8) + (instant_fps * 0.2)
                    fps = context.fps_ema

                # Publish frame
                await self.frame_processor.publish_frame(
                    camera_id=str(camera_id),
                    frame=annotated,
                    fps=fps,
                    detection_count=detection_count,
                    infer_fps=context.infer_fps_ema if context.inference_enabled else 0.0,
                )

                context.frames_processed += 1

                # Maintain stream FPS
                elapsed = asyncio.get_event_loop().time() - loop_start
                sleep_time = max(0, stream_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            print(f"[CAMERA:{context.name}] Processing cancelled")
        except Exception as e:
            print(f"[CAMERA:{context.name}] Error: {e}")
            context.state = CameraState.ERROR
            context.error_message = str(e)
            await self._update_camera_status(
                camera_id, CameraStatus.error, str(e)
            )
        finally:
            if context.cap:
                context.cap.release()
                context.cap = None

    async def _run_inference(
        self,
        context: CameraContext,
        frame: np.ndarray,
    ) -> None:
        """Run YOLO inference in a background thread and update state."""
        try:
            detections = await asyncio.to_thread(
                infer,
                self.model,
                frame,
                conf=context.confidence_threshold,
                imgsz=context.inference_width,
            )
            context.last_detections = detections

            await self.event_processor.process_detections(
                camera_id=context.camera_id,
                organization_id=context.organization_id,
                detections=detections,
                mode=context.detection_mode.value,
                polygon=context.zone_polygon,
                frame=frame,
            )
        except Exception as e:
            print(f"[CAMERA:{context.name}] Inference error: {e}")
        finally:
            now = asyncio.get_event_loop().time()
            if context.last_infer_time > 0:
                delta = max(now - context.last_infer_time, 1e-6)
                instant_fps = 1.0 / delta
                if context.infer_fps_ema <= 0:
                    context.infer_fps_ema = instant_fps
                else:
                    context.infer_fps_ema = (context.infer_fps_ema * 0.8) + (instant_fps * 0.2)
            context.last_infer_time = now
            context.infer_in_flight = False
            context.infer_task = None

    def _try_default_demo_fallback(
        self, context: CameraContext
    ) -> tuple[Optional[cv2.VideoCapture], Optional[str]]:
        """Try the default demo video URL as a fallback."""
        default_url = config.DEFAULT_DEMO_VIDEO_URL
        if default_url:
            print(f"[CAMERA:{context.name}] Trying default demo video: {default_url}")
            cap, error = self.rtsp_handler.open_file(default_url)
            if not error:
                return cap, None
            print(f"[CAMERA:{context.name}] Default demo video failed: {error}")

        # Final fallback: test pattern
        print(f"[CAMERA:{context.name}] Using test pattern")
        return get_test_pattern_capture(
            width=context.inference_width,
            height=context.inference_height
        ), None

    async def _connect_camera(
        self, context: CameraContext
    ) -> tuple[Optional[cv2.VideoCapture], Optional[str]]:
        """Connect to camera source."""
        # Use placeholder if configured or as fallback
        if context.use_placeholder and context.placeholder_video:
            cap, error = self.rtsp_handler.open_file(context.placeholder_video)
            if error:
                # Fallback to default demo video when placeholder fails
                print(f"[CAMERA:{context.name}] Placeholder failed ({error}), trying default")
                return self._try_default_demo_fallback(context)
            return cap, None

        # Try RTSP
        if context.source_type == SourceType.rtsp and context.rtsp_url:
            cap, error = await self.rtsp_handler.connect(
                context.rtsp_url,
                context.credentials_encrypted,
            )

            if error:
                # Fallback to placeholder if available
                if context.placeholder_video:
                    print(f"[CAMERA:{context.name}] RTSP failed, trying placeholder")
                    cap, placeholder_error = self.rtsp_handler.open_file(context.placeholder_video)
                    if not placeholder_error:
                        return cap, None
                    print(f"[CAMERA:{context.name}] Placeholder also failed")
                else:
                    print(f"[CAMERA:{context.name}] RTSP failed, no placeholder configured")

                # Try default demo video
                return self._try_default_demo_fallback(context)

            return cap, None

        # Try file source
        if context.source_type == SourceType.file and context.placeholder_video:
            cap, error = self.rtsp_handler.open_file(context.placeholder_video)
            if error:
                # Fallback to default demo video
                print(f"[CAMERA:{context.name}] Video source failed ({error})")
                return self._try_default_demo_fallback(context)
            return cap, None

        # No source configured, try default demo video
        print(f"[CAMERA:{context.name}] No source configured")
        return self._try_default_demo_fallback(context)

    async def _update_camera_status(
        self,
        camera_id: UUID,
        status: CameraStatus,
        error_message: Optional[str],
    ) -> None:
        """Update camera status in database."""
        try:
            async with async_session_factory() as session:
                repo = GlobalCameraRepository(session)
                await repo.update_status(camera_id, status, error_message)
        except Exception as e:
            print(f"[CAMERA_MANAGER] Failed to update status: {e}")

    async def _refresh_loop(self) -> None:
        """Periodically refresh camera list."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Refresh every minute
                await self.refresh_cameras()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[CAMERA_MANAGER] Refresh error: {e}")

    def get_camera_stats(self) -> Dict[str, Any]:
        """Get statistics for all cameras."""
        stats = {
            "total": len(self.cameras),
            "streaming": 0,
            "error": 0,
            "connecting": 0,
            "cameras": [],
        }

        for context in self.cameras.values():
            camera_stat = {
                "id": str(context.camera_id),
                "name": context.name,
                "state": context.state.value,
                "frames_processed": context.frames_processed,
            }

            if context.state == CameraState.STREAMING:
                stats["streaming"] += 1
            elif context.state == CameraState.ERROR:
                stats["error"] += 1
                camera_stat["error"] = context.error_message
            elif context.state == CameraState.CONNECTING:
                stats["connecting"] += 1

            stats["cameras"].append(camera_stat)

        return stats


# Global manager instance
_camera_manager: Optional[CameraManager] = None


async def get_camera_manager() -> CameraManager:
    """Get or create the camera manager."""
    global _camera_manager
    if _camera_manager is None:
        _camera_manager = CameraManager()
        await _camera_manager.initialize()
    return _camera_manager
