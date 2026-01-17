"""Configuration module for Safety Video Analytics Demo."""

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# Detection class IDs from the Construction-Hazard-Detection-YOLO11 model
CLASS_HARDHAT = 0
CLASS_MASK = 1
CLASS_NO_HARDHAT = 2
CLASS_NO_MASK = 3
CLASS_NO_SAFETY_VEST = 4
CLASS_PERSON = 5
CLASS_SAFETY_CONE = 6
CLASS_SAFETY_VEST = 7
CLASS_MACHINERY = 8
CLASS_UTILITY_POLE = 9
CLASS_VEHICLE = 10

CLASS_NAMES = {
    CLASS_HARDHAT: "Hardhat",
    CLASS_MASK: "Mask",
    CLASS_NO_HARDHAT: "NO-Hardhat",
    CLASS_NO_MASK: "NO-Mask",
    CLASS_NO_SAFETY_VEST: "NO-Safety Vest",
    CLASS_PERSON: "Person",
    CLASS_SAFETY_CONE: "Safety Cone",
    CLASS_SAFETY_VEST: "Safety Vest",
    CLASS_MACHINERY: "Machinery",
    CLASS_UTILITY_POLE: "Utility Pole",
    CLASS_VEHICLE: "Vehicle",
}

# Default paths
DEFAULT_WEIGHTS = "data/weights/best_yolo11s.pt"
DEFAULT_VIDEO = "data/videos/construction_workers.mp4"
DEFAULT_CONFIG = "data/config/default.json"

# Server settings
DEFAULT_PORT = 8123
DEFAULT_HOST = "0.0.0.0"

# Model settings
DEFAULT_CONF = 0.25
DEFAULT_IMGSZ = 640

# Hugging Face model info
HF_REPO_ID = "yihong1120/Construction-Hazard-Detection-YOLO11"
HF_WEIGHTS_PATH = "models/pt/best_yolo11s.pt"

# Sample video URLs (multiple sources for reliability)
SAMPLE_VIDEO_URLS = [
    # Sample-Videos.com - Big Buck Bunny (works reliably)
    "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
    # Archive.org - sample video
    "https://ia600300.us.archive.org/17/items/BigBuckBunny_328/BigBuckBunny_512kb.mp4",
]


@dataclass
class Config:
    """Application configuration."""
    mode: str = "ppe"  # "ppe" or "zone"
    source: str = DEFAULT_VIDEO
    weights: str = DEFAULT_WEIGHTS
    conf: float = DEFAULT_CONF
    imgsz: int = DEFAULT_IMGSZ
    port: int = DEFAULT_PORT
    host: str = DEFAULT_HOST
    zone_polygon: List[Tuple[int, int]] = field(default_factory=lambda: [
        (100, 100), (500, 100), (500, 400), (100, 400)
    ])
    save_output: bool = False
    output_path: Optional[str] = None

    @classmethod
    def from_json(cls, path: str) -> "Config":
        """Load configuration from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)

        # Convert zone_polygon from list of lists to list of tuples
        if "zone_polygon" in data:
            data["zone_polygon"] = [tuple(p) for p in data["zone_polygon"]]

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Config":
        """Create configuration from parsed arguments."""
        config = cls()

        # Load from JSON if provided
        if args.config and os.path.exists(args.config):
            config = cls.from_json(args.config)

        # Override with CLI arguments
        if args.mode:
            config.mode = args.mode
        if args.source:
            config.source = args.source
        if args.weights:
            config.weights = args.weights
        if args.conf is not None:
            config.conf = args.conf
        if args.imgsz is not None:
            config.imgsz = args.imgsz
        if args.port is not None:
            config.port = args.port

        return config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Safety Video Analytics Demo - PPE and Zone Violation Detection"
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        default=DEFAULT_CONFIG,
        help=f"Path to JSON config file (default: {DEFAULT_CONFIG})"
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["ppe", "zone"],
        help="Detection mode: 'ppe' for hardhat/vest detection, 'zone' for restricted area"
    )
    parser.add_argument(
        "--source", "-s",
        type=str,
        help="Video source: file path or camera index (0 for webcam)"
    )
    parser.add_argument(
        "--weights", "-w",
        type=str,
        help=f"Path to YOLO weights file (default: {DEFAULT_WEIGHTS})"
    )
    parser.add_argument(
        "--conf",
        type=float,
        help=f"Confidence threshold (default: {DEFAULT_CONF})"
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        help=f"Inference image size (default: {DEFAULT_IMGSZ})"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        help=f"Server port (default: {DEFAULT_PORT})"
    )

    return parser.parse_args()


def get_config() -> Config:
    """Get configuration from CLI args and/or JSON file.

    When running under uvicorn/FastAPI, uses default config.
    When running directly, parses CLI arguments.
    """
    import sys

    # Detect if running under uvicorn (argv[0] contains 'uvicorn')
    if 'uvicorn' in sys.argv[0] or any('uvicorn' in arg for arg in sys.argv):
        # Running under uvicorn - use defaults or JSON config
        config = Config()
        if os.path.exists(DEFAULT_CONFIG):
            try:
                config = Config.from_json(DEFAULT_CONFIG)
            except Exception:
                pass
        return config

    # Running directly - parse CLI args
    args = parse_args()
    return Config.from_args(args)
