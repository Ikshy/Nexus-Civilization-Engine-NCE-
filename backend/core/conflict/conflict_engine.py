"""
Nexus Civilization Engine - Conflict & Cooperation Engine
Combat resolution, coalition formation, rebellion, peace negotiation.
"""
from __future__ import annotations
import random
import math
import logging
from typing import Optional
from collections import defaultdict

from backend.core.enums import (
    AgentType, AgentState, ActionType, ResourceType,
    COMBAT_BASE_DAMAGE
)
from backend.core.models import Agent, Faction, Position, ResourceBundle, SimulationEvent
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class CombatSystem:
    """Handles individual and group combat resolution."""

    WEAPON_BONUS = 15.0
    GUARD_DEFENSE_BONUS = 0.3
    AMBUSH_BONUS = 1.5
    TERRAIN_MODIFIERS = {
        "forest": {"attacker": 0.8, "defender": 1.2},
        "mountain": {"attacker": 0.7, "defender": 1.3},
        "urban": {"attacker": 0.9, "defender": 1.1},
        "plains": {"attacker": 1.0, "defender": 1.0},
        "desert": {"attacker": 0.9, "defender": 0.9},
    }

    def resolve_combat(
        self,
        attacker: Agent,
        defender: Agent,
        terrain: str = "plains",
        is_ambush: bool = False,
        tick: int = 0,
    ) -> dict:
        """Resolve combat between two agents. Returns outcome."""
        terrain_mod = self.TERRAIN_MODIFIERS.get(terrain, {"attacker": 1.0, "defender": 1.0})

        # Calculate attack power
        attack_power = (
            COMBAT_BASE_DAMAGE * attacker.skills.combat *
            (1 + attacker.personality.aggression * 0.3) *
            terrain_mod["attacker"]
        )
        if is_ambush:
            attack_power *= self.AMBUSH_BONUS
        if attacker.inventory.get(ResourceType.WEAPONS) > 0:
            attack_power += self.WEAPON_BONUS
            attacker.inventory.subtract(ResourceType.WEAPONS, 0.1)  # Weapon degradation

        # Calculate defense power
        defense_power = (
            COMBAT_BASE_DAMAGE * 0.5 +
            defender.skills.combat * 0.5 *
            terrain_mod["defender"]
        )
        if defender.agent_type == AgentType.GUARD:
            defense_power *= (1 + self.GUARD_DEFENSE_BONUS)
        if defender.inventory.get(ResourceType.WEAPONS) > 0:
            defense_power += self.WEAPON_BONUS * 0.5

        # Energy affects combat effectiveness
        attacker_energy_mod = max(0.3, attacker.vitals.energy / 100)
        defender_energy_mod = max(0.3, defender.vitals.energy / 100)
        attack_power *= attacker_energy_mod
        defense_power *= defender_energy_mod

        # Random variance (fog of war)
        attack_roll = attack_power * random.uniform(0.7, 1.3)
        defense_roll = defense_power * random.uniform(0.7, 1.3)

        # Apply damage
        net_damage = max(0, attack_roll - defense_roll * 0.5)
        counter_damage = max(0, defense_roll * 0.3 - attack_power * 0.1)

        defender.vitals.health -= net_damage
        attacker.vitals.health -= counter_damage

        # Energy cost
        attacker.vitals.energy -= 10
        defender.vitals.energy -= 7

        # Stress increase
        attacker.vitals.stress = min(100, attacker.vitals.stress + 15)
        defender.vitals.stress = min(100, defender.vitals.stress + 20)

        attacker_won = net_damage > counter_damage

        outcome = {
            "attacker_id": attacker.agent_id,
            "defender_id": defender.agent_id,
            "attacker_damage_dealt": net_damage,
            "attacker_damage_taken": counter_damage,
            "attacker_won": attacker_won,
            "attacker_health": attacker.vitals.health,
            "defender_health": defender.vitals.health,
            "defender_alive": defender.vitals.health > 0,
            "attacker_alive": attacker.vitals.health > 0,
            "tick": tick,
        }

        logger.debug(
            f"Combat: {attacker.name} vs {defender.name} | "
            f"Dealt {net_damage:.1f}, Took {counter_damage:.1f} | Won: {attacker_won}"
        )
        return outcome

    def resolve_theft(
        self, thief: Agent, victim: Agent, tick: int
    ) -> dict:
        """Attempt theft based on espionage skill."""
        success_prob = thief.skills.espionage * 0.7 - victim.skills.espionage * 0.3
        success_prob = max(0.05, min(0.85, success_prob))

        if random.random() < success_prob:
            # Steal a random resource
            resources_available = [
                r for r in ResourceType
                if victim.inventory.get(r) > 5 and r != ResourceType.WEAPONS
            ]
            if not resources_available:
                return {"success": False, "reason": "nothing_to_steal"}

            resource = random.choice(resources_available)
            amount = min(victim.inventory.get(resource) * 0.3, 20.0)
            victim.inventory.subtract(resource, amount)
            thief.inventory.add(resource, amount)

            from backend.core.enums import CrimeType
            if CrimeType.THEFT not in thief.crimes_committed:
                thief.crimes_committed.append(CrimeType.THEFT)

            logger.debug(f"{thief.name} stole {amount:.1f} {resource.value} from {victim.name}")
            return {"success": True, "resource": resource.value, "amount": amount, "tick": tick}
        else:
            # Caught! Combat might ensue
            return {
                "success": False,
                "caught": True,
                "tick": tick,
            }

    def resolve_group_combat(
        self,
        attackers: list[Agent],
        defenders: list[Agent],
        terrain: str = "plains",
        tick: int = 0,
    ) -> dict:
        """Resolve faction-level combat."""
        if not attackers or not defenders:
            return {"no_combat": True}

        attacker_power = sum(
            a.skills.combat * max(0.3, a.vitals.health / 100) * max(0.3, a.vitals.energy / 100)
            for a in attackers
        )
        defender_power = sum(
            d.skills.combat * max(0.3, d.vitals.health / 100) * max(0.3, d.vitals.energy / 100)
            for d in defenders
        )

        terrain_mod = self.TERRAIN_MODIFIERS.get(terrain, {"attacker": 1.0, "defender": 1.0})
        attacker_power *= terrain_mod["attacker"]
        defender_power *= terrain_mod["defender"]

        # Weapon advantages
        attacker_weapons = sum(a.inventory.get(ResourceType.WEAPONS) for a in attackers)
        defender_weapons = sum(d.inventory.get(ResourceType.WEAPONS) for d in defenders)
        attacker_power += attacker_weapons * 0.5
        defender_power += defender_weapons * 0.5

        # Random variance
        attack_roll = attacker_power * random.uniform(0.8, 1.2)
        defense_roll = defender_power * random.uniform(0.8, 1.2)

        attackers_win = attack_roll > defense_roll
        damage_to_defenders = max(0, (attack_roll - defense_roll * 0.5) / len(defenders))
        damage_to_attackers = max(0, (defense_roll * 0.3) / len(attackers))

        casualties_defenders = []
        casualties_attackers = []

        for agent in defenders:
            agent.vitals.health -= damage_to_defenders
            agent.vitals.stress = min(100, agent.vitals.stress + 25)
            if agent.vitals.health <= 0:
                casualties_defenders.append(agent.agent_id)

        for agent in attackers:
            agent.vitals.health -= damage_to_attackers
            agent.vitals.stress = min(100, agent.vitals.stress + 20)
            if agent.vitals.health <= 0:
                casualties_attackers.append(agent.agent_id)

        return {
            "attackers_win": attackers_win,
            "casualties_defenders": casualties_defenders,
            "casualties_attackers": casualties_attackers,
            "damage_to_defenders": damage_to_defenders,
            "damage_to_attackers": damage_to_attackers,
            "tick": tick,
        }


