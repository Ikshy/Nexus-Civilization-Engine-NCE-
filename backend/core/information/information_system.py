"""
Information Warfare Layer — NCE
Handles news, rumors, fake info, belief propagation, echo chambers, trust erosion.
"""
from __future__ import annotations
import math
import random
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import numpy as np

from ..enums import InformationType, BeliefStrength, AgentType
from ..models import Agent, NewsArticle, AgentBelief, GossipEntry, WorldState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Broadcast:
    broadcast_id: str
    source_agent_id: str
    content: str
    info_type: InformationType
    truth_value: float          # 0.0 = total lie, 1.0 = truth
    emotional_charge: float     # 0–1, how alarming/exciting
    reach: Set[str] = field(default_factory=set)
    tick_created: int = 0
    tick_expires: int = 100
    amplification: float = 1.0  # virality multiplier


@dataclass
class EchoChamber:
    chamber_id: str
    member_ids: Set[str]
    dominant_belief: str
    cohesion: float             # 0–1
    insularity: float           # 0–1 resistance to outside info
    formed_tick: int = 0


@dataclass
class InformationCascade:
    cascade_id: str
    origin_broadcast_id: str
    wave: List[Set[str]] = field(default_factory=list)  # each entry = agents reached at step N
    total_reached: int = 0
    tick_start: int = 0
    still_active: bool = True


@dataclass
class TrustErosionEvent:
    agent_id: str
    eroded_by: float
    reason: str
    tick: int


# ---------------------------------------------------------------------------
# News System
# ---------------------------------------------------------------------------

class NewsSystem:
    """Generates, distributes, and tracks news articles."""

    def __init__(self):
        self.articles: Dict[str, NewsArticle] = {}
        self._article_counter = 0

    # ---- generation --------------------------------------------------------

    def generate_article(
        self,
        author_id: str,
        headline: str,
        content: str,
        truth_value: float,
        info_type: InformationType,
        tick: int,
    ) -> NewsArticle:
        self._article_counter += 1
        aid = f"article_{self._article_counter:05d}"
        article = NewsArticle(
            article_id=aid,
            author_id=author_id,
            headline=headline,
            content=content,
            truth_value=truth_value,
            info_type=info_type,
            tick_published=tick,
            readers=set(),
            belief_impact={},
        )
        self.articles[aid] = article
        logger.debug("News article %s published by %s (truth=%.2f)", aid, author_id, truth_value)
        return article

    def generate_fake_news(
        self,
        author_id: str,
        target_agent_id: str,
        accusation: str,
        tick: int,
    ) -> NewsArticle:
        """Deliberately false article targeting a specific agent."""
        headline = f"BREAKING: Agent {target_agent_id} {accusation}"
        return self.generate_article(
            author_id=author_id,
            headline=headline,
            content=f"Sources claim that agent {target_agent_id} has been involved in {accusation}. "
                    f"Multiple witnesses confirm. Investigation ongoing.",
            truth_value=random.uniform(0.0, 0.15),
            info_type=InformationType.FAKE_NEWS,
            tick=tick,
        )

    # ---- distribution ------------------------------------------------------

    def distribute_to_agent(self, article: NewsArticle, agent: Agent) -> float:
        """
        Expose agent to article. Returns belief impact delta.
        Agent credibility filtering applied.
        """
        if article.article_id in agent.memory.semantic_memory:
            return 0.0  # already read

        article.readers.add(agent.agent_id)
        agent.memory.semantic_memory[article.article_id] = {
            "type": "news",
            "headline": article.headline,
            "truth_perceived": self._perceived_truth(agent, article),
        }

        impact = self._compute_belief_impact(agent, article)
        article.belief_impact[agent.agent_id] = impact
        return impact

    def _perceived_truth(self, agent: Agent, article: NewsArticle) -> float:
        """How true the agent perceives the article based on skills and bias."""
        base = article.truth_value
        # Scientist/Spy are better at detecting fakes
        detection_bonus = 0.0
        if agent.agent_type in (AgentType.SCIENTIST, AgentType.SPY):
            detection_bonus = 0.25
        noise = random.gauss(0, 0.1)
        return max(0.0, min(1.0, base + detection_bonus + noise))

    def _compute_belief_impact(self, agent: Agent, article: NewsArticle) -> float:
        """How much the article shifts the agent's beliefs."""
        perceived = self._perceived_truth(agent, article)
        gullibility = 1.0 - agent.skills.reasoning * 0.5
        emotional = getattr(article, "emotional_charge", 0.5)
        return perceived * gullibility * (0.5 + 0.5 * emotional)


