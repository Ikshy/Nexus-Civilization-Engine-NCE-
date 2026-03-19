"""
Nexus Civilization Engine - Governance System
Laws, courts, enforcement, taxation, corruption, institutional drift.
"""
from __future__ import annotations
import random
import logging
from typing import Optional
from collections import defaultdict

from backend.core.enums import (
    AgentType, CrimeType, GovernanceType, LawStatus, ActionType
)
from backend.core.models import (
    Agent, Faction, Law, CourtCase, SimulationEvent, ResourceBundle, ResourceType
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class LawSystem:
    """Manages laws, proposals, and enforcement."""

    DEFAULT_LAWS = [
        Law(
            name="Anti-Theft Law",
            description="Prohibits stealing resources from other agents",
            crime_type=CrimeType.THEFT,
            penalty={"fine": 30.0, "imprisonment": 10},
            enforcement_rate=0.7,
        ),
        Law(
            name="Anti-Assault Law",
            description="Prohibits unprovoked attacks on citizens",
            crime_type=CrimeType.ASSAULT,
            penalty={"fine": 50.0, "imprisonment": 20},
            enforcement_rate=0.65,
        ),
        Law(
            name="Anti-Corruption Law",
            description="Prohibits officials from accepting bribes",
            crime_type=CrimeType.CORRUPTION,
            penalty={"fine": 100.0, "imprisonment": 30},
            enforcement_rate=0.4,  # Harder to enforce
        ),
        Law(
            name="Market Regulation",
            description="Prohibits market manipulation and cartel behavior",
            crime_type=CrimeType.MARKET_MANIPULATION,
            penalty={"fine": 200.0, "imprisonment": 5},
            enforcement_rate=0.3,
        ),
    ]

    def __init__(self):
        self.active_laws: dict[str, Law] = {}
        self.law_history: list[dict] = []
        self._initialize_default_laws()

    def _initialize_default_laws(self) -> None:
        for law in self.DEFAULT_LAWS:
            self.active_laws[law.law_id] = law

    def propose_law(
        self,
        proposer: Agent,
        faction_id: str,
        crime_type: CrimeType,
        penalty: dict,
        enforcement_rate: float,
        tick: int,
    ) -> Law:
        law = Law(
            name=f"{crime_type.value.replace('_', ' ').title()} Law",
            description=f"Law proposed by {proposer.name}",
            crime_type=crime_type,
            penalty=penalty,
            faction_id=faction_id,
            enacted_tick=tick,
            enforcement_rate=enforcement_rate,
        )
        # In democracy: requires vote; in dictatorship: immediate
        self.active_laws[law.law_id] = law
        logger.info(f"Law enacted: {law.name}")
        return law

    def repeal_law(self, law_id: str, tick: int) -> bool:
        law = self.active_laws.pop(law_id, None)
        if law:
            law.is_active = False
            self.law_history.append({
                "law_id": law_id,
                "name": law.name,
                "enacted": law.enacted_tick,
                "repealed": tick,
            })
            return True
        return False

    def get_laws_for_faction(self, faction_id: Optional[str]) -> list[Law]:
        return [
            law for law in self.active_laws.values()
            if law.is_active and (law.faction_id == faction_id or law.faction_id is None)
        ]

    def get_law_for_crime(self, crime_type: CrimeType) -> Optional[Law]:
        for law in self.active_laws.values():
            if law.crime_type == crime_type and law.is_active:
                return law
        return None

    def is_crime_legal(self, crime_type: CrimeType, faction_id: Optional[str]) -> bool:
        """Check if an action is criminalized in this faction."""
        laws = self.get_laws_for_faction(faction_id)
        return any(law.crime_type == crime_type for law in laws)

    def exploit_loophole(self, agent: Agent, crime_type: CrimeType) -> bool:
        """Agents with high deception may find loopholes."""
        law = self.get_law_for_crime(crime_type)
        if not law:
            return True  # No law = legal
        loophole_prob = agent.personality.deception * 0.3 + agent.skills.trading * 0.1
        return random.random() < loophole_prob


class CourtSystem:
    """Judicial proceedings and verdicts."""

    def __init__(self, law_system: LawSystem):
        self.law_system = law_system
        self.pending_cases: list[CourtCase] = []
        self.verdict_history: list[CourtCase] = []
        self._corruption_level: float = 0.1  # 0-1

    def file_case(
        self,
        defendant: Agent,
        crime_type: CrimeType,
        evidence_strength: float,
        tick: int,
    ) -> CourtCase:
        case = CourtCase(
            defendant_id=defendant.agent_id,
            crime_type=crime_type,
            evidence_strength=evidence_strength,
            tick=tick,
        )
        self.pending_cases.append(case)
        return case

    def process_cases(
        self,
        agents_by_id: dict[str, Agent],
        lifecycle_manager,
        tick: int,
    ) -> list[dict]:
        """Process all pending court cases. Returns events."""
        events = []

        for case in list(self.pending_cases):
            defendant = agents_by_id.get(case.defendant_id)
            if not defendant or not defendant.is_alive():
                self.pending_cases.remove(case)
                continue

            verdict, event = self._render_verdict(case, defendant, lifecycle_manager, tick)
            case.verdict = verdict
            case.penalty_applied = True
            self.verdict_history.append(case)
            self.pending_cases.remove(case)
            if event:
                events.append(event)

        return events

    def _render_verdict(
        self,
        case: CourtCase,
        defendant: Agent,
        lifecycle_manager,
        tick: int,
    ) -> tuple[str, Optional[dict]]:
        # Check for corruption - wealthy/powerful defendants may escape
        bribery_escape = (
            self._corruption_level > 0.5 and
            defendant.inventory.get(ResourceType.MONEY) > 100 and
            random.random() < self._corruption_level * 0.5
        )

        if bribery_escape:
            defendant.inventory.subtract(ResourceType.MONEY, 50)  # Bribe cost
            defendant.crimes_committed.append(CrimeType.BRIBERY)
            logger.debug(f"{defendant.name} bribed their way out of {case.crime_type.value}")
            return "not_guilty_bribed", {
                "event_type": "court_verdict",
                "verdict": "not_guilty_bribed",
                "defendant": case.defendant_id,
                "crime": case.crime_type.value,
                "corruption": True,
                "tick": tick,
            }

        # Conviction based on evidence
        conviction_threshold = 0.5 + self._corruption_level * 0.1
        if case.evidence_strength > conviction_threshold:
            verdict = "guilty"
            self._apply_penalty(case, defendant, lifecycle_manager, tick)
        else:
            verdict = "not_guilty"

        event = {
            "event_type": "court_verdict",
            "verdict": verdict,
            "defendant": case.defendant_id,
            "crime": case.crime_type.value,
            "tick": tick,
        }
        logger.debug(f"Verdict: {defendant.name} - {verdict} for {case.crime_type.value}")
        return verdict, event

    def _apply_penalty(
        self, case: CourtCase, defendant: Agent, lifecycle_manager, tick: int
    ) -> None:
        law = self.law_system.get_law_for_crime(case.crime_type)
        if not law:
            return

        penalty = law.penalty
        fine = penalty.get("fine", 0)
        imprisonment = penalty.get("imprisonment", 0)

        # Apply fine
        if fine > 0:
            available = defendant.inventory.get(ResourceType.MONEY)
            actual_fine = min(fine, available)
            defendant.inventory.subtract(ResourceType.MONEY, actual_fine)
            defendant.reputation -= 10.0

        # Apply imprisonment
        if imprisonment > 0 and lifecycle_manager:
            lifecycle_manager.imprison_agent(defendant.agent_id, imprisonment, tick)

    def increase_corruption(self, amount: float) -> None:
        self._corruption_level = min(1.0, self._corruption_level + amount)

    def decrease_corruption(self, amount: float) -> None:
        self._corruption_level = max(0.0, self._corruption_level - amount)

    def get_corruption_level(self) -> float:
        return self._corruption_level


class EnforcementSystem:
    """Police/guard enforcement of laws."""

    def __init__(self, law_system: LawSystem, court_system: CourtSystem):
        self.law_system = law_system
        self.court = court_system
        self._patrol_radius: int = 5

    def patrol_and_enforce(
        self,
        guard: Agent,
        nearby_agents: list[Agent],
        tick: int,
    ) -> list[dict]:
        """Guard agent patrols and enforces laws."""
        events = []

        for suspect in nearby_agents:
            if suspect.agent_id == guard.agent_id:
                continue
            if not suspect.is_alive():
                continue

            # Check suspect's recent crimes
            for crime in suspect.crimes_committed[:]:
                law = self.law_system.get_law_for_crime(crime)
                if not law:
                    continue

                # Enforcement probability
                detection_prob = (
                    law.enforcement_rate *
                    guard.skills.espionage *
                    (1 - suspect.skills.espionage * 0.3)
                )

                if random.random() < detection_prob:
                    case = self.court.file_case(suspect, crime, evidence_strength=0.7, tick=tick)
                    suspect.crimes_committed.remove(crime)  # Crime is being processed
                    events.append({
                        "event_type": "arrest",
                        "guard_id": guard.agent_id,
                        "suspect_id": suspect.agent_id,
                        "crime": crime.value,
                        "tick": tick,
                    })
                    logger.debug(f"Arrest: {suspect.name} by {guard.name} for {crime.value}")
                    break  # One arrest at a time

        return events

    def set_patrol_radius(self, radius: int) -> None:
        self._patrol_radius = radius


class InstitutionSystem:
    """Tracks institutional health and reform."""

    def __init__(self):
        self.institutions: dict[str, dict] = {
            "judiciary": {"health": 0.8, "corruption": 0.1, "trust": 0.7},
            "legislature": {"health": 0.7, "corruption": 0.15, "trust": 0.6},
            "enforcement": {"health": 0.75, "corruption": 0.12, "trust": 0.65},
            "market_regulator": {"health": 0.6, "corruption": 0.2, "trust": 0.5},
        }

    def degrade_institution(self, institution: str, amount: float) -> None:
        if institution in self.institutions:
            inst = self.institutions[institution]
            inst["health"] = max(0.0, inst["health"] - amount)
            inst["corruption"] = min(1.0, inst["corruption"] + amount * 0.5)
            inst["trust"] = max(0.0, inst["trust"] - amount * 0.3)

    def reform_institution(self, institution: str, reformer: Agent, amount: float) -> bool:
        if institution not in self.institutions:
            return False
        if reformer.agent_type not in (AgentType.LEADER, AgentType.DIPLOMAT, AgentType.MEDIATOR):
            return False
        inst = self.institutions[institution]
        inst["health"] = min(1.0, inst["health"] + amount)
        inst["corruption"] = max(0.0, inst["corruption"] - amount * 0.5)
        inst["trust"] = min(1.0, inst["trust"] + amount * 0.3)
        return True

    def get_overall_stability(self) -> float:
        if not self.institutions:
            return 0.5
        avg_health = sum(i["health"] for i in self.institutions.values()) / len(self.institutions)
        avg_corruption = sum(i["corruption"] for i in self.institutions.values()) / len(self.institutions)
        return avg_health * (1 - avg_corruption * 0.5)


class GovernanceSystem:
    """
    Orchestrates all governance: laws, courts, enforcement,
    institutions, and political dynamics.
    """

    def __init__(self):
        self.law_system = LawSystem()
        self.court_system = CourtSystem(self.law_system)
        self.enforcement = EnforcementSystem(self.law_system, self.court_system)
        self.institutions = InstitutionSystem()
        self._crime_reports: list[dict] = []

    def report_crime(
        self,
        criminal: Agent,
        crime_name: str,
        evidence: float,
        tick: int,
    ) -> None:
        """Report a crime for prosecution."""
        try:
            crime_type = CrimeType(crime_name)
        except ValueError:
            crime_type = CrimeType.THEFT  # Default

        case = self.court_system.file_case(criminal, crime_type, evidence, tick)
        self._crime_reports.append({
            "criminal_id": criminal.agent_id,
            "crime": crime_name,
            "evidence": evidence,
            "tick": tick,
        })

    def tick(
        self,
        agents: list[Agent],
        factions: dict[str, object],
        lifecycle_manager,
        tick: int,
    ) -> list[dict]:
        """Process governance tick. Returns events."""
        events = []
        alive = [a for a in agents if a.is_alive()]
        agents_by_id = {a.agent_id: a for a in alive}

        # Guards enforce laws
        guards = [a for a in alive if a.agent_type == AgentType.GUARD]
        for guard in guards:
            # Find nearby agents to patrol
            from backend.core.agents.agent_system import AgentRegistry
            # Use position to find nearby - simplified
            nearby = [
                a for a in alive
                if a.position.distance_to(guard.position) <= 5 and a.agent_id != guard.agent_id
            ]
            enforcement_events = self.enforcement.patrol_and_enforce(guard, nearby, tick)
            events.extend(enforcement_events)

        # Process court cases
        court_events = self.court_system.process_cases(agents_by_id, lifecycle_manager, tick)
        events.extend(court_events)

        # Release prisoners
        for agent in alive:
            if agent.is_imprisoned:
                lifecycle_manager.release_agent(agent.agent_id, tick)

        # Institutional drift
        corruption_level = self.court_system.get_corruption_level()
        if corruption_level > 0.5:
            self.institutions.degrade_institution("judiciary", 0.001)

        # Reform attempts by diplomats/mediators
        for agent in alive:
            if agent.agent_type in (AgentType.DIPLOMAT, AgentType.MEDIATOR):
                if random.random() < 0.01:
                    self.institutions.reform_institution("judiciary", agent, 0.01)

        # Update world stability
        stability = self.institutions.get_overall_stability()

        return events

    def get_governance_snapshot(self) -> dict:
        return {
            "active_laws": len(self.law_system.active_laws),
            "pending_cases": len(self.court_system.pending_cases),
            "verdict_count": len(self.court_system.verdict_history),
            "corruption_level": self.court_system.get_corruption_level(),
            "institutional_stability": self.institutions.get_overall_stability(),
            "institutions": self.institutions.institutions,
        }
