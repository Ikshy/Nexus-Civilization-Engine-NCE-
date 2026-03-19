"""
Nexus Civilization Engine - Core Enumerations and Constants
"""
from enum import Enum, auto
from typing import Final


# ─────────────────────────── Agent Types ────────────────────────────

class AgentType(str, Enum):
    WORKER = "worker"
    TRADER = "trader"
    LEADER = "leader"
    SCIENTIST = "scientist"
    BUILDER = "builder"
    SPY = "spy"
    FARMER = "farmer"
    THIEF = "thief"
    DIPLOMAT = "diplomat"
    GUARD = "guard"
    REBEL = "rebel"
    MEDIATOR = "mediator"


class AgentState(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    TRADING = "trading"
    TRAVELING = "traveling"
    FIGHTING = "fighting"
    HIDING = "hiding"
    NEGOTIATING = "negotiating"
    DEAD = "dead"
    IMPRISONED = "imprisoned"


# ─────────────────────────── Resources ──────────────────────────────

class ResourceType(str, Enum):
    FOOD = "food"
    WATER = "water"
    ENERGY = "energy"
    TOOLS = "tools"
    LAND = "land"
    MONEY = "money"
    INFORMATION = "information"
    LABOR = "labor"
    MEDICINE = "medicine"
    COMPUTING = "computing"
    WEAPONS = "weapons"
    RAW_MATERIALS = "raw_materials"


# ─────────────────────────── World ──────────────────────────────────

class TerrainType(str, Enum):
    PLAINS = "plains"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    DESERT = "desert"
    WATER = "water"
    URBAN = "urban"
    FERTILE = "fertile"
    WASTELAND = "wasteland"


class ZoneType(str, Enum):
    SAFE = "safe"
    NEUTRAL = "neutral"
    DANGEROUS = "dangerous"
    CONTESTED = "contested"
    CONTROLLED = "controlled"


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class WeatherType(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    DROUGHT = "drought"
    BLIZZARD = "blizzard"
    HEATWAVE = "heatwave"


class DisasterType(str, Enum):
    FAMINE = "famine"
    PLAGUE = "plague"
    FLOOD = "flood"
    EARTHQUAKE = "earthquake"
    WAR = "war"
    MARKET_CRASH = "market_crash"
    POLITICAL_COLLAPSE = "political_collapse"
    CLIMATE_DISASTER = "climate_disaster"


# ─────────────────────────── Social ─────────────────────────────────

class RelationshipType(str, Enum):
    ALLY = "ally"
    FRIEND = "friend"
    NEUTRAL = "neutral"
    RIVAL = "rival"
    ENEMY = "enemy"
    SUBORDINATE = "subordinate"
    SUPERIOR = "superior"
    TRADE_PARTNER = "trade_partner"


class ActionType(str, Enum):
    TRADE = "trade"
    ATTACK = "attack"
    COOPERATE = "cooperate"
    BETRAY = "betray"
    NEGOTIATE = "negotiate"
    BRIBE = "bribe"
    THREATEN = "threaten"
    LIE = "lie"
    GOSSIP = "gossip"
    GIFT = "gift"
    STEAL = "steal"
    REPORT_CRIME = "report_crime"
    FORM_ALLIANCE = "form_alliance"
    BREAK_ALLIANCE = "break_alliance"
    VOTE = "vote"
    REBEL = "rebel"
    MIGRATE = "migrate"
    RESEARCH = "research"
    BUILD = "build"
    HARVEST = "harvest"
    REST = "rest"
    SPY_ON = "spy_on"
    SPREAD_RUMOR = "spread_rumor"


# ─────────────────────────── Governance ─────────────────────────────

class GovernanceType(str, Enum):
    ANARCHY = "anarchy"
    DEMOCRACY = "democracy"
    OLIGARCHY = "oligarchy"
    DICTATORSHIP = "dictatorship"
    THEOCRACY = "theocracy"
    TECHNOCRACY = "technocracy"


class LawStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    REPEALED = "repealed"
    VIOLATED = "violated"


class CrimeType(str, Enum):
    THEFT = "theft"
    ASSAULT = "assault"
    CORRUPTION = "corruption"
    TREASON = "treason"
    MARKET_MANIPULATION = "market_manipulation"
    MURDER = "murder"
    BRIBERY = "bribery"
    ESPIONAGE = "espionage"


# ─────────────────────────── Information ────────────────────────────

class InformationType(str, Enum):
    NEWS = "news"
    RUMOR = "rumor"
    PROPAGANDA = "propaganda"
    INTELLIGENCE = "intelligence"
    DISINFORMATION = "disinformation"


class BeliefStrength(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    ABSOLUTE = "absolute"


# ─────────────────────────── Simulation ─────────────────────────────

class SimulationStatus(str, Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class ScenarioType(str, Enum):
    RESOURCE_COLLAPSE = "resource_collapse"
    WAR_ONSET = "war_onset"
    PLAGUE = "plague"
    MARKET_CRASH = "market_crash"
    POLITICAL_INSTABILITY = "political_instability"
    CLIMATE_DISASTER = "climate_disaster"
    GOLDEN_AGE = "golden_age"
    TECHNOLOGICAL_LEAP = "technological_leap"


# ─────────────────────────── Constants ──────────────────────────────

MAX_HEALTH: Final[float] = 100.0
MAX_ENERGY: Final[float] = 100.0
MAX_STRESS: Final[float] = 100.0
MAX_TRUST: Final[float] = 1.0
MIN_TRUST: Final[float] = -1.0
MAX_REPUTATION: Final[float] = 100.0
MIN_REPUTATION: Final[float] = -100.0
MAX_TRAIT_VALUE: Final[float] = 1.0
MIN_TRAIT_VALUE: Final[float] = 0.0

BASE_METABOLISM: Final[float] = 0.5   # food/energy units per tick
BASE_MOVEMENT_COST: Final[float] = 1.0
COMBAT_BASE_DAMAGE: Final[float] = 10.0
GOSSIP_DECAY_RATE: Final[float] = 0.05
INFLATION_DAMPING: Final[float] = 0.1

RESOURCE_REGEN_RATES: Final[dict] = {
    ResourceType.FOOD: 0.3,
    ResourceType.WATER: 0.5,
    ResourceType.ENERGY: 0.2,
    ResourceType.TOOLS: 0.05,
    ResourceType.MEDICINE: 0.1,
    ResourceType.RAW_MATERIALS: 0.15,
}

TERRAIN_RESOURCE_MODIFIERS: Final[dict] = {
    TerrainType.FERTILE: {ResourceType.FOOD: 2.0, ResourceType.WATER: 1.5},
    TerrainType.FOREST: {ResourceType.FOOD: 1.2, ResourceType.RAW_MATERIALS: 2.0},
    TerrainType.MOUNTAIN: {ResourceType.RAW_MATERIALS: 1.8, ResourceType.ENERGY: 1.3},
    TerrainType.DESERT: {ResourceType.FOOD: 0.2, ResourceType.WATER: 0.1, ResourceType.ENERGY: 1.5},
    TerrainType.WATER: {ResourceType.FOOD: 1.5, ResourceType.WATER: 3.0},
    TerrainType.URBAN: {ResourceType.MONEY: 2.0, ResourceType.COMPUTING: 2.5, ResourceType.LABOR: 2.0},
    TerrainType.PLAINS: {ResourceType.FOOD: 1.0, ResourceType.LABOR: 1.2},
    TerrainType.WASTELAND: {ResourceType.FOOD: 0.1, ResourceType.WATER: 0.2},
}

SEASON_MODIFIERS: Final[dict] = {
    Season.SPRING: {ResourceType.FOOD: 1.3, ResourceType.WATER: 1.2},
    Season.SUMMER: {ResourceType.FOOD: 1.5, ResourceType.ENERGY: 1.4, ResourceType.WATER: 0.8},
    Season.AUTUMN: {ResourceType.FOOD: 1.2, ResourceType.RAW_MATERIALS: 1.3},
    Season.WINTER: {ResourceType.FOOD: 0.5, ResourceType.WATER: 0.6, ResourceType.ENERGY: 0.7},
}
