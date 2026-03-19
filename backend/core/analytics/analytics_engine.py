"""
Emergent Analytics Engine — NCE
Detects cooperation clusters, conflict zones, leadership emergence,
inequality, migration, instability. Provides graph analysis and metrics.
"""
from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

import numpy as np
import networkx as nx

from ..enums import AgentType, ActionType
from ..models import Agent, WorldState, SimulationMetrics, SimulationEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CooperationCluster:
    cluster_id: str
    member_ids: List[str]
    cohesion_score: float
    dominant_type: str
    avg_trust: float
    size: int


@dataclass
class ConflictZone:
    zone_id: str
    center: Tuple[int, int]
    radius: int
    intensity: float          # 0–1
    involved_agents: Set[str]
    tick_detected: int


@dataclass
class LeadershipSignal:
    agent_id: str
    influence_score: float
    follower_count: int
    agent_type: str
    centrality: float


@dataclass
class MigrationPattern:
    tick: int
    from_zone: str
    to_zone: str
    agent_count: int
    avg_stress_trigger: float


@dataclass
class InstabilityAlert:
    tick: int
    severity: float           # 0–1
    reasons: List[str]
    at_risk_agents: List[str]


@dataclass
class AnalyticsSnapshot:
    tick: int
    gini_coefficient: float
    entropy: float
    stability_index: float
    cooperation_clusters: List[CooperationCluster]
    conflict_zones: List[ConflictZone]
    leadership_signals: List[LeadershipSignal]
    migration_patterns: List[MigrationPattern]
    instability_alert: Optional[InstabilityAlert]
    network_metrics: Dict
    population_stats: Dict


# ---------------------------------------------------------------------------
# Graph Analysis
# ---------------------------------------------------------------------------

