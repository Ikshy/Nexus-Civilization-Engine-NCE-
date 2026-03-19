"""
Simulation Orchestrator — NCE
Main async tick loop coordinating all engines.
"""
from __future__ import annotations
import asyncio
import time
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

import numpy as np

from ..core.enums import (
    AgentType, ScenarioType, SimulationStatus, ActionType, InformationType
)
from ..core.models import (
    Agent, WorldState, SimulationEvent, SimulationMetrics, Position
)
from ..core.world.world_engine import WorldEngine
from ..core.agents.agent_system import AgentFactory, AgentRegistry, AgentLifecycleManager
from ..core.cognitive.cognitive_engine import CognitiveEngine
from ..core.economy.economy_engine import EconomyEngine
from ..core.social.social_system import SocialSystem
from ..core.conflict.conflict_engine import ConflictEngine
from ..core.governance.governance_system import GovernanceSystem
from ..core.information.information_system import InformationSystem
from ..core.analytics.analytics_engine import AnalyticsEngine
from ..core.scenarios.scenario_engine import ScenarioEngine
from ..config.settings import SimulationSettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simulation Config
# ---------------------------------------------------------------------------

@dataclass
class SimulationConfig:
    sim_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    world_width: int = 50
    world_height: int = 50
    initial_agents: int = 80
    max_agents: int = 200
    tick_interval_ms: float = 100.0     # ms between ticks in real-time mode
    max_ticks: int = 10000
    random_seed: Optional[int] = None
    analytics_interval: int = 10
    log_events: bool = True
    auto_scenarios: bool = True


# ---------------------------------------------------------------------------
# Action Executor
# ---------------------------------------------------------------------------

