"""
Nexus Civilization Engine - Cognitive Engine
Full perception → memory → planning → action decision loop for agents.
"""
from __future__ import annotations
import random
import math
import logging
from typing import Optional, Any
from collections import deque

from backend.core.enums import (
    AgentType, AgentState, ActionType, ResourceType, RelationshipType,
    BeliefStrength, MAX_HEALTH, MAX_ENERGY
)
from backend.core.models import (
    Agent, Position, MemoryEntry, AgentGoal, AgentBelief,
    Cell, ResourceBundle, GossipEntry, TrustEntry
)

logger = logging.getLogger(__name__)

# Perception range by type
PERCEPTION_RANGE = {
    AgentType.SPY: 8,
    AgentType.GUARD: 6,
    AgentType.LEADER: 5,
    AgentType.DIPLOMAT: 5,
    AgentType.TRADER: 4,
    AgentType.REBEL: 4,
    AgentType.WORKER: 3,
    AgentType.FARMER: 3,
    AgentType.BUILDER: 3,
    AgentType.THIEF: 5,
    AgentType.SCIENTIST: 4,
    AgentType.MEDIATOR: 5,
}

SHORT_TERM_MEMORY_LIMIT = 20
EPISODIC_MEMORY_LIMIT = 200


class PerceptionModule:
    """Gathers information about an agent's environment."""

    def perceive(
        self,
        agent: Agent,
        nearby_agents: list[Agent],
        nearby_cells: list[Cell],
        world_events: list[dict],
    ) -> dict[str, Any]:
        """Build a perception dict from world state."""
        perception_range = PERCEPTION_RANGE.get(agent.agent_type, 3)

        # Filter to actually visible agents/cells
        visible_agents = [
            a for a in nearby_agents
            if a.agent_id != agent.agent_id and
               a.position.distance_to(agent.position) <= perception_range and
               a.is_alive()
        ]

        # Check if any spies are in stealth (reduce visibility)
        visible_agents = [
            a for a in visible_agents
            if not (a.agent_type == AgentType.SPY and
                    a.skills.espionage > 0.7 and
                    random.random() < a.skills.espionage * 0.5)
        ]

        # Resource awareness
        available_resources: dict[ResourceType, float] = {}
        for cell in nearby_cells:
            for resource, amount in cell.resources.resources.items():
                available_resources[resource] = available_resources.get(resource, 0) + amount

        # Threat assessment
        threats = [
            a for a in visible_agents
            if a.personality.aggression > 0.6 and
               agent.get_trust(a.agent_id) < -0.3
        ]

        # Opportunity assessment
        opportunities = []
        if available_resources.get(ResourceType.FOOD, 0) > 20 and agent.vitals.hunger > 30:
            opportunities.append({"type": "gather_food", "priority": agent.vitals.hunger / 100})
        if available_resources.get(ResourceType.WATER, 0) > 20 and agent.vitals.thirst > 30:
            opportunities.append({"type": "gather_water", "priority": agent.vitals.thirst / 100})

        # Trade opportunities
        for other in visible_agents:
            if other.agent_type == AgentType.TRADER or other.agent_type == AgentType.WORKER:
                opportunities.append({"type": "trade", "agent_id": other.agent_id, "priority": 0.3})

        return {
            "visible_agents": visible_agents,
            "threats": threats,
            "opportunities": opportunities,
            "available_resources": available_resources,
            "recent_world_events": world_events[-5:] if world_events else [],
            "nearby_cells": nearby_cells,
            "danger_level": len(threats) / max(1, len(visible_agents)),
        }


