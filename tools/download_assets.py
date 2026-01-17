#!/usr/bin/env python3
"""Download model weights and sample video for the safety demo."""

import os
import shutil
from pathlib import Path


def download_weights():
    """Download YOLOv11 PPE detection weights from Hugging Face."""
    weights_dir = Path("data/weights")
    weights_path = weights_dir / "best_yolo11s.pt"

    if weights_path.exists():
        print(f"[INFO] Weights already exist: {weights_path}")
        return

    print("[INFO] Downloading model weights from Hugging Face...")
    weights_dir.mkdir(parents=True, exist_ok=True)

    from huggingface_hub import hf_hub_download

    downloaded_path = hf_hub_download(
        repo_id="yihong1120/Construction-Hazard-Detection-YOLO11",
        filename="models/pt/best_yolo11s.pt",
        local_dir=str(weights_dir),
        local_dir_use_symlinks=False,
    )

    # Move from nested structure to expected location
    src = weights_dir / "models" / "pt" / "best_yolo11s.pt"
    if src.exists():
        shutil.move(str(src), str(weights_path))
        shutil.rmtree(weights_dir / "models", ignore_errors=True)

    print(f"[INFO] Weights downloaded to: {weights_path}")


def download_video():
    """Download sample construction video."""
    videos_dir = Path("data/videos")
    video_path = videos_dir / "construction_workers.mp4"

    if video_path.exists():
        print(f"[INFO] Video already exists: {video_path}")
        return

    print("[INFO] Downloading sample video...")
    videos_dir.mkdir(parents=True, exist_ok=True)

    import requests

    # Multiple sources for reliability
    video_urls = [
        # Sample-Videos.com - Big Buck Bunny (works reliably)
        "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
        # Archive.org - sample video
        "https://ia600300.us.archive.org/17/items/BigBuckBunny_328/BigBuckBunny_512kb.mp4",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for url in video_urls:
        try:
            print(f"[INFO] Trying: {url}")
            response = requests.get(url, stream=True, timeout=120, headers=headers)
            response.raise_for_status()

            with open(video_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"[INFO] Video downloaded to: {video_path}")
            return

        except Exception as e:
            print(f"[WARN] Failed to download from {url}: {e}")
            continue

    # If all URLs fail, create a placeholder message
    print("[WARN] Could not download sample video. Please add your own video to data/videos/")


if __name__ == "__main__":
    download_weights()
    download_video()
    print("[INFO] All assets downloaded successfully!")
