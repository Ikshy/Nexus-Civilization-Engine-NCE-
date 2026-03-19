"""
Scenario Engine — NCE
Runtime injection of scenarios: resource collapse, war, plague,
market crash, political instability, climate disaster.
"""
from __future__ import annotations
import random
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

import numpy as np

from ..enums import ScenarioType, AgentType, ResourceType, DisasterType
from ..models import Agent, WorldState, SimulationEvent, Cell, Position

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario state
# ---------------------------------------------------------------------------

class ScenarioStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    RESOLVED = "resolved"
    FAILED = "failed"


@dataclass
class ScenarioEffect:
    """Describes one atomic effect applied to the world."""
    effect_type: str      # e.g. "reduce_resource", "kill_agents", "modify_law"
    target: str           # "world", "agents", "faction:<id>", "region:<x,y,r>"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    scenario_id: str
    scenario_type: ScenarioType
    name: str
    description: str
    severity: float               # 0–1
    duration_ticks: int
    tick_start: int = 0
    tick_end: int = 0
    status: ScenarioStatus = ScenarioStatus.PENDING
    effects: List[ScenarioEffect] = field(default_factory=list)
    tick_effects: List[ScenarioEffect] = field(default_factory=list)  # applied every tick
    resolution_condition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scenario Definitions
# ---------------------------------------------------------------------------

def build_resource_collapse(severity: float = 0.7, tick: int = 0) -> Scenario:
    """Severe reduction in all resource supply."""
    return Scenario(
        scenario_id=f"rc_{tick}",
        scenario_type=ScenarioType.RESOURCE_COLLAPSE,
        name="Resource Collapse",
        description="Critical shortage of food, water, and energy across the civilization.",
        severity=severity,
        duration_ticks=100,
        tick_start=tick,
        effects=[
            ScenarioEffect("reduce_resource", "world",
                           {"resource": "food", "factor": 1.0 - severity * 0.8}),
            ScenarioEffect("reduce_resource", "world",
                           {"resource": "water", "factor": 1.0 - severity * 0.7}),
            ScenarioEffect("reduce_resource", "world",
                           {"resource": "energy", "factor": 1.0 - severity * 0.6}),
        ],
        tick_effects=[
            ScenarioEffect("stress_agents", "agents",
                           {"delta": severity * 2.0, "threshold_health": 50}),
            ScenarioEffect("reduce_regen", "world",
                           {"factor": 1.0 - severity * 0.5}),
        ],
        resolution_condition="avg_food > 20",
    )


def build_war_onset(faction_a: str, faction_b: str, severity: float = 0.8, tick: int = 0) -> Scenario:
    """Open warfare between two factions."""
    return Scenario(
        scenario_id=f"war_{tick}",
        scenario_type=ScenarioType.WAR_ONSET,
        name=f"War: {faction_a} vs {faction_b}",
        description=f"Full-scale conflict erupts between {faction_a} and {faction_b}.",
        severity=severity,
        duration_ticks=150,
        tick_start=tick,
        effects=[
            ScenarioEffect("declare_war", "factions",
                           {"faction_a": faction_a, "faction_b": faction_b}),
            ScenarioEffect("reduce_trust", "agents",
                           {"between_factions": [faction_a, faction_b], "delta": -0.5}),
        ],
        tick_effects=[
            ScenarioEffect("war_attrition", "agents",
                           {"faction_a": faction_a, "faction_b": faction_b,
                            "damage": severity * 5.0}),
            ScenarioEffect("destroy_infrastructure", "world",
                           {"probability": severity * 0.02}),
        ],
        resolution_condition="faction_war_ended",
    )