class MemorySystem:
    """Manages all memory types for an agent."""

    def store_short_term(self, agent: Agent, entry: MemoryEntry) -> None:
        agent.short_term_memory.append(entry)
        # Enforce size limit - oldest memories first
        if len(agent.short_term_memory) > SHORT_TERM_MEMORY_LIMIT:
            # Consolidate important short-term memories to episodic
            oldest = agent.short_term_memory.pop(0)
            if abs(oldest.emotional_weight) > 0.5:
                self.consolidate_to_episodic(agent, oldest)

    def consolidate_to_episodic(self, agent: Agent, entry: MemoryEntry) -> None:
        agent.episodic_memory.append(entry)
        if len(agent.episodic_memory) > EPISODIC_MEMORY_LIMIT:
            # Remove weakest memories
            agent.episodic_memory.sort(key=lambda m: m.strength, reverse=True)
            agent.episodic_memory = agent.episodic_memory[:EPISODIC_MEMORY_LIMIT]

    def decay_memories(self, agent: Agent, tick: int) -> None:
        """Decay memory strength over time."""
        for memory in agent.episodic_memory:
            memory.strength = max(0.0, memory.strength - memory.decay_rate)

        # Remove very faded memories
        agent.episodic_memory = [m for m in agent.episodic_memory if m.strength > 0.05]

    def recall_about(self, agent: Agent, subject_id: str) -> list[MemoryEntry]:
        """Recall memories about a specific agent."""
        memories = []
        for m in agent.episodic_memory + agent.short_term_memory:
            if m.subject_id == subject_id:
                memories.append(m)
        return sorted(memories, key=lambda m: m.tick, reverse=True)

    def recall_recent(self, agent: Agent, event_type: str, n: int = 5) -> list[MemoryEntry]:
        """Recall recent memories of a specific type."""
        matches = [m for m in agent.short_term_memory if m.event_type == event_type]
        return sorted(matches, key=lambda m: m.tick, reverse=True)[:n]

    def update_social_memory(self, agent: Agent, subject_id: str, entry: MemoryEntry) -> None:
        if subject_id not in agent.social_memory:
            agent.social_memory[subject_id] = []
        agent.social_memory[subject_id].append(entry)
        # Keep last 20 interactions per agent
        if len(agent.social_memory[subject_id]) > 20:
            agent.social_memory[subject_id] = agent.social_memory[subject_id][-20:]

    def get_emotional_state(self, agent: Agent) -> dict[str, float]:
        """Derive emotional state from recent memories."""
        emotions = {"fear": 0.0, "anger": 0.0, "joy": 0.0, "sadness": 0.0, "trust": 0.0}

        for memory in agent.short_term_memory[-10:]:
            w = memory.emotional_weight
            if w < -0.7:
                emotions["fear"] += abs(w) * 0.5
                emotions["anger"] += abs(w) * 0.3
            elif w < -0.3:
                emotions["sadness"] += abs(w) * 0.6
            elif w > 0.7:
                emotions["joy"] += w * 0.7
                emotions["trust"] += w * 0.3
            elif w > 0.3:
                emotions["trust"] += w * 0.5

        # Normalize
        for k in emotions:
            emotions[k] = min(1.0, emotions[k])

        agent.emotional_state = emotions
        return emotions


class PredictionModule:
    """Predicts other agents' behaviors based on observed history."""

    def predict_action(
        self,
        observer: Agent,
        target: Agent,
        context: dict[str, Any],
    ) -> dict[str, float]:
        """Predict probable actions of target agent."""
        trust = observer.get_trust(target.agent_id)
        memories = observer.social_memory.get(target.agent_id, [])

        # Base predictions from personality
        predictions: dict[str, float] = {}
        p = target.personality

        predictions[ActionType.TRADE.value] = 0.3 + p.greed * 0.2
        predictions[ActionType.COOPERATE.value] = 0.4 + p.altruism * 0.3 - p.aggression * 0.2
        predictions[ActionType.ATTACK.value] = p.aggression * 0.3 + (1 - trust) * 0.2
        predictions[ActionType.BETRAY.value] = p.deception * 0.2 + (1 - p.loyalty) * 0.1
        predictions[ActionType.NEGOTIATE.value] = p.charisma * 0.3 + p.patience * 0.2

        # Update from memories of past behavior
        betrayal_count = sum(1 for m in memories if m.event_type == "betrayal")
        cooperation_count = sum(1 for m in memories if m.event_type == "cooperation")

        if betrayal_count > 0:
            predictions[ActionType.BETRAY.value] += betrayal_count * 0.1
            predictions[ActionType.COOPERATE.value] -= betrayal_count * 0.05

        if cooperation_count > 0:
            predictions[ActionType.COOPERATE.value] += cooperation_count * 0.05

        # Normalize
        total = sum(predictions.values())
        if total > 0:
            predictions = {k: v / total for k, v in predictions.items()}

        return predictions