# ---------------------------------------------------------------------------
# Rumor System
# ---------------------------------------------------------------------------

class RumorSystem:
    """Manages rumor creation, spread, mutation, and decay."""

    def __init__(self):
        self.rumors: Dict[str, GossipEntry] = {}
        self._rumor_counter = 0

    def create_rumor(
        self,
        originator_id: str,
        subject_id: str,
        content: str,
        truth_value: float,
        tick: int,
    ) -> GossipEntry:
        self._rumor_counter += 1
        rid = f"rumor_{self._rumor_counter:05d}"
        rumor = GossipEntry(
            gossip_id=rid,
            originator_id=originator_id,
            subject_id=subject_id,
            content=content,
            truth_value=truth_value,
            spread_count=0,
            believers=set(),
            tick_created=tick,
        )
        self.rumors[rid] = rumor
        return rumor

    def spread_rumor(
        self,
        rumor: GossipEntry,
        spreader: Agent,
        target: Agent,
        social_trust: float,
        tick: int,
    ) -> bool:
        """
        Attempt to spread rumor from spreader to target.
        Returns True if target believes it.
        """
        if rumor.gossip_id in target.memory.social_memory:
            return False  # already heard

        # Probability of believing
        credibility = max(0.1, social_trust)
        skepticism = target.skills.reasoning * 0.3
        p_believe = credibility * (1.0 - skepticism) * rumor.truth_value + \
                    credibility * 0.2  # some gullibility regardless

        p_believe = min(0.95, p_believe)
        believed = random.random() < p_believe

        target.memory.social_memory[rumor.gossip_id] = {
            "type": "rumor",
            "about": rumor.subject_id,
            "content": rumor.content,
            "believed": believed,
            "tick_heard": tick,
        }

        rumor.spread_count += 1
        if believed:
            rumor.believers.add(target.agent_id)

        # Mutation: slight distortion
        if random.random() < 0.15:
            rumor.content = self._mutate_content(rumor.content)
            rumor.truth_value = max(0.0, rumor.truth_value - 0.05)

        return believed

    def _mutate_content(self, content: str) -> str:
        """Telephone-game distortion of rumor content."""
        mutations = [
            lambda s: s.replace("possibly", "definitely"),
            lambda s: s.replace("sometimes", "always"),
            lambda s: s + " Everyone knows this.",
            lambda s: "Reliable sources say: " + s,
        ]
        return random.choice(mutations)(content)

    def decay_rumors(self, tick: int, decay_rate: float = 0.01):
        """Reduce truth perceived over time."""
        for rumor in self.rumors.values():
            age = tick - rumor.tick_created
            rumor.truth_value = max(0.0, rumor.truth_value - decay_rate * math.log1p(age))


# ---------------------------------------------------------------------------
# Belief Propagation Model
# ---------------------------------------------------------------------------

