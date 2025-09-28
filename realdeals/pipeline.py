from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol, Sequence

from .models import Deal, DealScore, ensure_aware
from .scoring import DealScorer


class DealConnector(Protocol):
    """A source capable of returning deals."""

    def fetch_deals(self, *, since: datetime | None = None) -> Sequence[Deal]:
        ...


@dataclass(slots=True)
class TopDeal:
    deal: Deal
    score: DealScore


class DealCurationError(Exception):
    pass


class DealPipeline:
    """Coordinates fetching, deduplication, scoring, and top deal selection."""

    def __init__(
        self,
        *,
        connectors: Sequence[DealConnector],
        scorer: DealScorer | None = None,
        now: datetime | None = None,
        max_deals: int = 10,
        freshness_cutoff_hours: int = 96,
        min_discount: float = 0.5,
    ) -> None:
        if not connectors:
            raise ValueError("at least one connector is required")
        self.connectors = connectors
        self.scorer = scorer or DealScorer(now=now)
        self.max_deals = max_deals
        self.now = ensure_aware(now or datetime.now(timezone.utc))
        self.freshness_cutoff_hours = freshness_cutoff_hours
        self.min_discount = min_discount

    def run(self) -> list[TopDeal]:
        candidate_deals = self._collect_deals()
        curated = self._curate(candidate_deals)
        scored = self.scorer.score_many(curated)
        scored.sort(key=lambda s: (s.total, s.discount_component, s.rarity_component), reverse=True)
        top = [TopDeal(deal=score.deal, score=score) for score in scored[: self.max_deals]]
        if len(top) < self.max_deals:
            raise DealCurationError(
                f"Expected {self.max_deals} top deals but curated {len(top)}. Increase supply or relax filters."
            )
        return top

    def _collect_deals(self) -> list[Deal]:
        deals: list[Deal] = []
        for connector in self.connectors:
            deals.extend(connector.fetch_deals(since=self.now))
        if not deals:
            raise DealCurationError("No deals were returned by connectors")
        return deals

    def _curate(self, deals: Iterable[Deal]) -> list[Deal]:
        seen: OrderedDict[str, Deal] = OrderedDict()
        for deal in deals:
            normalized_id = deal.normalized_id()
            if normalized_id in seen:
                existing = seen[normalized_id]
                if deal.discount > existing.discount:
                    seen[normalized_id] = deal
                continue
            if not self._is_deal_valid(deal):
                continue
            seen[normalized_id] = deal
        curated = list(seen.values())
        curated.sort(key=lambda d: d.listed_at, reverse=True)
        return curated

    def _is_deal_valid(self, deal: Deal) -> bool:
        discount = deal.discount
        if discount < self.min_discount:
            return False
        hours_since_listed = (self.now - ensure_aware(deal.listed_at)).total_seconds() / 3600
        if hours_since_listed > self.freshness_cutoff_hours:
            return False
        if deal.inventory is not None and deal.inventory == 0:
            return False
        return True


def curate_daily_top_deals(connectors: Sequence[DealConnector], *, now: datetime | None = None) -> list[TopDeal]:
    pipeline = DealPipeline(connectors=connectors, now=now)
    return pipeline.run()
