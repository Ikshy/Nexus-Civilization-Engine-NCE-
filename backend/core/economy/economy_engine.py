"""
Nexus Civilization Engine - Economy Engine
Supply-demand markets, trading, inflation, black market, debt, taxation.
"""
from __future__ import annotations
import random
import math
import logging
from typing import Optional
from collections import defaultdict
import numpy as np

from backend.core.enums import ResourceType, AgentType, ActionType, CrimeType
from backend.core.models import (
    Agent, MarketPrice, MarketListing, TradeOffer, DebtEntry,
    ResourceBundle, SimulationEvent
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)

BASE_PRICES = {
    ResourceType.FOOD: 2.0,
    ResourceType.WATER: 1.5,
    ResourceType.ENERGY: 3.0,
    ResourceType.TOOLS: 5.0,
    ResourceType.LAND: 10.0,
    ResourceType.MONEY: 1.0,
    ResourceType.INFORMATION: 8.0,
    ResourceType.LABOR: 4.0,
    ResourceType.MEDICINE: 12.0,
    ResourceType.COMPUTING: 15.0,
    ResourceType.WEAPONS: 10.0,
    ResourceType.RAW_MATERIALS: 1.5,
}


class PriceModel:
    """Supply-demand price calculation with elasticity."""

    PRICE_ELASTICITY = {
        ResourceType.FOOD: 0.8,       # inelastic - people must eat
        ResourceType.WATER: 0.9,
        ResourceType.MEDICINE: 0.7,   # very inelastic
        ResourceType.TOOLS: 1.2,
        ResourceType.ENERGY: 1.0,
        ResourceType.WEAPONS: 1.5,
        ResourceType.INFORMATION: 2.0,
        ResourceType.COMPUTING: 1.8,
    }

    def compute_price(
        self,
        resource: ResourceType,
        supply: float,
        demand: float,
        inflation: float,
        crisis_multiplier: float = 1.0,
    ) -> float:
        """Compute market price from supply/demand."""
        if supply <= 0:
            supply = 0.1  # Avoid division by zero
        base = BASE_PRICES.get(resource, 1.0)
        elasticity = self.PRICE_ELASTICITY.get(resource, 1.0)

        # Supply-demand ratio
        ratio = demand / supply
        price_pressure = (ratio ** elasticity)

        # Apply inflation and crisis
        price = base * price_pressure * (1 + inflation) * crisis_multiplier

        # Clamp to prevent extreme prices
        min_price = base * 0.1
        max_price = base * 20.0
        return max(min_price, min(max_price, price))