class BeliefPropagationEngine:
    """
    Models how beliefs spread through agent networks.
    Uses a simplified DeGroot learning model.
    """

    def __init__(self):
        self.belief_vectors: Dict[str, Dict[str, float]] = {}  # agent_id -> {topic: strength}
        self.topic_history: Dict[str, List[float]] = defaultdict(list)

    def initialize_agent_beliefs(self, agent: Agent):
        """Seed initial beliefs from personality."""
        self.belief_vectors[agent.agent_id] = {
            "authority_trust": 0.3 + agent.personality.agreeableness * 0.4,
            "market_fairness": 0.5 + agent.personality.altruism * 0.3,
            "violence_justified": agent.personality.aggression * 0.5,
            "cooperation_value": agent.personality.altruism * 0.7,
            "elite_conspiracy": random.uniform(0.0, 0.4),
        }

    def update_belief_from_source(
        self,
        listener_id: str,
        speaker_id: str,
        topic: str,
        speaker_belief: float,
        trust_weight: float,
    ):
        """DeGroot update: listener moves toward speaker weighted by trust."""
        if listener_id not in self.belief_vectors:
            return
        current = self.belief_vectors[listener_id].get(topic, 0.5)
        updated = (1 - trust_weight) * current + trust_weight * speaker_belief
        self.belief_vectors[listener_id][topic] = updated

    def propagate_across_network(
        self,
        agents: Dict[str, Agent],
        trust_graph: Dict[str, Dict[str, float]],
        topic: str,
        iterations: int = 3,
    ):
        """Run DeGroot iterations across the trust network."""
        agent_ids = list(agents.keys())

        for _ in range(iterations):
            new_beliefs: Dict[str, float] = {}
            for aid in agent_ids:
                if aid not in self.belief_vectors:
                    continue
                neighbors = trust_graph.get(aid, {})
                if not neighbors:
                    continue

                total_weight = sum(neighbors.values()) + 1.0  # +1 for self
                self_belief = self.belief_vectors[aid].get(topic, 0.5)
                weighted_sum = self_belief  # self-weight = 1.0

                for neighbor_id, trust in neighbors.items():
                    nb = self.belief_vectors.get(neighbor_id, {}).get(topic, 0.5)
                    weighted_sum += trust * nb

                new_beliefs[aid] = weighted_sum / total_weight

            for aid, val in new_beliefs.items():
                if topic not in self.belief_vectors.get(aid, {}):
                    self.belief_vectors.setdefault(aid, {})[topic] = val
                else:
                    self.belief_vectors[aid][topic] = val

        # Record mean belief
        vals = [self.belief_vectors.get(a, {}).get(topic, 0.5) for a in agent_ids]
        self.topic_history[topic].append(float(np.mean(vals)))

    def detect_polarization(self, topic: str) -> float:
        """Returns 0–1 measure of polarization on a topic."""
        vals = [v.get(topic, 0.5) for v in self.belief_vectors.values()]
        if len(vals) < 2:
            return 0.0
        std = float(np.std(vals))
        # Bimodal → high polarization
        return min(1.0, std * 3.0)

    def get_consensus(self, topic: str) -> float:
        """Mean belief value across all agents."""
        vals = [v.get(topic, 0.5) for v in self.belief_vectors.values()]
        return float(np.mean(vals)) if vals else 0.5


# ---------------------------------------------------------------------------
# Echo Chamber Detector
# ---------------------------------------------------------------------------

class EchoChamberDetector:
    """Identifies echo chambers from belief similarity + communication patterns."""

    def __init__(self):
        self.chambers: Dict[str, EchoChamber] = {}
        self._chamber_counter = 0

    def detect_chambers(
        self,
        agents: Dict[str, Agent],
        belief_engine: BeliefPropagationEngine,
        trust_graph: Dict[str, Dict[str, float]],
        similarity_threshold: float = 0.15,
    ) -> List[EchoChamber]:
        """
        Group agents into echo chambers based on:
        - High mutual trust
        - Similar beliefs on key topics
        """
        topics = ["authority_trust", "elite_conspiracy", "violence_justified"]
        agent_ids = list(agents.keys())

        # Build belief similarity matrix
        def similarity(a1: str, a2: str) -> float:
            b1 = belief_engine.belief_vectors.get(a1, {})
            b2 = belief_engine.belief_vectors.get(a2, {})
            diffs = [abs(b1.get(t, 0.5) - b2.get(t, 0.5)) for t in topics]
            return 1.0 - (sum(diffs) / len(topics))

        # Simple greedy clustering
        assigned: Dict[str, str] = {}
        new_chambers: List[EchoChamber] = []

        for aid in agent_ids:
            if aid in assigned:
                continue
            members = {aid}
            for other in agent_ids:
                if other == aid or other in assigned:
                    continue
                trust = trust_graph.get(aid, {}).get(other, 0)
                if trust > 0.4 and similarity(aid, other) > (1.0 - similarity_threshold):
                    members.add(other)

            if len(members) >= 3:
                self._chamber_counter += 1
                cid = f"chamber_{self._chamber_counter:04d}"
                # Dominant belief = topic with highest variance among this group
                dominant = max(
                    topics,
                    key=lambda t: np.std([
                        belief_engine.belief_vectors.get(m, {}).get(t, 0.5)
                        for m in members
                    ]),
                )
                cohesion = float(np.mean([
                    trust_graph.get(a, {}).get(b, 0)
                    for a in members for b in members if a != b
                ])) if len(members) > 1 else 0.5

                chamber = EchoChamber(
                    chamber_id=cid,
                    member_ids=members,
                    dominant_belief=dominant,
                    cohesion=cohesion,
                    insularity=cohesion * 0.8,
                )
                self.chambers[cid] = chamber
                new_chambers.append(chamber)
                for m in members:
                    assigned[m] = cid

        return new_chambers