class ActionExecutor:
    """Translates cognitive engine action decisions into world state changes."""

    def __init__(
        self,
        world: WorldEngine,
        economy: EconomyEngine,
        social: SocialSystem,
        conflict: ConflictEngine,
        governance: GovernanceSystem,
        information: InformationSystem,
    ):
        self.world = world
        self.economy = economy
        self.social = social
        self.conflict = conflict
        self.governance = governance
        self.information = information

    def execute(
        self,
        agent: Agent,
        action: Dict[str, Any],
        agents: Dict[str, Agent],
        world_state: WorldState,
        tick: int,
    ) -> List[SimulationEvent]:
        events: List[SimulationEvent] = []
        action_type = action.get("type")

        try:
            if action_type == ActionType.MOVE.value:
                events += self._move(agent, action, world_state, tick)

            elif action_type == ActionType.GATHER.value:
                events += self._gather(agent, action, world_state, tick)

            elif action_type == ActionType.TRADE.value:
                events += self._trade(agent, action, agents, world_state, tick)

            elif action_type == ActionType.ATTACK.value:
                events += self._attack(agent, action, agents, world_state, tick)

            elif action_type == ActionType.NEGOTIATE.value:
                events += self._negotiate(agent, action, agents, world_state, tick)

            elif action_type == ActionType.REST.value:
                agent.vitals.energy = min(100, agent.vitals.energy + 15)
                agent.vitals.stress = max(0, agent.vitals.stress - 5)

            elif action_type == ActionType.BROADCAST.value:
                self._broadcast(agent, action, agents, world_state, tick)

            elif action_type == ActionType.BRIBE.value:
                events += self._bribe(agent, action, agents, tick)

            elif action_type == ActionType.SPY.value:
                events += self._spy(agent, action, agents, tick)

            elif action_type == ActionType.BUILD.value:
                events += self._build(agent, action, world_state, tick)

            elif action_type == ActionType.FARM.value:
                events += self._farm(agent, action, world_state, tick)

            elif action_type == ActionType.STEAL.value:
                events += self._steal(agent, action, agents, world_state, tick)

            elif action_type == ActionType.RECRUIT.value:
                events += self._recruit(agent, action, agents, tick)

            elif action_type == ActionType.RESEARCH.value:
                events += self._research(agent, action, tick)

            elif action_type == ActionType.HEAL.value:
                events += self._heal(agent, action, agents, tick)

            elif action_type == ActionType.LOBBY.value:
                events += self._lobby(agent, action, world_state, tick)

        except Exception as e:
            logger.warning("Action %s by agent %s failed: %s", action_type, agent.agent_id, e)

        return events

    # ---- action handlers ---------------------------------------------------

    def _move(self, agent, action, ws, tick):
        target = action.get("target_position", {})
        tx, ty = target.get("x", agent.position.x), target.get("y", agent.position.y)
        tx = max(0, min(ws.width - 1, tx))
        ty = max(0, min(ws.height - 1, ty))
        cell = ws.cells.get((tx, ty))
        if cell and cell.passable:
            agent.position = Position(x=tx, y=ty)
            agent.vitals.energy = max(0, agent.vitals.energy - 2)
        return []

    def _gather(self, agent, action, ws, tick):
        resource = action.get("resource", "food")
        cell = ws.cells.get((agent.position.x, agent.position.y))
        if not cell:
            return []
        amount = min(
            getattr(cell.resources, resource, 0),
            10 + agent.skills.farming * 5,
        )
        setattr(cell.resources, resource, getattr(cell.resources, resource, 0) - amount)
        current = getattr(agent.resources, resource, 0)
        setattr(agent.resources, resource, current + amount)
        agent.vitals.energy = max(0, agent.vitals.energy - 5)
        return []

    def _trade(self, agent, action, agents, ws, tick):
        target_id = action.get("target_agent_id")
        target = agents.get(target_id)
        if not target:
            return []
        offer = action.get("offer", {})
        request = action.get("request", {})
        # Simple direct transfer if target has resources
        for res, amt in offer.items():
            a_has = getattr(agent.resources, res, 0)
            t_wants = getattr(target.resources, res, 0)
            if a_has >= amt:
                setattr(agent.resources, res, a_has - amt)
                setattr(target.resources, res, t_wants + amt)
        for res, amt in request.items():
            t_has = getattr(target.resources, res, 0)
            if t_has >= amt:
                setattr(target.resources, res, t_has - amt)
                a_has = getattr(agent.resources, res, 0)
                setattr(agent.resources, res, a_has + amt)
        # Update trust
        trust_delta = 0.05
        if agent.agent_id in target.trust_map:
            target.trust_map[agent.agent_id].score = min(1.0, target.trust_map[agent.agent_id].score + trust_delta)
        return [SimulationEvent(
            event_id=f"trade_{tick}_{agent.agent_id}",
            event_type="trade_completed",
            tick=tick,
            description=f"{agent.agent_id} traded with {target_id}",
            agent_ids=[agent.agent_id, target_id],
        )]

    def _attack(self, agent, action, agents, ws, tick):
        target_id = action.get("target_agent_id")
        target = agents.get(target_id)
        if not target:
            return []
        events = self.conflict.combat.individual_combat(agent, target, ws, tick)
        return events

    def _negotiate(self, agent, action, agents, ws, tick):
        target_id = action.get("target_agent_id")
        target = agents.get(target_id)
        if not target:
            return []
        result = self.social.negotiation.negotiate(agent, target, action.get("terms", {}), tick)
        return []

    def _broadcast(self, agent, action, agents, ws, tick):
        content = action.get("content", "General announcement")
        truth = action.get("truth_value", 0.8)
        emotional = action.get("emotional_charge", 0.3)
        trust_graph = self.social.relationship_graph.get_trust_graph()
        self.information.agent_broadcasts(
            agent, content, InformationType.BROADCAST,
            truth, emotional, tick, agents, trust_graph
        )

    def _bribe(self, agent, action, agents, tick):
        target_id = action.get("target_agent_id")
        target = agents.get(target_id)
        if not target:
            return []
        amount = min(action.get("amount", 10), agent.resources.money)
        agent.resources.money -= amount
        target.resources.money += amount
        if target_id in agent.trust_map:
            agent.trust_map[target_id].score = min(1.0, agent.trust_map[target_id].score + 0.1)
        if agent.agent_id in target.trust_map:
            target.trust_map[agent.agent_id].score = min(1.0, target.trust_map[agent.agent_id].score + 0.15)
        return []

    def _spy(self, agent, action, agents, tick):
        target_id = action.get("target_agent_id")
        target = agents.get(target_id)
        if not target:
            return []
        # Gain information about target
        info_key = f"spy_info_{target_id}_{tick}"
        agent.memory.semantic_memory[info_key] = {
            "type": "intelligence",
            "subject": target_id,
            "resources": {k: v for k, v in target.resources.__dict__.items()},
            "vitals": {k: v for k, v in target.vitals.__dict__.items()},
            "faction": target.faction_id,
            "tick": tick,
        }
        return [SimulationEvent(
            event_id=f"spy_{tick}_{agent.agent_id}",
            event_type="espionage",
            tick=tick,
            description=f"Agent {agent.agent_id} spied on {target_id}",
            agent_ids=[agent.agent_id, target_id],
        )]

    def _build(self, agent, action, ws, tick):
        from ..core.models import Building
        if agent.resources.tools < 5 or agent.resources.energy < 20:
            return []
        agent.resources.tools -= 5
        agent.resources.energy -= 20
        agent.vitals.energy = max(0, agent.vitals.energy - 20)
        bid = f"building_{tick}_{agent.agent_id}"
        building = Building(
            building_id=bid,
            building_type=action.get("building_type", "shelter"),
            owner_id=agent.agent_id,
            position=agent.position,
            health=100,
            capacity=10,
        )
        ws.buildings[bid] = building
        cell = ws.cells.get((agent.position.x, agent.position.y))
        if cell:
            cell.building_id = bid
        return [SimulationEvent(
            event_id=f"build_{tick}_{agent.agent_id}",
            event_type="building_constructed",
            tick=tick,
            description=f"Agent {agent.agent_id} built {building.building_type}",
            agent_ids=[agent.agent_id],
            position=agent.position,
        )]

    def _farm(self, agent, action, ws, tick):
        cell = ws.cells.get((agent.position.x, agent.position.y))
        if not cell:
            return []
        bonus = agent.skills.farming * 3
        cell.resources.food = min(100, cell.resources.food + bonus)
        agent.vitals.energy = max(0, agent.vitals.energy - 8)
        return []

    def _steal(self, agent, action, agents, ws, tick):
        return self.conflict.combat.resolve_theft(agent, agents, ws, tick)

    def _recruit(self, agent, action, agents, tick):
        target_id = action.get("target_agent_id")
        target = agents.get(target_id)
        if not target or not agent.faction_id:
            return []
        # Recruit if target trusts agent and is not in a faction
        trust = agent.trust_map.get(target_id)
        if trust and trust.score > 0.6 and not target.faction_id:
            target.faction_id = agent.faction_id
            return [SimulationEvent(
                event_id=f"recruit_{tick}_{target_id}",
                event_type="agent_recruited",
                tick=tick,
                description=f"{target_id} recruited into faction {agent.faction_id}",
                agent_ids=[agent.agent_id, target_id],
            )]
        return []

    def _research(self, agent, action, tick):
        field_name = action.get("field", "reasoning")
        skill_val = getattr(agent.skills, field_name, None)
        if skill_val is not None:
            improvement = 0.01 * agent.skills.reasoning
            setattr(agent.skills, field_name, min(1.0, skill_val + improvement))
        return []

    def _heal(self, agent, action, agents, tick):
        target_id = action.get("target_agent_id", agent.agent_id)
        target = agents.get(target_id, agent)
        if agent.resources.medicine >= 5:
            agent.resources.medicine -= 5
            heal_amount = 20 + agent.skills.medicine * 15
            target.vitals.health = min(100, target.vitals.health + heal_amount)
        return []

    def _lobby(self, agent, action, ws, tick):
        # Attempt to influence law/governance
        law_id = action.get("law_id")
        if not law_id:
            return []
        amount_spent = min(action.get("amount", 5), agent.resources.money)
        agent.resources.money -= amount_spent
        ws.institution_health = min(100, getattr(ws, "institution_health", 80) + amount_spent * 0.1)
        return []