def build_plague(severity: float = 0.6, tick: int = 0) -> Scenario:
    """Epidemic spreading through agent population."""
    return Scenario(
        scenario_id=f"plague_{tick}",
        scenario_type=ScenarioType.PLAGUE,
        name="Plague Outbreak",
        description="A highly contagious disease sweeps through the population.",
        severity=severity,
        duration_ticks=80,
        tick_start=tick,
        effects=[
            ScenarioEffect("infect_agents", "agents",
                           {"infection_rate": severity * 0.3, "initial_infected": 3}),
        ],
        tick_effects=[
            ScenarioEffect("spread_disease", "agents",
                           {"transmission_rate": severity * 0.15, "health_damage": severity * 3.0}),
            ScenarioEffect("reduce_medicine", "world",
                           {"factor": 0.9}),
        ],
        resolution_condition="infected_count < 5",
        metadata={"infected_agents": set()},
    )


def build_market_crash(severity: float = 0.75, tick: int = 0) -> Scenario:
    """Sudden economic collapse."""
    return Scenario(
        scenario_id=f"crash_{tick}",
        scenario_type=ScenarioType.MARKET_CRASH,
        name="Market Crash",
        description="Financial panic erases wealth and collapses trade systems.",
        severity=severity,
        duration_ticks=60,
        tick_start=tick,
        effects=[
            ScenarioEffect("devalue_money", "agents",
                           {"factor": 1.0 - severity * 0.7}),
            ScenarioEffect("close_market", "world",
                           {"duration": 10}),
            ScenarioEffect("spike_inflation", "world",
                           {"factor": 1.0 + severity * 3.0}),
        ],
        tick_effects=[
            ScenarioEffect("reduce_trade", "world",
                           {"factor": 1.0 - severity * 0.4}),
            ScenarioEffect("stress_agents", "agents",
                           {"delta": severity * 1.5}),
        ],
        resolution_condition="market_price_stable",
    )


def build_political_instability(severity: float = 0.65, tick: int = 0) -> Scenario:
    """Governance breakdown, law enforcement collapse."""
    return Scenario(
        scenario_id=f"polinstab_{tick}",
        scenario_type=ScenarioType.POLITICAL_INSTABILITY,
        name="Political Crisis",
        description="Government authority collapses. Law enforcement fails.",
        severity=severity,
        duration_ticks=120,
        tick_start=tick,
        effects=[
            ScenarioEffect("reduce_enforcement", "world",
                           {"factor": 1.0 - severity * 0.8}),
            ScenarioEffect("invalidate_laws", "world",
                           {"fraction": severity * 0.5}),
            ScenarioEffect("reduce_institution_health", "world",
                           {"delta": -severity * 30}),
        ],
        tick_effects=[
            ScenarioEffect("spawn_rebels", "agents",
                           {"probability": severity * 0.05}),
            ScenarioEffect("reduce_institution_health", "world",
                           {"delta": -severity * 0.5}),
        ],
        resolution_condition="institution_health > 50",
    )


def build_climate_disaster(severity: float = 0.7, tick: int = 0) -> Scenario:
    """Climate disaster: extreme weather, terrain damage, resource destruction."""
    return Scenario(
        scenario_id=f"climate_{tick}",
        scenario_type=ScenarioType.CLIMATE_DISASTER,
        name="Climate Catastrophe",
        description="Extreme climate events devastate terrain and resources.",
        severity=severity,
        duration_ticks=200,
        tick_start=tick,
        effects=[
            ScenarioEffect("damage_terrain", "world",
                           {"fraction": severity * 0.4, "damage_type": "flood"}),
            ScenarioEffect("reduce_resource", "world",
                           {"resource": "food", "factor": 1.0 - severity * 0.6}),
            ScenarioEffect("reduce_resource", "world",
                           {"resource": "water", "factor": 1.0 - severity * 0.3}),
        ],
        tick_effects=[
            ScenarioEffect("weather_damage", "agents",
                           {"health_damage": severity * 1.0, "probability": 0.1}),
            ScenarioEffect("destroy_buildings", "world",
                           {"probability": severity * 0.01}),
            ScenarioEffect("reduce_regen", "world",
                           {"factor": 1.0 - severity * 0.3}),
        ],
        resolution_condition="avg_terrain_health > 60",
    )


