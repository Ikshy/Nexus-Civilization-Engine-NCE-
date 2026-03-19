"""
Nexus Civilization Engine - Core Data Models
All dataclasses used across simulation subsystems.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any
from uuid import uuid4, UUID
import time

from backend.core.enums import (
    AgentType, AgentState, ResourceType, TerrainType, ZoneType,
    WeatherType, Season, RelationshipType, ActionType,
    InformationType, BeliefStrength, CrimeType, GovernanceType
)


def new_id() -> str:
    return str(uuid4())


# ─────────────────────────── Position ───────────────────────────────

@dataclass
class Position:
    x: int
    y: int

    def distance_to(self, other: Position) -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def neighbors(self, radius: int = 1) -> list[Position]:
        return [
            Position(self.x + dx, self.y + dy)
            for dx in range(-radius, radius + 1)
            for dy in range(-radius, radius + 1)
            if not (dx == 0 and dy == 0)
        ]

    def __hash__(self):
        return hash((self.x, self.y))


# ─────────────────────────── Resources ──────────────────────────────

@dataclass
class ResourceBundle:
    resources: dict[ResourceType, float] = field(default_factory=dict)

    def get(self, resource: ResourceType) -> float:
        return self.resources.get(resource, 0.0)

    def set(self, resource: ResourceType, amount: float) -> None:
        self.resources[resource] = max(0.0, amount)

    def add(self, resource: ResourceType, amount: float) -> None:
        self.resources[resource] = max(0.0, self.resources.get(resource, 0.0) + amount)

    def subtract(self, resource: ResourceType, amount: float) -> bool:
        current = self.resources.get(resource, 0.0)
        if current < amount:
            return False
        self.resources[resource] = current - amount
        return True

    def total_value(self, prices: dict[ResourceType, float]) -> float:
        return sum(self.get(r) * prices.get(r, 1.0) for r in ResourceType)

    def copy(self) -> ResourceBundle:
        return ResourceBundle(resources=dict(self.resources))


# ─────────────────────────── Agent Models ───────────────────────────

@dataclass
class PersonalityTraits:
    greed: float = 0.5          # 0-1: tendency to hoard resources
    altruism: float = 0.5       # 0-1: willingness to help others
    aggression: float = 0.5     # 0-1: tendency toward conflict
    deception: float = 0.5      # 0-1: willingness to lie/betray
    loyalty: float = 0.5        # 0-1: commitment to alliances
    curiosity: float = 0.5      # 0-1: willingness to explore/innovate
    risk_tolerance: float = 0.5 # 0-1: risk appetite
    charisma: float = 0.5       # 0-1: social influence
    patience: float = 0.5       # 0-1: long-term thinking
    conformity: float = 0.5     # 0-1: adherence to norms


@dataclass
class AgentSkills:
    combat: float = 0.1
    farming: float = 0.1
    trading: float = 0.1
    crafting: float = 0.1
    leadership: float = 0.1
    espionage: float = 0.1
    diplomacy: float = 0.1
    science: float = 0.1
    building: float = 0.1
    medicine: float = 0.1


@dataclass
class AgentVitals:
    health: float = 100.0
    energy: float = 100.0
    stress: float = 0.0
    hunger: float = 0.0
    thirst: float = 0.0
    morale: float = 50.0


@dataclass
class AgentGoal:
    goal_id: str = field(default_factory=new_id)
    description: str = ""
    priority: float = 1.0
    target_agent_id: Optional[str] = None
    target_position: Optional[Position] = None
    target_resource: Optional[ResourceType] = None
    target_amount: float = 0.0
    deadline_tick: Optional[int] = None
    is_achieved: bool = False
    is_hidden: bool = False      # Hidden from other agents


@dataclass
class MemoryEntry:
    entry_id: str = field(default_factory=new_id)
    tick: int = 0
    event_type: str = ""
    subject_id: Optional[str] = None  # Agent this memory is about
    content: dict[str, Any] = field(default_factory=dict)
    emotional_weight: float = 0.0    # -1 to 1 (negative = bad, positive = good)
    decay_rate: float = 0.01
    strength: float = 1.0            # Fades over time


@dataclass
class TrustEntry:
    agent_id: str = ""
    trust_score: float = 0.0          # -1.0 to 1.0
    interaction_count: int = 0
    last_interaction_tick: int = 0
    betrayal_count: int = 0
    cooperation_count: int = 0


@dataclass
class AgentBelief:
    belief_id: str = field(default_factory=new_id)
    topic: str = ""
    content: str = ""
    strength: BeliefStrength = BeliefStrength.WEAK
    source_agent_id: Optional[str] = None
    is_true: bool = True          # Ground truth (hidden from agents)
    adopted_tick: int = 0


@dataclass
class Agent:
    agent_id: str = field(default_factory=new_id)
    name: str = ""
    agent_type: AgentType = AgentType.WORKER
    state: AgentState = AgentState.IDLE

    # Physical
    position: Position = field(default_factory=lambda: Position(0, 0))
    age: int = 0
    alive: bool = True

    # Attributes
    personality: PersonalityTraits = field(default_factory=PersonalityTraits)
    skills: AgentSkills = field(default_factory=AgentSkills)
    vitals: AgentVitals = field(default_factory=AgentVitals)

    # Economy
    inventory: ResourceBundle = field(default_factory=ResourceBundle)
    net_worth: float = 0.0

    # Social
    reputation: float = 50.0
    faction_id: Optional[str] = None
    alliance_ids: list[str] = field(default_factory=list)
    trust_map: dict[str, TrustEntry] = field(default_factory=dict)
    relationship_map: dict[str, RelationshipType] = field(default_factory=dict)

    # Cognitive
    short_term_memory: list[MemoryEntry] = field(default_factory=list)
    episodic_memory: list[MemoryEntry] = field(default_factory=list)
    semantic_memory: dict[str, Any] = field(default_factory=dict)  # World knowledge
    social_memory: dict[str, list[MemoryEntry]] = field(default_factory=dict)  # Per-agent
    emotional_state: dict[str, float] = field(default_factory=dict)  # Emotions

    # Goals
    short_term_goals: list[AgentGoal] = field(default_factory=list)
    long_term_goals: list[AgentGoal] = field(default_factory=list)
    hidden_intentions: list[AgentGoal] = field(default_factory=list)

    # Beliefs and ideology
    beliefs: list[AgentBelief] = field(default_factory=list)
    ideology: dict[str, float] = field(default_factory=dict)  # e.g. {"equality": 0.8}

    # History
    action_history: list[dict[str, Any]] = field(default_factory=list)
    crimes_committed: list[CrimeType] = field(default_factory=list)
    is_imprisoned: bool = False
    imprisonment_end_tick: Optional[int] = None

    # Metadata
    created_tick: int = 0
    last_active_tick: int = 0

    def is_alive(self) -> bool:
        return self.alive and self.vitals.health > 0

    def get_trust(self, agent_id: str) -> float:
        entry = self.trust_map.get(agent_id)
        return entry.trust_score if entry else 0.0


# ─────────────────────────── World Models ───────────────────────────

@dataclass
class Cell:
    position: Position
    terrain: TerrainType = TerrainType.PLAINS
    zone: ZoneType = ZoneType.NEUTRAL
    resources: ResourceBundle = field(default_factory=ResourceBundle)
    occupant_ids: list[str] = field(default_factory=list)
    building_ids: list[str] = field(default_factory=list)
    pollution: float = 0.0
    fertility: float = 1.0
    contested: bool = False
    controller_faction: Optional[str] = None


@dataclass
class WorldState:
    tick: int = 0
    day: int = 0
    season: Season = Season.SPRING
    year: int = 0
    weather: WeatherType = WeatherType.CLEAR
    temperature: float = 20.0
    active_disasters: list[dict[str, Any]] = field(default_factory=list)
    global_stability: float = 1.0
    total_population: int = 0
    dominant_faction: Optional[str] = None


@dataclass
class Building:
    building_id: str = field(default_factory=new_id)
    name: str = ""
    building_type: str = ""
    position: Position = field(default_factory=lambda: Position(0, 0))
    owner_id: Optional[str] = None
    faction_id: Optional[str] = None
    health: float = 100.0
    capacity: int = 10
    production_rate: dict[ResourceType, float] = field(default_factory=dict)
    built_tick: int = 0


# ─────────────────────────── Economy Models ─────────────────────────

@dataclass
class MarketListing:
    listing_id: str = field(default_factory=new_id)
    seller_id: str = ""
    resource: ResourceType = ResourceType.FOOD
    quantity: float = 0.0
    price_per_unit: float = 1.0
    is_black_market: bool = False
    expires_tick: Optional[int] = None
    created_tick: int = 0


@dataclass
class TradeOffer:
    offer_id: str = field(default_factory=new_id)
    proposer_id: str = ""
    recipient_id: str = ""
    offered: ResourceBundle = field(default_factory=ResourceBundle)
    requested: ResourceBundle = field(default_factory=ResourceBundle)
    is_accepted: Optional[bool] = None
    created_tick: int = 0
    expires_tick: Optional[int] = None
    is_deceptive: bool = False  # Hidden flag


@dataclass
class MarketPrice:
    resource: ResourceType = ResourceType.FOOD
    base_price: float = 1.0
    current_price: float = 1.0
    supply: float = 100.0
    demand: float = 100.0
    price_history: list[float] = field(default_factory=list)
    last_updated_tick: int = 0


@dataclass
class DebtEntry:
    debt_id: str = field(default_factory=new_id)
    debtor_id: str = ""
    creditor_id: str = ""
    amount: float = 0.0
    interest_rate: float = 0.05
    due_tick: int = 0
    is_paid: bool = False
    is_defaulted: bool = False


# ─────────────────────────── Social Models ──────────────────────────

@dataclass
class Faction:
    faction_id: str = field(default_factory=new_id)
    name: str = ""
    leader_id: Optional[str] = None
    member_ids: list[str] = field(default_factory=list)
    territory: list[Position] = field(default_factory=list)
    resources: ResourceBundle = field(default_factory=ResourceBundle)
    reputation: float = 50.0
    ideology: dict[str, float] = field(default_factory=dict)
    ally_faction_ids: list[str] = field(default_factory=list)
    enemy_faction_ids: list[str] = field(default_factory=list)
    governance_type: GovernanceType = GovernanceType.DEMOCRACY
    laws: list[str] = field(default_factory=list)
    formed_tick: int = 0


@dataclass
class GossipEntry:
    gossip_id: str = field(default_factory=new_id)
    originator_id: str = ""
    subject_id: str = ""
    content: str = ""
    info_type: InformationType = InformationType.RUMOR
    is_true: bool = True
    spread_count: int = 0
    believers: list[str] = field(default_factory=list)
    created_tick: int = 0
    decay_rate: float = 0.05


@dataclass
class NegotiationState:
    negotiation_id: str = field(default_factory=new_id)
    participants: list[str] = field(default_factory=list)
    topic: str = ""
    current_offer: Optional[TradeOffer] = None
    rounds: int = 0
    max_rounds: int = 5
    status: str = "open"  # open, agreed, failed
    created_tick: int = 0


# ─────────────────────────── Governance Models ──────────────────────

@dataclass
class Law:
    law_id: str = field(default_factory=new_id)
    name: str = ""
    description: str = ""
    crime_type: CrimeType = CrimeType.THEFT
    penalty: dict[str, Any] = field(default_factory=dict)  # {"fine": 50, "imprisonment": 10}
    faction_id: Optional[str] = None
    enacted_tick: int = 0
    is_active: bool = True
    enforcement_rate: float = 0.8  # 0-1 probability of enforcement


@dataclass
class CourtCase:
    case_id: str = field(default_factory=new_id)
    defendant_id: str = ""
    crime_type: CrimeType = CrimeType.THEFT
    evidence_strength: float = 0.5
    verdict: Optional[str] = None  # "guilty", "not_guilty"
    penalty_applied: bool = False
    tick: int = 0


# ─────────────────────────── Events ─────────────────────────────────

@dataclass
class SimulationEvent:
    event_id: str = field(default_factory=new_id)
    tick: int = 0
    event_type: str = ""
    severity: float = 1.0
    affected_agents: list[str] = field(default_factory=list)
    affected_positions: list[Position] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class NewsArticle:
    article_id: str = field(default_factory=new_id)
    headline: str = ""
    content: str = ""
    info_type: InformationType = InformationType.NEWS
    author_id: Optional[str] = None
    faction_id: Optional[str] = None
    is_propaganda: bool = False
    truth_score: float = 1.0  # 0 = pure disinformation
    reach: int = 0
    believers: list[str] = field(default_factory=list)
    published_tick: int = 0


# ─────────────────────────── Analytics ──────────────────────────────

@dataclass
class SimulationMetrics:
    tick: int = 0
    population: int = 0
    alive_agents: int = 0
    total_wealth: float = 0.0
    gini_coefficient: float = 0.0
    average_trust: float = 0.0
    conflict_count: int = 0
    trade_volume: float = 0.0
    stability_index: float = 1.0
    information_entropy: float = 0.0
    faction_count: int = 0
    crime_rate: float = 0.0
    average_happiness: float = 50.0
    resource_scarcity: dict[str, float] = field(default_factory=dict)
