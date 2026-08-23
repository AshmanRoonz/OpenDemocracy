"""Continuous preference elicitation with human-confirmed projection.

Elections force coarse, infrequent, high-friction input. The alternative is a
profile that learns a citizen's *value hierarchy* through lightweight
interactions over time, then projects it onto novel issues — so nobody has to
re-deliberate every question from scratch. That projection is where power
relocates: an opaque layer sitting between raw signals and the official "will"
is worse than the party machines it replaces. So this module is built on three
hard rules:

1. **Projection is never a vote.** A projection is a *suggestion* shown back to
   its owner. Only an explicit human confirmation (or override) produces a
   stance that counts, and the record keeps both — what the model suggested and
   what the human decided.
2. **Every projection is explainable in one screen.** The math is a weighted
   dot product over named value axes; each axis's contribution is reported so a
   citizen can see exactly *why* the suggestion points where it does — and
   contest it by correcting the axis, not fighting a black box.
3. **Everything is auditable and revocable.** Every learning event and every
   decision is appended to an inspectable trail, and a profile can be erased.

No statistical machinery beyond running means lives here on purpose: the
mapping from voices to output must be inspectable by the people it speaks for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

# A single lightweight interaction says little; confidence in an axis grows
# with repeated, consistent signals. n observations → confidence n/(n+K).
CONFIDENCE_HALFWAY_OBSERVATIONS = 3.0

# Below this overall confidence a projection abstains: the honest answer is
# "we don't know your view yet — please weigh in directly".
MIN_PROJECTION_CONFIDENCE = 0.3

# Suggested stances inside this dead zone around 0 read as "no clear lean".
NEUTRAL_BAND = 0.15


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass
class AxisBelief:
    """The profile's current belief about the citizen on one value axis.

    ``position`` is a running mean in [-1, 1] (e.g. on axis
    ``"public-services"``: -1 = shrink, +1 = expand). ``observations`` counts
    the explicit signals behind it — confidence is derived, never asserted.
    """

    axis: str
    position: float = 0.0
    observations: int = 0

    @property
    def confidence(self) -> float:
        return self.observations / (self.observations + CONFIDENCE_HALFWAY_OBSERVATIONS)


@dataclass
class LearningEvent:
    """One append-only audit record of the profile changing."""

    axis: str
    signal: float
    position_after: float
    source: str  # e.g. "confirmed-vote", "survey", "correction"
    at: datetime = field(default_factory=_now)


class StanceStatus(StrEnum):
    PROVISIONAL = "provisional"  # machine suggestion, counts for nothing
    CONFIRMED = "confirmed"  # human accepted the suggestion
    OVERRIDDEN = "overridden"  # human decided differently


@dataclass
class AxisContribution:
    """One line of a projection's explanation: axis × alignment = contribution."""

    axis: str
    citizen_position: float
    topic_alignment: float
    confidence: float

    @property
    def contribution(self) -> float:
        return self.citizen_position * self.topic_alignment * self.confidence


@dataclass
class Projection:
    """A suggested stance on a topic, with its full explanation attached.

    ``stance`` is in [-1, 1] (support ↔ oppose the topic's proposition), or
    ``None`` when the profile abstains for lack of confidence. It never enters
    an aggregate: see :meth:`PreferenceProfile.decide`.
    """

    topic_id: str
    stance: float | None
    confidence: float
    contributions: list[AxisContribution]
    status: StanceStatus = StanceStatus.PROVISIONAL

    @property
    def leaning(self) -> str:
        if self.stance is None:
            return "abstain"
        if abs(self.stance) < NEUTRAL_BAND:
            return "neutral"
        return "support" if self.stance > 0 else "oppose"

    def explain(self) -> list[str]:
        """Human-readable, one-line-per-axis account of the suggestion."""
        lines = []
        for c in sorted(self.contributions, key=lambda c: -abs(c.contribution)):
            lines.append(
                f"{c.axis}: your position {c.citizen_position:+.2f} × topic "
                f"alignment {c.topic_alignment:+.2f} (confidence "
                f"{c.confidence:.0%}) → {c.contribution:+.2f}"
            )
        return lines