# ---------------------------------------------------------------------------
# Trust Erosion Tracker
# ---------------------------------------------------------------------------

class TrustErosionTracker:
    """Tracks how misinformation degrades inter-agent trust over time."""

    def __init__(self):
        self.erosion_log: List[TrustErosionEvent] = []
        self.total_erosion: Dict[str, float] = defaultdict(float)

    def apply_erosion(
        self,
        agent_id: str,
        amount: float,
        reason: str,
        tick: int,
        trust_graph: Dict[str, Dict[str, float]],
    ):
        """Reduce trust FROM this agent in the graph."""
        event = TrustErosionEvent(
            agent_id=agent_id,
            eroded_by=amount,
            reason=reason,
            tick=tick,
        )
        self.erosion_log.append(event)
        self.total_erosion[agent_id] += amount

        # Reduce incoming trust from others toward this agent
        for source_id, targets in trust_graph.items():
            if agent_id in targets:
                targets[agent_id] = max(0.0, targets[agent_id] - amount * 0.5)

    def erosion_from_fake_news(
        self,
        fake_article: NewsArticle,
        tick: int,
        trust_graph: Dict[str, Dict[str, float]],
        agents: Dict[str, Agent],
    ):
        """
        When fake news is exposed, erode trust in the author.
        When fake news is believed, erode trust in the target.
        """
        author_id = fake_article.author_id
        # Readers who believed it erode trust in the target
        target_id = fake_article.content.split("agent ")[1].split(" ")[0] if "agent " in fake_article.content else None
        if target_id and target_id in agents:
            self.apply_erosion(target_id, 0.1 * len(fake_article.readers), "fake_news_believed", tick, trust_graph)

        # Author loses trust when article is marked fake (low truth)
        if fake_article.truth_value < 0.2:
            self.apply_erosion(author_id, 0.05 * len(fake_article.readers), "fake_news_author", tick, trust_graph)

    def get_most_eroded(self, n: int = 5) -> List[Tuple[str, float]]:
        return sorted(self.total_erosion.items(), key=lambda x: -x[1])[:n]


# ---------------------------------------------------------------------------
# Information Cascade Tracker
# ---------------------------------------------------------------------------

class CascadeTracker:
    """Tracks how information spreads in waves through the network."""

    def __init__(self):
        self.cascades: Dict[str, InformationCascade] = {}
        self._cascade_counter = 0

    def start_cascade(self, broadcast_id: str, origin_agents: Set[str], tick: int) -> InformationCascade:
        self._cascade_counter += 1
        cid = f"cascade_{self._cascade_counter:04d}"
        cascade = InformationCascade(
            cascade_id=cid,
            origin_broadcast_id=broadcast_id,
            wave=[origin_agents.copy()],
            total_reached=len(origin_agents),
            tick_start=tick,
        )
        self.cascades[cid] = cascade
        return cascade

    def advance_cascade(
        self,
        cascade: InformationCascade,
        trust_graph: Dict[str, Dict[str, float]],
        spread_prob: float = 0.3,
    ) -> Set[str]:
        """Advance cascade by one wave. Returns newly reached agents."""
        if not cascade.still_active:
            return set()

        already_reached = {aid for wave in cascade.wave for aid in wave}
        last_wave = cascade.wave[-1]
        new_wave: Set[str] = set()

        for agent_id in last_wave:
            for neighbor_id, trust in trust_graph.get(agent_id, {}).items():
                if neighbor_id in already_reached:
                    continue
                p = spread_prob * trust
                if random.random() < p:
                    new_wave.add(neighbor_id)

        if new_wave:
            cascade.wave.append(new_wave)
            cascade.total_reached += len(new_wave)
        else:
            cascade.still_active = False

        return new_wave


