"""Scenario generation — create plausible futures under different assumptions.

Each scenario is a named bundle of assumptions + the simulation results
that follow. This lets decision-makers compare "what if" alternatives
side-by-side.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from opendemocracy.modeling.simulation import DimensionModel, simulate
from opendemocracy.modeling.tradeoffs import find_tradeoffs
from opendemocracy.models import Scenario

logger = logging.getLogger(__name__)


@dataclass
class ScenarioDefinition:
    """User-facing definition of a scenario (before simulation)."""

    name: str
    description: str
    assumptions: list[str]
    dimension_models: list[DimensionModel]


def generate_scenarios(definitions: list[ScenarioDefinition]) -> list[Scenario]:
    """Simulate each scenario definition and return full Scenario objects."""
    scenarios: list[Scenario] = []

    for defn in definitions:
        projections = simulate(defn.dimension_models)
        tradeoffs = find_tradeoffs(projections)

        scenarios.append(
            Scenario(
                name=defn.name,
                description=defn.description,
                assumptions=defn.assumptions,
                projections=projections,
                tradeoffs=tradeoffs,
            )
        )

    logger.info("Generated %d scenarios", len(scenarios))
    return scenarios
