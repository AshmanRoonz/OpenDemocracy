"""Integration test — run the full pilot pipeline in demo mode."""

from opendemocracy.output.reports import generate_report
from opendemocracy.pilot.runner import _generate_synthetic_opinions, run_pipeline


class TestPilotRunner:
    def test_full_pipeline_demo_mode(self) -> None:
        opinions = _generate_synthetic_opinions(40)
        report = run_pipeline(opinions)

        assert report.topic == "universal basic income"
        assert report.total_opinions == 40
        assert len(report.clusters) > 0
        assert len(report.scenarios) == 3  # optimistic, moderate, pessimistic

    def test_report_generation(self) -> None:
        opinions = _generate_synthetic_opinions(40)
        report = run_pipeline(opinions)
        markdown = generate_report(report)

        assert "# OpenDemocracy AI" in markdown
        assert "Opinion Clusters" in markdown
        assert "Projected Scenarios" in markdown
        assert "Methodology" in markdown

    def test_scenarios_have_projections(self) -> None:
        opinions = _generate_synthetic_opinions(40)
        report = run_pipeline(opinions)

        for scenario in report.scenarios:
            assert len(scenario.projections) > 0
            for proj in scenario.projections:
                assert proj.dimension
                assert proj.confidence > 0

    def test_bias_warnings_present(self) -> None:
        opinions = _generate_synthetic_opinions(40)
        report = run_pipeline(opinions)
        # Synthetic data should trigger at least the temporal clustering warning
        assert isinstance(report.bias_warnings, list)