class PlanningEngine:
    """Generates action plans based on goals, memory, and perception."""

    def __init__(self):
        self.memory_system = MemorySystem()
        self.prediction = PredictionModule()

    def plan(
        self,
        agent: Agent,
        perception: dict[str, Any],
        tick: int,
        market_prices: dict[ResourceType, float],
    ) -> Optional[dict[str, Any]]:
        """
        Generate the best action for an agent given current state.
        Returns an action dict or None if agent should stay idle.
        """
        if not agent.is_alive() or agent.state == AgentState.IMPRISONED:
            return None

        # Check energy - need to rest
        if agent.vitals.energy < 20:
            return {"action": ActionType.REST, "agent_id": agent.agent_id}

        # Critical survival needs override everything
        survival_action = self._check_survival_needs(agent, perception, tick)
        if survival_action:
            return survival_action

        # Check active goals
        goal_action = self._pursue_active_goal(agent, perception, tick, market_prices)
        if goal_action:
            return goal_action

        # Type-specific default behavior
        return self._default_behavior(agent, perception, tick, market_prices)

    def _check_survival_needs(
        self, agent: Agent, perception: dict, tick: int
    ) -> Optional[dict]:
        """Check if agent has critical survival needs."""
        # Critical health
        if agent.vitals.health < 20:
            # Look for medicine nearby
            resources = perception.get("available_resources", {})
            if resources.get(ResourceType.MEDICINE, 0) > 0:
                return {
                    "action": ActionType.HARVEST,
                    "resource": ResourceType.MEDICINE,
                    "agent_id": agent.agent_id,
                    "priority": 1.0,
                }

        # Severe hunger
        if agent.vitals.hunger > 70:
            resources = perception.get("available_resources", {})
            if resources.get(ResourceType.FOOD, 0) > 0:
                return {
                    "action": ActionType.HARVEST,
                    "resource": ResourceType.FOOD,
                    "agent_id": agent.agent_id,
                    "priority": 0.95,
                }
            # Try to buy or trade
            visible = perception.get("visible_agents", [])
            traders = [a for a in visible if a.inventory.get(ResourceType.FOOD) > 10]
            if traders:
                return {
                    "action": ActionType.TRADE,
                    "agent_id": agent.agent_id,
                    "target_id": traders[0].agent_id,
                    "offer": {ResourceType.MONEY: 5},
                    "request": {ResourceType.FOOD: 10},
                    "priority": 0.9,
                }

        # Threats - flee or fight
        threats = perception.get("threats", [])
        if threats and agent.vitals.health > 30:
            threat = threats[0]
            # Decide fight or flight based on personality and relative strength
            if (agent.personality.aggression > 0.6 and
                    agent.skills.combat > threat.skills.combat * 0.8):
                return {
                    "action": ActionType.ATTACK,
                    "agent_id": agent.agent_id,
                    "target_id": threat.agent_id,
                    "priority": 0.8,
                }
            else:
                return {
                    "action": ActionType.MIGRATE,
                    "agent_id": agent.agent_id,
                    "flee_from": threat.agent_id,
                    "priority": 0.85,
                }

        return None

    def _pursue_active_goal(
        self, agent: Agent, perception: dict, tick: int, market_prices: dict
    ) -> Optional[dict]:
        """Try to advance the highest-priority active goal."""
        all_goals = sorted(
            agent.short_term_goals + agent.long_term_goals,
            key=lambda g: g.priority, reverse=True
        )

        for goal in all_goals:
            if goal.is_achieved:
                continue

            action = self._goal_to_action(agent, goal, perception, market_prices)
            if action:
                return action

        return None

    def _goal_to_action(
        self, agent: Agent, goal: AgentGoal, perception: dict, market_prices: dict
    ) -> Optional[dict]:
        """Convert a goal into a concrete action."""
        if goal.target_resource:
            # Resource acquisition goal
            inventory_amount = agent.inventory.get(goal.target_resource)
            if inventory_amount >= goal.target_amount:
                goal.is_achieved = True
                return None

            # Try to gather from environment
            resources = perception.get("available_resources", {})
            if resources.get(goal.target_resource, 0) > 0:
                return {
                    "action": ActionType.HARVEST,
                    "resource": goal.target_resource,
                    "agent_id": agent.agent_id,
                }

            # Try to trade for it
            visible = perception.get("visible_agents", [])
            for other in visible:
                if other.inventory.get(goal.target_resource) > 5:
                    return {
                        "action": ActionType.TRADE,
                        "agent_id": agent.agent_id,
                        "target_id": other.agent_id,
                        "request": {goal.target_resource: 10},
                        "offer": {ResourceType.MONEY: 10 * market_prices.get(goal.target_resource, 1.0)},
                    }

        elif goal.target_agent_id:
            target = next(
                (a for a in perception.get("visible_agents", []) if a.agent_id == goal.target_agent_id),
                None
            )
            if target:
                return {
                    "action": ActionType.NEGOTIATE,
                    "agent_id": agent.agent_id,
                    "target_id": goal.target_agent_id,
                }

        return None

    def _default_behavior(
        self, agent: Agent, perception: dict, tick: int, market_prices: dict
    ) -> dict[str, Any]:
        """Type-specific default behavior when no urgent goal."""
        visible = perception.get("visible_agents", [])
        resources = perception.get("available_resources", {})

        behaviors = {
            AgentType.FARMER: self._farmer_behavior,
            AgentType.TRADER: self._trader_behavior,
            AgentType.BUILDER: self._builder_behavior,
            AgentType.GUARD: self._guard_behavior,
            AgentType.SPY: self._spy_behavior,
            AgentType.THIEF: self._thief_behavior,
            AgentType.REBEL: self._rebel_behavior,
            AgentType.DIPLOMAT: self._diplomat_behavior,
            AgentType.SCIENTIST: self._scientist_behavior,
            AgentType.MEDIATOR: self._mediator_behavior,
        }

        behavior_fn = behaviors.get(agent.agent_type)
        if behavior_fn:
            return behavior_fn(agent, perception, tick, market_prices)

        # Default worker behavior
        return self._worker_behavior(agent, perception, tick, market_prices)

    def _farmer_behavior(self, agent, perception, tick, prices) -> dict:
        resources = perception.get("available_resources", {})
        if resources.get(ResourceType.FOOD, 0) > 5:
            return {"action": ActionType.HARVEST, "resource": ResourceType.FOOD, "agent_id": agent.agent_id}
        return {"action": ActionType.REST, "agent_id": agent.agent_id}

    def _trader_behavior(self, agent, perception, tick, prices) -> dict:
        visible = perception.get("visible_agents", [])
        if visible:
            target = random.choice(visible)
            # Find what they might want vs what we have
            for resource in ResourceType:
                if agent.inventory.get(resource) > 20:
                    return {
                        "action": ActionType.TRADE,
                        "agent_id": agent.agent_id,
                        "target_id": target.agent_id,
                        "offer": {resource: 10},
                        "request": {ResourceType.MONEY: 10 * prices.get(resource, 1.0)},
                    }
        return {"action": ActionType.MIGRATE, "agent_id": agent.agent_id, "direction": "random"}

    def _builder_behavior(self, agent, perception, tick, prices) -> dict:
        if (agent.inventory.get(ResourceType.TOOLS) > 5 and
                agent.inventory.get(ResourceType.RAW_MATERIALS) > 10):
            return {"action": ActionType.BUILD, "agent_id": agent.agent_id}
        return {"action": ActionType.HARVEST, "resource": ResourceType.RAW_MATERIALS, "agent_id": agent.agent_id}

    def _guard_behavior(self, agent, perception, tick, prices) -> dict:
        threats = perception.get("threats", [])
        if threats:
            return {"action": ActionType.ATTACK, "agent_id": agent.agent_id, "target_id": threats[0].agent_id}
        return {"action": ActionType.REST, "agent_id": agent.agent_id}

    def _spy_behavior(self, agent, perception, tick, prices) -> dict:
        visible = perception.get("visible_agents", [])
        if visible:
            target = random.choice(visible)
            return {"action": ActionType.SPY_ON, "agent_id": agent.agent_id, "target_id": target.agent_id}
        return {"action": ActionType.MIGRATE, "agent_id": agent.agent_id, "direction": "random"}

    def _thief_behavior(self, agent, perception, tick, prices) -> dict:
        visible = perception.get("visible_agents", [])
        rich_targets = [a for a in visible if a.inventory.total_value(prices) > 50]
        if rich_targets and agent.personality.risk_tolerance > 0.4:
            target = random.choice(rich_targets)
            return {"action": ActionType.STEAL, "agent_id": agent.agent_id, "target_id": target.agent_id}
        return {"action": ActionType.REST, "agent_id": agent.agent_id}

    def _rebel_behavior(self, agent, perception, tick, prices) -> dict:
        visible = perception.get("visible_agents", [])
        guards = [a for a in visible if a.agent_type == AgentType.GUARD]
        if guards and agent.personality.aggression > 0.5:
            return {"action": ActionType.REBEL, "agent_id": agent.agent_id}
        # Recruit
        workers = [a for a in visible if a.agent_type == AgentType.WORKER]
        if workers:
            target = random.choice(workers)
            return {"action": ActionType.GOSSIP, "agent_id": agent.agent_id,
                    "target_id": target.agent_id, "content": "regime_critique"}
        return {"action": ActionType.SPREAD_RUMOR, "agent_id": agent.agent_id}

    def _diplomat_behavior(self, agent, perception, tick, prices) -> dict:
        visible = perception.get("visible_agents", [])
        conflicts = [a for a in visible if a.state == AgentState.FIGHTING]
        if conflicts:
            return {"action": ActionType.NEGOTIATE, "agent_id": agent.agent_id,
                    "target_id": conflicts[0].agent_id}
        if visible:
            target = random.choice(visible)
            return {"action": ActionType.FORM_ALLIANCE, "agent_id": agent.agent_id,
                    "target_id": target.agent_id}
        return {"action": ActionType.MIGRATE, "agent_id": agent.agent_id, "direction": "random"}

    def _scientist_behavior(self, agent, perception, tick, prices) -> dict:
        if agent.inventory.get(ResourceType.COMPUTING) > 0:
            return {"action": ActionType.RESEARCH, "agent_id": agent.agent_id}
        return {"action": ActionType.HARVEST, "resource": ResourceType.COMPUTING, "agent_id": agent.agent_id}

    def _mediator_behavior(self, agent, perception, tick, prices) -> dict:
        visible = perception.get("visible_agents", [])
        if visible:
            # Help lowest-health agent
            needy = min(visible, key=lambda a: a.vitals.health)
            if needy.vitals.health < 50:
                return {"action": ActionType.GIFT, "agent_id": agent.agent_id,
                        "target_id": needy.agent_id, "resource": ResourceType.MEDICINE}
        return {"action": ActionType.REST, "agent_id": agent.agent_id}

    def _worker_behavior(self, agent, perception, tick, prices) -> dict:
        resources = perception.get("available_resources", {})
        # Work on whatever is available
        for resource in [ResourceType.FOOD, ResourceType.RAW_MATERIALS, ResourceType.TOOLS]:
            if resources.get(resource, 0) > 5:
                return {"action": ActionType.HARVEST, "resource": resource, "agent_id": agent.agent_id}
        return {"action": ActionType.REST, "agent_id": agent.agent_id}


