"""Chat runtime utilities that integrate with the memory orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from src.schemas import Message, TranscriptRequest

from src.memory_orchestrator import (
    AdaptiveMemoryOrchestrator,
    MemoryInjection,
    MessageEvent,
    MessageRole,
    MemoryOrchestratorClient,
)


@dataclass
class InjectionBuffer:
    """Collects orchestrator injections for synchronous workflows."""

    items: List[MemoryInjection] = field(default_factory=list)

    def listener(self, injection: MemoryInjection) -> None:
        self.items.append(injection)


class ChatRuntimeBridge:
    """Thin wrapper that converts TranscriptRequests into streaming events."""

    def __init__(self, orchestrator: MemoryOrchestratorClient | None = None) -> None:
        self._orchestrator = orchestrator or AdaptiveMemoryOrchestrator()

    async def ingest_transcript(self, request: TranscriptRequest) -> None:
        """Stream a batch TranscriptRequest through the orchestrator."""

        metadata = {"user_id": request.user_id}

        for index, message in enumerate(request.history):
            event = _event_from_message(request.user_id, index, message, metadata)
            await self._orchestrator.stream_message(event)

        await self._orchestrator.flush()

    async def run_with_injections(self, request: TranscriptRequest) -> List[MemoryInjection]:
        """Stream the transcript and return any injections emitted."""

        buffer = InjectionBuffer()
        subscription = self._orchestrator.subscribe_injections(buffer.listener)
        try:
            await self.ingest_transcript(request)
        finally:
            subscription.close()
        return buffer.items

    async def shutdown(self) -> None:
        await self._orchestrator.shutdown()


def _event_from_message(
    conversation_id: str,
    index: int,
    message: Message,
    metadata: dict[str, str],
) -> MessageEvent:
    role = MessageRole(message.role)
    timestamp = getattr(message, "timestamp", None)
    if timestamp is None:
        timestamp = datetime.utcnow()
    return MessageEvent(
        conversation_id=conversation_id,
        message_id=f"{conversation_id}-{index}",
        role=role,
        content=message.content,
        metadata=metadata,
        timestamp=timestamp,
    )