class RebellionSystem:
    """Models uprising and resistance movements."""

    def __init__(self):
        self.active_rebellions: dict[str, dict] = {}
        self.rebellion_history: list[dict] = []

    def assess_rebellion_risk(
        self,
        faction_id: str,
        members: list[Agent],
        inequality: float,
        oppression_level: float,
    ) -> float:
        """Calculate probability of rebellion breaking out."""
        if not members:
            return 0.0

        avg_morale = sum(m.vitals.morale for m in members) / len(members)
        avg_trust_in_leaders = 0.0
        rebel_count = sum(1 for m in members if m.agent_type == AgentType.REBEL)

        # Base rebellion risk
        risk = (
            (1 - avg_morale / 100) * 0.3 +
            inequality * 0.3 +
            oppression_level * 0.2 +
            (rebel_count / max(1, len(members))) * 0.2
        )

        return min(1.0, risk)

    def trigger_rebellion(
        self,
        faction_id: str,
        rebels: list[Agent],
        tick: int,
    ) -> dict:
        """Trigger a rebellion event."""
        rebellion = {
            "rebellion_id": f"reb_{faction_id}_{tick}",
            "faction_id": faction_id,
            "rebel_ids": [r.agent_id for r in rebels],
            "start_tick": tick,
            "status": "active",
            "strength": len(rebels),
        }
        self.active_rebellions[rebellion["rebellion_id"]] = rebellion
        logger.warning(f"Rebellion triggered in faction {faction_id} by {len(rebels)} rebels")
        return rebellion

    def process_rebellion(
        self,
        rebellion_id: str,
        all_agents: list[Agent],
        tick: int,
        combat_system: CombatSystem,
    ) -> dict:
        """Process an active rebellion."""
        rebellion = self.active_rebellions.get(rebellion_id)
        if not rebellion:
            return {}

        rebel_agents = [a for a in all_agents if a.agent_id in rebellion["rebel_ids"] and a.is_alive()]
        guard_agents = [
            a for a in all_agents
            if a.agent_type == AgentType.GUARD and
               a.faction_id == rebellion["faction_id"] and a.is_alive()
        ]

        if not rebel_agents:
            rebellion["status"] = "suppressed"
            return {"outcome": "suppressed", "rebellion_id": rebellion_id}

        if not guard_agents:
            rebellion["status"] = "success"
            return {"outcome": "success", "rebellion_id": rebellion_id}

        # Battle
        result = combat_system.resolve_group_combat(rebel_agents, guard_agents, tick=tick)

        if result.get("attackers_win"):
            rebellion["strength"] += 2  # Rebellion grows on success
            if rebellion["strength"] > len(guard_agents) * 2:
                rebellion["status"] = "success"
                return {"outcome": "success", "rebellion_id": rebellion_id, "battle": result}
        else:
            rebellion["strength"] = max(0, rebellion["strength"] - 3)
            if rebellion["strength"] <= 0:
                rebellion["status"] = "suppressed"
                return {"outcome": "suppressed", "rebellion_id": rebellion_id, "battle": result}

        return {"outcome": "ongoing", "rebellion_id": rebellion_id, "battle": result}

    def check_rebellions(
        self,
        factions: dict[str, Faction],
        agents_by_faction: dict[str, list[Agent]],
        inequality: float,
        tick: int,
    ) -> list[dict]:
        """Check all factions for rebellion risk."""
        events = []
        threshold = settings.simulation.rebellion_threshold

        for faction_id, faction in factions.items():
            members = agents_by_faction.get(faction_id, [])
            rebel_members = [m for m in members if m.agent_type == AgentType.REBEL]

            risk = self.assess_rebellion_risk(faction_id, members, inequality, 0.3)

            if risk > threshold and rebel_members and random.random() < risk * 0.1:
                # Check if rebellion already active for this faction
                already_active = any(
                    r["faction_id"] == faction_id and r["status"] == "active"
                    for r in self.active_rebellions.values()
                )
                if not already_active:
                    rebellion = self.trigger_rebellion(faction_id, rebel_members, tick)
                    events.append({
                        "event_type": "rebellion_started",
                        "faction_id": faction_id,
                        "faction_name": faction.name,
                        "rebel_count": len(rebel_members),
                        "tick": tick,
                    })

        return events


