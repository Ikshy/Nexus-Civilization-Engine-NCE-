"""
Nexus Civilization Engine - World Engine
Full grid-based world with terrain, weather, seasons, resources, and disasters.
"""
from __future__ import annotations
import random
import math
import logging
from typing import Optional, Iterator
from collections import defaultdict

import numpy as np

from backend.core.enums import (
    TerrainType, ZoneType, WeatherType, Season, DisasterType,
    ResourceType, TERRAIN_RESOURCE_MODIFIERS, SEASON_MODIFIERS,
    RESOURCE_REGEN_RATES
)
from backend.core.models import (
    Cell, Position, WorldState, ResourceBundle, SimulationEvent, Building
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class TerrainGenerator:
    """Procedural terrain generation using Perlin-like noise."""

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def generate(self, width: int, height: int) -> np.ndarray:
        """Returns a 2D array of TerrainType values."""
        # Multi-octave noise simulation
        noise = np.zeros((height, width))
        for octave in [1, 2, 4, 8]:
            scale = 1.0 / octave
            freq_w = max(1, width // octave)
            freq_h = max(1, height // octave)
            base = self.rng.random((freq_h, freq_w))
            # Simple bilinear upscale
            from PIL import Image
            img = Image.fromarray((base * 255).astype(np.uint8))
            img_resized = img.resize((width, height), Image.BILINEAR)
            noise += scale * np.array(img_resized) / 255.0

        noise /= noise.max()

        terrain = np.empty((height, width), dtype=object)
        for y in range(height):
            for x in range(width):
                v = noise[y, x]
                if v < 0.1:
                    terrain[y, x] = TerrainType.WATER
                elif v < 0.25:
                    terrain[y, x] = TerrainType.FERTILE
                elif v < 0.45:
                    terrain[y, x] = TerrainType.PLAINS
                elif v < 0.60:
                    terrain[y, x] = TerrainType.FOREST
                elif v < 0.70:
                    terrain[y, x] = TerrainType.URBAN
                elif v < 0.82:
                    terrain[y, x] = TerrainType.MOUNTAIN
                elif v < 0.92:
                    terrain[y, x] = TerrainType.DESERT
                else:
                    terrain[y, x] = TerrainType.WASTELAND
        return terrain

    def _fallback_generate(self, width: int, height: int) -> np.ndarray:
        """Fallback if PIL not available - use simple random terrain."""
        terrain = np.empty((height, width), dtype=object)
        types = list(TerrainType)
        weights = [0.05, 0.15, 0.25, 0.15, 0.1, 0.1, 0.1, 0.1]
        for y in range(height):
            for x in range(width):
                terrain[y, x] = random.choices(types, weights=weights)[0]
        return terrain


class WeatherSystem:
    """Manages weather patterns, transitions, and effects."""

    TRANSITIONS = {
        WeatherType.CLEAR:    {WeatherType.CLEAR: 0.6, WeatherType.CLOUDY: 0.3, WeatherType.RAIN: 0.1},
        WeatherType.CLOUDY:   {WeatherType.CLEAR: 0.2, WeatherType.CLOUDY: 0.4, WeatherType.RAIN: 0.3, WeatherType.STORM: 0.1},
        WeatherType.RAIN:     {WeatherType.CLOUDY: 0.3, WeatherType.RAIN: 0.5, WeatherType.STORM: 0.15, WeatherType.CLEAR: 0.05},
        WeatherType.STORM:    {WeatherType.RAIN: 0.5, WeatherType.STORM: 0.3, WeatherType.CLOUDY: 0.2},
        WeatherType.DROUGHT:  {WeatherType.DROUGHT: 0.7, WeatherType.CLEAR: 0.2, WeatherType.HEATWAVE: 0.1},
        WeatherType.BLIZZARD: {WeatherType.BLIZZARD: 0.4, WeatherType.CLOUDY: 0.4, WeatherType.CLEAR: 0.2},
        WeatherType.HEATWAVE: {WeatherType.HEATWAVE: 0.5, WeatherType.DROUGHT: 0.3, WeatherType.CLEAR: 0.2},
    }

    SEASON_WEATHER_BIAS = {
        Season.SPRING:  {WeatherType.RAIN: 0.3, WeatherType.CLEAR: 0.4, WeatherType.CLOUDY: 0.3},
        Season.SUMMER:  {WeatherType.CLEAR: 0.5, WeatherType.HEATWAVE: 0.2, WeatherType.DROUGHT: 0.15, WeatherType.STORM: 0.15},
        Season.AUTUMN:  {WeatherType.CLOUDY: 0.4, WeatherType.RAIN: 0.3, WeatherType.CLEAR: 0.3},
        Season.WINTER:  {WeatherType.BLIZZARD: 0.2, WeatherType.CLOUDY: 0.5, WeatherType.CLEAR: 0.3},
    }

    def __init__(self):
        self.current: WeatherType = WeatherType.CLEAR
        self.duration: int = 0
        self.min_duration: int = 3

    def update(self, season: Season) -> WeatherType:
        self.duration += 1
        if self.duration < self.min_duration:
            return self.current

        # Blend transition matrix with season bias
        transitions = dict(self.TRANSITIONS.get(self.current, {}))
        season_bias = self.SEASON_WEATHER_BIAS.get(season, {})
        for w, prob in season_bias.items():
            transitions[w] = transitions.get(w, 0.0) * 0.6 + prob * 0.4

        # Normalize
        total = sum(transitions.values())
        if total == 0:
            return self.current
        options = list(transitions.keys())
        probs = [transitions[w] / total for w in options]
        new_weather = random.choices(options, weights=probs)[0]

        if new_weather != self.current:
            self.current = new_weather
            self.duration = 0
            logger.debug(f"Weather changed to {new_weather.value} in {season.value}")

        return self.current

    def temperature_effect(self, base_temp: float, season: Season) -> float:
        season_temps = {Season.SPRING: 15, Season.SUMMER: 28, Season.AUTUMN: 12, Season.WINTER: -5}
        weather_offsets = {
            WeatherType.HEATWAVE: 10, WeatherType.DROUGHT: 5, WeatherType.BLIZZARD: -15,
            WeatherType.STORM: -5, WeatherType.RAIN: -3, WeatherType.CLEAR: 0, WeatherType.CLOUDY: -2,
        }
        return season_temps.get(season, 15) + weather_offsets.get(self.current, 0)

    def resource_modifier(self) -> dict[ResourceType, float]:
        modifiers = {r: 1.0 for r in ResourceType}
        if self.current == WeatherType.DROUGHT:
            modifiers[ResourceType.FOOD] = 0.4
            modifiers[ResourceType.WATER] = 0.2
        elif self.current == WeatherType.STORM:
            modifiers[ResourceType.FOOD] = 0.7
            modifiers[ResourceType.ENERGY] = 0.8
        elif self.current == WeatherType.BLIZZARD:
            modifiers[ResourceType.FOOD] = 0.5
            modifiers[ResourceType.WATER] = 0.6
            modifiers[ResourceType.ENERGY] = 0.5
        elif self.current == WeatherType.RAIN:
            modifiers[ResourceType.WATER] = 1.5
            modifiers[ResourceType.FOOD] = 1.1
        elif self.current == WeatherType.HEATWAVE:
            modifiers[ResourceType.WATER] = 0.6
            modifiers[ResourceType.ENERGY] = 1.3
        return modifiers


class DisasterSystem:
    """Manages world disasters - triggers, effects, and recovery."""

    DISASTER_CONFIGS = {
        DisasterType.FAMINE: {
            "food_drain": 0.8, "health_drain": 5.0, "duration_ticks": 50,
            "trigger_threshold": 0.2,  # food scarcity
            "recovery_rate": 0.05,
        },
        DisasterType.PLAGUE: {
            "health_drain": 8.0, "spread_radius": 5, "duration_ticks": 80,
            "mortality_rate": 0.3,
            "recovery_rate": 0.03,
        },
        DisasterType.FLOOD: {
            "area_radius": 10, "duration_ticks": 20, "food_drain": 0.5,
            "building_damage": 30.0,
            "recovery_rate": 0.1,
        },
        DisasterType.EARTHQUAKE: {
            "area_radius": 8, "duration_ticks": 1, "building_damage": 70.0,
            "health_drain": 20.0, "immediate": True,
        },
        DisasterType.MARKET_CRASH: {
            "price_multiplier": 3.0, "duration_ticks": 60, "trust_drain": 0.2,
            "recovery_rate": 0.02,
        },
        DisasterType.POLITICAL_COLLAPSE: {
            "law_enforcement_drain": 0.8, "duration_ticks": 100,
            "faction_stability_drain": 0.5,
        },
        DisasterType.CLIMATE_DISASTER: {
            "area_radius": 20, "duration_ticks": 200, "food_drain": 0.6,
            "water_drain": 0.4, "fertility_drain": 0.7,
        },
    }

    def __init__(self):
        self.active_disasters: dict[str, dict] = {}  # id -> disaster state
        self._next_check_tick: int = 50

    def check_triggers(self, world_state: WorldState, resource_scarcity: dict, stability: float) -> list[dict]:
        """Check conditions that might trigger disasters."""
        new_disasters = []

        # Famine from food scarcity
        if resource_scarcity.get("food", 0) > 0.7 and DisasterType.FAMINE.value not in self.active_disasters:
            if random.random() < 0.15:
                new_disasters.append(self._create_disaster(DisasterType.FAMINE, world_state.tick))

        # Plague from population density and poor conditions
        if stability < 0.3 and DisasterType.PLAGUE.value not in self.active_disasters:
            if random.random() < 0.05:
                new_disasters.append(self._create_disaster(DisasterType.PLAGUE, world_state.tick))

        # Market crash from instability
        if stability < 0.25 and DisasterType.MARKET_CRASH.value not in self.active_disasters:
            if random.random() < 0.08:
                new_disasters.append(self._create_disaster(DisasterType.MARKET_CRASH, world_state.tick))

        # Random disasters
        if random.random() < 0.001:
            disaster_type = random.choice([DisasterType.EARTHQUAKE, DisasterType.FLOOD])
            new_disasters.append(self._create_disaster(disaster_type, world_state.tick))

        for d in new_disasters:
            self.active_disasters[d["disaster_id"]] = d
            logger.warning(f"Disaster triggered: {d['type']} at tick {world_state.tick}")

        return new_disasters

    def _create_disaster(self, disaster_type: DisasterType, tick: int) -> dict:
        config = self.DISASTER_CONFIGS.get(disaster_type, {})
        return {
            "disaster_id": f"dis_{disaster_type.value}_{tick}",
            "type": disaster_type.value,
            "start_tick": tick,
            "duration": config.get("duration_ticks", 30),
            "config": config,
            "severity": random.uniform(0.5, 1.0),
        }

    def update(self, current_tick: int) -> list[str]:
        """Remove expired disasters, return their IDs."""
        expired = []
        for d_id, disaster in list(self.active_disasters.items()):
            if current_tick - disaster["start_tick"] >= disaster["duration"]:
                expired.append(d_id)
                del self.active_disasters[d_id]
                logger.info(f"Disaster ended: {disaster['type']}")
        return expired

    def inject_disaster(self, disaster_type: DisasterType, tick: int, severity: float = 1.0) -> dict:
        """Manually inject a disaster (for scenario engine)."""
        disaster = self._create_disaster(disaster_type, tick)
        disaster["severity"] = severity
        self.active_disasters[disaster["disaster_id"]] = disaster
        return disaster


class WorldEngine:
    """
    The main world engine. Manages the grid, terrain, resources,
    weather, time, and environmental events.
    """

    def __init__(
        self,
        width: int = None,
        height: int = None,
        seed: int = 42,
    ):
        self.width = width or settings.simulation.world_width
        self.height = height or settings.simulation.world_height
        self.seed = seed
        self.rng = random.Random(seed)

        # Initialize grid
        self.grid: dict[tuple[int, int], Cell] = {}
        self.buildings: dict[str, Building] = {}

        # Subsystems
        self.weather_system = WeatherSystem()
        self.disaster_system = DisasterSystem()
        self.terrain_gen = TerrainGenerator(seed)

        # World state
        self.state = WorldState()
        self._day_tick_counter: int = 0

        # Event queue for world events
        self._event_queue: list[SimulationEvent] = []

        self._initialize_world()
        logger.info(f"WorldEngine initialized: {self.width}x{self.height} grid")

    def _initialize_world(self) -> None:
        """Generate the initial world grid with terrain and resources."""
        try:
            terrain_map = self.terrain_gen.generate(self.width, self.height)
        except Exception:
            logger.warning("PIL not available, using fallback terrain generation")
            terrain_map = self.terrain_gen._fallback_generate(self.width, self.height)

        for y in range(self.height):
            for x in range(self.width):
                pos = Position(x, y)
                terrain = terrain_map[y, x]
                cell = Cell(
                    position=pos,
                    terrain=terrain,
                    zone=self._assign_zone(terrain),
                    resources=self._initial_resources(terrain),
                    fertility=self._initial_fertility(terrain),
                )
                self.grid[(x, y)] = cell

    def _assign_zone(self, terrain: TerrainType) -> ZoneType:
        zone_map = {
            TerrainType.URBAN: ZoneType.SAFE,
            TerrainType.FERTILE: ZoneType.SAFE,
            TerrainType.PLAINS: ZoneType.NEUTRAL,
            TerrainType.FOREST: ZoneType.NEUTRAL,
            TerrainType.MOUNTAIN: ZoneType.DANGEROUS,
            TerrainType.DESERT: ZoneType.DANGEROUS,
            TerrainType.WATER: ZoneType.NEUTRAL,
            TerrainType.WASTELAND: ZoneType.DANGEROUS,
        }
        return zone_map.get(terrain, ZoneType.NEUTRAL)

    def _initial_resources(self, terrain: TerrainType) -> ResourceBundle:
        bundle = ResourceBundle()
        modifiers = TERRAIN_RESOURCE_MODIFIERS.get(terrain, {})
        base_amounts = {
            ResourceType.FOOD: 50.0,
            ResourceType.WATER: 40.0,
            ResourceType.ENERGY: 30.0,
            ResourceType.RAW_MATERIALS: 20.0,
            ResourceType.TOOLS: 5.0,
            ResourceType.MONEY: 10.0,
        }
        for resource, base in base_amounts.items():
            modifier = modifiers.get(resource, 0.5)
            amount = base * modifier * self.rng.uniform(0.7, 1.3)
            if amount > 0:
                bundle.set(resource, amount)
        return bundle

    def _initial_fertility(self, terrain: TerrainType) -> float:
        fertility_map = {
            TerrainType.FERTILE: 1.0,
            TerrainType.PLAINS: 0.7,
            TerrainType.FOREST: 0.5,
            TerrainType.URBAN: 0.3,
            TerrainType.MOUNTAIN: 0.2,
            TerrainType.DESERT: 0.1,
            TerrainType.WATER: 0.6,
            TerrainType.WASTELAND: 0.05,
        }
        return fertility_map.get(terrain, 0.5) * self.rng.uniform(0.8, 1.2)

    def get_cell(self, x: int, y: int) -> Optional[Cell]:
        return self.grid.get((x, y))

    def get_cell_at(self, pos: Position) -> Optional[Cell]:
        return self.grid.get((pos.x, pos.y))

    def is_valid_position(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def get_neighbors(self, pos: Position, radius: int = 1) -> list[Cell]:
        cells = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = pos.x + dx, pos.y + dy
                cell = self.grid.get((nx, ny))
                if cell:
                    cells.append(cell)
        return cells

    def get_region(self, center: Position, radius: int) -> list[Cell]:
        """Get all cells within radius of center."""
        cells = []
        for x in range(max(0, center.x - radius), min(self.width, center.x + radius + 1)):
            for y in range(max(0, center.y - radius), min(self.height, center.y + radius + 1)):
                dist = math.sqrt((x - center.x) ** 2 + (y - center.y) ** 2)
                if dist <= radius:
                    cell = self.grid.get((x, y))
                    if cell:
                        cells.append(cell)
        return cells

    def find_nearest_resource(
        self, from_pos: Position, resource: ResourceType, min_amount: float = 1.0
    ) -> Optional[Position]:
        """Find the nearest cell with a given resource."""
        best_pos = None
        best_dist = float("inf")
        for (x, y), cell in self.grid.items():
            if cell.resources.get(resource) >= min_amount:
                dist = math.sqrt((x - from_pos.x) ** 2 + (y - from_pos.y) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_pos = cell.position
        return best_pos

    def tick(self) -> list[SimulationEvent]:
        """Advance world by one tick. Returns list of events."""
        events = []
        self.state.tick += 1

        # Time progression
        self._day_tick_counter += 1
        if self._day_tick_counter >= settings.simulation.day_length_ticks:
            self._day_tick_counter = 0
            self.state.day += 1
            events.extend(self._on_new_day())

            # Season progression
            days_per_season = settings.simulation.season_length_days
            season_index = (self.state.day // days_per_season) % 4
            new_season = list(Season)[season_index]
            if new_season != self.state.season:
                self.state.season = new_season
                events.append(self._create_season_event(new_season))

            # Year progression
            total_days = settings.simulation.season_length_days * 4
            if self.state.day % total_days == 0 and self.state.day > 0:
                self.state.year += 1
                logger.info(f"Year {self.state.year} begins")

        # Weather update
        new_weather = self.weather_system.update(self.state.season)
        if new_weather != self.state.weather:
            self.state.weather = new_weather
            events.append(SimulationEvent(
                tick=self.state.tick,
                event_type="weather_change",
                data={"weather": new_weather.value, "season": self.state.season.value},
            ))
        self.state.temperature = self.weather_system.temperature_effect(20.0, self.state.season)

        # Resource regeneration
        self._regenerate_resources()

        # Disaster checks
        resource_scarcity = self._compute_resource_scarcity()
        new_disasters = self.disaster_system.check_triggers(
            self.state, resource_scarcity, self.state.global_stability
        )
        for d in new_disasters:
            events.append(SimulationEvent(
                tick=self.state.tick,
                event_type="disaster_start",
                severity=d["severity"],
                data=d,
            ))

        expired = self.disaster_system.update(self.state.tick)
        for d_id in expired:
            events.append(SimulationEvent(
                tick=self.state.tick, event_type="disaster_end",
                data={"disaster_id": d_id},
            ))

        # Apply active disaster effects
        self._apply_disaster_effects()

        # Consume any queued events
        events.extend(self._event_queue)
        self._event_queue.clear()

        return events

    def _on_new_day(self) -> list[SimulationEvent]:
        events = []
        # Fertility recovery
        for cell in self.grid.values():
            if cell.fertility < 1.0 and cell.terrain != TerrainType.WASTELAND:
                cell.fertility = min(1.0, cell.fertility + 0.001)
            # Pollution decay
            cell.pollution = max(0.0, cell.pollution - 0.005)
        return events

    def _create_season_event(self, season: Season) -> SimulationEvent:
        logger.info(f"Season changed to {season.value} at tick {self.state.tick}")
        return SimulationEvent(
            tick=self.state.tick,
            event_type="season_change",
            data={"season": season.value, "day": self.state.day},
        )

    def _regenerate_resources(self) -> None:
        """Regenerate resources on all cells based on terrain, weather, season."""
        weather_mods = self.weather_system.resource_modifier()
        season_mods = SEASON_MODIFIERS.get(self.state.season, {})

        for cell in self.grid.values():
            if cell.terrain == TerrainType.WATER:
                # Water cells don't regen most resources
                cell.resources.add(ResourceType.WATER, 2.0)
                continue

            terrain_mods = TERRAIN_RESOURCE_MODIFIERS.get(cell.terrain, {})

            for resource, base_rate in RESOURCE_REGEN_RATES.items():
                terrain_mod = terrain_mods.get(resource, 0.3)
                weather_mod = weather_mods.get(resource, 1.0)
                season_mod = season_mods.get(resource, 1.0)
                fertility_mod = cell.fertility if resource in (ResourceType.FOOD, ResourceType.WATER) else 1.0

                regen = base_rate * terrain_mod * weather_mod * season_mod * fertility_mod

                # Cap resources to prevent infinite accumulation
                current = cell.resources.get(resource)
                max_cap = 500.0
                if current < max_cap:
                    cell.resources.add(resource, regen)

    def _apply_disaster_effects(self) -> None:
        """Apply ongoing disaster effects to the world."""
        for disaster in self.disaster_system.active_disasters.values():
            config = disaster["config"]
            severity = disaster["severity"]

            if disaster["type"] == DisasterType.FAMINE.value:
                for cell in self.grid.values():
                    cell.resources.subtract(ResourceType.FOOD, config["food_drain"] * severity * 0.01)

            elif disaster["type"] == DisasterType.CLIMATE_DISASTER.value:
                for cell in self.grid.values():
                    cell.fertility = max(0.05, cell.fertility - config["fertility_drain"] * severity * 0.001)
                    cell.resources.subtract(ResourceType.FOOD, config["food_drain"] * severity * 0.005)
                    cell.resources.subtract(ResourceType.WATER, config["water_drain"] * severity * 0.005)

    def _compute_resource_scarcity(self) -> dict[str, float]:
        """Compute global resource scarcity index (0=abundant, 1=scarce)."""
        totals: dict[ResourceType, float] = defaultdict(float)
        for cell in self.grid.values():
            for resource in ResourceType:
                totals[resource] += cell.resources.get(resource)

        scarcity = {}
        base_expected = {
            ResourceType.FOOD: self.width * self.height * 10,
            ResourceType.WATER: self.width * self.height * 15,
            ResourceType.ENERGY: self.width * self.height * 5,
        }
        for resource, expected in base_expected.items():
            actual = totals[resource]
            scarcity[resource.value] = max(0.0, min(1.0, 1.0 - (actual / expected)))

        return scarcity

    def extract_resource(
        self, pos: Position, resource: ResourceType, amount: float
    ) -> float:
        """Extract resources from a cell. Returns actual extracted amount."""
        cell = self.get_cell_at(pos)
        if not cell:
            return 0.0
        available = cell.resources.get(resource)
        extracted = min(available, amount)
        cell.resources.subtract(resource, extracted)
        # Reduce fertility on heavy extraction
        if resource == ResourceType.FOOD:
            cell.fertility = max(0.1, cell.fertility - extracted * 0.0001)
        return extracted

    def deposit_resource(self, pos: Position, resource: ResourceType, amount: float) -> None:
        """Deposit resources at a cell."""
        cell = self.get_cell_at(pos)
        if cell:
            cell.resources.add(resource, amount)

    def add_building(self, building: Building) -> None:
        self.buildings[building.building_id] = building
        cell = self.get_cell_at(building.position)
        if cell:
            cell.building_ids.append(building.building_id)

    def get_agent_cell(self, agent_id: str) -> Optional[Cell]:
        for cell in self.grid.values():
            if agent_id in cell.occupant_ids:
                return cell
        return None

    def move_agent(self, agent_id: str, from_pos: Position, to_pos: Position) -> bool:
        if not self.is_valid_position(to_pos):
            return False
        to_cell = self.get_cell_at(to_pos)
        if to_cell and to_cell.terrain == TerrainType.WATER:
            return False  # Can't walk on water
        from_cell = self.get_cell_at(from_pos)
        if from_cell and agent_id in from_cell.occupant_ids:
            from_cell.occupant_ids.remove(agent_id)
        if to_cell:
            to_cell.occupant_ids.append(agent_id)
        return True

    def get_world_snapshot(self) -> dict:
        """Serializable snapshot of world state for API."""
        return {
            "tick": self.state.tick,
            "day": self.state.day,
            "season": self.state.season.value,
            "year": self.state.year,
            "weather": self.state.weather.value,
            "temperature": self.state.temperature,
            "global_stability": self.state.global_stability,
            "active_disasters": list(self.disaster_system.active_disasters.values()),
            "width": self.width,
            "height": self.height,
            "resource_scarcity": self._compute_resource_scarcity(),
        }

    def inject_disaster(self, disaster_type: DisasterType, severity: float = 1.0) -> dict:
        """External disaster injection for scenario engine."""
        return self.disaster_system.inject_disaster(disaster_type, self.state.tick, severity)

    def get_heatmap(self, resource: ResourceType) -> list[list[float]]:
        """Generate a heatmap of resource distribution."""
        grid = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                cell = self.grid.get((x, y))
                row.append(cell.resources.get(resource) if cell else 0.0)
            grid.append(row)
        return grid

    def get_zone_map(self) -> list[list[str]]:
        grid = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                cell = self.grid.get((x, y))
                row.append(cell.zone.value if cell else "unknown")
            grid.append(row)
        return grid

    def get_terrain_map(self) -> list[list[str]]:
        grid = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                cell = self.grid.get((x, y))
                row.append(cell.terrain.value if cell else "unknown")
            grid.append(row)
        return grid

    def all_cells(self) -> Iterator[Cell]:
        yield from self.grid.values()
