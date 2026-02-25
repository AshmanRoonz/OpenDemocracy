"""UBI pilot configuration — dimension models and scenario definitions.

Encodes the structural assumptions for a Universal Basic Income analysis.
Every number here is an estimate that must be declared, challenged, and
refined by the community. Nothing is hidden.
"""

from __future__ import annotations

from opendemocracy.modeling.scenarios import ScenarioDefinition
from opendemocracy.modeling.simulation import DimensionModel

TOPIC = "universal basic income"

# ---------------------------------------------------------------------------
# Impact dimensions — each is a measurable outcome with a projected trajectory
# ---------------------------------------------------------------------------

POVERTY_RATE = DimensionModel(
    name="poverty_rate",
    base_effect=-0.08,  # 8% reduction in year 1
    growth_curve="logarithmic",
    rate=0.8,
    confidence=0.65,
    assumptions=[
        "UBI set at national poverty-line level",
        "No clawback from existing means-tested benefits",
    ],
)

LABOR_PARTICIPATION = DimensionModel(
    name="labor_force_participation",
    base_effect=-0.02,  # small initial dip
    growth_curve="decay",
    rate=0.3,
    confidence=0.45,
    assumptions=[
        "Based on Finland/Stockton pilot findings",
        "Assumes voluntary participation in labor market",
    ],
)

INFLATION = DimensionModel(
    name="inflation",
    base_effect=0.03,  # 3% initial inflationary pressure
    growth_curve="decay",
    rate=0.5,
    confidence=0.40,
    assumptions=[
        "Central bank maintains current monetary policy",
        "No concurrent supply-side reforms",
    ],
)

ENTREPRENEURSHIP = DimensionModel(
    name="entrepreneurship_rate",
    base_effect=0.04,
    growth_curve="logarithmic",
    rate=0.6,
    confidence=0.50,
    assumptions=[
        "UBI provides safety net for risk-taking",
        "No changes to business regulation",
    ],
)

FISCAL_COST = DimensionModel(
    name="fiscal_cost_gdp_share",
    base_effect=0.05,  # 5% of GDP in year 1
    growth_curve="linear",
    rate=0.2,
    confidence=0.60,
    assumptions=[
        "Funded by broad-based taxation",
        "Administrative savings from replacing means-tested programs",
    ],
)

MENTAL_HEALTH = DimensionModel(
    name="mental_health_improvement",
    base_effect=0.06,
    growth_curve="logarithmic",
    rate=0.7,
    confidence=0.55,
    assumptions=[
        "Based on Manitoba Mincome and Finnish pilot data",
        "Reduction in financial stress as primary mechanism",
    ],
)

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIO_OPTIMISTIC = ScenarioDefinition(
    name="Optimistic",
    description=(
        "UBI implemented with complementary reforms (education investment, "
        "job retraining). Inflation managed through monetary policy. "
        "Strong poverty reduction with moderate fiscal cost."
    ),
    assumptions=[
        "Complementary education and retraining investment",
        "Active monetary policy management",
        "Gradual phase-in over 2 years",
        "UBI set at poverty-line level",
    ],
    dimension_models=[
        POVERTY_RATE,
        DimensionModel("labor_force_participation", -0.01, "decay", 0.5, 0.50),
        DimensionModel("inflation", 0.02, "decay", 0.7, 0.45),
        ENTREPRENEURSHIP,
        DimensionModel("fiscal_cost_gdp_share", 0.04, "linear", 0.15, 0.55),
        MENTAL_HEALTH,
    ],
)

SCENARIO_PESSIMISTIC = ScenarioDefinition(
    name="Pessimistic",
    description=(
        "UBI implemented without complementary reforms. Inflation erodes "
        "purchasing power. Labor participation drops significantly. "
        "Fiscal cost grows unsustainably."
    ),
    assumptions=[
        "No complementary policy reforms",
        "Loose monetary policy",
        "Immediate full implementation",
        "UBI set above poverty-line level",
    ],
    dimension_models=[
        DimensionModel("poverty_rate", -0.04, "logarithmic", 0.5, 0.50),
        DimensionModel("labor_force_participation", -0.05, "logarithmic", 0.4, 0.40),
        DimensionModel("inflation", 0.06, "logarithmic", 0.8, 0.35),
        DimensionModel("entrepreneurship_rate", 0.02, "decay", 0.3, 0.35),
        DimensionModel("fiscal_cost_gdp_share", 0.08, "linear", 0.3, 0.50),
        DimensionModel("mental_health_improvement", 0.03, "decay", 0.4, 0.40),
    ],
)

SCENARIO_MODERATE = ScenarioDefinition(
    name="Moderate (base case)",
    description=(
        "UBI at a modest level with partial reform. Mixed effects: clear "
        "poverty reduction, small labor market shifts, manageable inflation."
    ),
    assumptions=[
        "Partial complementary reforms",
        "Standard monetary policy",
        "Phase-in over 3 years",
        "UBI set at 75% of poverty-line level",
    ],
    dimension_models=[
        POVERTY_RATE,
        LABOR_PARTICIPATION,
        INFLATION,
        ENTREPRENEURSHIP,
        FISCAL_COST,
        MENTAL_HEALTH,
    ],
)

ALL_SCENARIOS = [SCENARIO_OPTIMISTIC, SCENARIO_MODERATE, SCENARIO_PESSIMISTIC]
