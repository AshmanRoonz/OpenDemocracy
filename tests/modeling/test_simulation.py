"""Tests for impact simulation."""

from opendemocracy.modeling.simulation import DimensionModel, simulate


class TestSimulate:
    def test_returns_projections(self) -> None:
        models = [
            DimensionModel(name="poverty_rate", base_effect=-0.08, confidence=0.6),
            DimensionModel(name="inflation", base_effect=0.03, growth_curve="decay", confidence=0.4),
        ]
        projections = simulate(models)
        assert len(projections) == 2

    def test_projection_dimensions_match(self) -> None:
        models = [DimensionModel(name="test_dim", base_effect=0.1)]
        projections = simulate(models)
        assert projections[0].dimension == "test_dim"

    def test_logarithmic_growth_increases_over_time(self) -> None:
        models = [DimensionModel(name="x", base_effect=0.1, growth_curve="logarithmic")]
        projections = simulate(models)
        p = projections[0]
        assert abs(p.long_term) > abs(p.short_term)

    def test_decay_shrinks_over_time(self) -> None:
        models = [DimensionModel(name="x", base_effect=0.1, growth_curve="decay", rate=0.5)]
        projections = simulate(models)
        p = projections[0]
        assert abs(p.short_term) > abs(p.long_term)

    def test_confidence_preserved(self) -> None:
        models = [DimensionModel(name="x", base_effect=0.1, confidence=0.75)]
        projections = simulate(models)
        assert projections[0].confidence == 0.75
