"""Main application - FastAPI server with multi-camera video analytics."""

import os
import sys
import threading
import webbrowser
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from .config import get_config, DEFAULT_WEIGHTS, DEFAULT_VIDEO
from .api.router import router as api_router
from .core.camera_manager import get_camera_manager
from .core.event_processor import get_event_processor


# Ensure directories exist
def ensure_directories():
    """Ensure all required directories exist."""
    dirs = [
        "data/weights",
        "data/videos",
        "data/config",
        "data/output",
        "data/db",
        "data/thumbnails",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def download_weights():
    """Download model weights from Hugging Face if not present."""
    weights_path = Path(DEFAULT_WEIGHTS)

    if weights_path.exists():
        print(f"[INFO] Weights already exist: {weights_path}")
        return str(weights_path)

    print("[INFO] Downloading weights from Hugging Face...")
    ensure_directories()

    try:
        from huggingface_hub import hf_hub_download
        import shutil

        downloaded_path = hf_hub_download(
            repo_id="yihong1120/Construction-Hazard-Detection-YOLO11",
            filename="models/pt/best_yolo11s.pt",
            local_dir=str(weights_path.parent),
            local_dir_use_symlinks=False,
        )

        # Move to expected location if needed
        actual_path = weights_path.parent / "models" / "pt" / "best_yolo11s.pt"
        if actual_path.exists():
            shutil.move(str(actual_path), str(weights_path))
            shutil.rmtree(weights_path.parent / "models", ignore_errors=True)

        print(f"[INFO] Weights downloaded to: {weights_path}")
        return str(weights_path)

    except Exception as e:
        print(f"[ERROR] Failed to download weights: {e}")
        raise


def download_sample_video():
    """Download sample video if not present."""
    video_path = Path(DEFAULT_VIDEO)

    if video_path.exists():
        print(f"[INFO] Sample video already exists: {video_path}")
        return str(video_path)

    print("[INFO] Downloading sample video...")
    ensure_directories()

    import requests

    video_urls = [
        "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
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

            print(f"[INFO] Sample video downloaded to: {video_path}")
            return str(video_path)

        except Exception as e:
            print(f"[WARN] Failed to download from {url}: {e}")
            continue

    print("[WARN] Could not download sample video automatically.")
    return None


def ensure_assets():
    """Ensure all required assets are present."""
    download_weights()
    download_sample_video()


def is_docker():
    """Check if running inside Docker container."""
    return os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER", False)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    print("=" * 60)
    print("  Safety Video Analytics Dashboard")
    print("  Multi-Camera Professional Demo")
    print("=" * 60)

    # Get configuration
    config = get_config()
    print(f"\n[CONFIG] Mode: {config.mode}")
    print(f"[CONFIG] Port: {config.port}")
    print(f"[CONFIG] Confidence: {config.conf}")

    # Ensure assets
    print("\n[SETUP] Checking assets...")
    ensure_assets()

    # Initialize camera manager
    print("\n[SETUP] Starting camera manager...")
    manager = get_camera_manager()
    manager.start()

    # Auto-open browser
    url = f"http://localhost:{config.port}"
    if not is_docker():
        print(f"\n[INFO] Opening browser: {url}")
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    else:
        print(f"\n[INFO] Running in Docker - open manually: {url}")

    print(f"\n[SERVER] Starting on port {config.port}...")
    print("=" * 60)

    yield  # Application runs here

    # Shutdown
    print("\n[SHUTDOWN] Stopping camera manager...")
    manager.stop()
    print("[SHUTDOWN] Complete")


# Create FastAPI app
app = FastAPI(
    title="Safety Video Analytics",
    description="Multi-camera PPE detection and zone monitoring dashboard",
    version="2.0.0",
    lifespan=lifespan,
)

# Mount static files
static_path = Path(__file__).parent.parent / "frontend" / "dist"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Mount thumbnails
thumbnails_path = Path("data/thumbnails")
thumbnails_path.mkdir(parents=True, exist_ok=True)
app.mount("/thumbnails", StaticFiles(directory=str(thumbnails_path)), name="thumbnails")

# Include API router
app.include_router(api_router)


# Dashboard HTML (temporary until React frontend is built)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Safety Video Analytics - Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        dark: {
                            900: '#0f0f1a',
                            800: '#1a1a2e',
                            700: '#252542',
                            600: '#2f2f4a',
                        },
                        accent: '#00d4aa',
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0f0f1a; }
        .sidebar { background-color: #1a1a2e; }
        .card { background-color: #1a1a2e; border: 1px solid #2f2f4a; }
        .camera-feed { border: 2px solid #2f2f4a; border-radius: 8px; overflow: hidden; }
        .zone-tag { font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
        .zone-warehouse { background-color: rgba(255, 165, 0, 0.2); color: #ffa500; }
        .zone-production { background-color: rgba(0, 255, 0, 0.2); color: #00ff00; }
        .zone-common { background-color: rgba(0, 255, 255, 0.2); color: #00ffff; }
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #ff4444;
            color: white;
            padding: 16px 24px;
            border-radius: 8px;
            animation: slideIn 0.3s ease;
            z-index: 1000;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .event-item {
            border-left: 3px solid #ff4444;
            padding-left: 12px;
            margin-bottom: 12px;
        }
        .event-item.warning { border-color: #ffaa00; }
    </style>
</head>
<body class="text-white min-h-screen">
    <div class="flex">
        <!-- Sidebar -->
        <nav class="sidebar w-64 min-h-screen p-4 fixed left-0 top-0">
            <div class="flex items-center gap-3 mb-8">
                <div class="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-dark-900" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"/>
                    </svg>
                </div>
                <span class="text-xl font-semibold">SafetyVision</span>
            </div>

            <div class="space-y-2">
                <a href="/" class="flex items-center gap-3 p-3 bg-dark-700 rounded-lg text-accent">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 6a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zm11-1a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z"/>
                    </svg>
                    Dashboard
                </a>
                <a href="/live" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/>
                    </svg>
                    Live View
                </a>
                <a href="#events" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"/>
                    </svg>
                    Events
                </a>
                <a href="/docs" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"/>
                    </svg>
                    API Docs
                </a>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="ml-64 flex-1 p-6">
            <!-- Header -->
            <div class="flex justify-between items-center mb-6">
                <h1 class="text-3xl font-bold">Dashboard</h1>
                <div class="flex items-center gap-4">
                    <span id="datetime" class="text-gray-400"></span>
                    <button onclick="location.reload()" class="bg-dark-700 px-4 py-2 rounded-lg hover:bg-dark-600 transition">
                        Refresh
                    </button>
                </div>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="card p-6 rounded-xl">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-gray-400 text-sm mb-1">Violations Today</p>
                            <p id="violations-count" class="text-4xl font-bold">0</p>
                            <p id="violations-change" class="text-sm text-red-400 mt-1"></p>
                        </div>
                        <div class="w-12 h-12 bg-red-500/20 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92z"/>
                            </svg>
                        </div>
                    </div>
                </div>

                <div class="card p-6 rounded-xl">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-gray-400 text-sm mb-1">Active Cameras</p>
                            <p class="text-4xl font-bold">
                                <span id="active-cameras">0</span>
                                <span class="text-gray-500 text-2xl">/ <span id="total-cameras">0</span></span>
                            </p>
                            <p class="text-sm text-green-400 mt-1">All systems online</p>
                        </div>
                        <div class="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm12.553 1.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z"/>
                            </svg>
                        </div>
                    </div>
                </div>

                <div class="card p-6 rounded-xl">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-gray-400 text-sm mb-1">AI Processing</p>
                            <p id="ai-scanned" class="text-4xl font-bold">0</p>
                            <p class="text-sm text-accent mt-1">Frames analyzed</p>
                        </div>
                        <div class="w-12 h-12 bg-accent/20 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-accent" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M13 7H7v6h6V7z"/>
                                <path fill-rule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2z"/>
                            </svg>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Camera Grid -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div class="card rounded-xl overflow-hidden">
                    <div class="p-4 border-b border-dark-600">
                        <h2 class="text-xl font-semibold">Live Cameras</h2>
                    </div>
                    <div id="camera-grid" class="grid grid-cols-2 gap-4 p-4">
                        <!-- Camera tiles will be inserted here -->
                    </div>
                </div>

                <!-- Recent Activity -->
                <div class="card rounded-xl">
                    <div class="p-4 border-b border-dark-600 flex justify-between items-center">
                        <h2 class="text-xl font-semibold">Recent Activity</h2>
                        <button class="text-accent text-sm hover:underline">Mark all read</button>
                    </div>
                    <div id="activity-feed" class="p-4 max-h-96 overflow-y-auto">
                        <p class="text-gray-500 text-center py-8">No recent events</p>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Toast container -->
    <div id="toast-container"></div>

    <script>
        // Update datetime
        function updateDateTime() {
            const now = new Date();
            document.getElementById('datetime').textContent = now.toLocaleString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        }
        setInterval(updateDateTime, 1000);
        updateDateTime();

        // Fetch and display stats
        async function fetchStats() {
            try {
                const response = await fetch('/api/stats/summary');
                const data = await response.json();

                document.getElementById('violations-count').textContent = data.violations_today;
                document.getElementById('active-cameras').textContent = data.active_cameras;
                document.getElementById('total-cameras').textContent = data.total_cameras;
                document.getElementById('ai-scanned').textContent = data.ai_scanned.toLocaleString();

                const change = data.violations_change_percent;
                const changeEl = document.getElementById('violations-change');
                if (change > 0) {
                    changeEl.textContent = `+${change}% from yesterday`;
                    changeEl.className = 'text-sm text-red-400 mt-1';
                } else if (change < 0) {
                    changeEl.textContent = `${change}% from yesterday`;
                    changeEl.className = 'text-sm text-green-400 mt-1';
                } else {
                    changeEl.textContent = 'Same as yesterday';
                    changeEl.className = 'text-sm text-gray-400 mt-1';
                }
            } catch (e) {
                console.error('Failed to fetch stats:', e);
            }
        }

        // Fetch and display cameras
        async function fetchCameras() {
            try {
                const response = await fetch('/api/cameras');
                const data = await response.json();

                const grid = document.getElementById('camera-grid');
                grid.innerHTML = data.cameras.map(cam => `
                    <div class="camera-feed relative">
                        <img src="/api/stream/${cam.id}" alt="${cam.name}" class="w-full aspect-video object-cover">
                        <div class="absolute top-2 left-2 flex items-center gap-2">
                            <span class="zone-tag zone-${cam.zone.toLowerCase()}">${cam.zone}</span>
                        </div>
                        <div class="absolute bottom-2 left-2 right-2 flex justify-between items-center">
                            <span class="text-sm font-medium">${cam.name}</span>
                            <span class="text-xs text-gray-400">${cam.fps.toFixed(1)} FPS</span>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to fetch cameras:', e);
            }
        }

        // Fetch live events
        async function fetchEvents() {
            try {
                const response = await fetch('/api/events/live?limit=10');
                const data = await response.json();

                const feed = document.getElementById('activity-feed');
                if (data.events.length === 0) {
                    feed.innerHTML = '<p class="text-gray-500 text-center py-8">No recent events</p>';
                } else {
                    feed.innerHTML = data.events.map(event => `
                        <div class="event-item ${event.severity}">
                            <div class="flex items-start gap-3">
                                <div class="w-8 h-8 bg-red-500/20 rounded flex items-center justify-center flex-shrink-0">
                                    <svg class="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92z"/>
                                    </svg>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <p class="text-sm font-medium">${event.message}</p>
                                    <p class="text-xs text-gray-500">${new Date(event.timestamp).toLocaleTimeString()}</p>
                                </div>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error('Failed to fetch events:', e);
            }
        }

        // Show toast notification
        function showToast(message, type = 'error') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.innerHTML = `
                <div class="flex items-center gap-3">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92z"/>
                    </svg>
                    <span>${message}</span>
                </div>
            `;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        }

        // SSE for real-time events
        const eventSource = new EventSource('/api/sse/events');

        eventSource.addEventListener('violation', (e) => {
            const data = JSON.parse(e.data);
            showToast(data.message);
            fetchEvents();
            fetchStats();
        });

        eventSource.addEventListener('connected', () => {
            console.log('SSE connected');
        });

        // Initial fetch
        fetchStats();
        fetchCameras();
        fetchEvents();

        // Refresh stats periodically
        setInterval(fetchStats, 10000);
        setInterval(fetchEvents, 5000);
    </script>
</body>
</html>
"""

# Live view page
LIVE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Safety Video Analytics - Live View</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        dark: { 900: '#0f0f1a', 800: '#1a1a2e', 700: '#252542', 600: '#2f2f4a' },
                        accent: '#00d4aa',
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0f0f1a; }
        .sidebar { background-color: #1a1a2e; }
        .camera-feed { border: 2px solid #2f2f4a; border-radius: 8px; overflow: hidden; position: relative; }
        .camera-feed:hover { border-color: #00d4aa; }
        .zone-tag { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; }
        .zone-warehouse { background-color: rgba(255, 165, 0, 0.3); color: #ffa500; }
        .zone-production { background-color: rgba(0, 255, 0, 0.3); color: #00ff00; }
        .zone-common { background-color: rgba(0, 255, 255, 0.3); color: #00ffff; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #00ff00; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body class="text-white min-h-screen">
    <div class="flex">
        <!-- Sidebar -->
        <nav class="sidebar w-64 min-h-screen p-4 fixed left-0 top-0">
            <div class="flex items-center gap-3 mb-8">
                <div class="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-dark-900" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"/>
                    </svg>
                </div>
                <span class="text-xl font-semibold">SafetyVision</span>
            </div>

            <div class="space-y-2">
                <a href="/" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 6a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zm11-1a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z"/>
                    </svg>
                    Dashboard
                </a>
                <a href="/live" class="flex items-center gap-3 p-3 bg-dark-700 rounded-lg text-accent">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/>
                    </svg>
                    Live View
                </a>
                <a href="/docs" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"/>
                    </svg>
                    API Docs
                </a>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="ml-64 flex-1 p-6">
            <div class="flex justify-between items-center mb-6">
                <div>
                    <h1 class="text-3xl font-bold">Live View</h1>
                    <p class="text-gray-400 mt-1">Real-time camera feeds with AI detection</p>
                </div>
                <div class="flex items-center gap-4">
                    <select id="layout-select" class="bg-dark-700 border border-dark-600 rounded-lg px-4 py-2">
                        <option value="2x2">2x2 Grid</option>
                        <option value="3x2">3x2 Grid</option>
                        <option value="1x1">Single View</option>
                    </select>
                    <span id="datetime" class="text-gray-400"></span>
                </div>
            </div>

            <div id="camera-grid" class="grid grid-cols-2 gap-6">
                <!-- Camera feeds will be inserted here -->
            </div>
        </main>
    </div>

    <script>
        function updateDateTime() {
            const now = new Date();
            document.getElementById('datetime').textContent = now.toLocaleString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        }
        setInterval(updateDateTime, 1000);
        updateDateTime();

        async function fetchCameras() {
            try {
                const response = await fetch('/api/cameras');
                const data = await response.json();

                const grid = document.getElementById('camera-grid');
                grid.innerHTML = data.cameras.map(cam => `
                    <div class="camera-feed">
                        <img src="/api/stream/${cam.id}" alt="${cam.name}" class="w-full aspect-video object-cover">
                        <div class="absolute top-3 left-3 flex items-center gap-2">
                            <div class="status-dot"></div>
                            <span class="zone-tag zone-${cam.zone.toLowerCase()}">${cam.zone}</span>
                        </div>
                        <div class="absolute top-3 right-3 bg-black/50 px-2 py-1 rounded text-xs">
                            ${cam.fps.toFixed(1)} FPS
                        </div>
                        <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
                            <h3 class="font-semibold">${cam.name}</h3>
                            <p class="text-sm text-gray-400">Camera ${cam.id}</p>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to fetch cameras:', e);
            }
        }

        document.getElementById('layout-select').addEventListener('change', (e) => {
            const grid = document.getElementById('camera-grid');
            switch (e.target.value) {
                case '1x1': grid.className = 'grid grid-cols-1 gap-6'; break;
                case '2x2': grid.className = 'grid grid-cols-2 gap-6'; break;
                case '3x2': grid.className = 'grid grid-cols-3 gap-6'; break;
            }
        });

        fetchCameras();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard page."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/live", response_class=HTMLResponse)
async def live_view():
    """Serve the live view page."""
    return HTMLResponse(content=LIVE_HTML)


def main():
    """Main entry point."""
    config = get_config()
    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