SCENARIO_BUILDERS: Dict[ScenarioType, Callable] = {
    ScenarioType.RESOURCE_COLLAPSE: build_resource_collapse,
    ScenarioType.WAR_ONSET: build_war_onset,
    ScenarioType.PLAGUE: build_plague,
    ScenarioType.MARKET_CRASH: build_market_crash,
    ScenarioType.POLITICAL_INSTABILITY: build_political_instability,
    ScenarioType.CLIMATE_DISASTER: build_climate_disaster,
}


# ---------------------------------------------------------------------------
# Effect Applier
# ---------------------------------------------------------------------------

class EffectApplier:
    """Applies ScenarioEffects to world state and agent collections."""

    def apply_effect(
        self,
        effect: ScenarioEffect,
        agents: Dict[str, Agent],
        world_state: WorldState,
        tick: int,
        extra_context: Dict = None,
    ) -> List[SimulationEvent]:
        ctx = extra_context or {}
        handler = getattr(self, f"_handle_{effect.effect_type}", None)
        if handler is None:
            logger.warning("Unknown effect type: %s", effect.effect_type)
            return []
        return handler(effect, agents, world_state, tick, ctx) or []

    # ---- handlers ----------------------------------------------------------

    def _handle_reduce_resource(self, effect, agents, world_state, tick, ctx):
        resource = effect.parameters.get("resource", "food")
        factor = effect.parameters.get("factor", 0.5)
        # Apply to world cells
        for cell in world_state.cells.values():
            current = getattr(cell.resources, resource, 0)
            setattr(cell.resources, resource, current * factor)
        return [SimulationEvent(
            event_id=f"eff_{tick}_{effect.effect_type}",
            event_type="resource_reduced",
            tick=tick,
            description=f"Scenario: {resource} reduced by factor {factor:.2f}",
        )]

    def _handle_stress_agents(self, effect, agents, world_state, tick, ctx):
        delta = effect.parameters.get("delta", 5.0)
        threshold = effect.parameters.get("threshold_health", 0)
        events = []
        for agent in agents.values():
            if agent.vitals.health <= threshold or threshold == 0:
                agent.vitals.stress = min(100, agent.vitals.stress + delta)
        return events

    def _handle_reduce_regen(self, effect, agents, world_state, tick, ctx):
        factor = effect.parameters.get("factor", 0.7)
        world_state.regen_modifier = getattr(world_state, "regen_modifier", 1.0) * factor
        return []

    def _handle_declare_war(self, effect, agents, world_state, tick, ctx):
        fa = effect.parameters.get("faction_a")
        fb = effect.parameters.get("faction_b")
        if fa and fb:
            world_state.active_wars = getattr(world_state, "active_wars", set())
            world_state.active_wars.add((fa, fb))
        return [SimulationEvent(
            event_id=f"war_{tick}",
            event_type="war_declared",
            tick=tick,
            description=f"War declared between {fa} and {fb}",
        )]

    def _handle_reduce_trust(self, effect, agents, world_state, tick, ctx):
        factions = effect.parameters.get("between_factions", [])
        delta = effect.parameters.get("delta", -0.3)
        for agent in agents.values():
            if agent.faction_id in factions:
                for tid, entry in agent.trust_map.items():
                    target = agents.get(tid)
                    if target and target.faction_id in factions and target.faction_id != agent.faction_id:
                        entry.score = max(0.0, entry.score + delta)
        return []

    def _handle_war_attrition(self, effect, agents, world_state, tick, ctx):
        fa = effect.parameters.get("faction_a")
        fb = effect.parameters.get("faction_b")
        damage = effect.parameters.get("damage", 3.0)
        events = []
        for agent in agents.values():
            if agent.faction_id in (fa, fb):
                if random.random() < 0.15:
                    agent.vitals.health = max(0, agent.vitals.health - damage)
                    if agent.vitals.health == 0:
                        events.append(SimulationEvent(
                            event_id=f"death_war_{tick}_{agent.agent_id}",
                            event_type="agent_death_war",
                            tick=tick,
                            description=f"Agent {agent.agent_id} killed in war",
                            agent_ids=[agent.agent_id],
                        ))
        return events

    def _handle_infect_agents(self, effect, agents, world_state, tick, ctx):
        rate = effect.parameters.get("infection_rate", 0.2)
        n_initial = effect.parameters.get("initial_infected", 3)
        agent_list = [a for a in agents.values() if a.vitals.health > 0]
        to_infect = random.sample(agent_list, min(n_initial, len(agent_list)))
        infected = ctx.get("infected_agents", set())
        for a in to_infect:
            infected.add(a.agent_id)
        ctx["infected_agents"] = infected
        return [SimulationEvent(
            event_id=f"plague_start_{tick}",
            event_type="plague_outbreak",
            tick=tick,
            description=f"Plague infected {len(to_infect)} initial agents",
        )]

    def _handle_spread_disease(self, effect, agents, world_state, tick, ctx):
        transmission = effect.parameters.get("transmission_rate", 0.1)
        damage = effect.parameters.get("health_damage", 3.0)
        infected = ctx.get("infected_agents", set())
        new_infected = set()
        events = []
        for aid in list(infected):
            agent = agents.get(aid)
            if not agent:
                continue
            agent.vitals.health = max(0, agent.vitals.health - damage)
            # Spread to nearby agents
            for other_id, other in agents.items():
                if other_id in infected:
                    continue
                dist = abs(agent.position.x - other.position.x) + abs(agent.position.y - other.position.y)
                if dist <= 3 and random.random() < transmission:
                    new_infected.add(other_id)
        infected |= new_infected
        # Chance of recovery (medicine skill)
        for aid in list(infected):
            agent = agents.get(aid)
            if agent and agent.skills.medicine > 0.5:
                if random.random() < agent.skills.medicine * 0.1:
                    infected.discard(aid)
        ctx["infected_agents"] = infected
        if new_infected:
            events.append(SimulationEvent(
                event_id=f"spread_{tick}",
                event_type="disease_spread",
                tick=tick,
                description=f"Disease spread to {len(new_infected)} new agents",
            ))
        return events

    def _handle_devalue_money(self, effect, agents, world_state, tick, ctx):
        factor = effect.parameters.get("factor", 0.3)
        for agent in agents.values():
            agent.resources.money *= factor
        world_state.inflation_rate = getattr(world_state, "inflation_rate", 1.0) * (1.0 / factor)
        return [SimulationEvent(
            event_id=f"crash_{tick}",
            event_type="market_crash",
            tick=tick,
            description=f"Money devalued to {factor:.0%} of previous value",
        )]

    def _handle_spike_inflation(self, effect, agents, world_state, tick, ctx):
        factor = effect.parameters.get("factor", 2.0)
        world_state.inflation_rate = getattr(world_state, "inflation_rate", 1.0) * factor
        return []

    def _handle_reduce_enforcement(self, effect, agents, world_state, tick, ctx):
        factor = effect.parameters.get("factor", 0.3)
        world_state.enforcement_strength = getattr(world_state, "enforcement_strength", 1.0) * factor
        return []

    def _handle_invalidate_laws(self, effect, agents, world_state, tick, ctx):
        fraction = effect.parameters.get("fraction", 0.5)
        laws = getattr(world_state, "active_laws", [])
        n_invalidate = int(len(laws) * fraction)
        for law in random.sample(laws, min(n_invalidate, len(laws))):
            law.status = "suspended"
        return []

    def _handle_reduce_institution_health(self, effect, agents, world_state, tick, ctx):
        delta = effect.parameters.get("delta", -10)
        world_state.institution_health = max(0, getattr(world_state, "institution_health", 100) + delta)
        return []

    def _handle_spawn_rebels(self, effect, agents, world_state, tick, ctx):
        prob = effect.parameters.get("probability", 0.05)
        events = []
        for agent in agents.values():
            if agent.vitals.stress > 70 and random.random() < prob:
                agent.agent_type = AgentType.REBEL
                events.append(SimulationEvent(
                    event_id=f"rebel_{tick}_{agent.agent_id}",
                    event_type="agent_radicalized",
                    tick=tick,
                    description=f"Agent {agent.agent_id} became a Rebel",
                    agent_ids=[agent.agent_id],
                ))
        return events

    def _handle_damage_terrain(self, effect, agents, world_state, tick, ctx):
        fraction = effect.parameters.get("fraction", 0.3)
        damage_type = effect.parameters.get("damage_type", "flood")
        cells = list(world_state.cells.values())
        n_damage = int(len(cells) * fraction)
        for cell in random.sample(cells, min(n_damage, len(cells))):
            cell.resources.food *= 0.3
            cell.resources.water = min(cell.resources.water * 2.0, 100) if damage_type == "flood" else 0
            cell.passable = random.random() > 0.3
        return [SimulationEvent(
            event_id=f"terrain_{tick}",
            event_type="terrain_damaged",
            tick=tick,
            description=f"Climate disaster damaged {n_damage} terrain cells",
        )]

    def _handle_weather_damage(self, effect, agents, world_state, tick, ctx):
        dmg = effect.parameters.get("health_damage", 1.0)
        prob = effect.parameters.get("probability", 0.1)
        for agent in agents.values():
            if random.random() < prob:
                agent.vitals.health = max(0, agent.vitals.health - dmg)
        return []

    def _handle_destroy_buildings(self, effect, agents, world_state, tick, ctx):
        prob = effect.parameters.get("probability", 0.01)
        buildings = list(world_state.buildings.values())
        destroyed = []
        for b in buildings:
            if random.random() < prob:
                destroyed.append(b.building_id)
        for bid in destroyed:
            del world_state.buildings[bid]
        return []

    def _handle_close_market(self, effect, agents, world_state, tick, ctx):
        duration = effect.parameters.get("duration", 10)
        world_state.market_closed_until = tick + duration
        return []

    def _handle_reduce_trade(self, effect, agents, world_state, tick, ctx):
        factor = effect.parameters.get("factor", 0.5)
        world_state.trade_volume_modifier = getattr(world_state, "trade_volume_modifier", 1.0) * factor
        return []

    def _handle_destroy_infrastructure(self, effect, agents, world_state, tick, ctx):
        prob = effect.parameters.get("probability", 0.01)
        cells = list(world_state.cells.values())
        for cell in cells:
            if cell.building_id and random.random() < prob:
                if cell.building_id in world_state.buildings:
                    del world_state.buildings[cell.building_id]
                cell.building_id = None
        return []

    def _handle_reduce_medicine(self, effect, agents, world_state, tick, ctx):
        factor = effect.parameters.get("factor", 0.9)
        for cell in world_state.cells.values():
            cell.resources.medicine *= factor
        return []


