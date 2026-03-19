"""
Async event bus for simulation module communication.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

from core.logging_setup import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    # World events
    WORLD_TICK = "world.tick"
    RESOURCE_SPAWNED = "world.resource.spawned"
    RESOURCE_DEPLETED = "world.resource.depleted"
    DISASTER_STARTED = "world.disaster.started"
    DISASTER_ENDED = "world.disaster.ended"
    WEATHER_CHANGED = "world.weather.changed"
    SEASON_CHANGED = "world.season.changed"

    # Agent events
    AGENT_SPAWNED = "agent.spawned"
    AGENT_DIED = "agent.died"
    AGENT_MOVED = "agent.moved"
    AGENT_ACTION = "agent.action"
    AGENT_STATE_CHANGED = "agent.state.changed"

    # Economy events
    TRADE_EXECUTED = "economy.trade.executed"
    PRICE_CHANGED = "economy.price.changed"
    MARKET_CRASH = "economy.market.crash"
    DEBT_DEFAULT = "economy.debt.default"

    # Social events
    ALLIANCE_FORMED = "social.alliance.formed"
    ALLIANCE_BROKEN = "social.alliance.broken"
    BETRAYAL = "social.betrayal"
    GOSSIP_SPREAD = "social.gossip.spread"
    NORM_VIOLATED = "social.norm.violated"

    # Conflict events
    CONFLICT_STARTED = "conflict.started"
    CONFLICT_ENDED = "conflict.ended"
    REBELLION_STARTED = "conflict.rebellion.started"
    PEACE_NEGOTIATED = "conflict.peace.negotiated"

    # Governance events
    LAW_ENACTED = "governance.law.enacted"
    LAW_VIOLATED = "governance.law.violated"
    CORRUPTION_DETECTED = "governance.corruption.detected"
    ELECTION_HELD = "governance.election.held"

    # Information events
    NEWS_PUBLISHED = "info.news.published"
    RUMOR_SPREAD = "info.rumor.spread"
    MISINFORMATION = "info.misinformation"

    # Scenario events
    SCENARIO_INJECTED = "scenario.injected"

    # Analytics events
    PATTERN_DETECTED = "analytics.pattern.detected"
    METRIC_UPDATED = "analytics.metric.updated"


@dataclass
class Event:
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    tick: int = 0
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "source": self.source,
            "tick": self.tick,
        }


Handler = Callable[[Event], Coroutine]


class EventBus:
    """Central async event bus for simulation modules."""

    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[Handler]] = defaultdict(list)
        self._global_handlers: List[Handler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=10000)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: Handler) -> None:
        self._global_handlers.append(handler)

    async def publish(self, event: Event) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("event_bus_queue_full", event_type=event.type)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("event_bus_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("event_bus_stopped")

    async def _process_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                await self._dispatch(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("event_bus_error", error=str(e))

    async def _dispatch(self, event: Event) -> None:
        handlers = self._handlers.get(event.type, []) + self._global_handlers
        if handlers:
            await asyncio.gather(
                *[h(event) for h in handlers],
                return_exceptions=True,
            )


# Global event bus instance
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