class CognitiveEngine:
    """
    Orchestrates the full cognitive loop for all agents:
    Perceive → Interpret → Remember → Predict → Plan → Act
    """

    def __init__(self):
        self.perception = PerceptionModule()
        self.memory = MemorySystem()
        self.prediction = PredictionModule()
        self.planning = PlanningEngine()

    def process_agent(
        self,
        agent: Agent,
        nearby_agents: list[Agent],
        nearby_cells: list[Cell],
        world_events: list[dict],
        tick: int,
        market_prices: dict[ResourceType, float],
    ) -> Optional[dict[str, Any]]:
        """Full cognitive cycle for one agent. Returns intended action."""
        if not agent.is_alive():
            return None

        # 1. Perception
        percept = self.perception.perceive(agent, nearby_agents, nearby_cells, world_events)

        # 2. Memory recall & update
        self.memory.decay_memories(agent, tick)
        emotional_state = self.memory.get_emotional_state(agent)
        agent.vitals.stress = min(100.0, agent.vitals.stress + emotional_state.get("fear", 0) * 5)

        # 3. Interpret perceptions → update beliefs
        self._update_beliefs(agent, percept, tick)

        # 4. Update trust based on observations
        self._update_trust_from_perception(agent, percept, tick)

        # 5. Planning
        action = self.planning.plan(agent, percept, tick, market_prices)

        # 6. Store current perception as short-term memory
        if percept.get("threats"):
            self.memory.store_short_term(agent, MemoryEntry(
                tick=tick,
                event_type="perceived_threat",
                content={"count": len(percept["threats"])},
                emotional_weight=-0.6,
            ))

        agent.last_active_tick = tick
        return action

    def _update_beliefs(self, agent: Agent, percept: dict, tick: int) -> None:
        """Form/update beliefs from perceptions."""
        resources = percept.get("available_resources", {})
        world_events = percept.get("recent_world_events", [])

        for event in world_events:
            if event.get("event_type") == "disaster_start":
                belief = AgentBelief(
                    topic="world_danger",
                    content=f"Disaster: {event.get('data', {}).get('type', 'unknown')}",
                    strength=BeliefStrength.STRONG,
                    is_true=True,
                    adopted_tick=tick,
                )
                # Don't duplicate beliefs
                if not any(b.topic == "world_danger" for b in agent.beliefs):
                    agent.beliefs.append(belief)

        # Food scarcity belief
        if resources.get(ResourceType.FOOD, 0) < 5:
            if not any(b.topic == "food_scarcity" for b in agent.beliefs):
                agent.beliefs.append(AgentBelief(
                    topic="food_scarcity",
                    content="Food is scarce",
                    strength=BeliefStrength.MODERATE,
                    is_true=True,
                    adopted_tick=tick,
                ))
        else:
            agent.beliefs = [b for b in agent.beliefs if b.topic != "food_scarcity"]

    def _update_trust_from_perception(self, agent: Agent, percept: dict, tick: int) -> None:
        """Update trust scores based on observed agent behaviors."""
        visible = percept.get("visible_agents", [])
        for other in visible:
            if other.agent_id not in agent.trust_map:
                agent.trust_map[other.agent_id] = TrustEntry(
                    agent_id=other.agent_id,
                    trust_score=0.0,
                    last_interaction_tick=tick,
                )

            entry = agent.trust_map[other.agent_id]
            entry.last_interaction_tick = tick

            # Passive trust updates based on type
            if other.agent_type == AgentType.MEDIATOR:
                entry.trust_score = min(1.0, entry.trust_score + 0.01)
            elif other.agent_type == AgentType.THIEF:
                entry.trust_score = max(-1.0, entry.trust_score - 0.02)

    def record_interaction(
        self,
        agent: Agent,
        other_agent_id: str,
        action: ActionType,
        outcome: str,
        tick: int,
    ) -> None:
        """Record the result of an interaction in memory."""
        emotional_weights = {
            "betrayed": -0.9,
            "robbed": -0.8,
            "attacked": -0.8,
            "trade_success": 0.4,
            "cooperation": 0.5,
            "gift_received": 0.7,
            "helped": 0.6,
            "threatened": -0.5,
            "bribed": -0.3,
        }
        weight = emotional_weights.get(outcome, 0.0)

        memory = MemoryEntry(
            tick=tick,
            event_type=outcome,
            subject_id=other_agent_id,
            content={"action": action.value, "outcome": outcome},
            emotional_weight=weight,
        )
        self.memory.store_short_term(agent, memory)
        self.memory.update_social_memory(agent, other_agent_id, memory)

        # Update trust
        if other_agent_id in agent.trust_map:
            entry = agent.trust_map[other_agent_id]
            trust_delta = weight * 0.2
            entry.trust_score = max(-1.0, min(1.0, entry.trust_score + trust_delta))
            if outcome == "betrayed":
                entry.betrayal_count += 1
            elif outcome in ("trade_success", "cooperation", "gift_received"):
                entry.cooperation_count += 1
        else:
            weight_init = max(-1.0, min(1.0, weight * 0.5))
            agent.trust_map[other_agent_id] = TrustEntry(
                agent_id=other_agent_id,
                trust_score=weight_init,
                last_interaction_tick=tick,
                betrayal_count=1 if outcome == "betrayed" else 0,
                cooperation_count=1 if outcome in ("trade_success", "cooperation") else 0,
            )

    def learn_from_outcome(self, agent: Agent, action: ActionType, success: bool, tick: int) -> None:
        """Simple reinforcement learning - strengthen skills on success."""
        skill_map = {
            ActionType.TRADE: "trading",
            ActionType.ATTACK: "combat",
            ActionType.NEGOTIATE: "diplomacy",
            ActionType.SPY_ON: "espionage",
            ActionType.STEAL: "espionage",
            ActionType.BUILD: "building",
            ActionType.HARVEST: "farming",
            ActionType.RESEARCH: "science",
        }
        skill_name = skill_map.get(action)
        if skill_name and hasattr(agent.skills, skill_name):
            current = getattr(agent.skills, skill_name)
            delta = 0.001 if success else -0.0005
            setattr(agent.skills, skill_name, max(0.0, min(1.0, current + delta)))
