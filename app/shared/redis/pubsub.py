"""Redis pub/sub helpers for frame and event streaming."""

import json
import asyncio
import time
from typing import AsyncGenerator, Callable, Optional, Dict
from uuid import UUID

import redis.asyncio as redis

from .client import get_redis


# Channel patterns
FRAME_CHANNEL_PREFIX = "frames:"
EVENT_CHANNEL_PREFIX = "events:"

# Subscriber count cache (shared across instances)
_subscriber_cache: Dict[str, tuple[int, float]] = {}
_SUBSCRIBER_CACHE_TTL = 1.0  # seconds


def _decode_metadata(raw: Optional[dict]) -> dict:
    """Decode Redis hash values into a string-keyed dict."""
    if not raw:
        return {}
    decoded = {}
    for key, value in raw.items():
        if isinstance(key, bytes):
            key = key.decode("utf-8", "ignore")
        if isinstance(value, bytes):
            value = value.decode("utf-8", "ignore")
        decoded[key] = value
    return decoded


class FramePublisher:
    """Publishes annotated frames to Redis."""

    def __init__(self, client: redis.Redis):
        self.client = client
        self._last_latest_frame_update: Dict[str, float] = {}
        self._latest_frame_update_interval = 2.0  # Update latest_frame every 2 seconds when no subscribers

    async def get_subscriber_count(self, camera_id: str) -> int:
        """
        Get the number of subscribers to a camera's frame channel.

        Uses cached result for 1 second to avoid hammering Redis.
        """
        global _subscriber_cache
        channel = f"{FRAME_CHANNEL_PREFIX}{camera_id}"
        now = time.time()

        # Check cache
        if channel in _subscriber_cache:
            count, cached_at = _subscriber_cache[channel]
            if now - cached_at < _SUBSCRIBER_CACHE_TTL:
                return count

        # Query Redis
        try:
            result = await self.client.pubsub_numsub(channel)
            # result is a list of (channel, count) tuples
            count = result[0][1] if result else 0
            _subscriber_cache[channel] = (count, now)
            return count
        except Exception:
            return 0  # Assume no subscribers on error

    async def publish_frame(
        self,
        camera_id: str,
        frame_data: bytes,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Publish a frame to Redis.

        Args:
            camera_id: Camera identifier
            frame_data: JPEG-encoded frame bytes
            metadata: Optional metadata (fps, detection count, etc.)

        Returns:
            Number of subscribers that received the message
        """
        channel = f"{FRAME_CHANNEL_PREFIX}{camera_id}"

        # Store latest frame for new subscribers
        await self.client.set(
            f"latest_frame:{camera_id}",
            frame_data,
            ex=10,  # Expire after 10 seconds
        )

        # Publish to channel
        return await self.client.publish(channel, frame_data)

    async def publish_frame_with_metadata(
        self,
        camera_id: str,
        frame_data: bytes,
        fps: float,
        detection_count: int,
        infer_fps: Optional[float] = None,
    ) -> None:
        """Publish frame and update metadata."""
        # Publish frame
        await self.publish_frame(camera_id, frame_data)

        # Update metadata
        metadata = {
            "fps": fps,
            "detection_count": detection_count,
        }
        if infer_fps is not None:
            metadata["infer_fps"] = infer_fps
        await self.client.hset(
            f"camera_meta:{camera_id}",
            mapping=metadata,
        )
        await self.client.expire(f"camera_meta:{camera_id}", 30)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self.client:
            await self.client.close()


class FrameSubscriber:
    """Subscribes to frame updates from Redis."""

    def __init__(self, client: redis.Redis):
        self.client = client
        self._pubsub: Optional[redis.client.PubSub] = None

    async def get_latest_frame(self, camera_id: str) -> Optional[bytes]:
        """Get the latest frame for a camera."""
        return await self.client.get(f"latest_frame:{camera_id}")

    async def get_metadata(self, camera_id: str) -> dict:
        """Get latest metadata (fps, infer_fps, detection_count) for a camera."""
        raw = await self.client.hgetall(f"camera_meta:{camera_id}")
        return _decode_metadata(raw)

    async def subscribe(self, camera_id: str) -> AsyncGenerator[bytes, None]:
        """
        Subscribe to frame updates for a camera.

        Yields:
            JPEG-encoded frame bytes
        """
        channel = f"{FRAME_CHANNEL_PREFIX}{camera_id}"
        self._pubsub = self.client.pubsub()

        try:
            await self._pubsub.subscribe(channel)

            # First, yield the latest frame if available
            latest = await self.get_latest_frame(camera_id)
            if latest:
                yield latest

            # Then yield frames as they come
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    yield message["data"]

        finally:
            if self._pubsub:
                await self._pubsub.unsubscribe(channel)
                await self._pubsub.close()

    async def unsubscribe(self) -> None:
        """Unsubscribe from frame updates."""
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None


class SharedFrameBroadcaster:
    """
    Shared broadcaster for frame streaming.

    Maintains a single Redis subscription per camera and fans out
    frames to multiple clients using asyncio queues. This reduces
    Redis connections when multiple viewers watch the same camera.
    """

    def __init__(self, client: redis.Redis):
        self.client = client
        # camera_id -> (pubsub, set of client queues, listener task)
        self._subscriptions: Dict[str, tuple] = {}
        self._lock = asyncio.Lock()

    async def get_latest_frame(self, camera_id: str) -> Optional[bytes]:
        """Get the latest frame for a camera."""
        return await self.client.get(f"latest_frame:{camera_id}")

    async def subscribe(self, camera_id: str) -> AsyncGenerator[bytes, None]:
        """
        Subscribe to frame updates for a camera.

        Uses a shared subscription when multiple clients watch the same camera.

        Yields:
            JPEG-encoded frame bytes
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=5)  # Buffer up to 5 frames

        async with self._lock:
            if camera_id not in self._subscriptions:
                # Create new subscription for this camera
                pubsub = self.client.pubsub()
                clients: set = set()
                channel = f"{FRAME_CHANNEL_PREFIX}{camera_id}"
                await pubsub.subscribe(channel)

                # Start listener task
                task = asyncio.create_task(
                    self._listener_loop(camera_id, pubsub, clients)
                )
                self._subscriptions[camera_id] = (pubsub, clients, task)

            _, clients, _ = self._subscriptions[camera_id]
            clients.add(queue)

        try:
            # First, yield the latest frame if available
            latest = await self.get_latest_frame(camera_id)
            if latest:
                yield latest

            # Then yield frames from the shared queue
            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield frame
                except asyncio.TimeoutError:
                    # Check if we're still supposed to be running
                    continue

        except asyncio.CancelledError:
            pass
        finally:
            # Unregister client
            async with self._lock:
                if camera_id in self._subscriptions:
                    _, clients, _ = self._subscriptions[camera_id]
                    clients.discard(queue)

                    # If no more clients, clean up subscription
                    if not clients:
                        await self._cleanup_subscription(camera_id)

    async def _listener_loop(
        self,
        camera_id: str,
        pubsub: redis.client.PubSub,
        clients: set,
    ) -> None:
        """Listen for frames and broadcast to all registered clients."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    frame_data = message["data"]

                    # Broadcast to all clients
                    dead_clients = []
                    for queue in list(clients):
                        try:
                            # Non-blocking put, drop frame if queue is full
                            queue.put_nowait(frame_data)
                        except asyncio.QueueFull:
                            pass  # Client is too slow, skip this frame
                        except Exception:
                            dead_clients.append(queue)

                    # Remove dead clients
                    for queue in dead_clients:
                        clients.discard(queue)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[BROADCASTER] Listener error for {camera_id}: {e}")

    async def _cleanup_subscription(self, camera_id: str) -> None:
        """Clean up a camera subscription."""
        if camera_id not in self._subscriptions:
            return

        pubsub, clients, task = self._subscriptions.pop(camera_id)

        # Cancel listener task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Close pubsub
        try:
            channel = f"{FRAME_CHANNEL_PREFIX}{camera_id}"
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass

    async def close(self) -> None:
        """Close all subscriptions."""
        async with self._lock:
            for camera_id in list(self._subscriptions.keys()):
                await self._cleanup_subscription(camera_id)


class EventPublisher:
    """Publishes events to Redis for SSE broadcast."""

    def __init__(self, client: redis.Redis):
        self.client = client

    async def publish_event(
        self,
        organization_id: str,
        event_data: dict,
    ) -> int:
        """
        Publish an event to Redis.

        Args:
            organization_id: Organization identifier (for tenant isolation)
            event_data: Event data dictionary

        Returns:
            Number of subscribers that received the message
        """
        channel = f"{EVENT_CHANNEL_PREFIX}{organization_id}"
        message = json.dumps(event_data)
        return await self.client.publish(channel, message.encode())

    async def publish_violation(
        self,
        organization_id: str,
        event_id: str,
        camera_id: str,
        camera_name: str,
        violation_type: str,
        severity: str,
        confidence: float,
        message: str,
    ) -> int:
        """Publish a violation event."""
        event_data = {
            "type": "violation",
            "data": {
                "id": event_id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "violation_type": violation_type,
                "severity": severity,
                "confidence": confidence,
                "message": message,
            },
        }
        return await self.publish_event(organization_id, event_data)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self.client:
            await self.client.close()


class EventSubscriber:
    """Subscribes to event updates from Redis for SSE."""

    def __init__(self, client: redis.Redis):
        self.client = client
        self._pubsub: Optional[redis.client.PubSub] = None

    async def subscribe(self, organization_id: str) -> AsyncGenerator[dict, None]:
        """
        Subscribe to events for an organization.

        Yields:
            Event data dictionaries
        """
        channel = f"{EVENT_CHANNEL_PREFIX}{organization_id}"
        self._pubsub = self.client.pubsub()

        try:
            await self._pubsub.subscribe(channel)

            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except json.JSONDecodeError:
                        continue

        finally:
            if self._pubsub:
                await self._pubsub.unsubscribe(channel)
                await self._pubsub.close()

    async def unsubscribe(self) -> None:
        """Unsubscribe from events."""
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None


async def get_frame_publisher() -> FramePublisher:
    """Get a frame publisher instance."""
    client = await get_redis()
    return FramePublisher(client)


async def get_frame_subscriber() -> FrameSubscriber:
    """Get a frame subscriber instance."""
    client = await get_redis()
    return FrameSubscriber(client)


# Global shared broadcaster instance (singleton for web service)
_shared_broadcaster: Optional[SharedFrameBroadcaster] = None


async def get_shared_frame_broadcaster() -> SharedFrameBroadcaster:
    """
    Get the shared frame broadcaster instance.

    Uses a single Redis connection shared across all stream clients.
    This is more efficient when multiple clients watch the same camera.
    """
    global _shared_broadcaster
    if _shared_broadcaster is None:
        client = await get_redis()
        _shared_broadcaster = SharedFrameBroadcaster(client)
    return _shared_broadcaster


async def get_event_publisher() -> EventPublisher:
    """Get an event publisher instance."""
    client = await get_redis()
    return EventPublisher(client)


async def get_event_subscriber() -> EventSubscriber:
    """Get an event subscriber instance."""
    client = await get_redis()
    return EventSubscriber(client)
