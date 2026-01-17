"""Redis pub/sub helpers for frame and event streaming."""

import json
import asyncio
from typing import AsyncGenerator, Callable, Optional
from uuid import UUID

import redis.asyncio as redis

from .client import get_redis


# Channel patterns
FRAME_CHANNEL_PREFIX = "frames:"
EVENT_CHANNEL_PREFIX = "events:"


class FramePublisher:
    """Publishes annotated frames to Redis."""

    def __init__(self, client: redis.Redis):
        self.client = client

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
    ) -> None:
        """Publish frame and update metadata."""
        # Publish frame
        await self.publish_frame(camera_id, frame_data)

        # Update metadata
        metadata = {
            "fps": fps,
            "detection_count": detection_count,
        }
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


async def get_event_publisher() -> EventPublisher:
    """Get an event publisher instance."""
    client = await get_redis()
    return EventPublisher(client)


async def get_event_subscriber() -> EventSubscriber:
    """Get an event subscriber instance."""
    client = await get_redis()
    return EventSubscriber(client)
