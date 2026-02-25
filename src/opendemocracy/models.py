"""Core data models shared across all layers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SourcePlatform(Enum):
    """Where an opinion was collected from."""

    REDDIT = "reddit"
    TWITTER = "twitter"
    SURVEY = "survey"
    ASSEMBLY = "assembly"
    API = "api"


class Stance(Enum):
    """High-level stance on a topic."""

    STRONGLY_SUPPORT = "strongly_support"
    SUPPORT = "support"
    NEUTRAL = "neutral"
    OPPOSE = "oppose"
    STRONGLY_OPPOSE = "strongly_oppose"


@dataclass
class Demographics:
    """Self-reported demographic information (all fields optional)."""

    age_range: str | None = None  # e.g. "25-34"
    region: str | None = None  # e.g. "US-West", "EU-North"
    employment_status: str | None = None  # e.g. "employed", "unemployed", "student"
    income_bracket: str | None = None  # e.g. "low", "middle", "high"


@dataclass
class Opinion:
    """A single anonymized opinion from a participant."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str = ""
    source: SourcePlatform = SourcePlatform.SURVEY
    topic: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    demographics: Demographics = field(default_factory=Demographics)
    # Populated by processing layer
    embedding: list[float] = field(default_factory=list)
    sentiment_scores: dict[str, float] = field(default_factory=dict)
    cluster_id: int = -1


@dataclass
class ClusterResult:
    """A group of opinions that share similar perspectives."""

    cluster_id: int = 0
    label: str = ""
    size: int = 0
    representative_texts: list[str] = field(default_factory=list)
    mean_sentiment: dict[str, float] = field(default_factory=dict)
    demographic_breakdown: dict[str, dict[str, int]] = field(default_factory=dict)
    stance_distribution: dict[str, float] = field(default_factory=dict)


@dataclass
class ImpactProjection:
    """Projected impact of a policy along one dimension."""

    dimension: str = ""  # e.g. "poverty_rate", "labor_participation"
    short_term: float = 0.0  # 1-2 year projection
    medium_term: float = 0.0  # 3-5 year projection
    long_term: float = 0.0  # 5-10 year projection
    confidence: float = 0.0  # 0-1 confidence score
    assumptions: list[str] = field(default_factory=list)


@dataclass
class Tradeoff:
    """A pair of values or outcomes that are in tension."""

    dimension_a: str = ""
    dimension_b: str = ""
    description: str = ""
    severity: float = 0.0  # 0-1, how severe the tradeoff is


@dataclass
class Scenario:
    """A coherent future projection under stated assumptions."""

    name: str = ""
    description: str = ""
    assumptions: list[str] = field(default_factory=list)
    projections: list[ImpactProjection] = field(default_factory=list)
    tradeoffs: list[Tradeoff] = field(default_factory=list)


@dataclass
class PilotReport:
    """Complete output of a pilot analysis."""

    topic: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    total_opinions: int = 0
    clusters: list[ClusterResult] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    bias_warnings: list[str] = field(default_factory=list)
    methodology_notes: list[str] = field(default_factory=list)
