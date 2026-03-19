"""
Database layer — NCE
SQLAlchemy async engine, session factory, and repositories.
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from .orm_models import (
    Base, SimulationRun, AgentRecord, AnalyticsSnapshotRecord,
    EventRecord, ScenarioRecord, WorldSnapshotRecord
)
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

def get_engine():
    settings = get_settings()
    url = settings.database.url.replace("postgresql://", "postgresql+asyncpg://")
    return create_async_engine(
        url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
    )


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session():
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


# ---------------------------------------------------------------------------
# Simulation Repository
# ---------------------------------------------------------------------------

class SimulationRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(self, sim_id: str, config: Dict) -> SimulationRun:
        run = SimulationRun(sim_id=sim_id, config=config, status="running")
        self.session.add(run)
        await self.session.flush()
        return run

    async def update_run_status(self, sim_id: str, status: str, tick: int):
        from datetime import datetime
        result = await self.session.execute(
            select(SimulationRun).where(SimulationRun.sim_id == sim_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.status = status
            run.tick_count = tick
            if status in ("stopped", "completed", "error"):
                run.ended_at = datetime.utcnow()
            await self.session.flush()

    async def get_run(self, sim_id: str) -> Optional[SimulationRun]:
        result = await self.session.execute(
            select(SimulationRun).where(SimulationRun.sim_id == sim_id)
        )
        return result.scalar_one_or_none()

    async def list_runs(self, limit: int = 20) -> List[SimulationRun]:
        result = await self.session.execute(
            select(SimulationRun).order_by(desc(SimulationRun.started_at)).limit(limit)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Analytics Repository
# ---------------------------------------------------------------------------

class AnalyticsRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_snapshot(self, sim_id: str, snap_data: Dict) -> AnalyticsSnapshotRecord:
        pop = snap_data.get("population_stats", {})
        record = AnalyticsSnapshotRecord(
            sim_id=sim_id,
            tick=snap_data.get("tick", 0),
            gini_coefficient=snap_data.get("gini_coefficient", 0),
            entropy=snap_data.get("entropy", 0),
            stability_index=snap_data.get("stability_index", 0),
            population=pop.get("total", 0),
            alive_agents=pop.get("alive", 0),
            avg_health=pop.get("avg_health", 0),
            avg_stress=pop.get("avg_stress", 0),
            num_conflict_zones=len(snap_data.get("conflict_zones", [])),
            num_coop_clusters=len(snap_data.get("cooperation_clusters", [])),
            network_density=snap_data.get("network_metrics", {}).get("density", 0),
            full_data=snap_data,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_snapshots(
        self,
        sim_id: str,
        from_tick: int = 0,
        to_tick: int = 99999,
        limit: int = 100,
    ) -> List[AnalyticsSnapshotRecord]:
        result = await self.session.execute(
            select(AnalyticsSnapshotRecord)
            .where(
                AnalyticsSnapshotRecord.sim_id == sim_id,
                AnalyticsSnapshotRecord.tick >= from_tick,
                AnalyticsSnapshotRecord.tick <= to_tick,
            )
            .order_by(AnalyticsSnapshotRecord.tick)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_metric_trend(self, sim_id: str, metric: str, limit: int = 50) -> List[Dict]:
        result = await self.session.execute(
            select(AnalyticsSnapshotRecord.tick, getattr(AnalyticsSnapshotRecord, metric))
            .where(AnalyticsSnapshotRecord.sim_id == sim_id)
            .order_by(AnalyticsSnapshotRecord.tick)
            .limit(limit)
        )
        return [{"tick": row[0], "value": row[1]} for row in result.all()]


# ---------------------------------------------------------------------------
# Events Repository
# ---------------------------------------------------------------------------

class EventsRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_save_events(self, sim_id: str, events: List[Dict]):
        records = [
            EventRecord(
                sim_id=sim_id,
                event_id=e.get("event_id", ""),
                event_type=e.get("event_type", "unknown"),
                tick=e.get("tick", 0),
                description=e.get("description", ""),
                agent_ids=e.get("agent_ids") or [],
                position_x=e.get("position_x"),
                position_y=e.get("position_y"),
            )
            for e in events
        ]
        self.session.add_all(records)
        await self.session.flush()

    async def get_events(
        self,
        sim_id: str,
        event_type: Optional[str] = None,
        from_tick: int = 0,
        limit: int = 100,
    ) -> List[EventRecord]:
        query = (
            select(EventRecord)
            .where(
                EventRecord.sim_id == sim_id,
                EventRecord.tick >= from_tick,
            )
            .order_by(desc(EventRecord.tick))
            .limit(limit)
        )
        if event_type:
            query = query.where(EventRecord.event_type == event_type)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_event_type_counts(self, sim_id: str) -> Dict[str, int]:
        result = await self.session.execute(
            select(EventRecord.event_type, func.count(EventRecord.id))
            .where(EventRecord.sim_id == sim_id)
            .group_by(EventRecord.event_type)
        )
        return {row[0]: row[1] for row in result.all()}


# ---------------------------------------------------------------------------
# Agent Repository
# ---------------------------------------------------------------------------

class AgentRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_agent(self, sim_id: str, agent_data: Dict) -> AgentRecord:
        record = AgentRecord(
            sim_id=sim_id,
            agent_id=agent_data["agent_id"],
            agent_type=agent_data["agent_type"],
            name=agent_data.get("name", ""),
            faction_id=agent_data.get("faction_id"),
            born_tick=agent_data.get("born_tick", 0),
            personality=agent_data.get("personality", {}),
            skills=agent_data.get("skills", {}),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def mark_dead(self, sim_id: str, agent_id: str, tick: int, health: float, wealth: float):
        result = await self.session.execute(
            select(AgentRecord).where(
                AgentRecord.sim_id == sim_id,
                AgentRecord.agent_id == agent_id,
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.died_tick = tick
            record.final_health = health
            record.final_wealth = wealth
            await self.session.flush()

    async def get_agents(self, sim_id: str, alive_only: bool = True) -> List[AgentRecord]:
        query = select(AgentRecord).where(AgentRecord.sim_id == sim_id)
        if alive_only:
            query = query.where(AgentRecord.died_tick.is_(None))
        result = await self.session.execute(query)
        return list(result.scalars().all())
