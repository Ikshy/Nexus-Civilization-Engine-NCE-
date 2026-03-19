"""
Nexus Civilization Engine - Agent System
Agent creation, registry, and lifecycle management.
"""
from __future__ import annotations
import random
import logging
from typing import Optional, Iterator
from collections import defaultdict

from backend.core.enums import (
    AgentType, AgentState, ResourceType, RelationshipType,
    MAX_HEALTH, MAX_ENERGY, MAX_STRESS
)
from backend.core.models import (
    Agent, Position, PersonalityTraits, AgentSkills, AgentVitals,
    ResourceBundle, AgentGoal, MemoryEntry, TrustEntry
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# ─────────────────────────── Name Generator ─────────────────────────

FIRST_NAMES = [
    "Aria", "Brom", "Cael", "Deva", "Elix", "Fyra", "Gorn", "Hale",
    "Iris", "Jace", "Kira", "Lorn", "Mira", "Nox", "Ora", "Pike",
    "Quen", "Rael", "Sora", "Tarn", "Ula", "Vex", "Wren", "Xara",
    "Yeva", "Zorn", "Astra", "Bane", "Cris", "Dael", "Eron", "Faye",
    "Gael", "Haven", "Ivan", "Jana", "Kane", "Lyra", "Marc", "Nova",
]

LAST_NAMES = [
    "Stone", "Vale", "Crest", "Ford", "Glen", "Hart", "Isle", "Jade",
    "Knox", "Lake", "Moor", "Nile", "Oak", "Peak", "Reed", "Shaw",
    "Thorn", "Ash", "Blaze", "Cliff", "Dusk", "Edge", "Fern", "Gale",
    "Haze", "Ink", "Jet", "Kern", "Lark", "Marsh", "North", "Ord",
]


def generate_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


# ─────────────────────────── Trait Profiles ─────────────────────────

AGENT_TYPE_TRAIT_PROFILES = {
    AgentType.WORKER:    PersonalityTraits(greed=0.3, altruism=0.6, aggression=0.2, deception=0.1, loyalty=0.7),
    AgentType.TRADER:    PersonalityTraits(greed=0.7, altruism=0.4, aggression=0.3, deception=0.5, loyalty=0.4, charisma=0.7),
    AgentType.LEADER:    PersonalityTraits(greed=0.5, altruism=0.5, aggression=0.4, deception=0.4, loyalty=0.6, charisma=0.8, patience=0.7),
    AgentType.SCIENTIST: PersonalityTraits(greed=0.3, altruism=0.6, aggression=0.1, deception=0.2, curiosity=0.9, patience=0.8),
    AgentType.BUILDER:   PersonalityTraits(greed=0.4, altruism=0.5, aggression=0.2, deception=0.1, loyalty=0.7, patience=0.7),
    AgentType.SPY:       PersonalityTraits(greed=0.5, altruism=0.2, aggression=0.5, deception=0.9, loyalty=0.3, risk_tolerance=0.8),
    AgentType.FARMER:    PersonalityTraits(greed=0.3, altruism=0.6, aggression=0.2, deception=0.1, loyalty=0.8, patience=0.8),
    AgentType.THIEF:     PersonalityTraits(greed=0.8, altruism=0.1, aggression=0.6, deception=0.8, loyalty=0.2, risk_tolerance=0.7),
    AgentType.DIPLOMAT:  PersonalityTraits(greed=0.4, altruism=0.6, aggression=0.1, deception=0.5, charisma=0.9, patience=0.8),
    AgentType.GUARD:     PersonalityTraits(greed=0.2, altruism=0.4, aggression=0.6, deception=0.2, loyalty=0.9, risk_tolerance=0.5),
    AgentType.REBEL:     PersonalityTraits(greed=0.4, altruism=0.6, aggression=0.7, deception=0.5, loyalty=0.5, risk_tolerance=0.8),
    AgentType.MEDIATOR:  PersonalityTraits(greed=0.2, altruism=0.8, aggression=0.1, deception=0.2, charisma=0.8, patience=0.9),
}

AGENT_TYPE_SKILL_PROFILES = {
    AgentType.WORKER:    AgentSkills(crafting=0.6, building=0.5, farming=0.4),
    AgentType.TRADER:    AgentSkills(trading=0.8, diplomacy=0.5, crafting=0.3),
    AgentType.LEADER:    AgentSkills(leadership=0.8, diplomacy=0.6, combat=0.4),
    AgentType.SCIENTIST: AgentSkills(science=0.9, medicine=0.5, crafting=0.4),
    AgentType.BUILDER:   AgentSkills(building=0.9, crafting=0.7, farming=0.2),
    AgentType.SPY:       AgentSkills(espionage=0.9, combat=0.5, diplomacy=0.4),
    AgentType.FARMER:    AgentSkills(farming=0.9, building=0.3, medicine=0.2),
    AgentType.THIEF:     AgentSkills(espionage=0.7, combat=0.5, trading=0.4),
    AgentType.DIPLOMAT:  AgentSkills(diplomacy=0.9, leadership=0.5, trading=0.5),
    AgentType.GUARD:     AgentSkills(combat=0.8, leadership=0.4, espionage=0.3),
    AgentType.REBEL:     AgentSkills(combat=0.7, espionage=0.5, leadership=0.4),
    AgentType.MEDIATOR:  AgentSkills(diplomacy=0.8, leadership=0.6, medicine=0.3),
}

AGENT_TYPE_INITIAL_RESOURCES = {
    AgentType.WORKER:    {ResourceType.FOOD: 20, ResourceType.TOOLS: 5, ResourceType.MONEY: 10},
    AgentType.TRADER:    {ResourceType.FOOD: 15, ResourceType.MONEY: 100, ResourceType.TOOLS: 10},
    AgentType.LEADER:    {ResourceType.FOOD: 30, ResourceType.MONEY: 80, ResourceType.TOOLS: 15},
    AgentType.SCIENTIST: {ResourceType.FOOD: 20, ResourceType.COMPUTING: 10, ResourceType.MONEY: 30},
    AgentType.BUILDER:   {ResourceType.FOOD: 20, ResourceType.TOOLS: 25, ResourceType.RAW_MATERIALS: 30},
    AgentType.SPY:       {ResourceType.FOOD: 15, ResourceType.MONEY: 50, ResourceType.INFORMATION: 20},
    AgentType.FARMER:    {ResourceType.FOOD: 50, ResourceType.WATER: 30, ResourceType.TOOLS: 10},
    AgentType.THIEF:     {ResourceType.FOOD: 10, ResourceType.MONEY: 30, ResourceType.WEAPONS: 5},
    AgentType.DIPLOMAT:  {ResourceType.FOOD: 25, ResourceType.MONEY: 60, ResourceType.INFORMATION: 30},
    AgentType.GUARD:     {ResourceType.FOOD: 20, ResourceType.WEAPONS: 20, ResourceType.MONEY: 25},
    AgentType.REBEL:     {ResourceType.FOOD: 15, ResourceType.WEAPONS: 15, ResourceType.INFORMATION: 10},
    AgentType.MEDIATOR:  {ResourceType.FOOD: 20, ResourceType.MEDICINE: 15, ResourceType.MONEY: 40},
}


class AgentFactory:
    """Creates agents with appropriate traits, skills, and initial state."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self._name_counter: dict[str, int] = defaultdict(int)

    def create(
        self,
        agent_type: AgentType,
        position: Position,
        tick: int = 0,
        name: Optional[str] = None,
        faction_id: Optional[str] = None,
        personality_noise: float = 0.15,
    ) -> Agent:
        """Create a new agent of specified type with randomized traits."""
        name = name or generate_name(self.rng)
        base_personality = AGENT_TYPE_TRAIT_PROFILES[agent_type]
        base_skills = AGENT_TYPE_SKILL_PROFILES[agent_type]

        personality = self._jitter_personality(base_personality, personality_noise)
        skills = self._jitter_skills(base_skills, personality_noise)
        inventory = self._create_initial_inventory(agent_type)

        agent = Agent(
            name=name,
            agent_type=agent_type,
            position=position,
            personality=personality,
            skills=skills,
            vitals=AgentVitals(
                health=MAX_HEALTH * self.rng.uniform(0.8, 1.0),
                energy=MAX_ENERGY * self.rng.uniform(0.7, 1.0),
                stress=MAX_STRESS * self.rng.uniform(0.0, 0.2),
                morale=self.rng.uniform(40, 70),
            ),
            inventory=inventory,
            reputation=self.rng.uniform(30, 70),
            faction_id=faction_id,
            created_tick=tick,
            last_active_tick=tick,
            age=self.rng.randint(18, 50),
            ideology=self._generate_ideology(),
        )

        # Set initial goals based on type
        agent.short_term_goals = self._generate_initial_goals(agent_type)
        agent.long_term_goals = self._generate_long_term_goals(agent_type)

        logger.debug(f"Created agent: {name} ({agent_type.value}) at {position}")
        return agent

    def _jitter_personality(self, base: PersonalityTraits, noise: float) -> PersonalityTraits:
        def jitter(v: float) -> float:
            return max(0.0, min(1.0, v + self.rng.gauss(0, noise)))

        return PersonalityTraits(
            greed=jitter(base.greed),
            altruism=jitter(base.altruism),
            aggression=jitter(base.aggression),
            deception=jitter(base.deception),
            loyalty=jitter(base.loyalty),
            curiosity=jitter(base.curiosity),
            risk_tolerance=jitter(base.risk_tolerance),
            charisma=jitter(base.charisma),
            patience=jitter(base.patience),
            conformity=jitter(base.conformity),
        )

    def _jitter_skills(self, base: AgentSkills, noise: float) -> AgentSkills:
        def jitter(v: float) -> float:
            return max(0.0, min(1.0, v + self.rng.gauss(0, noise)))

        return AgentSkills(
            combat=jitter(base.combat),
            farming=jitter(base.farming),
            trading=jitter(base.trading),
            crafting=jitter(base.crafting),
            leadership=jitter(base.leadership),
            espionage=jitter(base.espionage),
            diplomacy=jitter(base.diplomacy),
            science=jitter(base.science),
            building=jitter(base.building),
            medicine=jitter(base.medicine),
        )

    def _create_initial_inventory(self, agent_type: AgentType) -> ResourceBundle:
        bundle = ResourceBundle()
        base = AGENT_TYPE_INITIAL_RESOURCES.get(agent_type, {})
        for resource, amount in base.items():
            bundle.set(resource, amount * self.rng.uniform(0.7, 1.3))
        return bundle

    def _generate_ideology(self) -> dict[str, float]:
        return {
            "equality": self.rng.random(),
            "freedom": self.rng.random(),
            "authority": self.rng.random(),
            "tradition": self.rng.random(),
            "progress": self.rng.random(),
            "collectivism": self.rng.random(),
        }

    def _generate_initial_goals(self, agent_type: AgentType) -> list[AgentGoal]:
        goals = []
        # Universal survival goal
        goals.append(AgentGoal(
            description="Survive - maintain food and health",
            priority=1.0,
            target_resource=ResourceType.FOOD,
            target_amount=30.0,
        ))
        # Type-specific goals
        type_goals = {
            AgentType.TRADER: AgentGoal(description="Accumulate wealth", priority=0.8,
                                         target_resource=ResourceType.MONEY, target_amount=200.0),
            AgentType.BUILDER: AgentGoal(description="Build shelter", priority=0.8),
            AgentType.FARMER: AgentGoal(description="Grow food surplus", priority=0.8,
                                         target_resource=ResourceType.FOOD, target_amount=100.0),
            AgentType.GUARD: AgentGoal(description="Protect territory", priority=0.8),
            AgentType.REBEL: AgentGoal(description="Resist authority", priority=0.8, is_hidden=True),
            AgentType.SPY: AgentGoal(description="Gather intelligence", priority=0.8, is_hidden=True),
            AgentType.THIEF: AgentGoal(description="Steal resources", priority=0.8, is_hidden=True),
        }
        if agent_type in type_goals:
            goals.append(type_goals[agent_type])
        return goals

    def _generate_long_term_goals(self, agent_type: AgentType) -> list[AgentGoal]:
        goals = []
        type_goals = {
            AgentType.LEADER: AgentGoal(description="Control faction", priority=0.9),
            AgentType.TRADER: AgentGoal(description="Control market", priority=0.7),
            AgentType.SCIENTIST: AgentGoal(description="Achieve technological breakthrough", priority=0.9),
            AgentType.REBEL: AgentGoal(description="Overthrow governance", priority=0.9, is_hidden=True),
            AgentType.DIPLOMAT: AgentGoal(description="Establish lasting peace", priority=0.8),
        }
        if agent_type in type_goals:
            goals.append(type_goals[agent_type])
        return goals

    def create_population(
        self,
        count: int,
        world_width: int,
        world_height: int,
        tick: int = 0,
        type_distribution: Optional[dict[AgentType, float]] = None,
    ) -> list[Agent]:
        """Create a diverse initial population."""
        if type_distribution is None:
            type_distribution = {
                AgentType.WORKER: 0.25,
                AgentType.FARMER: 0.15,
                AgentType.TRADER: 0.10,
                AgentType.BUILDER: 0.08,
                AgentType.GUARD: 0.08,
                AgentType.SCIENTIST: 0.05,
                AgentType.LEADER: 0.03,
                AgentType.DIPLOMAT: 0.05,
                AgentType.MEDIATOR: 0.05,
                AgentType.THIEF: 0.05,
                AgentType.SPY: 0.04,
                AgentType.REBEL: 0.07,
            }

        types = list(type_distribution.keys())
        weights = list(type_distribution.values())
        agents = []

        for _ in range(count):
            agent_type = self.rng.choices(types, weights=weights)[0]
            pos = Position(
                x=self.rng.randint(0, world_width - 1),
                y=self.rng.randint(0, world_height - 1),
            )
            agents.append(self.create(agent_type, pos, tick))

        logger.info(f"Created population of {count} agents")
        return agents


class AgentRegistry:
    """Thread-safe in-memory registry for all agents."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._by_type: dict[AgentType, set[str]] = defaultdict(set)
        self._by_faction: dict[str, set[str]] = defaultdict(set)
        self._by_position: dict[tuple[int, int], set[str]] = defaultdict(set)

    def register(self, agent: Agent) -> None:
        self._agents[agent.agent_id] = agent
        self._by_type[agent.agent_type].add(agent.agent_id)
        if agent.faction_id:
            self._by_faction[agent.faction_id].add(agent.agent_id)
        self._by_position[(agent.position.x, agent.position.y)].add(agent.agent_id)

    def unregister(self, agent_id: str) -> None:
        agent = self._agents.pop(agent_id, None)
        if agent:
            self._by_type[agent.agent_type].discard(agent_id)
            if agent.faction_id:
                self._by_faction[agent.faction_id].discard(agent_id)
            self._by_position[(agent.position.x, agent.position.y)].discard(agent_id)

    def get(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    def get_all(self) -> list[Agent]:
        return list(self._agents.values())

    def get_alive(self) -> list[Agent]:
        return [a for a in self._agents.values() if a.is_alive()]

    def get_by_type(self, agent_type: AgentType) -> list[Agent]:
        return [self._agents[aid] for aid in self._by_type[agent_type] if aid in self._agents]

    def get_by_faction(self, faction_id: str) -> list[Agent]:
        return [self._agents[aid] for aid in self._by_faction[faction_id] if aid in self._agents]

    def get_nearby(self, pos: Position, radius: int = 3) -> list[Agent]:
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                key = (pos.x + dx, pos.y + dy)
                for aid in self._by_position.get(key, set()):
                    agent = self._agents.get(aid)
                    if agent and agent.is_alive():
                        nearby.append(agent)
        return nearby

    def update_position(self, agent_id: str, old_pos: Position, new_pos: Position) -> None:
        self._by_position[(old_pos.x, old_pos.y)].discard(agent_id)
        self._by_position[(new_pos.x, new_pos.y)].add(agent_id)

    def update_faction(self, agent_id: str, old_faction: Optional[str], new_faction: Optional[str]) -> None:
        if old_faction:
            self._by_faction[old_faction].discard(agent_id)
        if new_faction:
            self._by_faction[new_faction].add(agent_id)

    def count(self) -> int:
        return len(self._agents)

    def alive_count(self) -> int:
        return sum(1 for a in self._agents.values() if a.is_alive())

    def all_agents(self) -> Iterator[Agent]:
        yield from self._agents.values()

    def to_snapshot(self) -> list[dict]:
        """Serialize all agents for API."""
        snapshots = []
        for agent in self._agents.values():
            snapshots.append({
                "agent_id": agent.agent_id,
                "name": agent.name,
                "type": agent.agent_type.value,
                "state": agent.state.value,
                "position": {"x": agent.position.x, "y": agent.position.y},
                "health": agent.vitals.health,
                "energy": agent.vitals.energy,
                "stress": agent.vitals.stress,
                "morale": agent.vitals.morale,
                "reputation": agent.reputation,
                "faction_id": agent.faction_id,
                "alive": agent.alive,
                "age": agent.age,
                "net_worth": agent.net_worth,
                "inventory": {r.value: v for r, v in agent.inventory.resources.items()},
            })
        return snapshots


class AgentLifecycleManager:
    """Manages agent aging, death, reproduction, and state transitions."""

    def __init__(self, registry: AgentRegistry, factory: AgentFactory):
        self.registry = registry
        self.factory = factory
        self._death_events: list[dict] = []
        self._birth_events: list[dict] = []

    def process_tick(self, tick: int, world_conditions: dict) -> list[dict]:
        """Process lifecycle for all agents. Returns events."""
        events = []
        stability = world_conditions.get("stability", 1.0)
        disaster_active = world_conditions.get("disaster_active", False)

        for agent in list(self.registry.get_alive()):
            # Age
            if tick % settings.simulation.day_length_ticks == 0:
                agent.age += 1

            # Metabolic consumption
            self._apply_metabolism(agent)

            # Stress effects
            self._apply_stress_effects(agent)

            # Death checks
            death_event = self._check_death(agent, tick, disaster_active)
            if death_event:
                events.append(death_event)

        # Spawn new agents if population too low
        alive = self.registry.alive_count()
        if alive < settings.simulation.initial_agents * 0.3:
            # Emergency respawn to prevent extinction
            spawn_event = self._emergency_spawn(tick)
            if spawn_event:
                events.append(spawn_event)

        return events

    def _apply_metabolism(self, agent: Agent) -> None:
        """Consume food and water each tick."""
        from backend.core.enums import BASE_METABOLISM
        food_needed = BASE_METABOLISM * (1 + agent.vitals.stress / 100)
        water_needed = BASE_METABOLISM * 0.8

        if not agent.inventory.subtract(ResourceType.FOOD, food_needed):
            agent.vitals.hunger = min(100.0, agent.vitals.hunger + 5.0)
            agent.vitals.health -= 1.0
        else:
            agent.vitals.hunger = max(0.0, agent.vitals.hunger - 2.0)

        if not agent.inventory.subtract(ResourceType.WATER, water_needed):
            agent.vitals.thirst = min(100.0, agent.vitals.thirst + 6.0)
            agent.vitals.health -= 1.5
        else:
            agent.vitals.thirst = max(0.0, agent.vitals.thirst - 3.0)

        # Natural energy recovery when idle
        if agent.state == AgentState.IDLE:
            agent.vitals.energy = min(MAX_ENERGY, agent.vitals.energy + 2.0)
        else:
            agent.vitals.energy = max(0.0, agent.vitals.energy - 1.0)

        # Morale decay
        if agent.vitals.hunger > 50 or agent.vitals.thirst > 50:
            agent.vitals.morale = max(0.0, agent.vitals.morale - 1.0)

    def _apply_stress_effects(self, agent: Agent) -> None:
        if agent.vitals.stress > 80:
            agent.vitals.health -= 0.5
            agent.vitals.morale -= 0.5
        elif agent.vitals.stress > 50:
            agent.vitals.morale -= 0.2
        else:
            agent.vitals.stress = max(0.0, agent.vitals.stress - 0.5)

    def _check_death(self, agent: Agent, tick: int, disaster_active: bool) -> Optional[dict]:
        should_die = False
        cause = "unknown"

        if agent.vitals.health <= 0:
            should_die = True
            cause = "health_depletion"
        elif agent.age > 80 and random.random() < 0.001:
            should_die = True
            cause = "old_age"
        elif disaster_active and random.random() < 0.002:
            should_die = True
            cause = "disaster"

        if should_die:
            agent.alive = False
            agent.state = AgentState.DEAD
            self.registry.unregister(agent.agent_id)
            logger.debug(f"Agent {agent.name} died: {cause}")
            return {
                "event_type": "agent_death",
                "agent_id": agent.agent_id,
                "name": agent.name,
                "cause": cause,
                "tick": tick,
            }
        return None

    def _emergency_spawn(self, tick: int) -> Optional[dict]:
        """Spawn a few new agents to prevent collapse."""
        spawned = []
        world_width = settings.simulation.world_width
        world_height = settings.simulation.world_height
        count = min(10, settings.simulation.initial_agents // 5)
        agents = self.factory.create_population(count, world_width, world_height, tick)
        for agent in agents:
            self.registry.register(agent)
            spawned.append(agent.agent_id)
        logger.info(f"Emergency spawn: {count} agents at tick {tick}")
        return {"event_type": "emergency_spawn", "count": count, "tick": tick, "agents": spawned}

    def kill_agent(self, agent_id: str, cause: str, tick: int) -> Optional[dict]:
        """Forcibly kill an agent (combat, execution, etc.)."""
        agent = self.registry.get(agent_id)
        if not agent or not agent.alive:
            return None
        agent.alive = False
        agent.state = AgentState.DEAD
        agent.vitals.health = 0
        self.registry.unregister(agent_id)
        return {"event_type": "agent_death", "agent_id": agent_id, "name": agent.name, "cause": cause, "tick": tick}

    def imprison_agent(self, agent_id: str, duration_ticks: int, tick: int) -> None:
        agent = self.registry.get(agent_id)
        if agent:
            agent.is_imprisoned = True
            agent.imprisonment_end_tick = tick + duration_ticks
            agent.state = AgentState.IMPRISONED

    def release_agent(self, agent_id: str, tick: int) -> None:
        agent = self.registry.get(agent_id)
        if agent and agent.is_imprisoned:
            if agent.imprisonment_end_tick and tick >= agent.imprisonment_end_tick:
                agent.is_imprisoned = False
                agent.imprisonment_end_tick = None
                agent.state = AgentState.IDLE