# ---------------------------------------------------------------------------
# Resolution Checker
# ---------------------------------------------------------------------------

class ResolutionChecker:
    """Checks whether a scenario's resolution condition has been met."""

    def check(
        self,
        scenario: Scenario,
        agents: Dict[str, Agent],
        world_state: WorldState,
        tick: int,
    ) -> bool:
        cond = scenario.resolution_condition
        if not cond:
            return tick >= scenario.tick_end

        try:
            if cond == "avg_food > 20":
                foods = [cell.resources.food for cell in world_state.cells.values()]
                return float(np.mean(foods)) > 20

            if cond == "faction_war_ended":
                active_wars = getattr(world_state, "active_wars", set())
                fa = scenario.effects[0].parameters.get("faction_a") if scenario.effects else None
                fb = scenario.effects[0].parameters.get("faction_b") if scenario.effects else None
                return (fa, fb) not in active_wars

            if cond == "infected_count < 5":
                infected = scenario.metadata.get("infected_agents", set())
                return len(infected) < 5

            if cond == "market_price_stable":
                return getattr(world_state, "inflation_rate", 1.0) < 1.5

            if cond == "institution_health > 50":
                return getattr(world_state, "institution_health", 100) > 50

            if cond == "avg_terrain_health > 60":
                # Simplified: check if average food is recovering
                foods = [cell.resources.food for cell in world_state.cells.values()]
                return float(np.mean(foods)) > 15

        except Exception as e:
            logger.warning("Resolution check error for %s: %s", scenario.scenario_id, e)

        return tick >= scenario.tick_end


