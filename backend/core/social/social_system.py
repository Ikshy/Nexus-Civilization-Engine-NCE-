"""
Nexus Civilization Engine - Social System
Relationships, trust propagation, gossip, alliances, faction formation, cultural norms.
"""
from __future__ import annotations
import random
import math
import logging
from typing import Optional
from collections import defaultdict
import networkx as nx

from backend.core.enums import (
    RelationshipType, ActionType, AgentType, InformationType,
    GOSSIP_DECAY_RATE
)
from backend.core.models import (
    Agent, Faction, GossipEntry, NegotiationState, TrustEntry,
    MemoryEntry, ResourceBundle, SimulationEvent
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class RelationshipGraph:
    """
    NetworkX-backed social graph tracking relationships between all agents.
    Edges carry: trust, relationship_type, interaction_count, last_tick
    """

    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()

    def add_agent(self, agent_id: str, metadata: dict) -> None:
        self.graph.add_node(agent_id, **metadata)

    def remove_agent(self, agent_id: str) -> None:
        if agent_id in self.graph:
            self.graph.remove_node(agent_id)

    def update_relationship(
        self,
        from_id: str,
        to_id: str,
        trust_delta: float,
        interaction_type: str,
        tick: int,
    ) -> None:
        if not self.graph.has_node(from_id):
            self.graph.add_node(from_id)
        if not self.graph.has_node(to_id):
            self.graph.add_node(to_id)

        if self.graph.has_edge(from_id, to_id):
            edge = self.graph[from_id][to_id]
            old_trust = edge.get("trust", 0.0)
            new_trust = max(-1.0, min(1.0, old_trust + trust_delta))
            edge["trust"] = new_trust
            edge["interaction_count"] = edge.get("interaction_count", 0) + 1
            edge["last_tick"] = tick
            edge["relationship"] = self._trust_to_relationship(new_trust)
        else:
            trust = max(-1.0, min(1.0, trust_delta))
            self.graph.add_edge(
                from_id, to_id,
                trust=trust,
                relationship=self._trust_to_relationship(trust),
                interaction_count=1,
                last_tick=tick,
            )

    def get_trust(self, from_id: str, to_id: str) -> float:
        if self.graph.has_edge(from_id, to_id):
            return self.graph[from_id][to_id].get("trust", 0.0)
        return 0.0

    def get_allies(self, agent_id: str) -> list[str]:
        if agent_id not in self.graph:
            return []
        return [
            n for n in self.graph.successors(agent_id)
            if self.graph[agent_id][n].get("trust", 0) > 0.5
        ]

    def get_enemies(self, agent_id: str) -> list[str]:
        if agent_id not in self.graph:
            return []
        return [
            n for n in self.graph.successors(agent_id)
            if self.graph[agent_id][n].get("trust", 0) < -0.3
        ]

    def decay_relationships(self, inactive_agents: set[str], tick: int) -> None:
        """Decay trust for agents who haven't interacted recently."""
        for from_id, to_id in list(self.graph.edges()):
            edge = self.graph[from_id][to_id]
            last_tick = edge.get("last_tick", 0)
            if tick - last_tick > 50:
                # Decay toward neutral
                trust = edge.get("trust", 0.0)
                edge["trust"] = trust * (1 - settings.simulation.reputation_decay_rate)
                edge["relationship"] = self._trust_to_relationship(edge["trust"])

    def _trust_to_relationship(self, trust: float) -> str:
        if trust > 0.7:
            return RelationshipType.ALLY.value
        elif trust > 0.3:
            return RelationshipType.FRIEND.value
        elif trust > -0.3:
            return RelationshipType.NEUTRAL.value
        elif trust > -0.6:
            return RelationshipType.RIVAL.value
        else:
            return RelationshipType.ENEMY.value

    def get_network_metrics(self) -> dict:
        if len(self.graph) < 2:
            return {}
        try:
            return {
                "density": nx.density(self.graph),
                "avg_clustering": nx.average_clustering(self.graph.to_undirected()),
                "components": nx.number_weakly_connected_components(self.graph),
                "node_count": self.graph.number_of_nodes(),
                "edge_count": self.graph.number_of_edges(),
            }
        except Exception:
            return {"node_count": self.graph.number_of_nodes()}

    def get_centrality(self) -> dict[str, float]:
        if len(self.graph) < 2:
            return {}
        try:
            return nx.betweenness_centrality(self.graph, normalized=True)
        except Exception:
            return {}

    def get_communities(self) -> list[set[str]]:
        """Detect community clusters."""
        try:
            undirected = self.graph.to_undirected()
            communities = list(nx.community.greedy_modularity_communities(undirected))
            return [set(c) for c in communities]
        except Exception:
            return []

    def serialize_for_api(self, max_nodes: int = 200) -> dict:
        """Return a sample of the graph for visualization."""
        nodes_to_show = list(self.graph.nodes())[:max_nodes]
        subgraph = self.graph.subgraph(nodes_to_show)
        return {
            "nodes": [
                {
                    "id": n,
                    **{k: v for k, v in self.graph.nodes[n].items()
                       if isinstance(v, (str, int, float, bool))},
                }
                for n in subgraph.nodes()
            ],
            "edges": [
                {
                    "source": u, "target": v,
                    "trust": d.get("trust", 0),
                    "relationship": d.get("relationship", "neutral"),
                }
                for u, v, d in subgraph.edges(data=True)
            ],
        }


class GossipSystem:
    """Models information spreading through social networks."""

    def __init__(self, relationship_graph: RelationshipGraph):
        self.graph = relationship_graph
        self.active_gossip: dict[str, GossipEntry] = {}
        self.archived: list[GossipEntry] = []

    def create_gossip(
        self,
        originator: Agent,
        subject_id: str,
        content: str,
        info_type: InformationType,
        is_true: bool,
        tick: int,
    ) -> GossipEntry:
        entry = GossipEntry(
            originator_id=originator.agent_id,
            subject_id=subject_id,
            content=content,
            info_type=info_type,
            is_true=is_true,
            believers=[originator.agent_id],
            created_tick=tick,
        )
        self.active_gossip[entry.gossip_id] = entry
        return entry

    def spread_gossip(
        self,
        spreader: Agent,
        gossip_id: str,
        nearby_agents: list[Agent],
        tick: int,
    ) -> list[str]:
        """Spread a piece of gossip to nearby agents. Returns new believer IDs."""
        gossip = self.active_gossip.get(gossip_id)
        if not gossip:
            return []

        new_believers = []
        spread_range = settings.simulation.gossip_spread_radius

        for listener in nearby_agents:
            if listener.agent_id in gossip.believers:
                continue
            if listener.agent_id == gossip.subject_id:
                continue  # Don't spread to subject

            # Adoption probability based on:
            # 1. Spreader reputation/trust
            # 2. Listener's skepticism (inverse of curiosity and conformity)
            # 3. Emotional resonance

            trust = listener.get_trust(spreader.agent_id)
            base_prob = 0.3 + trust * 0.3
            skepticism = listener.personality.curiosity * 0.2

            # Personality adjustments
            if listener.personality.conformity > 0.6:
                base_prob += 0.1
            if gossip.info_type == InformationType.DISINFORMATION:
                base_prob -= 0.2  # Harder to spread lies to critical thinkers

            adoption_prob = max(0.05, min(0.9, base_prob - skepticism))

            if random.random() < adoption_prob:
                gossip.believers.append(listener.agent_id)
                gossip.spread_count += 1
                new_believers.append(listener.agent_id)

                # Affect beliefs of listener
                from backend.core.models import AgentBelief
                from backend.core.enums import BeliefStrength
                listener.beliefs.append(AgentBelief(
                    topic=f"gossip_{gossip.subject_id}",
                    content=gossip.content,
                    strength=BeliefStrength.WEAK,
                    source_agent_id=spreader.agent_id,
                    is_true=gossip.is_true,
                    adopted_tick=tick,
                ))

                # Affect reputation of subject
                subject_mention = gossip.subject_id
                if gossip.info_type in (InformationType.RUMOR, InformationType.DISINFORMATION):
                    # Negative gossip damages reputation
                    if hasattr(listener, 'relationship_map') and subject_mention:
                        pass  # Could update reputation here

        return new_believers

    def decay_gossip(self, tick: int) -> list[str]:
        """Decay gossip strength over time. Returns expired gossip IDs."""
        expired = []
        for gid, gossip in list(self.active_gossip.items()):
            age = tick - gossip.created_tick
            gossip.decay_rate = GOSSIP_DECAY_RATE * (1 + age / 100)

            # Archive if too old
            if age > 200 or gossip.spread_count > 100:
                self.archived.append(gossip)
                expired.append(gid)
                del self.active_gossip[gid]

        return expired


class FactionSystem:
    """Manages faction formation, governance, alliances, and conflict."""

    def __init__(self):
        self.factions: dict[str, Faction] = {}
        self._name_pool = [
            "Iron Collective", "Free Alliance", "Northern Order", "Southern League",
            "Merchant Guild", "Workers Union", "Scholar Society", "Shadow Network",
            "Peace Front", "Reform Movement", "Rebel Coalition", "Tech Syndicate",
        ]
        self._used_names: set[str] = set()

    def create_faction(
        self,
        founder: Agent,
        tick: int,
        name: Optional[str] = None,
    ) -> Faction:
        if name is None:
            available = [n for n in self._name_pool if n not in self._used_names]
            name = random.choice(available) if available else f"Faction-{len(self.factions)}"
        self._used_names.add(name)

        faction = Faction(
            name=name,
            leader_id=founder.agent_id,
            member_ids=[founder.agent_id],
            ideology=dict(founder.ideology),
            formed_tick=tick,
        )
        self.factions[faction.faction_id] = faction
        founder.faction_id = faction.faction_id
        logger.info(f"Faction formed: {name} by {founder.name}")
        return faction

    def recruit_member(
        self, faction_id: str, agent: Agent, recruiter: Agent
    ) -> bool:
        faction = self.factions.get(faction_id)
        if not faction:
            return False

        # Recruitment check
        trust = agent.get_trust(recruiter.agent_id)
        ideology_match = self._ideology_similarity(agent.ideology, faction.ideology)

        join_prob = 0.3 + trust * 0.3 + ideology_match * 0.4
        if agent.personality.conformity > 0.6:
            join_prob += 0.1
        if agent.faction_id:
            join_prob -= 0.3  # Harder to poach

        if random.random() < join_prob:
            if agent.faction_id:
                self._leave_faction(agent)
            agent.faction_id = faction_id
            faction.member_ids.append(agent.agent_id)
            return True
        return False

    def _leave_faction(self, agent: Agent) -> None:
        if not agent.faction_id:
            return
        faction = self.factions.get(agent.faction_id)
        if faction:
            if agent.agent_id in faction.member_ids:
                faction.member_ids.remove(agent.agent_id)
            if faction.leader_id == agent.agent_id:
                # Leadership succession
                if faction.member_ids:
                    faction.leader_id = faction.member_ids[0]
                else:
                    del self.factions[faction.faction_id]
        agent.faction_id = None

    def form_alliance(
        self, faction1_id: str, faction2_id: str, tick: int
    ) -> bool:
        f1 = self.factions.get(faction1_id)
        f2 = self.factions.get(faction2_id)
        if not f1 or not f2:
            return False
        if faction2_id in f1.ally_faction_ids:
            return True  # Already allied

        # Check ideology compatibility
        sim = self._ideology_similarity(f1.ideology, f2.ideology)
        if sim < 0.3:
            return False

        f1.ally_faction_ids.append(faction2_id)
        f2.ally_faction_ids.append(faction1_id)
        f1.enemy_faction_ids = [eid for eid in f1.enemy_faction_ids if eid != faction2_id]
        f2.enemy_faction_ids = [eid for eid in f2.enemy_faction_ids if eid != faction1_id]
        logger.info(f"Alliance formed: {f1.name} <-> {f2.name}")
        return True

    def break_alliance(self, faction1_id: str, faction2_id: str) -> None:
        f1 = self.factions.get(faction1_id)
        f2 = self.factions.get(faction2_id)
        if f1:
            f1.ally_faction_ids = [x for x in f1.ally_faction_ids if x != faction2_id]
        if f2:
            f2.ally_faction_ids = [x for x in f2.ally_faction_ids if x != faction1_id]

    def declare_war(self, attacker_id: str, defender_id: str) -> None:
        f1 = self.factions.get(attacker_id)
        f2 = self.factions.get(defender_id)
        if f1 and defender_id not in f1.enemy_faction_ids:
            f1.enemy_faction_ids.append(defender_id)
        if f2 and attacker_id not in f2.enemy_faction_ids:
            f2.enemy_faction_ids.append(attacker_id)
        self.break_alliance(attacker_id, defender_id)

    def _ideology_similarity(self, ideology1: dict, ideology2: dict) -> float:
        if not ideology1 or not ideology2:
            return 0.5
        common_keys = set(ideology1) & set(ideology2)
        if not common_keys:
            return 0.5
        diffs = [abs(ideology1[k] - ideology2[k]) for k in common_keys]
        return 1.0 - (sum(diffs) / len(diffs))

    def get_faction_power(self, faction_id: str, agents_by_id: dict[str, Agent]) -> float:
        faction = self.factions.get(faction_id)
        if not faction:
            return 0.0
        members = [agents_by_id.get(mid) for mid in faction.member_ids if mid in agents_by_id]
        members = [m for m in members if m and m.is_alive()]
        if not members:
            return 0.0
        combat_power = sum(m.skills.combat for m in members)
        economic_power = sum(m.net_worth for m in members) / 1000
        return combat_power + economic_power

    def update_faction_resources(self, agents: list[Agent]) -> None:
        """Aggregate resources from faction members."""
        for faction in self.factions.values():
            # Shared faction treasury tracked separately from individual inventories
            pass

    def get_factions_snapshot(self) -> list[dict]:
        return [
            {
                "faction_id": f.faction_id,
                "name": f.name,
                "leader_id": f.leader_id,
                "member_count": len(f.member_ids),
                "ally_count": len(f.ally_faction_ids),
                "enemy_count": len(f.enemy_faction_ids),
                "governance": f.governance_type.value,
                "formed_tick": f.formed_tick,
            }
            for f in self.factions.values()
        ]


class NegotiationEngine:
    """Handles multi-round negotiations between agents/factions."""

    def __init__(self):
        self.active_negotiations: dict[str, NegotiationState] = {}

    def initiate(
        self,
        initiator: Agent,
        counterpart: Agent,
        topic: str,
        tick: int,
    ) -> NegotiationState:
        neg = NegotiationState(
            participants=[initiator.agent_id, counterpart.agent_id],
            topic=topic,
            created_tick=tick,
        )
        self.active_negotiations[neg.negotiation_id] = neg
        return neg

    def process_round(
        self,
        neg_id: str,
        agents_by_id: dict[str, Agent],
        tick: int,
    ) -> dict:
        neg = self.active_negotiations.get(neg_id)
        if not neg or neg.status != "open":
            return {"status": "not_found"}

        neg.rounds += 1
        if neg.rounds > neg.max_rounds:
            neg.status = "failed"
            del self.active_negotiations[neg_id]
            return {"status": "failed", "reason": "max_rounds"}

        participants = [agents_by_id.get(pid) for pid in neg.participants]
        if not all(participants):
            neg.status = "failed"
            return {"status": "failed", "reason": "participant_unavailable"}

        # Simple negotiation outcome
        a1, a2 = participants[0], participants[1]
        trust = a1.get_trust(a2.agent_id)
        both_want = a1.personality.patience > 0.4 and a2.personality.patience > 0.4
        compatible = abs(a1.personality.aggression - a2.personality.aggression) < 0.5

        if trust > 0.2 and both_want and compatible:
            neg.status = "agreed"
            del self.active_negotiations[neg_id]
            return {"status": "agreed", "topic": neg.topic}

        return {"status": "ongoing", "rounds": neg.rounds}


class ReputationSystem:
    """Global reputation tracking and decay."""

    def __init__(self):
        self._reputation_changes: list[dict] = []

    def update_reputation(
        self,
        agent: Agent,
        delta: float,
        reason: str,
        tick: int,
        witnesses: list[Agent] = None,
    ) -> None:
        old_rep = agent.reputation
        agent.reputation = max(-100.0, min(100.0, agent.reputation + delta))

        self._reputation_changes.append({
            "tick": tick,
            "agent_id": agent.agent_id,
            "delta": delta,
            "old": old_rep,
            "new": agent.reputation,
            "reason": reason,
        })

        # Witnesses update their trust
        if witnesses:
            for witness in witnesses:
                trust_delta = delta * 0.05
                if agent.agent_id in witness.trust_map:
                    entry = witness.trust_map[agent.agent_id]
                    entry.trust_score = max(-1.0, min(1.0, entry.trust_score + trust_delta))

    def decay_all(self, agents: list[Agent]) -> None:
        """Reputation decays slowly toward 50 (neutral)."""
        rate = settings.simulation.reputation_decay_rate
        for agent in agents:
            if agent.is_alive():
                diff = agent.reputation - 50.0
                agent.reputation -= diff * rate * 0.01


class SocialSystem:
    """
    Orchestrates all social subsystems: relationships, gossip,
    factions, negotiations, and reputation.
    """

    def __init__(self):
        self.relationship_graph = RelationshipGraph()
        self.gossip_system = GossipSystem(self.relationship_graph)
        self.faction_system = FactionSystem()
        self.negotiation_engine = NegotiationEngine()
        self.reputation_system = ReputationSystem()

    def initialize_agents(self, agents: list[Agent]) -> None:
        """Register all agents in social graph."""
        for agent in agents:
            self.relationship_graph.add_agent(agent.agent_id, {
                "name": agent.name,
                "type": agent.agent_type.value,
                "faction": agent.faction_id or "",
            })

        # Create initial factions for leader-type agents
        leaders = [a for a in agents if a.agent_type == AgentType.LEADER]
        for leader in leaders[:3]:  # Max 3 initial factions
            if not leader.faction_id:
                self.faction_system.create_faction(leader, tick=0)

        # Assign workers/farmers to nearby factions
        for agent in agents:
            if agent.faction_id:
                continue
            if self.faction_system.factions and random.random() < 0.6:
                faction_id = random.choice(list(self.faction_system.factions.keys()))
                faction = self.faction_system.factions[faction_id]
                agent.faction_id = faction_id
                faction.member_ids.append(agent.agent_id)

    def tick(self, agents: list[Agent], tick: int) -> list[dict]:
        """Process social tick. Returns events."""
        events = []
        alive = [a for a in agents if a.is_alive()]

        # Decay gossip
        expired_gossip = self.gossip_system.decay_gossip(tick)

        # Decay relationships
        inactive = set()
        self.relationship_graph.decay_relationships(inactive, tick)

        # Reputation decay
        self.reputation_system.decay_all(alive)

        # Check for new faction formation (leaders without faction)
        for agent in alive:
            if (agent.agent_type == AgentType.LEADER and
                    not agent.faction_id and
                    len(self.faction_system.factions) < 10 and
                    random.random() < 0.01):
                faction = self.faction_system.create_faction(agent, tick)
                events.append({
                    "event_type": "faction_formed",
                    "faction_id": faction.faction_id,
                    "name": faction.name,
                    "leader": agent.agent_id,
                    "tick": tick,
                })

        # Update relationship graph metadata
        for agent in alive:
            if agent.agent_id in self.relationship_graph.graph:
                self.relationship_graph.graph.nodes[agent.agent_id].update({
                    "faction": agent.faction_id or "",
                    "reputation": agent.reputation,
                    "type": agent.agent_type.value,
                })

        return events

    def process_action_outcome(
        self,
        actor: Agent,
        target: Optional[Agent],
        action: ActionType,
        success: bool,
        tick: int,
        nearby_witnesses: list[Agent] = None,
    ) -> None:
        """Update social systems based on action outcome."""
        if not target:
            return

        # Trust updates
        trust_deltas = {
            ActionType.TRADE: (0.05 if success else -0.02),
            ActionType.COOPERATE: 0.1,
            ActionType.BETRAY: -0.4,
            ActionType.ATTACK: -0.3,
            ActionType.GIFT: 0.15,
            ActionType.BRIBE: 0.05,
            ActionType.NEGOTIATE: (0.08 if success else -0.03),
            ActionType.STEAL: -0.5,
            ActionType.LIE: -0.3,
            ActionType.GOSSIP: -0.05,
        }
        trust_delta = trust_deltas.get(action, 0.0)

        self.relationship_graph.update_relationship(
            actor.agent_id, target.agent_id, trust_delta, action.value, tick
        )

        # Reputation updates
        rep_deltas = {
            ActionType.TRADE: 1.0 if success else -0.5,
            ActionType.COOPERATE: 2.0,
            ActionType.BETRAY: -10.0,
            ActionType.ATTACK: -5.0,
            ActionType.GIFT: 3.0,
            ActionType.STEAL: -8.0,
        }
        rep_delta = rep_deltas.get(action, 0.0)
        if rep_delta != 0:
            self.reputation_system.update_reputation(
                actor, rep_delta, action.value, tick, nearby_witnesses
            )

    def spread_gossip_about(
        self,
        spreader: Agent,
        subject: Agent,
        content: str,
        is_true: bool,
        nearby: list[Agent],
        tick: int,
    ) -> GossipEntry:
        """Convenience method to create and spread gossip."""
        info_type = InformationType.RUMOR if is_true else InformationType.DISINFORMATION
        gossip = self.gossip_system.create_gossip(
            spreader, subject.agent_id, content, info_type, is_true, tick
        )
        self.gossip_system.spread_gossip(spreader, gossip.gossip_id, nearby, tick)
        return gossip

    def get_social_snapshot(self) -> dict:
        return {
            "relationship_metrics": self.relationship_graph.get_network_metrics(),
            "faction_count": len(self.faction_system.factions),
            "factions": self.faction_system.get_factions_snapshot(),
            "active_gossip": len(self.gossip_system.active_gossip),
            "active_negotiations": len(self.negotiation_engine.active_negotiations),
        }