class Market:
    """Central marketplace for resource trading."""

    def __init__(self):
        self.prices: dict[ResourceType, MarketPrice] = {
            r: MarketPrice(
                resource=r,
                base_price=BASE_PRICES.get(r, 1.0),
                current_price=BASE_PRICES.get(r, 1.0),
                supply=random.uniform(80, 120),
                demand=random.uniform(80, 120),
            )
            for r in ResourceType
        }
        self.listings: dict[str, MarketListing] = {}
        self.transaction_history: list[dict] = []
        self.total_volume: float = 0.0
        self.price_model = PriceModel()
        self.inflation_rate: float = settings.simulation.base_inflation_rate
        self._cumulative_inflation: float = 0.0

    def update_supply_demand(
        self,
        resource: ResourceType,
        supply_delta: float,
        demand_delta: float,
        tick: int,
    ) -> None:
        mp = self.prices[resource]
        mp.supply = max(0.1, mp.supply + supply_delta)
        mp.demand = max(0.1, mp.demand + demand_delta)

    def recompute_prices(
        self, tick: int, crisis_resources: Optional[list[ResourceType]] = None
    ) -> list[dict]:
        """Recompute all market prices. Returns price change events."""
        events = []
        crisis_set = set(crisis_resources or [])

        for resource, mp in self.prices.items():
            crisis_mult = 2.5 if resource in crisis_set else 1.0
            old_price = mp.current_price
            new_price = self.price_model.compute_price(
                resource, mp.supply, mp.demand, self._cumulative_inflation, crisis_mult
            )

            # Record price history
            mp.price_history.append(old_price)
            if len(mp.price_history) > 100:
                mp.price_history = mp.price_history[-100:]

            mp.current_price = new_price
            mp.last_updated_tick = tick

            # Emit large price change events
            if abs(new_price - old_price) / max(old_price, 0.01) > 0.3:
                events.append({
                    "event_type": "price_shock",
                    "resource": resource.value,
                    "old_price": old_price,
                    "new_price": new_price,
                    "change_pct": (new_price - old_price) / old_price * 100,
                    "tick": tick,
                })

        # Compound inflation
        self._cumulative_inflation = max(
            0.0, self._cumulative_inflation + self.inflation_rate * 0.001
        )
        return events

    def get_price(self, resource: ResourceType) -> float:
        return self.prices[resource].current_price

    def get_all_prices(self) -> dict[ResourceType, float]:
        return {r: mp.current_price for r, mp in self.prices.items()}

    def post_listing(
        self,
        seller: Agent,
        resource: ResourceType,
        quantity: float,
        price: float,
        tick: int,
        is_black_market: bool = False,
    ) -> Optional[MarketListing]:
        if not seller.inventory.subtract(resource, quantity):
            return None
        listing = MarketListing(
            seller_id=seller.agent_id,
            resource=resource,
            quantity=quantity,
            price_per_unit=price,
            is_black_market=is_black_market,
            expires_tick=tick + 20,
            created_tick=tick,
        )
        self.listings[listing.listing_id] = listing
        # Update supply
        self.update_supply_demand(resource, quantity, 0, tick)
        return listing

    def buy_from_listing(
        self,
        buyer: Agent,
        listing_id: str,
        quantity: float,
        tick: int,
    ) -> dict:
        listing = self.listings.get(listing_id)
        if not listing:
            return {"success": False, "reason": "listing_not_found"}

        buy_qty = min(quantity, listing.quantity)
        total_cost = buy_qty * listing.price_per_unit

        if not buyer.inventory.subtract(ResourceType.MONEY, total_cost):
            return {"success": False, "reason": "insufficient_funds"}

        listing.quantity -= buy_qty
        if listing.quantity <= 0:
            del self.listings[listing_id]

        buyer.inventory.add(listing.resource, buy_qty)
        self.total_volume += total_cost

        # Update supply/demand
        self.update_supply_demand(listing.resource, -buy_qty, -buy_qty * 0.1, tick)

        # Record transaction
        tx = {
            "tick": tick,
            "buyer_id": buyer.agent_id,
            "seller_id": listing.seller_id,
            "resource": listing.resource.value,
            "quantity": buy_qty,
            "price": listing.price_per_unit,
            "total": total_cost,
            "black_market": listing.is_black_market,
        }
        self.transaction_history.append(tx)
        if len(self.transaction_history) > 1000:
            self.transaction_history = self.transaction_history[-1000:]

        return {"success": True, "quantity": buy_qty, "cost": total_cost, "transaction": tx}

    def cleanup_expired(self, tick: int) -> list[str]:
        """Return resources from expired listings to sellers."""
        expired = []
        for lid, listing in list(self.listings.items()):
            if listing.expires_tick and tick > listing.expires_tick:
                expired.append(lid)
                del self.listings[lid]
        return expired

    def get_market_snapshot(self) -> dict:
        return {
            "prices": {r.value: mp.current_price for r, mp in self.prices.items()},
            "supply": {r.value: mp.supply for r, mp in self.prices.items()},
            "demand": {r.value: mp.demand for r, mp in self.prices.items()},
            "inflation": self._cumulative_inflation,
            "total_volume": self.total_volume,
            "active_listings": len(self.listings),
        }


