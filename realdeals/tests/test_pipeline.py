from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

import pytest

from realdeals.models import Deal
from realdeals.pipeline import DealConnector, DealPipeline, DealCurationError, TopDeal


class StaticConnector:
    def __init__(self, deals: Sequence[Deal]) -> None:
        self._deals = list(deals)
        self.calls: int = 0

    def fetch_deals(self, *, since: datetime | None = None) -> Sequence[Deal]:  # type: ignore[override]
        self.calls += 1
        return self._deals


def _deal(
    *,
    id: str,
    price: float,
    original_price: float,
    rarity: float,
    hours_ago: float,
    source: str = "trusted_marketplace",
    inventory: int | None = 1,
) -> Deal:
    now = datetime.now(timezone.utc)
    listed_at = now - timedelta(hours=hours_ago)
    return Deal(
        id=id,
        title=f"Deal {id}",
        url=f"https://example.com/{id}",
        price=price,
        original_price=original_price,
        source=source,
        listed_at=listed_at,
        rarity_score=rarity,
        inventory=inventory,
    )


def test_pipeline_returns_exactly_ten_deals(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    deals = [
        _deal(id=str(i), price=10, original_price=100, rarity=0.9 - i * 0.02, hours_ago=10) for i in range(12)
    ]
    connector = StaticConnector(deals)
    pipeline = DealPipeline(connectors=[connector], now=now)

    top_deals = pipeline.run()

    assert len(top_deals) == 10
    assert all(isinstance(td, TopDeal) for td in top_deals)
    assert connector.calls == 1


def test_pipeline_filters_duplicates_by_discount() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    better_deal = _deal(id="abc", price=10, original_price=100, rarity=0.9, hours_ago=1)
    worse_deal = _deal(id="ABC", price=20, original_price=100, rarity=0.9, hours_ago=1)
    connector = StaticConnector([worse_deal, better_deal])
    pipeline = DealPipeline(connectors=[connector], now=now, max_deals=1)

    top_deals = pipeline.run()

    assert len(top_deals) == 1
    assert top_deals[0].deal.price == 10


def test_pipeline_enforces_minimum_discount() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    good_deal = _deal(id="good", price=10, original_price=100, rarity=0.9, hours_ago=1)
    bad_deal = _deal(id="bad", price=60, original_price=100, rarity=1.0, hours_ago=1)
    connector = StaticConnector([good_deal, bad_deal])
    pipeline = DealPipeline(connectors=[connector], now=now, max_deals=1)

    top_deals = pipeline.run()

    assert len(top_deals) == 1
    assert top_deals[0].deal.id == "good"


def test_pipeline_raises_when_not_enough_deals() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    deals = [_deal(id=str(i), price=10, original_price=100, rarity=0.9, hours_ago=10) for i in range(5)]
    connector = StaticConnector(deals)
    pipeline = DealPipeline(connectors=[connector], now=now, max_deals=10)

    with pytest.raises(DealCurationError):
        pipeline.run()


def test_pipeline_rejects_stale_inventory() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    fresh_deal = _deal(id="fresh", price=10, original_price=100, rarity=0.9, hours_ago=10)
    stale_deal = _deal(id="stale", price=10, original_price=100, rarity=0.9, hours_ago=200)
    connector = StaticConnector([fresh_deal, stale_deal])
    pipeline = DealPipeline(connectors=[connector], now=now, max_deals=1)

    top_deals = pipeline.run()

    assert [deal.deal.id for deal in top_deals] == ["fresh"]


def test_pipeline_prioritises_rarity_on_ties() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rare = _deal(id="rare", price=10, original_price=100, rarity=0.9, hours_ago=1)
    common = _deal(id="common", price=10, original_price=100, rarity=0.1, hours_ago=1)
    connector = StaticConnector([common, rare])
    pipeline = DealPipeline(connectors=[connector], now=now, max_deals=2)

    top_deals = pipeline.run()

    assert [deal.deal.id for deal in top_deals] == ["rare", "common"]