class GraphAnalyzer:
    """NetworkX-based analysis of agent trust and interaction networks."""

    def build_trust_graph(
        self,
        agents: Dict[str, Agent],
        trust_threshold: float = 0.3,
    ) -> nx.DiGraph:
        G = nx.DiGraph()
        for aid, agent in agents.items():
            G.add_node(
                aid,
                agent_type=agent.agent_type.value,
                health=agent.vitals.health,
                wealth=sum(agent.resources.__dict__.values()),
            )
        for aid, agent in agents.items():
            for trusted_id, trust_entry in agent.trust_map.items():
                if trusted_id in agents and trust_entry.score >= trust_threshold:
                    G.add_edge(aid, trusted_id, weight=trust_entry.score)
        return G

    def detect_communities(self, G: nx.DiGraph) -> List[Set[str]]:
        """Louvain-style community detection via greedy modularity."""
        undirected = G.to_undirected()
        if len(undirected.nodes) == 0:
            return []
        try:
            communities = list(nx.community.greedy_modularity_communities(undirected))
            return [set(c) for c in communities]
        except Exception:
            return []

    def compute_centrality(self, G: nx.DiGraph) -> Dict[str, float]:
        if len(G.nodes) == 0:
            return {}
        try:
            return nx.pagerank(G, alpha=0.85, max_iter=100)
        except nx.PowerIterationFailedConvergence:
            return {n: 1.0 / len(G.nodes) for n in G.nodes}

    def compute_clustering(self, G: nx.DiGraph) -> Dict[str, float]:
        undirected = G.to_undirected()
        return nx.clustering(undirected)

    def shortest_path_length(self, G: nx.DiGraph, source: str, target: str) -> Optional[int]:
        try:
            return nx.shortest_path_length(G, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def avg_clustering_coefficient(self, G: nx.DiGraph) -> float:
        undirected = G.to_undirected()
        if len(undirected.nodes) == 0:
            return 0.0
        return nx.average_clustering(undirected)

    def network_density(self, G: nx.DiGraph) -> float:
        return nx.density(G)

    def strongly_connected_components(self, G: nx.DiGraph) -> List[Set[str]]:
        return [set(c) for c in nx.strongly_connected_components(G)]


# ---------------------------------------------------------------------------
# Inequality Metrics
# ---------------------------------------------------------------------------

class InequalityMetrics:
    """Computes Gini coefficient and related inequality measures."""

    def gini_coefficient(self, values: List[float]) -> float:
        """Gini coefficient: 0 = perfect equality, 1 = perfect inequality."""
        if not values or all(v == 0 for v in values):
            return 0.0
        arr = sorted(abs(v) for v in values)
        n = len(arr)
        cumsum = sum(arr)
        if cumsum == 0:
            return 0.0
        numerator = sum((i + 1) * arr[i] for i in range(n))
        return (2 * numerator) / (n * cumsum) - (n + 1) / n

    def wealth_distribution(self, agents: Dict[str, Agent]) -> Dict:
        wealths = []
        for agent in agents.values():
            w = (
                agent.resources.food * 1 +
                agent.resources.water * 1 +
                agent.resources.money * 2 +
                agent.resources.tools * 3 +
                agent.resources.medicine * 4
            )
            wealths.append(w)

        if not wealths:
            return {"gini": 0.0, "mean": 0.0, "std": 0.0, "top10_share": 0.0}

        arr = np.array(wealths)
        top10_threshold = np.percentile(arr, 90)
        top10_total = arr[arr >= top10_threshold].sum()
        total = arr.sum()

        return {
            "gini": self.gini_coefficient(wealths),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(arr.min()),
            "max": float(arr.max()),
            "top10_share": float(top10_total / total) if total > 0 else 0.0,
            "median": float(np.median(arr)),
        }

    def health_inequality(self, agents: Dict[str, Agent]) -> float:
        healths = [a.vitals.health for a in agents.values()]
        return self.gini_coefficient(healths)


# ---------------------------------------------------------------------------
# Entropy & Stability Metrics
# ---------------------------------------------------------------------------

class StabilityMetrics:
    """Measures system entropy and overall stability."""

    def shannon_entropy(self, distribution: List[float]) -> float:
        """Shannon entropy of a probability distribution."""
        if not distribution:
            return 0.0
        total = sum(distribution)
        if total == 0:
            return 0.0
        probs = [v / total for v in distribution if v > 0]
        return -sum(p * math.log2(p) for p in probs)

    def agent_type_entropy(self, agents: Dict[str, Agent]) -> float:
        """Diversity of agent types — low = monoculture, high = diverse."""
        counts: Dict[str, int] = defaultdict(int)
        for a in agents.values():
            counts[a.agent_type.value] += 1
        return self.shannon_entropy(list(counts.values()))

    def resource_entropy(self, agents: Dict[str, Agent]) -> float:
        """How evenly distributed resources are."""
        totals: Dict[str, float] = defaultdict(float)
        for a in agents.values():
            for k, v in a.resources.__dict__.items():
                totals[k] += v
        return self.shannon_entropy(list(totals.values()))

    def stability_index(
        self,
        agents: Dict[str, Agent],
        conflict_count: int,
        dead_this_tick: int,
        gini: float,
    ) -> float:
        """
        Composite stability index: 1.0 = perfectly stable, 0.0 = total collapse.
        """
        if not agents:
            return 0.0
        n = len(agents)

        avg_stress = np.mean([a.vitals.stress for a in agents.values()])
        avg_health = np.mean([a.vitals.health for a in agents.values()])
        conflict_rate = min(1.0, conflict_count / max(1, n))
        death_rate = min(1.0, dead_this_tick / max(1, n))

        # Weighted composite
        stability = (
            (1 - avg_stress / 100) * 0.25 +
            (avg_health / 100) * 0.25 +
            (1 - conflict_rate) * 0.20 +
            (1 - death_rate) * 0.15 +
            (1 - gini) * 0.15
        )
        return max(0.0, min(1.0, stability))


# ---------------------------------------------------------------------------
# Leadership Emergence Detector
# ---------------------------------------------------------------------------

class LeadershipDetector:
    """Detects emergent leaders based on influence and network centrality."""

    def detect_leaders(
        self,
        agents: Dict[str, Agent],
        centrality: Dict[str, float],
        trust_graph: Dict[str, Dict[str, float]],
        top_n: int = 5,
    ) -> List[LeadershipSignal]:
        signals: List[LeadershipSignal] = []

        for aid, agent in agents.items():
            # Follower count: agents that trust this agent highly
            followers = sum(
                1 for src_id, targets in trust_graph.items()
                if targets.get(aid, 0) > 0.6
            )
            # Influence = centrality + trust received + reputation
            c = centrality.get(aid, 0.0)
            rep = sum(agent.trust_map[tid].score for tid in agent.trust_map
                      if tid in agents) / max(1, len(agent.trust_map))
            influence = c * 0.4 + (followers / max(1, len(agents))) * 0.4 + rep * 0.2

            signals.append(LeadershipSignal(
                agent_id=aid,
                influence_score=influence,
                follower_count=followers,
                agent_type=agent.agent_type.value,
                centrality=c,
            ))

        signals.sort(key=lambda s: -s.influence_score)
        return signals[:top_n]


# ---------------------------------------------------------------------------
# Conflict Zone Detector
# ---------------------------------------------------------------------------

class ConflictZoneDetector:
    """Identifies geographic hotspots of conflict activity."""

    def __init__(self):
        self.zones: Dict[str, ConflictZone] = {}
        self._zone_counter = 0

    def detect_zones(
        self,
        conflict_events: List[SimulationEvent],
        tick: int,
        radius: int = 5,
    ) -> List[ConflictZone]:
        """Cluster recent conflict events into zones."""
        recent = [e for e in conflict_events if e.tick >= tick - 20]
        if not recent:
            return []

        # Extract positions from events
        positions: List[Tuple[int, int]] = []
        agents_by_pos: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
        for event in recent:
            if event.position:
                pos = (event.position.x, event.position.y)
                positions.append(pos)
                for aid in (event.agent_ids or []):
                    agents_by_pos[pos].add(aid)

        if not positions:
            return []

        # Simple grid-based clustering
        clusters: List[List[Tuple[int, int]]] = []
        assigned = set()
        for i, pos in enumerate(positions):
            if i in assigned:
                continue
            cluster = [pos]
            assigned.add(i)
            for j, other in enumerate(positions):
                if j in assigned:
                    continue
                dist = math.sqrt((pos[0]-other[0])**2 + (pos[1]-other[1])**2)
                if dist <= radius:
                    cluster.append(other)
                    assigned.add(j)
            clusters.append(cluster)

        zones: List[ConflictZone] = []
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            cx = int(np.mean([p[0] for p in cluster]))
            cy = int(np.mean([p[1] for p in cluster]))
            involved: Set[str] = set()
            for pos in cluster:
                involved |= agents_by_pos[pos]
            intensity = min(1.0, len(cluster) / 20.0)

            self._zone_counter += 1
            zone = ConflictZone(
                zone_id=f"zone_{self._zone_counter:04d}",
                center=(cx, cy),
                radius=radius,
                intensity=intensity,
                involved_agents=involved,
                tick_detected=tick,
            )
            zones.append(zone)
            self.zones[zone.zone_id] = zone

        return zones


# ---------------------------------------------------------------------------
# Migration Detector
# ---------------------------------------------------------------------------

class MigrationDetector:
    """Tracks agent movement patterns and detects mass migration."""

    def __init__(self):
        self._prev_positions: Dict[str, Tuple[int, int]] = {}
        self.patterns: List[MigrationPattern] = []
        self._pattern_counter = 0

    def update(self, agents: Dict[str, Agent], tick: int, world_state: WorldState):
        """Compare current positions to previous, detect mass movement."""
        current_positions: Dict[str, Tuple[int, int]] = {}
        for aid, agent in agents.items():
            current_positions[aid] = (agent.position.x, agent.position.y)

        if not self._prev_positions:
            self._prev_positions = current_positions
            return

        # Count movements by zone (simple quadrant-based zones)
        moves: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        for aid, pos in current_positions.items():
            prev = self._prev_positions.get(aid)
            if not prev:
                continue
            if prev == pos:
                continue
            from_zone = self._get_zone(prev, world_state)
            to_zone = self._get_zone(pos, world_state)
            if from_zone != to_zone:
                stress = agents[aid].vitals.stress if aid in agents else 50.0
                moves[(from_zone, to_zone)].append(stress)

        for (fz, tz), stresses in moves.items():
            if len(stresses) >= 3:  # significant mass movement
                self._pattern_counter += 1
                self.patterns.append(MigrationPattern(
                    tick=tick,
                    from_zone=fz,
                    to_zone=tz,
                    agent_count=len(stresses),
                    avg_stress_trigger=float(np.mean(stresses)),
                ))

        self._prev_positions = current_positions

    def _get_zone(self, pos: Tuple[int, int], world_state: WorldState) -> str:
        w = world_state.width
        h = world_state.height
        qx = "W" if pos[0] < w // 2 else "E"
        qy = "N" if pos[1] < h // 2 else "S"
        return f"{qy}{qx}"

    def get_recent_patterns(self, n: int = 5) -> List[MigrationPattern]:
        return self.patterns[-n:]


# ---------------------------------------------------------------------------
# Cooperation Cluster Detector
# ---------------------------------------------------------------------------

class CooperationClusterDetector:
    """Identifies groups of agents with high mutual cooperation."""

    def detect(
        self,
        agents: Dict[str, Agent],
        communities: List[Set[str]],
        trust_graph: Dict[str, Dict[str, float]],
    ) -> List[CooperationCluster]:
        clusters: List[CooperationCluster] = []

        for i, community in enumerate(communities):
            if len(community) < 2:
                continue
            member_ids = [aid for aid in community if aid in agents]
            if len(member_ids) < 2:
                continue

            # Average mutual trust within community
            trust_scores = []
            for a in member_ids:
                for b in member_ids:
                    if a != b:
                        t = trust_graph.get(a, {}).get(b, 0)
                        trust_scores.append(t)
            avg_trust = float(np.mean(trust_scores)) if trust_scores else 0.0

            # Dominant type
            type_counts: Dict[str, int] = defaultdict(int)
            for aid in member_ids:
                type_counts[agents[aid].agent_type.value] += 1
            dominant_type = max(type_counts, key=type_counts.get)

            # Cohesion = intra-cluster trust / max possible
            max_trust = len(member_ids) * (len(member_ids) - 1)
            actual_trust = sum(trust_scores)
            cohesion = actual_trust / max_trust if max_trust > 0 else 0.0

            clusters.append(CooperationCluster(
                cluster_id=f"cluster_{i:04d}",
                member_ids=member_ids,
                cohesion_score=cohesion,
                dominant_type=dominant_type,
                avg_trust=avg_trust,
                size=len(member_ids),
            ))

        clusters.sort(key=lambda c: -c.cohesion_score)
        return clusters


# ---------------------------------------------------------------------------
# Instability Detector
# ---------------------------------------------------------------------------

class InstabilityDetector:
    """Combines signals to assess overall system instability."""

    def assess(
        self,
        tick: int,
        agents: Dict[str, Agent],
        stability_index: float,
        gini: float,
        conflict_count: int,
        recent_deaths: int,
        polarization: Dict[str, float],
    ) -> Optional[InstabilityAlert]:
        reasons: List[str] = []
        severity = 0.0

        if stability_index < 0.3:
            reasons.append(f"Low stability index: {stability_index:.2f}")
            severity += 0.3

        if gini > 0.6:
            reasons.append(f"High inequality (Gini={gini:.2f})")
            severity += 0.2

        n = len(agents)
        if conflict_count > n * 0.3:
            reasons.append(f"High conflict rate: {conflict_count}/{n}")
            severity += 0.2

        if recent_deaths > n * 0.05:
            reasons.append(f"Elevated death rate: {recent_deaths}")
            severity += 0.15

        avg_pol = np.mean(list(polarization.values())) if polarization else 0.0
        if avg_pol > 0.5:
            reasons.append(f"High belief polarization: {avg_pol:.2f}")
            severity += 0.15

        if severity > 0.3:
            at_risk = [
                aid for aid, a in agents.items()
                if a.vitals.stress > 75 or a.vitals.health < 30
            ][:10]
            return InstabilityAlert(
                tick=tick,
                severity=min(1.0, severity),
                reasons=reasons,
                at_risk_agents=at_risk,
            )
        return None


# ---------------------------------------------------------------------------
# Event Timeline
# ---------------------------------------------------------------------------

class EventTimeline:
    """Maintains a structured log of significant simulation events."""

    def __init__(self, max_size: int = 10000):
        self.events: List[SimulationEvent] = []
        self.max_size = max_size
        self.event_counts: Dict[str, int] = defaultdict(int)

    def record(self, event: SimulationEvent):
        self.events.append(event)
        self.event_counts[event.event_type] += 1
        if len(self.events) > self.max_size:
            self.events = self.events[-self.max_size:]

    def get_window(self, from_tick: int, to_tick: int) -> List[SimulationEvent]:
        return [e for e in self.events if from_tick <= e.tick <= to_tick]

    def get_by_type(self, event_type: str, last_n: int = 50) -> List[SimulationEvent]:
        matching = [e for e in self.events if e.event_type == event_type]
        return matching[-last_n:]

    def summary(self) -> Dict:
        return dict(self.event_counts)


# ---------------------------------------------------------------------------
# Main Analytics Engine
# ---------------------------------------------------------------------------

class AnalyticsEngine:
    """
    Orchestrator for all analytics subsystems.
    Produces AnalyticsSnapshot each N ticks.
    """

    def __init__(self, snapshot_interval: int = 10):
        self.graph_analyzer = GraphAnalyzer()
        self.inequality = InequalityMetrics()
        self.stability = StabilityMetrics()
        self.leadership = LeadershipDetector()
        self.conflict_zones = ConflictZoneDetector()
        self.migration = MigrationDetector()
        self.cooperation = CooperationClusterDetector()
        self.instability = InstabilityDetector()
        self.timeline = EventTimeline()
        self.snapshot_interval = snapshot_interval

        self.snapshots: List[AnalyticsSnapshot] = []
        self._conflict_events: List[SimulationEvent] = []
        self._recent_deaths: int = 0
        self._recent_conflicts: int = 0

    def record_event(self, event: SimulationEvent):
        """Called by simulation to log events."""
        self.timeline.record(event)
        if "conflict" in event.event_type or "combat" in event.event_type:
            self._conflict_events.append(event)
            self._recent_conflicts += 1
        if "death" in event.event_type:
            self._recent_deaths += 1

    def tick(
        self,
        tick: int,
        agents: Dict[str, Agent],
        world_state: WorldState,
        trust_graph: Dict[str, Dict[str, float]],
        polarization: Optional[Dict[str, float]] = None,
    ) -> Optional[AnalyticsSnapshot]:
        """Run analytics. Returns snapshot every snapshot_interval ticks."""

        # Migration tracking runs every tick
        self.migration.update(agents, tick, world_state)

        if tick % self.snapshot_interval != 0:
            return None

        if not agents:
            return None

        logger.debug("Analytics Engine computing snapshot at tick %d", tick)

        # Build trust graph
        G = self.graph_analyzer.build_trust_graph(agents)

        # Community detection
        communities = self.graph_analyzer.detect_communities(G)

        # Centrality
        centrality = self.graph_analyzer.compute_centrality(G)

        # Inequality
        wealth_dist = self.inequality.wealth_distribution(agents)
        gini = wealth_dist["gini"]

        # Stability
        stability_idx = self.stability.stability_index(
            agents, self._recent_conflicts, self._recent_deaths, gini
        )

        # Entropy
        type_entropy = self.stability.agent_type_entropy(agents)

        # Network metrics
        network_metrics = {
            "density": self.graph_analyzer.network_density(G),
            "avg_clustering": self.graph_analyzer.avg_clustering_coefficient(G),
            "num_communities": len(communities),
            "node_count": len(G.nodes),
            "edge_count": len(G.edges),
        }

        # Leadership
        leadership_signals = self.leadership.detect_leaders(agents, centrality, trust_graph)

        # Conflict zones
        conflict_zone_list = self.conflict_zones.detect_zones(self._conflict_events, tick)

        # Cooperation clusters
        coop_clusters = self.cooperation.detect(agents, communities, trust_graph)

        # Instability
        pol = polarization or {}
        instability_alert = self.instability.assess(
            tick, agents, stability_idx, gini,
            self._recent_conflicts, self._recent_deaths, pol
        )

        # Population stats
        alive_agents = [a for a in agents.values() if a.vitals.health > 0]
        pop_stats = {
            "total": len(agents),
            "alive": len(alive_agents),
            "avg_health": float(np.mean([a.vitals.health for a in alive_agents])) if alive_agents else 0,
            "avg_stress": float(np.mean([a.vitals.stress for a in alive_agents])) if alive_agents else 0,
            "avg_energy": float(np.mean([a.vitals.energy for a in alive_agents])) if alive_agents else 0,
            "wealth": wealth_dist,
        }

        snap = AnalyticsSnapshot(
            tick=tick,
            gini_coefficient=gini,
            entropy=type_entropy,
            stability_index=stability_idx,
            cooperation_clusters=coop_clusters[:10],
            conflict_zones=conflict_zone_list[:10],
            leadership_signals=leadership_signals,
            migration_patterns=self.migration.get_recent_patterns(5),
            instability_alert=instability_alert,
            network_metrics=network_metrics,
            population_stats=pop_stats,
        )

        self.snapshots.append(snap)

        # Reset tick counters
        self._recent_deaths = 0
        self._recent_conflicts = 0

        if instability_alert:
            logger.warning(
                "INSTABILITY ALERT tick=%d severity=%.2f reasons=%s",
                tick, instability_alert.severity, instability_alert.reasons
            )

        return snap

    def get_latest_snapshot(self) -> Optional[AnalyticsSnapshot]:
        return self.snapshots[-1] if self.snapshots else None

    def get_trend(self, metric: str, last_n: int = 20) -> List[float]:
        """Return time series for a top-level scalar metric."""
        results = []
        for snap in self.snapshots[-last_n:]:
            val = getattr(snap, metric, None)
            if val is not None and isinstance(val, (int, float)):
                results.append(float(val))
        return results

    def export_summary(self) -> Dict:
        snap = self.get_latest_snapshot()
        if not snap:
            return {"status": "no_snapshots_yet"}
        return {
            "tick": snap.tick,
            "gini": snap.gini_coefficient,
            "entropy": snap.entropy,
            "stability": snap.stability_index,
            "cooperation_clusters": len(snap.cooperation_clusters),
            "conflict_zones": len(snap.conflict_zones),
            "leaders": [
                {"id": l.agent_id, "influence": l.influence_score, "followers": l.follower_count}
                for l in snap.leadership_signals
            ],
            "network": snap.network_metrics,
            "population": snap.population_stats,
            "instability": {
                "severity": snap.instability_alert.severity,
                "reasons": snap.instability_alert.reasons,
            } if snap.instability_alert else None,
            "event_summary": self.timeline.summary(),
        }