class TradeSystem:
    """Peer-to-peer trading with negotiation."""

    def __init__(self, market: Market):
        self.market = market
        self.active_offers: dict[str, TradeOffer] = {}
        self.completed_trades: list[dict] = []

    def propose_trade(
        self,
        proposer: Agent,
        recipient: Agent,
        offered: dict[ResourceType, float],
        requested: dict[ResourceType, float],
        tick: int,
        is_deceptive: bool = False,
    ) -> TradeOffer:
        offer_bundle = ResourceBundle(resources=dict(offered))
        request_bundle = ResourceBundle(resources=dict(requested))

        offer = TradeOffer(
            proposer_id=proposer.agent_id,
            recipient_id=recipient.agent_id,
            offered=offer_bundle,
            requested=request_bundle,
            is_deceptive=is_deceptive,
            created_tick=tick,
            expires_tick=tick + 5,
        )
        self.active_offers[offer.offer_id] = offer
        return offer

    def evaluate_trade(
        self, recipient: Agent, offer: TradeOffer, market_prices: dict[ResourceType, float]
    ) -> bool:
        """Agent evaluates whether to accept a trade."""
        # Calculate value exchange
        offered_value = sum(
            offer.offered.get(r) * market_prices.get(r, 1.0)
            for r in ResourceType
        )
        requested_value = sum(
            offer.requested.get(r) * market_prices.get(r, 1.0)
            for r in ResourceType
        )

        if requested_value <= 0:
            return True  # Free gift
        if offered_value <= 0:
            return False  # Nothing offered

        ratio = offered_value / requested_value
        # Accept if offer is fair or better, adjusted for greed
        fairness_threshold = 0.9 - recipient.personality.greed * 0.2

        # Trust modifier
        trust = recipient.get_trust(offer.proposer_id)
        if trust < -0.5:
            fairness_threshold = 1.1  # Require overvalue from enemies

        return ratio >= fairness_threshold

    def execute_trade(
        self, proposer: Agent, recipient: Agent, offer: TradeOffer, tick: int
    ) -> dict:
        """Execute a trade if both parties have resources."""
        # Verify proposer has offered resources
        for resource, amount in offer.offered.resources.items():
            if proposer.inventory.get(resource) < amount:
                return {"success": False, "reason": "proposer_insufficient"}

        # Verify recipient has requested resources
        for resource, amount in offer.requested.resources.items():
            if recipient.inventory.get(resource) < amount:
                return {"success": False, "reason": "recipient_insufficient"}

        # Execute transfer
        for resource, amount in offer.offered.resources.items():
            proposer.inventory.subtract(resource, amount)
            recipient.inventory.add(resource, amount)

        for resource, amount in offer.requested.resources.items():
            recipient.inventory.subtract(resource, amount)
            proposer.inventory.add(resource, amount)

        offer.is_accepted = True
        if offer.offer_id in self.active_offers:
            del self.active_offers[offer.offer_id]

        trade_record = {
            "tick": tick,
            "proposer_id": proposer.agent_id,
            "recipient_id": recipient.agent_id,
            "offered": {r.value: v for r, v in offer.offered.resources.items()},
            "requested": {r.value: v for r, v in offer.requested.resources.items()},
            "was_deceptive": offer.is_deceptive,
        }
        self.completed_trades.append(trade_record)
        logger.debug(f"Trade executed: {proposer.name} <-> {recipient.name}")
        return {"success": True, "trade": trade_record}

    def process_deceptive_trade(
        self, proposer: Agent, recipient: Agent, offer: TradeOffer, tick: int
    ) -> dict:
        """Handle deceptive trade where proposer provides inferior goods."""
        # Execute as normal but goods are substandard
        result = self.execute_trade(proposer, recipient, offer, tick)
        if result["success"]:
            # Recipient gets less value than expected
            for resource, amount in offer.offered.resources.items():
                cheat_amount = amount * random.uniform(0.3, 0.6)
                recipient.inventory.subtract(resource, cheat_amount)
        return result


