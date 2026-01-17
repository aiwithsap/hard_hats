"""Worker service configuration."""

import os


class WorkerConfig:
    """Configuration for worker service."""

    # Model settings
    WEIGHTS_PATH: str = os.getenv("WEIGHTS_PATH", "data/weights/best_yolo11s.pt")
    DEFAULT_CONF: float = float(os.getenv("DEFAULT_CONF", "0.25"))
    DEFAULT_IMGSZ: int = int(os.getenv("DEFAULT_IMGSZ", "640"))

    # RTSP settings
    RTSP_MAX_RETRIES: int = int(os.getenv("RTSP_MAX_RETRIES", "5"))
    RTSP_BASE_DELAY: float = float(os.getenv("RTSP_BASE_DELAY", "1.0"))
    RTSP_MAX_DELAY: float = float(os.getenv("RTSP_MAX_DELAY", "60.0"))
    RTSP_HEALTH_CHECK_INTERVAL: float = float(os.getenv("RTSP_HEALTH_CHECK_INTERVAL", "30.0"))

    # Processing settings
    DEFAULT_TARGET_FPS: float = float(os.getenv("DEFAULT_TARGET_FPS", "0.5"))
    MAX_CONCURRENT_CAMERAS: int = int(os.getenv("MAX_CONCURRENT_CAMERAS", "20"))

    # Deduplication
    COOLDOWN_SECONDS: int = int(os.getenv("COOLDOWN_SECONDS", "30"))

    # Thumbnail settings
    THUMBNAIL_DIR: str = os.getenv("THUMBNAIL_DIR", "data/thumbnails")
    THUMBNAIL_QUALITY: int = int(os.getenv("THUMBNAIL_QUALITY", "85"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production."""
        return os.getenv("RAILWAY_ENVIRONMENT") is not None


config = WorkerConfig()