@dataclass
class Decision:
    """The human ruling on a projection — the only thing that ever counts."""

    topic_id: str
    status: StanceStatus
    suggested_stance: float | None
    final_stance: float
    at: datetime = field(default_factory=_now)


class PreferenceProfile:
    """A citizen-owned value profile: learn, project, and stay contestable.

    The profile belongs to the citizen (stored locally, like ``Interests``).
    It learns only from explicit signals, projects only with an explanation,
    and records every event in :attr:`history` / :attr:`decisions`.
    """

    def __init__(self) -> None:
        self._beliefs: dict[str, AxisBelief] = {}
        self.history: list[LearningEvent] = []
        self.decisions: list[Decision] = []

    # -- learning ---------------------------------------------------------- #

    def record_signal(self, axis: str, signal: float, source: str) -> AxisBelief:
        """Fold one explicit signal in [-1, 1] on ``axis`` into the profile."""
        signal = max(-1.0, min(1.0, signal))
        axis = axis.strip().lower()
        belief = self._beliefs.setdefault(axis, AxisBelief(axis=axis))
        total = belief.position * belief.observations + signal
        belief.observations += 1
        belief.position = total / belief.observations
        self.history.append(
            LearningEvent(
                axis=axis,
                signal=signal,
                position_after=belief.position,
                source=source,
            )
        )
        return belief

    def belief(self, axis: str) -> AxisBelief | None:
        return self._beliefs.get(axis.strip().lower())

    def erase(self) -> None:
        """Right to be forgotten: drop every belief and the learning trail."""
        self._beliefs.clear()
        self.history.clear()
        self.decisions.clear()

    # -- projection -------------------------------------------------------- #

    def project(self, topic_id: str, alignments: dict[str, float]) -> Projection:
        """Suggest a stance on a topic from its declared value alignments.

        ``alignments`` maps axis name → how supporting the topic's proposition
        aligns with that axis, in [-1, 1] (declared openly on the issue, like
        tags). Axes the profile knows nothing about contribute nothing, and if
        overall confidence is too low the projection abstains rather than
        guessing.
        """
        contributions: list[AxisContribution] = []
        for axis, alignment in alignments.items():
            b = self.belief(axis)
            if b is None or b.observations == 0:
                continue
            contributions.append(
                AxisContribution(
                    axis=b.axis,
                    citizen_position=b.position,
                    topic_alignment=max(-1.0, min(1.0, alignment)),
                    confidence=b.confidence,
                )
            )

        if not contributions:
            return Projection(topic_id, None, 0.0, [])

        confidence = sum(c.confidence for c in contributions) / len(contributions)
        if confidence < MIN_PROJECTION_CONFIDENCE:
            return Projection(topic_id, None, confidence, contributions)

        raw = sum(c.contribution for c in contributions) / len(contributions)
        stance = max(-1.0, min(1.0, raw))
        return Projection(topic_id, stance, confidence, contributions)

    # -- human authority --------------------------------------------------- #

    def decide(
        self, projection: Projection, final_stance: float | None = None
    ) -> Decision:
        """Turn a projection into a countable stance — by human choice only.

        With ``final_stance`` omitted the citizen accepts the suggestion
        (requires one that exists); passing a value overrides it. An override
        also feeds back into learning: the model was wrong about them, and the
        correction is signal.
        """
        if final_stance is None:
            if projection.stance is None:
                raise ValueError("cannot confirm an abstaining projection")
            projection.status = StanceStatus.CONFIRMED
            final = projection.stance
        else:
            projection.status = StanceStatus.OVERRIDDEN
            final = max(-1.0, min(1.0, final_stance))
            for c in projection.contributions:
                if c.topic_alignment:
                    # The stance they chose, read back through each axis.
                    self.record_signal(
                        c.axis, final * c.topic_alignment, source="correction"
                    )

        decision = Decision(
            topic_id=projection.topic_id,
            status=projection.status,
            suggested_stance=projection.stance,
            final_stance=final,
        )
        self.decisions.append(decision)
        return decision