# ---------------------------------------------------------------------------
# Broadcast System
# ---------------------------------------------------------------------------

class BroadcastSystem:
    """Allows agents to broadcast information to their social network."""

    def __init__(self):
        self.broadcasts: Dict[str, Broadcast] = {}
        self._bc_counter = 0

    def create_broadcast(
        self,
        source_agent_id: str,
        content: str,
        info_type: InformationType,
        truth_value: float,
        emotional_charge: float,
        tick: int,
        duration: int = 50,
    ) -> Broadcast:
        self._bc_counter += 1
        bid = f"bc_{self._bc_counter:05d}"
        bc = Broadcast(
            broadcast_id=bid,
            source_agent_id=source_agent_id,
            content=content,
            info_type=info_type,
            truth_value=truth_value,
            emotional_charge=emotional_charge,
            tick_created=tick,
            tick_expires=tick + duration,
        )
        self.broadcasts[bid] = bc
        return bc

    def distribute_broadcast(
        self,
        broadcast: Broadcast,
        agents: Dict[str, Agent],
        trust_graph: Dict[str, Dict[str, float]],
    ) -> Set[str]:
        """Send broadcast to agents connected to source. Returns newly reached."""
        source_neighbors = trust_graph.get(broadcast.source_agent_id, {})
        newly_reached: Set[str] = set()

        for neighbor_id, trust in source_neighbors.items():
            if neighbor_id in broadcast.reach:
                continue
            # Probability of receiving proportional to trust and emotional charge
            p_receive = min(0.95, trust * (0.5 + 0.5 * broadcast.emotional_charge) * broadcast.amplification)
            if random.random() < p_receive:
                broadcast.reach.add(neighbor_id)
                newly_reached.add(neighbor_id)

        return newly_reached

    def expire_broadcasts(self, tick: int) -> List[str]:
        expired = [bid for bid, bc in self.broadcasts.items() if tick >= bc.tick_expires]
        for bid in expired:
            del self.broadcasts[bid]
        return expired


# ---------------------------------------------------------------------------
# Main Information System
# ---------------------------------------------------------------------------

