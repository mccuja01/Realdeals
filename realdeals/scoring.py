from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .models import Deal, DealScore, ensure_aware


@dataclass(frozen=True)
class ScoringWeights:
    discount: float = 0.5
    rarity: float = 0.2
    freshness: float = 0.15
    trust: float = 0.1
    inventory: float = 0.05

    def normalize(self) -> "ScoringWeights":
        total = self.discount + self.rarity + self.freshness + self.trust + self.inventory
        if total == 0:
            raise ValueError("scoring weights sum to zero")
        return ScoringWeights(
            discount=self.discount / total,
            rarity=self.rarity / total,
            freshness=self.freshness / total,
            trust=self.trust / total,
            inventory=self.inventory / total,
        )


DEFAULT_TRUST_WEIGHTS: dict[str, float] = {
    "museum_liquidations": 1.0,
    "trusted_marketplace": 0.9,
    "flash_sale": 0.8,
}


class DealScorer:
    def __init__(
        self,
        *,
        trust_weights: dict[str, float] | None = None,
        weights: ScoringWeights | None = None,
        now: datetime | None = None,
    ) -> None:
        self.trust_weights = trust_weights or DEFAULT_TRUST_WEIGHTS
        self.weights = (weights or ScoringWeights()).normalize()
        self.now = ensure_aware(now or datetime.now(timezone.utc))

    def score(self, deal: Deal) -> DealScore:
        normalized_discount = _clamp(deal.discount, 0.0, 0.99)
        rarity_component = _clamp(deal.rarity_score, 0.0, 1.0)
        freshness_component = self._freshness_component(deal)
        trust_component = self._trust_component(deal)
        inventory_component = self._inventory_component(deal)

        return DealScore(
            deal=deal,
            discount_component=normalized_discount * self.weights.discount,
            rarity_component=rarity_component * self.weights.rarity,
            freshness_component=freshness_component * self.weights.freshness,
            trust_component=trust_component * self.weights.trust,
            inventory_component=inventory_component * self.weights.inventory,
        )

    def score_many(self, deals: Iterable[Deal]) -> list[DealScore]:
        return [self.score(deal) for deal in deals]

    def _freshness_component(self, deal: Deal) -> float:
        listed_at = ensure_aware(deal.listed_at)
        hours_since_listed = (self.now - listed_at).total_seconds() / 3600
        if hours_since_listed <= 0:
            return 1.0
        decay_window_hours = 72
        decay = max(0.0, 1 - hours_since_listed / decay_window_hours)
        return decay

    def _trust_component(self, deal: Deal) -> float:
        return _clamp(self.trust_weights.get(deal.source, 0.5), 0.0, 1.0)

    def _inventory_component(self, deal: Deal) -> float:
        if deal.inventory is None:
            return 0.5
        if deal.inventory <= 0:
            return 0.0
        # Reward genuinely scarce deals but avoid rewarding plentiful stock
        scarcity_threshold = 5
        if deal.inventory <= scarcity_threshold:
            return 1 - (deal.inventory - 1) / max(scarcity_threshold - 1, 1)
        return 0.2


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
