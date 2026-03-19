"""
SQLAlchemy ORM models for NCE persistent storage.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Float, Integer, Boolean, Text,
    DateTime, ForeignKey, JSON, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id = Column(String(16), unique=True, nullable=False, index=True)
    config = Column(JSON, nullable=False)
    status = Column(String(20), default="running")
    tick_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)

    snapshots = relationship("AnalyticsSnapshot", back_populates="run", cascade="all, delete-orphan")
    events = relationship("EventRecord", back_populates="run", cascade="all, delete-orphan")


class AgentRecord(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id = Column(String(16), nullable=False, index=True)
    agent_id = Column(String(32), nullable=False)
    agent_type = Column(String(32), nullable=False)
    name = Column(String(64))
    faction_id = Column(String(32), nullable=True)
    born_tick = Column(Integer, default=0)
    died_tick = Column(Integer, nullable=True)
    final_health = Column(Float, default=100.0)
    final_wealth = Column(Float, default=0.0)
    personality = Column(JSON, default=dict)
    skills = Column(JSON, default=dict)
    history_summary = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_agents_sim_agent", "sim_id", "agent_id"),
    )


class AnalyticsSnapshotRecord(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id = Column(String(16), ForeignKey("simulation_runs.sim_id"), nullable=False, index=True)
    tick = Column(Integer, nullable=False)
    gini_coefficient = Column(Float)
    entropy = Column(Float)
    stability_index = Column(Float)
    population = Column(Integer)
    alive_agents = Column(Integer)
    avg_health = Column(Float)
    avg_stress = Column(Float)
    num_conflict_zones = Column(Integer, default=0)
    num_coop_clusters = Column(Integer, default=0)
    network_density = Column(Float)
    echo_chambers = Column(Integer, default=0)
    full_data = Column(JSON)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("SimulationRun", back_populates="snapshots")

    __table_args__ = (
        Index("ix_analytics_sim_tick", "sim_id", "tick"),
    )


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id = Column(String(16), ForeignKey("simulation_runs.sim_id"), nullable=False, index=True)
    event_id = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False, index=True)
    tick = Column(Integer, nullable=False)
    description = Column(Text)
    agent_ids = Column(JSON, default=list)
    position_x = Column(Integer, nullable=True)
    position_y = Column(Integer, nullable=True)
    extra_data = Column(JSON, default=dict)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("SimulationRun", back_populates="events")

    __table_args__ = (
        Index("ix_events_sim_tick", "sim_id", "tick"),
        Index("ix_events_sim_type", "sim_id", "event_type"),
    )


class ScenarioRecord(Base):
    __tablename__ = "scenario_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id = Column(String(16), nullable=False, index=True)
    scenario_id = Column(String(64), nullable=False)
    scenario_type = Column(String(64), nullable=False)
    name = Column(String(128))
    severity = Column(Float)
    tick_start = Column(Integer)
    tick_end = Column(Integer, nullable=True)
    status = Column(String(20), default="active")
    recorded_at = Column(DateTime, default=datetime.utcnow)


class WorldSnapshotRecord(Base):
    __tablename__ = "world_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id = Column(String(16), nullable=False, index=True)
    tick = Column(Integer, nullable=False)
    season = Column(String(16))
    weather = Column(String(32))
    day = Column(Integer)
    year = Column(Integer)
    active_disasters = Column(JSON, default=list)
    institution_health = Column(Float, default=100.0)
    inflation_rate = Column(Float, default=1.0)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_world_sim_tick", "sim_id", "tick"),
    )