class InformationSystem:
    """
    Orchestrator for all information warfare subsystems.
    Called once per simulation tick.
    """

    def __init__(self):
        self.news = NewsSystem()
        self.rumors = RumorSystem()
        self.belief_engine = BeliefPropagationEngine()
        self.echo_detector = EchoChamberDetector()
        self.trust_erosion = TrustErosionTracker()
        self.cascade_tracker = CascadeTracker()
        self.broadcast_system = BroadcastSystem()

        # Metrics history
        self.polarization_history: Dict[str, List[float]] = defaultdict(list)
        self.echo_chamber_count_history: List[int] = []

    def initialize(self, agents: Dict[str, Agent]):
        """Seed beliefs for all agents."""
        for agent in agents.values():
            self.belief_engine.initialize_agent_beliefs(agent)
        logger.info("InformationSystem initialized for %d agents", len(agents))

    def tick(
        self,
        tick: int,
        agents: Dict[str, Agent],
        world_state: WorldState,
        trust_graph: Dict[str, Dict[str, float]],
    ):
        """Run one information warfare tick."""
        agent_list = list(agents.values())
        if not agent_list:
            return

        # 1. Decay old rumors
        self.rumors.decay_rumors(tick)

        # 2. Expire old broadcasts
        self.broadcast_system.expire_broadcasts(tick)

        # 3. Spontaneous rumor creation (Spies and Leaders are most active)
        for agent in agent_list:
            if agent.agent_type in (AgentType.SPY, AgentType.LEADER) and random.random() < 0.03:
                target = random.choice(agent_list)
                if target.agent_id != agent.agent_id:
                    accusations = [
                        "hoarding food illegally",
                        "conspiring against the community",
                        "accepting bribes from outsiders",
                        "planning a revolt",
                        "selling counterfeit goods",
                    ]
                    rumor = self.rumors.create_rumor(
                        originator_id=agent.agent_id,
                        subject_id=target.agent_id,
                        content=f"Agent {target.agent_id} has been {random.choice(accusations)}.",
                        truth_value=random.uniform(0.0, 0.6),
                        tick=tick,
                    )
                    # Spread to 1-3 neighbors
                    neighbors = list(trust_graph.get(agent.agent_id, {}).items())
                    for neighbor_id, trust in random.sample(neighbors, min(3, len(neighbors))):
                        neighbor = agents.get(neighbor_id)
                        if neighbor:
                            self.rumors.spread_rumor(rumor, agent, neighbor, trust, tick)

        # 4. Fake news generation (Spy, Leader with high greed)
        for agent in agent_list:
            if agent.agent_type == AgentType.SPY and random.random() < 0.02:
                target = random.choice(agent_list)
                if target.agent_id != agent.agent_id:
                    fake = self.news.generate_fake_news(
                        author_id=agent.agent_id,
                        target_agent_id=target.agent_id,
                        accusation=random.choice([
                            "embezzling community resources",
                            "working for enemy factions",
                            "sabotaging infrastructure",
                        ]),
                        tick=tick,
                    )
                    # Apply trust erosion on target
                    self.trust_erosion.erosion_from_fake_news(fake, tick, trust_graph, agents)

        # 5. Belief propagation across network
        topics = ["authority_trust", "market_fairness", "cooperation_value", "elite_conspiracy"]
        for topic in topics:
            if tick % 5 == 0:  # every 5 ticks
                self.belief_engine.propagate_across_network(agents, trust_graph, topic, iterations=2)

        # 6. Echo chamber detection (every 20 ticks)
        if tick % 20 == 0:
            chambers = self.echo_detector.detect_chambers(agents, self.belief_engine, trust_graph)
            self.echo_chamber_count_history.append(len(self.echo_detector.chambers))
            if chambers:
                logger.info("Tick %d: %d echo chambers detected", tick, len(chambers))

        # 7. Record polarization metrics
        if tick % 10 == 0:
            for topic in topics:
                pol = self.belief_engine.detect_polarization(topic)
                self.polarization_history[topic].append(pol)

        # 8. Advance active cascades
        for cascade in list(self.cascade_tracker.cascades.values()):
            if cascade.still_active:
                self.cascade_tracker.advance_cascade(cascade, trust_graph)

    def agent_broadcasts(
        self,
        agent: Agent,
        content: str,
        info_type: InformationType,
        truth_value: float,
        emotional_charge: float,
        tick: int,
        agents: Dict[str, Agent],
        trust_graph: Dict[str, Dict[str, float]],
    ) -> Broadcast:
        """API for an agent to create and distribute a broadcast."""
        bc = self.broadcast_system.create_broadcast(
            source_agent_id=agent.agent_id,
            content=content,
            info_type=info_type,
            truth_value=truth_value,
            emotional_charge=emotional_charge,
            tick=tick,
        )
        newly_reached = self.broadcast_system.distribute_broadcast(bc, agents, trust_graph)

        # Start an information cascade
        if newly_reached:
            self.cascade_tracker.start_cascade(bc.broadcast_id, newly_reached, tick)

        return bc

    def get_info_summary(self) -> Dict:
        return {
            "total_rumors": len(self.rumors.rumors),
            "total_articles": len(self.news.articles),
            "active_broadcasts": len(self.broadcast_system.broadcasts),
            "echo_chambers": len(self.echo_detector.chambers),
            "active_cascades": sum(1 for c in self.cascade_tracker.cascades.values() if c.still_active),
            "polarization": {
                topic: vals[-1] if vals else 0.0
                for topic, vals in self.belief_engine.topic_history.items()
            },
            "most_eroded_agents": self.trust_erosion.get_most_eroded(5),
        }
