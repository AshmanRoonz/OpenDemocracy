"""Tradeoff analysis — identify where priorities genuinely conflict.

Compares impact projections across dimensions to find pairs that move in
opposing directions, surfacing the real tensions in policy choices.
"""

from __future__ import annotations

import logging

from opendemocracy.models import ImpactProjection, Tradeoff

logger = logging.getLogger(__name__)


def find_tradeoffs(
    projections: list[ImpactProjection],
    *,
    min_severity: float = 0.1,
) -> list[Tradeoff]:
    """Identify tradeoffs between pairs of impact dimensions.

    A tradeoff exists when one dimension improves while another worsens.
    Severity is proportional to the magnitude of the opposing effects.

    Parameters
    ----------
    projections:
        Impact projections from the simulation.
    min_severity:
        Minimum severity threshold to report a tradeoff (0-1).
    """
    tradeoffs: list[Tradeoff] = []

    for i, a in enumerate(projections):
        for b in projections[i + 1 :]:
            # Compare long-term directions
            if _signs_oppose(a.long_term, b.long_term):
                severity = min(abs(a.long_term) + abs(b.long_term), 1.0)
                if severity >= min_severity:
                    tradeoffs.append(
                        Tradeoff(
                            dimension_a=a.dimension,
                            dimension_b=b.dimension,
                            description=_describe(a, b),
                            severity=round(severity, 4),
                        )
                    )

    tradeoffs.sort(key=lambda t: t.severity, reverse=True)
    logger.info("Found %d tradeoffs above severity %.2f", len(tradeoffs), min_severity)
    return tradeoffs


def _signs_oppose(a: float, b: float) -> bool:
    """True if a and b have opposite signs (and neither is zero)."""
    return (a > 0 and b < 0) or (a < 0 and b > 0)


def _describe(a: ImpactProjection, b: ImpactProjection) -> str:
    """Generate a human-readable description of a tradeoff."""
    a_dir = "improves" if a.long_term > 0 else "worsens"
    b_dir = "improves" if b.long_term > 0 else "worsens"
    return (
        f"{a.dimension} {a_dir} ({a.long_term:+.2%}) while "
        f"{b.dimension} {b_dir} ({b.long_term:+.2%}) over the long term."
    )