class CoalitionEngine:
    """Manages strategic coalitions and multi-faction cooperation."""

    def __init__(self):
        self.coalitions: dict[str, dict] = {}

    def propose_coalition(
        self,
        proposer_faction_id: str,
        target_faction_ids: list[str],
        purpose: str,
        tick: int,
    ) -> dict:
        coalition = {
            "coalition_id": f"coal_{tick}",
            "member_factions": [proposer_faction_id] + target_faction_ids,
            "purpose": purpose,
            "formed_tick": tick,
            "status": "active",
        }
        self.coalitions[coalition["coalition_id"]] = coalition
        logger.info(f"Coalition formed: {purpose} with {len(coalition['member_factions'])} factions")
        return coalition

    def dissolve_coalition(self, coalition_id: str, reason: str, tick: int) -> None:
        coalition = self.coalitions.get(coalition_id)
        if coalition:
            coalition["status"] = "dissolved"
            coalition["dissolved_tick"] = tick
            coalition["dissolution_reason"] = reason


class PeaceNegotiationSystem:
    """Facilitates peace negotiations between warring factions."""

    def __init__(self):
        self.active_negotiations: dict[str, dict] = {}

    def initiate_peace(
        self,
        faction1_id: str,
        faction2_id: str,
        mediator_agent: Optional[Agent],
        tick: int,
    ) -> dict:
        neg = {
            "negotiation_id": f"peace_{faction1_id}_{faction2_id}_{tick}",
            "faction1_id": faction1_id,
            "faction2_id": faction2_id,
            "mediator_id": mediator_agent.agent_id if mediator_agent else None,
            "status": "ongoing",
            "rounds": 0,
            "started_tick": tick,
        }
        self.active_negotiations[neg["negotiation_id"]] = neg
        return neg

    def process_peace_round(
        self,
        neg_id: str,
        factions: dict[str, Faction],
        faction_powers: dict[str, float],
        tick: int,
    ) -> dict:
        neg = self.active_negotiations.get(neg_id)
        if not neg:
            return {}

        neg["rounds"] += 1

        f1 = factions.get(neg["faction1_id"])
        f2 = factions.get(neg["faction2_id"])
        if not f1 or not f2:
            neg["status"] = "failed"
            return {"status": "failed"}

        power1 = faction_powers.get(neg["faction1_id"], 0)
        power2 = faction_powers.get(neg["faction2_id"], 0)

        # Peace is more likely when powers are equal
        power_ratio = min(power1, power2) / max(power1, power2, 0.01)
        has_mediator = neg["mediator_id"] is not None
        mediation_bonus = 0.2 if has_mediator else 0.0

        peace_prob = power_ratio * 0.3 + mediation_bonus + (neg["rounds"] / 20) * 0.3
        peace_prob = min(0.9, peace_prob)

        if random.random() < peace_prob or neg["rounds"] > 15:
            neg["status"] = "agreed"
            f1.enemy_faction_ids = [eid for eid in f1.enemy_faction_ids if eid != f2.faction_id]
            f2.enemy_faction_ids = [eid for eid in f2.enemy_faction_ids if eid != f1.faction_id]
            logger.info(f"Peace agreement: {f1.name} <-> {f2.name}")
            return {"status": "agreed", "tick": tick}

        return {"status": "ongoing", "rounds": neg["rounds"]}


