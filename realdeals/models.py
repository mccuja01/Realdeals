from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class Deal:
    """Represents a deal that may be considered for the top-10 feed."""

    id: str
    title: str
    url: str
    price: float
    original_price: float
    source: str
    listed_at: datetime
    rarity_score: float = 0.0
    inventory: Optional[int] = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("price cannot be negative")
        if self.original_price <= 0:
            raise ValueError("original_price must be > 0")
        if self.price > self.original_price:
            raise ValueError("price cannot exceed original price")
        if not (0.0 <= self.rarity_score <= 1.0):
            raise ValueError("rarity_score must be between 0 and 1")
        if self.listed_at.tzinfo is None:
            raise ValueError("listed_at must be timezone-aware")

    @property
    def discount(self) -> float:
        """Returns the discount as a fraction in the range [0, 1]."""
        return (self.original_price - self.price) / self.original_price

    def normalized_id(self) -> str:
        """Identifier normalized to prevent duplicates from multiple sources."""
        return self.id.strip().lower()


@dataclass(slots=True)
class DealScore:
    deal: Deal
    discount_component: float
    rarity_component: float
    freshness_component: float
    trust_component: float
    inventory_component: float

    @property
    def total(self) -> float:
        return (
            self.discount_component
            + self.rarity_component
            + self.freshness_component
            + self.trust_component
            + self.inventory_component
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "discount": self.discount_component,
            "rarity": self.rarity_component,
            "freshness": self.freshness_component,
            "trust": self.trust_component,
            "inventory": self.inventory_component,
            "total": self.total,
        }


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
