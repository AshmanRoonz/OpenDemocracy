"""Consequence simulation — model downstream effects of policy choices.

This module provides a *declarative* simulation framework. Each policy is
defined by a set of impact dimensions with estimated effect sizes and decay/
growth curves. The simulator projects these effects forward in time under
stated assumptions.

For the UBI pilot, the dimensions include poverty rate, labor participation,
inflation, entrepreneurship, and fiscal cost.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from opendemocracy.models import ImpactProjection

logger = logging.getLogger(__name__)


@dataclass
class DimensionModel:
    """Parameters for projecting one impact dimension over time."""

    name: str
    # Base effect at year 1 (% change from status quo, e.g. -0.05 = 5% decrease)
    base_effect: float
    # How the effect changes over time: "linear", "logarithmic", "decay"
    growth_curve: str = "logarithmic"
    # Rate parameter for the curve
    rate: float = 1.0
    # Confidence in the estimate (0-1)
    confidence: float = 0.5
    # Key assumptions behind this projection
    assumptions: list[str] | None = None


def _project(model: DimensionModel, years: float) -> float:
    """Project the effect size at a given number of years."""
    base = model.base_effect
    if model.growth_curve == "linear":
        return base * years * model.rate
    elif model.growth_curve == "logarithmic":
        return base * math.log1p(years * model.rate)
    elif model.growth_curve == "decay":
        # Effect that fades over time (e.g. initial inflation shock)
        return base * math.exp(-model.rate * years)
    else:
        return base


def simulate(models: list[DimensionModel]) -> list[ImpactProjection]:
    """Run the simulation across all dimensions and return projections.

    Generates short-term (1-2yr), medium-term (3-5yr), and long-term (5-10yr)
    projections for each dimension.
    """
    projections: list[ImpactProjection] = []

    for model in models:
        proj = ImpactProjection(
            dimension=model.name,
            short_term=round(_project(model, 1.5), 4),
            medium_term=round(_project(model, 4.0), 4),
            long_term=round(_project(model, 7.5), 4),
            confidence=model.confidence,
            assumptions=model.assumptions or [],
        )
        projections.append(proj)

    logger.info("Simulated %d impact dimensions", len(projections))
    return projections