class TaxationSystem:
    """Government taxation and redistribution."""

    def __init__(self):
        self.tax_rate: float = settings.simulation.tax_rate
        self.collected_taxes: dict[str, float] = defaultdict(float)  # faction_id -> amount
        self.tax_history: list[dict] = []

    def collect_taxes(
        self,
        agents: list[Agent],
        faction_id: str,
        tick: int,
        progressive: bool = True,
    ) -> float:
        """Collect taxes from faction members."""
        total_collected = 0.0
        faction_agents = [a for a in agents if a.faction_id == faction_id and a.is_alive()]

        for agent in faction_agents:
            income = agent.inventory.get(ResourceType.MONEY)
            if income <= 0:
                continue

            if progressive:
                # Progressive tax: richer agents pay more
                rate = self._progressive_rate(income)
            else:
                rate = self.tax_rate

            tax_amount = income * rate

            # Compliance check - agents may evade
            evasion_prob = agent.personality.deception * 0.3 + (1 - agent.personality.conformity) * 0.2
            if random.random() < evasion_prob:
                tax_amount *= random.uniform(0.2, 0.8)  # Partial evasion
                # Record tax crime
                if ResourceType.MONEY not in agent.crimes_committed:
                    pass  # Could add tax_evasion crime type

            if agent.inventory.subtract(ResourceType.MONEY, tax_amount):
                total_collected += tax_amount

        self.collected_taxes[faction_id] += total_collected
        self.tax_history.append({
            "tick": tick,
            "faction_id": faction_id,
            "collected": total_collected,
            "agent_count": len(faction_agents),
        })
        return total_collected

    def redistribute(
        self, agents: list[Agent], faction_id: str, tax_pool: float, method: str = "equal"
    ) -> None:
        """Redistribute collected taxes."""
        faction_agents = [a for a in agents if a.faction_id == faction_id and a.is_alive()]
        if not faction_agents:
            return

        if method == "equal":
            per_agent = tax_pool / len(faction_agents)
            for agent in faction_agents:
                agent.inventory.add(ResourceType.MONEY, per_agent)
        elif method == "need_based":
            # Give more to poorer agents
            incomes = [a.inventory.get(ResourceType.MONEY) for a in faction_agents]
            total_income = sum(incomes) or 1
            weights = [1 - (inc / total_income) for inc in incomes]
            total_weight = sum(weights) or 1
            for agent, weight in zip(faction_agents, weights):
                share = tax_pool * (weight / total_weight)
                agent.inventory.add(ResourceType.MONEY, share)

    def _progressive_rate(self, income: float) -> float:
        """Calculate progressive tax rate based on income."""
        if income < 50:
            return 0.05
        elif income < 200:
            return 0.15
        elif income < 500:
            return 0.25
        else:
            return 0.40


class BlackMarket:
    """Underground economy - illegal goods, weapons, information."""

    def __init__(self, market: Market):
        self.market = market
        self.multiplier: float = settings.simulation.black_market_multiplier
        self.illegal_goods = {
            ResourceType.WEAPONS: True,
            ResourceType.INFORMATION: True,  # Stolen intel
        }
        self.transactions: list[dict] = []
        self.known_to: dict[str, set[str]] = {}  # agent_id -> set of agents who know about black market

    def can_access(self, agent: Agent) -> bool:
        """Check if agent has access to black market."""
        if agent.agent_type in (AgentType.THIEF, AgentType.SPY, AgentType.REBEL):
            return True
        if agent.personality.deception > 0.6 and agent.personality.risk_tolerance > 0.5:
            return True
        return False

    def transact(
        self,
        buyer: Agent,
        seller: Agent,
        resource: ResourceType,
        quantity: float,
        tick: int,
    ) -> dict:
        """Black market transaction - high price, risk of arrest."""
        market_price = self.market.get_price(resource)
        bm_price = market_price * self.multiplier

        total_cost = quantity * bm_price
        if not buyer.inventory.subtract(ResourceType.MONEY, total_cost):
            return {"success": False, "reason": "insufficient_funds"}
        if not seller.inventory.subtract(resource, quantity):
            return {"success": False, "reason": "seller_insufficient"}

        buyer.inventory.add(resource, quantity)
        # Seller gets inflated payment minus risk premium
        seller.inventory.add(ResourceType.MONEY, total_cost * 0.7)

        # Arrest risk
        arrest_risk = 0.05 + (1 - buyer.skills.espionage) * 0.1
        arrested = random.random() < arrest_risk

        tx = {
            "tick": tick,
            "buyer_id": buyer.agent_id,
            "seller_id": seller.agent_id,
            "resource": resource.value,
            "quantity": quantity,
            "price": bm_price,
            "arrested": arrested,
        }
        self.transactions.append(tx)

        if arrested:
            from backend.core.enums import CrimeType
            if CrimeType.THEFT not in buyer.crimes_committed:
                buyer.crimes_committed.append(CrimeType.THEFT)

        return {"success": True, "transaction": tx, "arrested": arrested}


