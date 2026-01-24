"""Worker service configuration."""

import os


class WorkerConfig:
    """Configuration for worker service."""

    # Model settings
    WEIGHTS_PATH: str = os.getenv("WEIGHTS_PATH", "data/weights/best_yolo11s.pt")
    DEFAULT_CONF: float = float(os.getenv("DEFAULT_CONF", "0.25"))
    # Smaller inference size = 4x faster inference (320x320 vs 640x640)
    DEFAULT_IMGSZ: int = int(os.getenv("DEFAULT_IMGSZ", "320"))

    # RTSP settings
    RTSP_MAX_RETRIES: int = int(os.getenv("RTSP_MAX_RETRIES", "5"))
    RTSP_BASE_DELAY: float = float(os.getenv("RTSP_BASE_DELAY", "1.0"))
    RTSP_MAX_DELAY: float = float(os.getenv("RTSP_MAX_DELAY", "60.0"))
    RTSP_HEALTH_CHECK_INTERVAL: float = float(os.getenv("RTSP_HEALTH_CHECK_INTERVAL", "30.0"))

    # Processing settings
    DEFAULT_TARGET_FPS: float = float(os.getenv("DEFAULT_TARGET_FPS", "0.5"))
    MAX_CONCURRENT_CAMERAS: int = int(os.getenv("MAX_CONCURRENT_CAMERAS", "20"))
    STREAM_FPS_MAX: float = float(os.getenv("STREAM_FPS_MAX", "15"))

    # Stream size limits (resize only if frame exceeds these dimensions)
    # Set to 0 to use inference dimensions as stream size
    STREAM_MAX_WIDTH: int = int(os.getenv("STREAM_MAX_WIDTH", "640"))
    STREAM_MAX_HEIGHT: int = int(os.getenv("STREAM_MAX_HEIGHT", "480"))

    # Deduplication
    COOLDOWN_SECONDS: int = int(os.getenv("COOLDOWN_SECONDS", "30"))

    # Thumbnail settings
    THUMBNAIL_DIR: str = os.getenv("THUMBNAIL_DIR", "data/thumbnails")
    THUMBNAIL_QUALITY: int = int(os.getenv("THUMBNAIL_QUALITY", "70"))

    # Stream JPEG quality (lower than thumbnail for faster encoding)
    STREAM_JPEG_QUALITY: int = int(os.getenv("STREAM_JPEG_QUALITY", "65"))

    # Demo video fallback (Big Buck Bunny - public domain from archive.org)
    DEFAULT_DEMO_VIDEO_URL: str = os.getenv(
        "DEFAULT_DEMO_VIDEO_URL",
        "https://archive.org/download/BigBuckBunny_328/BigBuckBunny_512kb.mp4"
    )

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production."""
        return os.getenv("RAILWAY_ENVIRONMENT") is not None


config = WorkerConfig()