# ---------------------------------------------------------------------------
# Main Scenario Engine
# ---------------------------------------------------------------------------

class ScenarioEngine:
    """
    Orchestrator for scenario injection and lifecycle management.
    Supports runtime injection via API.
    """

    def __init__(self):
        self.active_scenarios: Dict[str, Scenario] = {}
        self.completed_scenarios: List[Scenario] = []
        self.applier = EffectApplier()
        self.checker = ResolutionChecker()
        self._scenario_counter = 0
        self._extra_contexts: Dict[str, Dict] = {}  # per-scenario context

    def inject_scenario(
        self,
        scenario_type: ScenarioType,
        severity: float = 0.7,
        tick: int = 0,
        **kwargs,
    ) -> Scenario:
        """Inject a scenario at runtime."""
        builder = SCENARIO_BUILDERS.get(scenario_type)
        if builder is None:
            raise ValueError(f"Unknown scenario type: {scenario_type}")
        scenario = builder(severity=severity, tick=tick, **kwargs)
        scenario.tick_end = tick + scenario.duration_ticks
        scenario.status = ScenarioStatus.ACTIVE
        self.active_scenarios[scenario.scenario_id] = scenario
        self._extra_contexts[scenario.scenario_id] = scenario.metadata.copy()
        logger.info(
            "Scenario injected: %s (severity=%.2f, duration=%d ticks)",
            scenario.name, severity, scenario.duration_ticks
        )
        return scenario

    def inject_custom_scenario(self, scenario: Scenario) -> Scenario:
        """Inject a fully custom scenario object."""
        scenario.status = ScenarioStatus.ACTIVE
        self.active_scenarios[scenario.scenario_id] = scenario
        self._extra_contexts[scenario.scenario_id] = scenario.metadata.copy()
        return scenario

    def tick(
        self,
        tick: int,
        agents: Dict[str, Agent],
        world_state: WorldState,
    ) -> List[SimulationEvent]:
        """Apply all active scenario tick effects. Returns generated events."""
        all_events: List[SimulationEvent] = []

        for sid, scenario in list(self.active_scenarios.items()):
            ctx = self._extra_contexts.get(sid, {})

            # Apply one-time effects on first tick
            if scenario.tick_start == tick:
                for effect in scenario.effects:
                    events = self.applier.apply_effect(effect, agents, world_state, tick, ctx)
                    all_events.extend(events)
                logger.info("Scenario %s activated at tick %d", scenario.name, tick)

            # Apply recurring tick effects
            for effect in scenario.tick_effects:
                events = self.applier.apply_effect(effect, agents, world_state, tick, ctx)
                all_events.extend(events)

            # Update shared context back
            self._extra_contexts[sid] = ctx
            scenario.metadata.update(ctx)

            # Check resolution
            resolved = self.checker.check(scenario, agents, world_state, tick)
            if resolved or tick >= scenario.tick_end:
                scenario.status = ScenarioStatus.RESOLVED
                self.completed_scenarios.append(scenario)
                del self.active_scenarios[sid]
                logger.info("Scenario %s resolved at tick %d", scenario.name, tick)
                all_events.append(SimulationEvent(
                    event_id=f"resolve_{sid}_{tick}",
                    event_type="scenario_resolved",
                    tick=tick,
                    description=f"Scenario '{scenario.name}' resolved.",
                ))

        return all_events

    def get_status(self) -> Dict:
        return {
            "active": [
                {
                    "id": s.scenario_id,
                    "name": s.name,
                    "type": s.scenario_type.value,
                    "severity": s.severity,
                    "ticks_remaining": s.tick_end - s.tick_start,
                }
                for s in self.active_scenarios.values()
            ],
            "completed": [
                {"id": s.scenario_id, "name": s.name, "status": s.status.value}
                for s in self.completed_scenarios[-10:]
            ],
        }

    def list_available(self) -> List[Dict]:
        return [
            {
                "type": st.value,
                "description": SCENARIO_BUILDERS[st].__doc__.strip() if SCENARIO_BUILDERS.get(st) else "",
            }
            for st in ScenarioType
            if st in SCENARIO_BUILDERS
        ]
