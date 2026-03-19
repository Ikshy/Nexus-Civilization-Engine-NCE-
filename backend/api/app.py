"""
FastAPI Control Panel — NCE
REST API for simulation control, state query, and analytics retrieval.
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..services.simulation import SimulationService, SimulationConfig
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global simulation instance
# ---------------------------------------------------------------------------

_sim: Optional[SimulationService] = None


def get_sim() -> SimulationService:
    if _sim is None:
        raise HTTPException(status_code=503, detail="Simulation not initialized")
    return _sim


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    world_width: int = Field(50, ge=10, le=200)
    world_height: int = Field(50, ge=10, le=200)
    initial_agents: int = Field(80, ge=5, le=500)
    max_agents: int = Field(200, ge=10, le=1000)
    tick_interval_ms: float = Field(100.0, ge=10, le=5000)
    max_ticks: int = Field(10000, ge=100, le=100000)
    random_seed: Optional[int] = None
    auto_scenarios: bool = True


class ScenarioInjectRequest(BaseModel):
    scenario_type: str
    severity: float = Field(0.7, ge=0.0, le=1.0)
    faction_a: Optional[str] = None
    faction_b: Optional[str] = None


class AgentModifyRequest(BaseModel):
    agent_id: str
    modifications: Dict[str, Any]


class ParameterUpdateRequest(BaseModel):
    tick_interval_ms: Optional[float] = None
    auto_scenarios: Optional[bool] = None
    max_agents: Optional[int] = None


class CustomEventRequest(BaseModel):
    event_type: str
    description: str
    agent_ids: Optional[List[str]] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("NCE API starting up")
    yield
    logger.info("NCE API shutting down")
    if _sim:
        await _sim.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Nexus Civilization Engine API",
        description="Research-grade multi-agent civilization simulation control panel",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(simulation_router, prefix="/api/v1/simulation", tags=["Simulation Control"])
    app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(scenarios_router, prefix="/api/v1/scenarios", tags=["Scenarios"])
    app.include_router(world_router, prefix="/api/v1/world", tags=["World"])
    app.include_router(events_router, prefix="/api/v1/events", tags=["Events"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "nce-api"}

    return app


# ---------------------------------------------------------------------------
# Simulation Control Router
# ---------------------------------------------------------------------------

from fastapi import APIRouter

simulation_router = APIRouter()


@simulation_router.post("/start")
async def start_simulation(req: StartRequest, background_tasks: BackgroundTasks):
    global _sim
    settings = get_settings()
    config = SimulationConfig(
        world_width=req.world_width,
        world_height=req.world_height,
        initial_agents=req.initial_agents,
        max_agents=req.max_agents,
        tick_interval_ms=req.tick_interval_ms,
        max_ticks=req.max_ticks,
        random_seed=req.random_seed,
        auto_scenarios=req.auto_scenarios,
    )
    _sim = SimulationService(config, settings)
    _sim.initialize()
    background_tasks.add_task(_sim.run_async)
    return {
        "sim_id": config.sim_id,
        "status": "started",
        "config": config.__dict__,
    }


@simulation_router.post("/stop")
async def stop_simulation():
    sim = get_sim()
    await sim.stop()
    return {"status": "stopped", "tick": sim.tick}


@simulation_router.post("/pause")
async def pause_simulation():
    sim = get_sim()
    sim.pause()
    return {"status": "paused", "tick": sim.tick}


@simulation_router.post("/resume")
async def resume_simulation():
    sim = get_sim()
    sim.resume()
    return {"status": "running", "tick": sim.tick}


@simulation_router.post("/step")
async def step_simulation(n: int = Query(1, ge=1, le=100)):
    """Advance simulation by N ticks synchronously."""
    sim = get_sim()
    sim.run_sync(n)
    return {"status": "stepped", "tick": sim.tick, "steps": n}


@simulation_router.get("/state")
async def get_simulation_state():
    sim = get_sim()
    return sim.get_state_snapshot()


@simulation_router.get("/status")
async def get_simulation_status():
    sim = get_sim()
    return {
        "status": sim.status.value,
        "tick": sim.tick,
        "sim_id": sim.config.sim_id,
        "agent_count": len([a for a in sim.agents.values() if a.vitals.health > 0]),
        "active_scenarios": len(sim.scenarios.active_scenarios),
    }


@simulation_router.patch("/parameters")
async def update_parameters(req: ParameterUpdateRequest):
    sim = get_sim()
    if req.tick_interval_ms is not None:
        sim.config.tick_interval_ms = req.tick_interval_ms
    if req.auto_scenarios is not None:
        sim.config.auto_scenarios = req.auto_scenarios
    if req.max_agents is not None:
        sim.config.max_agents = req.max_agents
    return {"updated": True, "config": {
        "tick_interval_ms": sim.config.tick_interval_ms,
        "auto_scenarios": sim.config.auto_scenarios,
        "max_agents": sim.config.max_agents,
    }}


# ---------------------------------------------------------------------------
# Agents Router
# ---------------------------------------------------------------------------

agents_router = APIRouter()


@agents_router.get("/")
async def list_agents(
    alive_only: bool = True,
    agent_type: Optional[str] = None,
    faction: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    sim = get_sim()
    agents = list(sim.agents.values())
    if alive_only:
        agents = [a for a in agents if a.vitals.health > 0]
    if agent_type:
        agents = [a for a in agents if a.agent_type.value == agent_type]
    if faction:
        agents = [a for a in agents if a.faction_id == faction]
    agents = agents[:limit]

    return {
        "count": len(agents),
        "agents": [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "type": a.agent_type.value,
                "position": {"x": a.position.x, "y": a.position.y},
                "health": round(a.vitals.health, 1),
                "energy": round(a.vitals.energy, 1),
                "stress": round(a.vitals.stress, 1),
                "faction": a.faction_id,
            }
            for a in agents
        ],
    }


@agents_router.get("/{agent_id}")
async def get_agent(agent_id: str):
    sim = get_sim()
    detail = sim.get_agent_detail(agent_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@agents_router.patch("/{agent_id}")
async def modify_agent(agent_id: str, req: AgentModifyRequest):
    sim = get_sim()
    result = sim.modify_agent(agent_id, req.modifications)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@agents_router.get("/{agent_id}/memory")
async def get_agent_memory(agent_id: str):
    sim = get_sim()
    agent = sim.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "short_term": list(agent.memory.short_term)[-20:],
        "episodic": agent.memory.episodic[-20:],
        "semantic_keys": list(agent.memory.semantic_memory.keys())[-20:],
        "social_keys": list(agent.memory.social_memory.keys())[-20:],
        "emotional": agent.memory.emotional_memory[-20:],
    }


@agents_router.get("/{agent_id}/trust")
async def get_agent_trust(agent_id: str):
    sim = get_sim()
    agent = sim.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        tid: {
            "score": round(entry.score, 3),
            "interactions": entry.interaction_count,
            "last_tick": entry.last_interaction_tick,
        }
        for tid, entry in agent.trust_map.items()
        if tid in sim.agents
    }


# ---------------------------------------------------------------------------
# Analytics Router
# ---------------------------------------------------------------------------

analytics_router = APIRouter()


@analytics_router.get("/summary")
async def get_analytics_summary():
    sim = get_sim()
    return sim.get_analytics()


@analytics_router.get("/trends/{metric}")
async def get_metric_trend(metric: str, last_n: int = Query(20, ge=1, le=200)):
    sim = get_sim()
    valid = ["gini_coefficient", "entropy", "stability_index"]
    if metric not in valid:
        raise HTTPException(status_code=400, detail=f"Metric must be one of: {valid}")
    trend = sim.analytics.get_trend(metric, last_n)
    return {"metric": metric, "values": trend}


@analytics_router.get("/network")
async def get_network_metrics():
    sim = get_sim()
    snap = sim.analytics.get_latest_snapshot()
    if not snap:
        return {"status": "no_data"}
    return snap.network_metrics


@analytics_router.get("/leaders")
async def get_leaders():
    sim = get_sim()
    snap = sim.analytics.get_latest_snapshot()
    if not snap:
        return {"leaders": []}
    return {
        "leaders": [
            {
                "agent_id": l.agent_id,
                "influence": round(l.influence_score, 3),
                "followers": l.follower_count,
                "type": l.agent_type,
                "centrality": round(l.centrality, 3),
            }
            for l in snap.leadership_signals
        ]
    }


@analytics_router.get("/inequality")
async def get_inequality():
    sim = get_sim()
    snap = sim.analytics.get_latest_snapshot()
    if not snap:
        return {"status": "no_data"}
    return {
        "gini": snap.gini_coefficient,
        "population": snap.population_stats,
    }


@analytics_router.get("/clusters")
async def get_cooperation_clusters():
    sim = get_sim()
    snap = sim.analytics.get_latest_snapshot()
    if not snap:
        return {"clusters": []}
    return {
        "clusters": [
            {
                "id": c.cluster_id,
                "size": c.size,
                "cohesion": round(c.cohesion_score, 3),
                "dominant_type": c.dominant_type,
                "avg_trust": round(c.avg_trust, 3),
            }
            for c in snap.cooperation_clusters
        ]
    }


@analytics_router.get("/conflict-zones")
async def get_conflict_zones():
    sim = get_sim()
    snap = sim.analytics.get_latest_snapshot()
    if not snap:
        return {"zones": []}
    return {
        "zones": [
            {
                "id": z.zone_id,
                "center": {"x": z.center[0], "y": z.center[1]},
                "intensity": round(z.intensity, 3),
                "agents_involved": len(z.involved_agents),
            }
            for z in snap.conflict_zones
        ]
    }


@analytics_router.get("/information")
async def get_information_metrics():
    sim = get_sim()
    return sim.information.get_info_summary()


# ---------------------------------------------------------------------------
# Scenarios Router
# ---------------------------------------------------------------------------

scenarios_router = APIRouter()


@scenarios_router.get("/available")
async def list_available_scenarios():
    sim = get_sim()
    return {"scenarios": sim.scenarios.list_available()}


@scenarios_router.get("/status")
async def get_scenario_status():
    sim = get_sim()
    return sim.scenarios.get_status()


@scenarios_router.post("/inject")
async def inject_scenario(req: ScenarioInjectRequest):
    sim = get_sim()
    kwargs = {}
    if req.faction_a:
        kwargs["faction_a"] = req.faction_a
    if req.faction_b:
        kwargs["faction_b"] = req.faction_b
    result = sim.inject_scenario(req.scenario_type, req.severity, **kwargs)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# World Router
# ---------------------------------------------------------------------------

world_router = APIRouter()


@world_router.get("/state")
async def get_world_state():
    sim = get_sim()
    ws = sim.world_state
    return {
        "width": ws.width,
        "height": ws.height,
        "tick": ws.tick,
        "season": ws.season.value,
        "weather": ws.current_weather.value,
        "day": ws.day,
        "year": ws.year,
        "active_disasters": [d.value for d in ws.active_disasters],
        "buildings": len(ws.buildings),
        "institution_health": getattr(ws, "institution_health", 100),
        "enforcement_strength": getattr(ws, "enforcement_strength", 1.0),
        "inflation_rate": getattr(ws, "inflation_rate", 1.0),
    }


@world_router.get("/heatmap/{resource}")
async def get_heatmap(resource: str):
    sim = get_sim()
    valid_resources = ["food", "water", "energy", "tools", "medicine", "money"]
    if resource not in valid_resources:
        raise HTTPException(status_code=400, detail=f"Resource must be one of: {valid_resources}")
    grid = sim.get_world_heatmap(resource)
    return {"resource": resource, "grid": grid}


@world_router.get("/cells")
async def get_cells(
    x_min: int = 0, x_max: int = 49,
    y_min: int = 0, y_max: int = 49,
):
    sim = get_sim()
    ws = sim.world_state
    cells = []
    for (x, y), cell in ws.cells.items():
        if x_min <= x <= x_max and y_min <= y <= y_max:
            cells.append({
                "x": x,
                "y": y,
                "terrain": cell.terrain_type.value,
                "zone": cell.zone_type.value,
                "resources": {k: round(v, 1) for k, v in cell.resources.__dict__.items()},
                "passable": cell.passable,
                "building_id": cell.building_id,
            })
    return {"cells": cells, "count": len(cells)}


# ---------------------------------------------------------------------------
# Events Router
# ---------------------------------------------------------------------------

events_router = APIRouter()


@events_router.get("/recent")
async def get_recent_events(limit: int = Query(50, ge=1, le=500)):
    sim = get_sim()
    events = sim.event_log[-limit:]
    return {
        "count": len(events),
        "events": [
            {
                "tick": e.tick,
                "type": e.event_type,
                "description": e.description,
                "agents": e.agent_ids or [],
            }
            for e in reversed(events)
        ],
    }


@events_router.get("/timeline")
async def get_event_timeline(
    event_type: Optional[str] = None,
    from_tick: int = 0,
    to_tick: int = 99999,
    limit: int = Query(100, ge=1, le=1000),
):
    sim = get_sim()
    if event_type:
        events = sim.analytics.timeline.get_by_type(event_type, limit)
    else:
        events = sim.analytics.timeline.get_window(from_tick, to_tick)[-limit:]
    return {
        "count": len(events),
        "summary": sim.analytics.timeline.summary(),
        "events": [
            {"tick": e.tick, "type": e.event_type, "description": e.description}
            for e in events
        ],
    }


@events_router.post("/inject")
async def inject_event(req: CustomEventRequest):
    """Manually inject a simulation event."""
    sim = get_sim()
    from ..core.models import SimulationEvent
    event = SimulationEvent(
        event_id=f"manual_{sim.tick}",
        event_type=req.event_type,
        tick=sim.tick,
        description=req.description,
        agent_ids=req.agent_ids,
    )
    sim.analytics.record_event(event)
    sim.event_log.append(event)
    return {"status": "injected", "event_id": event.event_id}
