"""Report generation — produce human-readable analysis summaries.

Generates Markdown reports with full methodology transparency,
confidence intervals, and demographic breakdowns.
"""

from __future__ import annotations

import logging
from datetime import datetime

from opendemocracy.models import ClusterResult, PilotReport, Scenario

logger = logging.getLogger(__name__)


def generate_report(report: PilotReport) -> str:
    """Render a PilotReport as a Markdown document."""
    lines: list[str] = []

    lines.append(f"# OpenDemocracy AI — Pilot Report: {report.topic}")
    lines.append("")
    lines.append(f"*Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append(f"*Total opinions analyzed: {report.total_opinions}*")
    lines.append("")

    # Bias warnings
    if report.bias_warnings:
        lines.append("## Data Quality Warnings")
        lines.append("")
        for warning in report.bias_warnings:
            lines.append(f"- **Warning**: {warning}")
        lines.append("")

    # Cluster summaries
    if report.clusters:
        lines.append("## Opinion Clusters")
        lines.append("")
        for cluster in report.clusters:
            lines.append(f"### {cluster.label} ({cluster.size} opinions)")
            lines.append("")
            _render_cluster(lines, cluster)
            lines.append("")

    # Scenarios
    if report.scenarios:
        lines.append("## Projected Scenarios")
        lines.append("")
        for scenario in report.scenarios:
            _render_scenario(lines, scenario)
            lines.append("")

    # Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append("This analysis was produced by the OpenDemocracy AI pipeline.")
    lines.append("All algorithms are open-source and auditable.")
    lines.append("")
    if report.methodology_notes:
        for note in report.methodology_notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("---")
    lines.append("*This report presents distributions, not conclusions. "
                 "No single number should be taken as a definitive answer.*")

    return "\n".join(lines)


def _render_cluster(lines: list[str], cluster: ClusterResult) -> None:
    """Render a single cluster's details."""
    if cluster.stance_distribution:
        sd = cluster.stance_distribution
        lines.append(
            f"**Stance**: {sd.get('support', 0):.0%} support / "
            f"{sd.get('neutral', 0):.0%} neutral / "
            f"{sd.get('oppose', 0):.0%} oppose"
        )

    if cluster.mean_sentiment:
        ms = cluster.mean_sentiment
        parts = [f"{k}: {v:+.2f}" for k, v in ms.items()]
        lines.append(f"**Sentiment**: {', '.join(parts)}")

    if cluster.representative_texts:
        lines.append("")
        lines.append("**Representative views:**")
        for text in cluster.representative_texts:
            lines.append(f'> "{text}"')
            lines.append("")

    if cluster.demographic_breakdown:
        lines.append("**Demographic breakdown:**")
        for dim, groups in cluster.demographic_breakdown.items():
            lines.append(f"- *{dim}*: {groups}")


def _render_scenario(lines: list[str], scenario: Scenario) -> None:
    """Render a single scenario's details."""
    lines.append(f"### Scenario: {scenario.name}")
    lines.append("")
    lines.append(scenario.description)
    lines.append("")

    if scenario.assumptions:
        lines.append("**Assumptions:**")
        for a in scenario.assumptions:
            lines.append(f"- {a}")
        lines.append("")

    if scenario.projections:
        lines.append("| Dimension | Short-term | Medium-term | Long-term | Confidence |")
        lines.append("|---|---|---|---|---|")
        for p in scenario.projections:
            lines.append(
                f"| {p.dimension} | {p.short_term:+.2%} | "
                f"{p.medium_term:+.2%} | {p.long_term:+.2%} | "
                f"{p.confidence:.0%} |"
            )
        lines.append("")

    if scenario.tradeoffs:
        lines.append("**Key tradeoffs:**")
        for t in scenario.tradeoffs:
            lines.append(f"- {t.description} (severity: {t.severity:.2f})")
        lines.append("")