class DebtSystem:
    """Credit and debt management."""

    def __init__(self):
        self.debts: dict[str, DebtEntry] = {}
        self.default_events: list[dict] = []

    def create_debt(
        self,
        debtor: Agent,
        creditor: Agent,
        amount: float,
        interest_rate: float,
        due_tick: int,
        tick: int,
    ) -> DebtEntry:
        """Create a loan/debt."""
        debt = DebtEntry(
            debtor_id=debtor.agent_id,
            creditor_id=creditor.agent_id,
            amount=amount,
            interest_rate=interest_rate,
            due_tick=due_tick,
        )
        self.debts[debt.debt_id] = debt
        debtor.inventory.add(ResourceType.MONEY, amount)
        creditor.inventory.subtract(ResourceType.MONEY, amount)
        logger.debug(f"Debt created: {debtor.name} owes {creditor.name} {amount}")
        return debt

    def process_debts(
        self, agents_by_id: dict[str, Agent], tick: int
    ) -> list[dict]:
        """Process debt repayments. Returns events."""
        events = []
        for debt in list(self.debts.values()):
            if debt.is_paid or debt.is_defaulted:
                continue

            # Apply interest
            debt.amount *= 1 + debt.interest_rate * 0.01  # Per tick interest

            if tick >= debt.due_tick:
                debtor = agents_by_id.get(debt.debtor_id)
                creditor = agents_by_id.get(debt.creditor_id)

                if not debtor or not debtor.is_alive():
                    debt.is_defaulted = True
                    continue

                # Try to repay
                if debtor.inventory.subtract(ResourceType.MONEY, debt.amount):
                    if creditor and creditor.is_alive():
                        creditor.inventory.add(ResourceType.MONEY, debt.amount)
                    debt.is_paid = True
                    events.append({
                        "event_type": "debt_repaid",
                        "debtor_id": debt.debtor_id,
                        "creditor_id": debt.creditor_id,
                        "amount": debt.amount,
                        "tick": tick,
                    })
                else:
                    debt.is_defaulted = True
                    # Trust damage
                    if debtor and creditor:
                        if debt.creditor_id in debtor.trust_map:
                            debtor.trust_map[debt.creditor_id].trust_score = max(
                                -1.0, debtor.trust_map[debt.creditor_id].trust_score - 0.3
                            )
                    events.append({
                        "event_type": "debt_default",
                        "debtor_id": debt.debtor_id,
                        "creditor_id": debt.creditor_id,
                        "amount": debt.amount,
                        "tick": tick,
                    })
                    self.default_events.append(events[-1])

        return events