class DominanceHierarchy:
    """Tracks and updates power hierarchies among agents and factions."""

    def compute_dominance_scores(
        self,
        agents: list[Agent],
        social_centrality: dict[str, float],
    ) -> dict[str, float]:
        """Compute dominance score per agent."""
        scores = {}
        for agent in agents:
            if not agent.is_alive():
                continue
            centrality = social_centrality.get(agent.agent_id, 0.0)
            score = (
                agent.reputation / 100 * 0.3 +
                agent.skills.leadership * 0.2 +
                agent.skills.combat * 0.15 +
                agent.net_worth / max(1, max(a.net_worth for a in agents)) * 0.2 +
                centrality * 0.15
            )
            scores[agent.agent_id] = score
        return scores

    def get_dominant_agents(
        self, dominance_scores: dict[str, float], top_n: int = 5
    ) -> list[tuple[str, float]]:
        return sorted(dominance_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]


class ConflictEngine:
    """
    Orchestrates all conflict and cooperation subsystems.
    """

    def __init__(self):
        self.combat_system = CombatSystem()
        self.rebellion_system = RebellionSystem()
        self.coalition_engine = CoalitionEngine()
        self.peace_system = PeaceNegotiationSystem()
        self.dominance = DominanceHierarchy()
        self._conflict_log: list[dict] = []

    def tick(
        self,
        agents: list[Agent],
        factions: dict[str, Faction],
        inequality: float,
        social_centrality: dict[str, float],
        tick: int,
    ) -> list[dict]:
        """Process conflict/cooperation tick. Returns events."""
        events = []
        alive = [a for a in agents if a.is_alive()]

        # Organize agents by faction
        agents_by_faction: dict[str, list[Agent]] = defaultdict(list)
        for agent in alive:
            if agent.faction_id:
                agents_by_faction[agent.faction_id].append(agent)

        # Check rebellion risks
        rebellion_events = self.rebellion_system.check_rebellions(
            factions, agents_by_faction, inequality, tick
        )
        events.extend(rebellion_events)

        # Process active rebellions
        for reb_id in list(self.rebellion_system.active_rebellions.keys()):
            rebellion = self.rebellion_system.active_rebellions[reb_id]
            if rebellion["status"] == "active":
                result = self.rebellion_system.process_rebellion(
                    reb_id, alive, tick, self.combat_system
                )
                if result.get("outcome") in ("success", "suppressed"):
                    events.append({
                        "event_type": f"rebellion_{result['outcome']}",
                        "rebellion_id": reb_id,
                        "faction_id": rebellion["faction_id"],
                        "tick": tick,
                    })

        # Process active peace negotiations
        faction_powers = {
            fid: self.dominance.compute_dominance_scores(
                agents_by_faction.get(fid, []), social_centrality
            ).__len__()  # Simplified power
            for fid in factions
        }
        for neg_id in list(self.peace_system.active_negotiations.keys()):
            neg = self.peace_system.active_negotiations[neg_id]
            if neg["status"] == "ongoing":
                result = self.peace_system.process_peace_round(
                    neg_id, factions, faction_powers, tick
                )
                if result.get("status") == "agreed":
                    events.append({
                        "event_type": "peace_agreement",
                        "faction1": neg["faction1_id"],
                        "faction2": neg["faction2_id"],
                        "tick": tick,
                    })

        # Compute dominance hierarchy
        dom_scores = self.dominance.compute_dominance_scores(alive, social_centrality)
        top_agents = self.dominance.get_dominant_agents(dom_scores, 5)

        return events

    def execute_attack(
        self,
        attacker: Agent,
        defender: Agent,
        terrain: str,
        tick: int,
        lifecycle_manager=None,
    ) -> dict:
        """Execute an attack action with all side effects."""
        result = self.combat_system.resolve_combat(attacker, defender, terrain, tick=tick)

        # Handle deaths
        if not result["defender_alive"] and lifecycle_manager:
            lifecycle_manager.kill_agent(defender.agent_id, "combat", tick)
            attacker.inventory.add(ResourceType.WEAPONS, 0.5)  # Loot
        if not result["attacker_alive"] and lifecycle_manager:
            lifecycle_manager.kill_agent(attacker.agent_id, "combat_death", tick)

        self._conflict_log.append({**result, "type": "individual_combat"})
        return result

    def execute_theft(
        self, thief: Agent, victim: Agent, tick: int, governance_system=None
    ) -> dict:
        """Execute a theft with potential legal consequences."""
        result = self.combat_system.resolve_theft(thief, victim, tick)

        if result.get("caught") and governance_system:
            # Report to authorities
            governance_system.report_crime(thief, "theft", evidence=0.8, tick=tick)

        return result

    def get_conflict_summary(self) -> dict:
        return {
            "total_combats": len(self._conflict_log),
            "active_rebellions": len([
                r for r in self.rebellion_system.active_rebellions.values()
                if r["status"] == "active"
            ]),
            "active_coalitions": len([
                c for c in self.coalition_engine.coalitions.values()
                if c["status"] == "active"
            ]),
            "active_peace_negotiations": len([
                n for n in self.peace_system.active_negotiations.values()
                if n["status"] == "ongoing"
            ]),
        }
