"""Tests for tradeoff analysis."""

from opendemocracy.models import ImpactProjection
from opendemocracy.modeling.tradeoffs import find_tradeoffs


class TestFindTradeoffs:
    def test_finds_opposing_directions(self) -> None:
        projections = [
            ImpactProjection(dimension="poverty", short_term=-0.05, medium_term=-0.08, long_term=-0.10),
            ImpactProjection(dimension="inflation", short_term=0.03, medium_term=0.04, long_term=0.05),
        ]
        tradeoffs = find_tradeoffs(projections)
        assert len(tradeoffs) == 1
        assert tradeoffs[0].dimension_a == "poverty"
        assert tradeoffs[0].dimension_b == "inflation"

    def test_no_tradeoff_for_same_direction(self) -> None:
        projections = [
            ImpactProjection(dimension="a", long_term=0.1),
            ImpactProjection(dimension="b", long_term=0.2),
        ]
        tradeoffs = find_tradeoffs(projections)
        assert len(tradeoffs) == 0

    def test_respects_min_severity(self) -> None:
        projections = [
            ImpactProjection(dimension="a", long_term=-0.01),
            ImpactProjection(dimension="b", long_term=0.01),
        ]
        tradeoffs = find_tradeoffs(projections, min_severity=0.5)
        assert len(tradeoffs) == 0

    def test_sorted_by_severity(self) -> None:
        projections = [
            ImpactProjection(dimension="a", long_term=-0.1),
            ImpactProjection(dimension="b", long_term=0.1),
            ImpactProjection(dimension="c", long_term=0.5),
        ]
        tradeoffs = find_tradeoffs(projections, min_severity=0.0)
        if len(tradeoffs) > 1:
            assert tradeoffs[0].severity >= tradeoffs[1].severity
