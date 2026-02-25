"""Core data models shared across all layers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


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


class BiometricFactor(Enum):
    """Types of biometric data used for identity verification."""

    FINGERPRINT = "fingerprint"
    FACE = "face"
    IRIS = "iris"
    VOICE = "voice"


class SubmissionType(Enum):
    """What kind of participation a submission represents."""

    OPINION = "opinion"
    IDEA = "idea"
    VOTE = "vote"


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


# ---------------------------------------------------------------------------
# Biometric identity models
# ---------------------------------------------------------------------------


@dataclass
class BiometricTemplate:
    """A locally-stored biometric template for one factor.

    The raw biometric data (fingerprint image, face map, iris scan, voice
    sample) is processed into a compact template hash on the user's device.
    Only this hash is kept — the original capture is discarded immediately.
    Templates NEVER leave the device.
    """

    factor: BiometricFactor = BiometricFactor.FINGERPRINT
    template_hash: str = ""  # SHA-256 of the processed biometric template
    quality_score: float = 0.0  # 0-1, capture quality
    captured_at: datetime = field(default_factory=datetime.now)


@dataclass
class EnrollmentRecord:
    """Server-side record linking an anonymous ID to a public key.

    Created during biometric enrollment.  The server never sees biometric
    data — only the public key and which factor *types* were enrolled.
    """

    anonymous_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    public_key: str = ""  # PEM-encoded public key
    factors_enrolled: list[BiometricFactor] = field(default_factory=list)
    enrolled_at: datetime = field(default_factory=datetime.now)
    revoked: bool = False


@dataclass
class AuthChallenge:
    """A one-time challenge issued by the server during verification."""

    challenge_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    nonce: str = ""  # random bytes (hex-encoded)
    issued_at: datetime = field(default_factory=datetime.now)
    expires_seconds: int = 300  # 5-minute window
    consumed: bool = False


@dataclass
class VerificationResult:
    """Outcome of a biometric challenge-response verification."""

    verified: bool = False
    anonymous_id: str = ""
    factors_verified: list[BiometricFactor] = field(default_factory=list)
    verified_at: datetime = field(default_factory=datetime.now)
    reason: str = ""  # human-readable failure reason when verified=False


# ---------------------------------------------------------------------------
# Participation models
# ---------------------------------------------------------------------------


@dataclass
class Topic:
    """A topic or issue that participants can submit opinions/ideas/votes on."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    closes_at: datetime | None = None  # None = open-ended
    allow_opinions: bool = True
    allow_ideas: bool = True
    allow_votes: bool = True
    vote_options: list[str] = field(default_factory=list)  # for structured votes


@dataclass
class Submission:
    """A single verified submission (opinion, idea, or vote) from a participant."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    topic_id: str = ""
    anonymous_voter_id: str = ""  # maps to EnrollmentRecord.anonymous_id
    submission_type: SubmissionType = SubmissionType.OPINION
    content: str = ""  # free text for opinions/ideas, choice label for votes
    submitted_at: datetime = field(default_factory=datetime.now)