# ---------------------------------------------------------------------------
# Main Simulation Service
# ---------------------------------------------------------------------------

class SimulationService:
    """
    Top-level simulation orchestrator.
    Coordinates all subsystem engines through async tick loops.
    """

    def __init__(self, config: SimulationConfig, settings: SimulationSettings):
        self.config = config
        self.settings = settings
        self.status = SimulationStatus.IDLE
        self.tick = 0

        # Initialize subsystems
        self.world = WorldEngine(config.world_width, config.world_height)
        self.agent_factory = AgentFactory()
        self.agent_registry = AgentRegistry()
        self.lifecycle = AgentLifecycleManager()
        self.cognitive = CognitiveEngine()
        self.economy = EconomyEngine()
        self.social = SocialSystem()
        self.conflict = ConflictEngine()
        self.governance = GovernanceSystem()
        self.information = InformationSystem()
        self.analytics = AnalyticsEngine(snapshot_interval=config.analytics_interval)
        self.scenarios = ScenarioEngine()

        # Shared state
        self.agents: Dict[str, Agent] = {}
        self.world_state: Optional[WorldState] = None
        self.trust_graph: Dict[str, Dict[str, float]] = {}

        # Metrics
        self.metrics_history: List[SimulationMetrics] = []
        self.event_log: List[SimulationEvent] = []

        # Control
        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None

    # ---- initialization ----------------------------------------------------

    def initialize(self):
        """Set up world, agents, and all subsystems."""
        import random
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
            np.random.seed(self.config.random_seed)

        logger.info("Initializing simulation %s", self.config.sim_id)

        # World
        self.world_state = self.world.initialize()

        # Agents
        population = self.agent_factory.generate_population(
            self.config.initial_agents,
            self.world_state,
        )
        for agent in population:
            self.agents[agent.agent_id] = agent
            self.agent_registry.register(agent)

        # Subsystem init
        self.economy.initialize(self.world_state)
        self.social.initialize(self.agents)
        self.governance.initialize(self.world_state)
        self.information.initialize(self.agents)

        # Build action executor
        self.action_executor = ActionExecutor(
            self.world, self.economy, self.social,
            self.conflict, self.governance, self.information,
        )

        # Build initial trust graph
        self._rebuild_trust_graph()

        self.status = SimulationStatus.READY
        logger.info(
            "Simulation initialized: %d agents, %dx%d world",
            len(self.agents), self.config.world_width, self.config.world_height
        )

    def _rebuild_trust_graph(self):
        self.trust_graph = {}
        for aid, agent in self.agents.items():
            self.trust_graph[aid] = {
                tid: entry.score
                for tid, entry in agent.trust_map.items()
                if tid in self.agents
            }

    # ---- tick loop ---------------------------------------------------------

    async def run_async(self):
        """Async simulation loop."""
        self.status = SimulationStatus.RUNNING
        self._running = True
        logger.info("Simulation %s started", self.config.sim_id)

        try:
            while self._running and self.tick < self.config.max_ticks:
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue

                t0 = time.monotonic()
                await self._tick_async()
                elapsed = (time.monotonic() - t0) * 1000

                # Rate limiting
                sleep_ms = max(0, self.config.tick_interval_ms - elapsed)
                if sleep_ms > 0:
                    await asyncio.sleep(sleep_ms / 1000)

        except asyncio.CancelledError:
            logger.info("Simulation cancelled")
        except Exception as e:
            logger.error("Simulation error: %s", e, exc_info=True)
            self.status = SimulationStatus.ERROR
            raise
        finally:
            self.status = SimulationStatus.STOPPED
            logger.info("Simulation %s stopped at tick %d", self.config.sim_id, self.tick)

    def run_sync(self, n_ticks: int = 1):
        """Synchronous tick execution for testing."""
        self.status = SimulationStatus.RUNNING
        for _ in range(n_ticks):
            if self.tick >= self.config.max_ticks:
                break
            self._tick_sync()
        self.status = SimulationStatus.PAUSED

    async def _tick_async(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._tick_sync)

    def _tick_sync(self):
        """Single synchronous tick — all subsystems in order."""
        self.tick += 1
        tick = self.tick
        all_events: List[SimulationEvent] = []

        # 1. World tick (weather, resources, disasters)
        world_events = self.world.tick(tick, self.world_state)
        all_events.extend(world_events)

        # 2. Agent lifecycle (metabolism, death, spawning)
        lifecycle_events = self.lifecycle.tick(
            tick, self.agents, self.world_state,
            self.agent_factory, self.agent_registry, self.config.max_agents
        )
        all_events.extend(lifecycle_events)

        # 3. Cognitive engine (perception → planning → action decisions)
        agent_actions: Dict[str, Dict] = {}
        for aid, agent in list(self.agents.items()):
            if agent.vitals.health <= 0:
                continue
            try:
                action = self.cognitive.tick(
                    tick, agent, self.agents, self.world_state, self.social
                )
                agent_actions[aid] = action
            except Exception as e:
                logger.warning("Cognitive tick failed for %s: %s", aid, e)

        # 4. Execute actions
        for aid, action in agent_actions.items():
            agent = self.agents.get(aid)
            if not agent or agent.vitals.health <= 0:
                continue
            try:
                events = self.action_executor.execute(
                    agent, action, self.agents, self.world_state, tick
                )
                all_events.extend(events)
            except Exception as e:
                logger.warning("Action execution failed for %s: %s", aid, e)

        # 5. Economy tick
        economy_events = self.economy.tick(tick, self.agents, self.world_state)
        all_events.extend(economy_events)

        # 6. Social tick
        social_events = self.social.tick(tick, self.agents, self.world_state)
        all_events.extend(social_events)

        # 7. Conflict tick
        conflict_events = self.conflict.tick(tick, self.agents, self.world_state)
        all_events.extend(conflict_events)

        # 8. Governance tick
        gov_events = self.governance.tick(tick, self.agents, self.world_state)
        all_events.extend(gov_events)

        # 9. Information tick
        self._rebuild_trust_graph()
        self.information.tick(tick, self.agents, self.world_state, self.trust_graph)

        # 10. Scenario tick
        scenario_events = self.scenarios.tick(tick, self.agents, self.world_state)
        all_events.extend(scenario_events)

        # 11. Analytics tick
        pol = {
            topic: vals[-1] if vals else 0.0
            for topic, vals in self.information.belief_engine.topic_history.items()
        }
        for event in all_events:
            self.analytics.record_event(event)
        snap = self.analytics.tick(
            tick, self.agents, self.world_state, self.trust_graph, pol
        )

        # 12. Log events
        if self.config.log_events:
            self.event_log.extend(all_events)
            if len(self.event_log) > 50000:
                self.event_log = self.event_log[-50000:]

        # 13. Auto-scenario injection (random events)
        if self.config.auto_scenarios and tick % 200 == 0 and tick > 0:
            self._maybe_inject_auto_scenario(tick)

        if tick % 50 == 0:
            self._log_tick_summary(tick, snap)

    def _maybe_inject_auto_scenario(self, tick: int):
        """Randomly inject scenarios based on world state."""
        import random
        snap = self.analytics.get_latest_snapshot()
        if not snap:
            return

        # High inequality → political instability
        if snap.gini_coefficient > 0.6 and random.random() < 0.3:
            self.scenarios.inject_scenario(ScenarioType.POLITICAL_INSTABILITY, severity=0.5, tick=tick)

        # Low stability → resource collapse
        elif snap.stability_index < 0.3 and random.random() < 0.2:
            self.scenarios.inject_scenario(ScenarioType.RESOURCE_COLLAPSE, severity=0.4, tick=tick)

        # Random plague
        elif random.random() < 0.05:
            self.scenarios.inject_scenario(ScenarioType.PLAGUE, severity=0.4, tick=tick)

    def _log_tick_summary(self, tick: int, snap):
        alive = sum(1 for a in self.agents.values() if a.vitals.health > 0)
        logger.info(
            "Tick %d | Agents: %d alive | Events: %d | Scenarios: %d active",
            tick, alive, len(self.event_log), len(self.scenarios.active_scenarios)
        )

    # ---- control API -------------------------------------------------------

    async def start(self):
        if self.status not in (SimulationStatus.READY, SimulationStatus.STOPPED, SimulationStatus.PAUSED):
            return
        if self.status == SimulationStatus.READY:
            self.initialize()
        self._task = asyncio.create_task(self.run_async())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def pause(self):
        self._paused = True
        self.status = SimulationStatus.PAUSED

    def resume(self):
        self._paused = False
        self.status = SimulationStatus.RUNNING

    def inject_scenario(self, scenario_type: str, severity: float = 0.7, **kwargs) -> Dict:
        try:
            st = ScenarioType(scenario_type)
        except ValueError:
            return {"error": f"Unknown scenario type: {scenario_type}"}
        scenario = self.scenarios.inject_scenario(st, severity=severity, tick=self.tick, **kwargs)
        return {"scenario_id": scenario.scenario_id, "name": scenario.name}

    def modify_agent(self, agent_id: str, modifications: Dict) -> Dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": "Agent not found"}
        for key, value in modifications.items():
            if hasattr(agent.vitals, key):
                setattr(agent.vitals, key, value)
            elif hasattr(agent.resources, key):
                setattr(agent.resources, key, value)
        return {"success": True, "agent_id": agent_id}

    def get_state_snapshot(self) -> Dict:
        """Full state dump for API consumers."""
        snap = self.analytics.get_latest_snapshot()
        alive_agents = {aid: a for aid, a in self.agents.items() if a.vitals.health > 0}

        return {
            "sim_id": self.config.sim_id,
            "tick": self.tick,
            "status": self.status.value,
            "agents": {
                aid: {
                    "agent_id": aid,
                    "type": a.agent_type.value,
                    "position": {"x": a.position.x, "y": a.position.y},
                    "health": a.vitals.health,
                    "energy": a.vitals.energy,
                    "stress": a.vitals.stress,
                    "faction": a.faction_id,
                    "resources": {k: round(v, 2) for k, v in a.resources.__dict__.items()},
                }
                for aid, a in list(alive_agents.items())[:100]  # limit for API response
            },
            "world": {
                "width": self.world_state.width,
                "height": self.world_state.height,
                "tick": self.world_state.tick,
                "season": self.world_state.season.value,
                "weather": self.world_state.current_weather.value,
                "day": self.world_state.day,
                "year": self.world_state.year,
                "active_disasters": [d.value for d in self.world_state.active_disasters],
            },
            "analytics": self.analytics.export_summary() if snap else {},
            "scenarios": self.scenarios.get_status(),
            "information": self.information.get_info_summary(),
            "economy": self.economy.get_market_summary() if hasattr(self.economy, "get_market_summary") else {},
            "recent_events": [
                {
                    "tick": e.tick,
                    "type": e.event_type,
                    "description": e.description,
                }
                for e in self.event_log[-50:]
            ],
        }

    def get_agent_detail(self, agent_id: str) -> Optional[Dict]:
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "type": agent.agent_type.value,
            "position": {"x": agent.position.x, "y": agent.position.y},
            "vitals": {k: round(v, 2) for k, v in agent.vitals.__dict__.items()},
            "resources": {k: round(v, 2) for k, v in agent.resources.__dict__.items()},
            "personality": {k: round(v, 2) for k, v in agent.personality.__dict__.items()},
            "skills": {k: round(v, 2) for k, v in agent.skills.__dict__.items()},
            "faction": agent.faction_id,
            "goals": [{"type": g.goal_type, "priority": g.priority} for g in agent.goals],
            "trust_map": {
                tid: round(entry.score, 2)
                for tid, entry in list(agent.trust_map.items())[:20]
            },
            "memory": {
                "short_term": len(agent.memory.short_term),
                "episodic": len(agent.memory.episodic),
                "semantic": len(agent.memory.semantic_memory),
                "social": len(agent.memory.social_memory),
            },
        }

    def get_analytics(self) -> Dict:
        return self.analytics.export_summary()

    def get_world_heatmap(self, resource: str = "food") -> List[List[float]]:
        """Return 2D grid of resource values for frontend visualization."""
        grid = [[0.0] * self.world_state.width for _ in range(self.world_state.height)]
        for (x, y), cell in self.world_state.cells.items():
            val = getattr(cell.resources, resource, 0)
            if 0 <= y < self.world_state.height and 0 <= x < self.world_state.width:
                grid[y][x] = val
        return grid
