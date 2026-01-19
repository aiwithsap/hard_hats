"""Worker service entry point for video processing and YOLO inference.

Version: 2.1.0 - Added per-camera inference toggle support
"""

import asyncio
import signal
import sys
from typing import Optional

from .config import config
from .camera_manager import get_camera_manager, CameraManager


class WorkerService:
    """
    Main worker service that manages camera processing.

    Features:
    - Graceful startup and shutdown
    - Signal handling (SIGTERM, SIGINT)
    - Health monitoring
    - Stats reporting
    """

    def __init__(self):
        self.camera_manager: Optional[CameraManager] = None
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the worker service."""
        print("[WORKER] Starting worker service...")
        print(f"[WORKER] Log level: {config.LOG_LEVEL}")
        print(f"[WORKER] Max concurrent cameras: {config.MAX_CONCURRENT_CAMERAS}")
        print(f"[WORKER] Default FPS: {config.DEFAULT_TARGET_FPS}")

        self._running = True

        # Initialize camera manager
        self.camera_manager = await get_camera_manager()

        # Start camera manager
        await self.camera_manager.start()

        print("[WORKER] Worker service started")

        # Start stats reporting
        stats_task = asyncio.create_task(self._stats_loop())

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Cancel stats task
        stats_task.cancel()
        try:
            await stats_task
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop the worker service."""
        if not self._running:
            return

        print("[WORKER] Stopping worker service...")
        self._running = False

        # Stop camera manager
        if self.camera_manager:
            await self.camera_manager.stop()

        self._shutdown_event.set()
        print("[WORKER] Worker service stopped")

    async def _stats_loop(self) -> None:
        """Periodically log stats."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Log every minute

                if self.camera_manager:
                    stats = self.camera_manager.get_camera_stats()
                    print(
                        f"[WORKER] Stats - "
                        f"total={stats['total']}, "
                        f"streaming={stats['streaming']}, "
                        f"error={stats['error']}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WORKER] Stats error: {e}")

    def handle_signal(self, signum: int) -> None:
        """Handle shutdown signals."""
        print(f"[WORKER] Received signal {signum}, initiating shutdown...")
        asyncio.create_task(self.stop())


async def main() -> None:
    """Main entry point."""
    print("=" * 60)
    print("Hard Hats Detection - Worker Service")
    print("=" * 60)

    # Check environment
    if config.is_production():
        print("[WORKER] Running in production mode")
    else:
        print("[WORKER] Running in development mode")

    # Create worker service
    worker = WorkerService()

    # Set up signal handlers
    loop = asyncio.get_event_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: worker.handle_signal(s)
        )

    try:
        await worker.start()
    except KeyboardInterrupt:
        print("[WORKER] Keyboard interrupt received")
    except Exception as e:
        print(f"[WORKER] Fatal error: {e}")
        raise
    finally:
        await worker.stop()

    print("[WORKER] Shutdown complete")


def run() -> None:
    """Run the worker service."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