class EconomyEngine:
    """
    Orchestrates all economic systems: market, trading, taxation,
    black market, debt, and wealth distribution.
    """

    def __init__(self):
        self.market = Market()
        self.trade_system = TradeSystem(self.market)
        self.taxation = TaxationSystem()
        self.black_market = BlackMarket(self.market)
        self.debt_system = DebtSystem()
        self._tick_supply_tracker: dict[ResourceType, float] = defaultdict(float)
        self._tick_demand_tracker: dict[ResourceType, float] = defaultdict(float)

    def tick(
        self,
        agents: list[Agent],
        factions: dict[str, object],
        tick: int,
        active_disasters: list[dict],
    ) -> list[dict]:
        """Process one economy tick. Returns events."""
        events = []

        # Determine crisis resources
        crisis_resources = []
        for disaster in active_disasters:
            if disaster["type"] == "famine":
                crisis_resources.append(ResourceType.FOOD)
            elif disaster["type"] == "market_crash":
                crisis_resources.extend([ResourceType.MONEY, ResourceType.FOOD])

        # Update supply/demand from tracked flows
        for resource in ResourceType:
            supply_delta = self._tick_supply_tracker.get(resource, 0)
            demand_delta = self._tick_demand_tracker.get(resource, 0)
            self.market.update_supply_demand(resource, supply_delta, demand_delta, tick)

        # Recompute prices
        price_events = self.market.recompute_prices(tick, crisis_resources)
        events.extend(price_events)

        # Clean expired listings
        self.market.cleanup_expired(tick)

        # Process debts
        agents_by_id = {a.agent_id: a for a in agents}
        debt_events = self.debt_system.process_debts(agents_by_id, tick)
        events.extend(debt_events)

        # Collect taxes per faction (every 10 ticks)
        if tick % 10 == 0:
            for faction_id in factions:
                tax_pool = self.taxation.collect_taxes(agents, faction_id, tick)
                if tax_pool > 0:
                    self.taxation.redistribute(agents, faction_id, tax_pool * 0.7)

        # Update agent net worth
        prices = self.market.get_all_prices()
        for agent in agents:
            agent.net_worth = agent.inventory.total_value(prices)

        # Reset trackers
        self._tick_supply_tracker.clear()
        self._tick_demand_tracker.clear()

        return events

    def record_production(self, resource: ResourceType, amount: float) -> None:
        self._tick_supply_tracker[resource] += amount

    def record_consumption(self, resource: ResourceType, amount: float) -> None:
        self._tick_demand_tracker[resource] += amount

    def process_harvest_action(
        self, agent: Agent, resource: ResourceType, cell_amount: float, tick: int
    ) -> float:
        """Process a harvest action. Returns amount harvested."""
        skill_map = {
            ResourceType.FOOD: agent.skills.farming,
            ResourceType.RAW_MATERIALS: agent.skills.crafting,
            ResourceType.WATER: 0.8,
        }
        efficiency = skill_map.get(resource, 0.5)
        base_harvest = min(cell_amount, 10.0)
        harvested = base_harvest * efficiency * random.uniform(0.8, 1.2)

        agent.inventory.add(resource, harvested)
        self.record_production(resource, harvested)
        agent.state = AgentState.WORKING

        return harvested

    def process_trade_action(
        self,
        proposer: Agent,
        recipient: Agent,
        offered: dict[ResourceType, float],
        requested: dict[ResourceType, float],
        tick: int,
        deceptive: bool = False,
    ) -> dict:
        """Handle a trade between two agents."""
        prices = self.market.get_all_prices()
        offer = self.trade_system.propose_trade(
            proposer, recipient, offered, requested, tick, deceptive
        )

        # Recipient evaluates
        accepts = self.trade_system.evaluate_trade(recipient, offer, prices)
        if not accepts:
            return {"success": False, "reason": "rejected"}

        if deceptive:
            result = self.trade_system.process_deceptive_trade(proposer, recipient, offer, tick)
        else:
            result = self.trade_system.execute_trade(proposer, recipient, offer, tick)

        return result

    def get_gini_coefficient(self, agents: list[Agent]) -> float:
        """Calculate Gini coefficient for wealth inequality."""
        incomes = sorted([a.net_worth for a in agents if a.is_alive()])
        if not incomes or len(incomes) < 2:
            return 0.0
        n = len(incomes)
        total = sum(incomes)
        if total == 0:
            return 0.0
        cumsum = np.cumsum(incomes)
        return (2 * np.sum(cumsum) - total * (n + 1)) / (total * n)

    def get_snapshot(self) -> dict:
        return {
            "market": self.market.get_market_snapshot(),
            "black_market_transactions": len(self.black_market.transactions),
            "active_debts": len([d for d in self.debt_system.debts.values() if not d.is_paid]),
            "debt_defaults": len(self.debt_system.default_events),
        }


# Import to avoid circular - defined here for convenience
from backend.core.enums import AgentState
