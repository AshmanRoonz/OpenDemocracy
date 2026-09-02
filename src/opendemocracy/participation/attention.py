"""*What needs attention?* — where automatic flow hands over to choice.

Everything in Vote flows by default: a preference profile projects a stance, a
standing vote keeps standing. That is what makes daily participation possible
without fatigue. But flow is only legitimate while it is trustworthy, and this
module answers the one question that decides when it isn't — for *this*
citizen, on *this* issue, right now.

The answer is a list of named reasons, each with a fixed weight you can read
below. Attention is a budget, and every claim on it states its cause, so the
feed can never quietly become an engagement machine: if Vote asks for your
attention, it says exactly why.

The question runs both ways. Asked of the system, it is this feed. Asked of
the citizen — :data:`AGENDA_PROMPT` — it is the agenda: naming what nobody has
asked about yet is how a proposition is born. Together with "what changed your
mind?" these are Vote's standard questions: one opens choice, one closes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from opendemocracy.models import Topic
from opendemocracy.participation.preferences import PreferenceProfile
from opendemocracy.participation.relevance import (
    Interests,
    _aware,
    matches_interests,
    relevance_score,
)
from opendemocracy.participation.status import compute_status
from opendemocracy.participation.votes import StandingVoteLedger

# The question asked *of the citizen*. Answering it in one line creates a
# proposition — the agenda-setting move.
AGENDA_PROMPT = "What needs attention that nobody has asked about yet?"


class AttentionReason(StrEnum):
    """Why flow stopped being trustworthy for you on an issue."""

    VALUE_CONFLICT = "value_conflict"  # your own values pull opposite ways
    UNKNOWN_VALUES = "unknown_values"  # the profile can't project here
    PEERS_MOVING = "peers_moving"  # people who stood where you stand are moving
    STALE_VOTE = "stale_vote"  # the picture shifted since you last chose
    CLOSING_SOON = "closing_soon"  # the decision window is ending
    QUORUM_NEAR = "quorum_near"  # a few more voices make it legitimate
    NOT_YET_HEARD = "not_yet_heard"  # it concerns you and you haven't spoken


# Fixed, readable weights. A conflict inside your own values outranks anything
# the crowd is doing, because it is the one case where no default is honest.
WEIGHTS: dict[AttentionReason, float] = {
    AttentionReason.VALUE_CONFLICT: 3.0,
    AttentionReason.UNKNOWN_VALUES: 2.0,
    AttentionReason.PEERS_MOVING: 2.0,
    AttentionReason.CLOSING_SOON: 2.0,
    AttentionReason.STALE_VOTE: 1.5,
    AttentionReason.QUORUM_NEAR: 1.0,
    AttentionReason.NOT_YET_HEARD: 1.0,
}

# A value conflict needs real pull on both sides, not rounding noise.
CONFLICT_MIN_CONTRIBUTION = 0.15
# How many people must have moved away from your stance before it's a wave.
PEER_MOVE_MIN = 3
# A tally has "shifted" when the share behind your option moved this much.
STALE_SHIFT = 0.10
# Quorum counts as near from this fraction of the target.
QUORUM_NEAR_FRACTION = 0.8


@dataclass
class AttentionItem:
    """One issue that needs this citizen's attention, and every reason why."""

    topic: Topic
    reasons: list[AttentionReason]
    explanations: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return sum(WEIGHTS[r] for r in self.reasons)


def _value_reasons(
    topic: Topic, profile: PreferenceProfile | None
) -> list[tuple[AttentionReason, str]]:
    if profile is None or not topic.value_alignments:
        return []
    proj = profile.project(topic.id, topic.value_alignments)
    if proj.stance is None:
        return [
            (
                AttentionReason.UNKNOWN_VALUES,
                "Your profile can't project a stance here yet — "
                "it needs your own view.",
            )
        ]
    pos = [c for c in proj.contributions if c.contribution >= CONFLICT_MIN_CONTRIBUTION]
    neg = [
        c for c in proj.contributions if c.contribution <= -CONFLICT_MIN_CONTRIBUTION
    ]
    if pos and neg:
        a = max(pos, key=lambda c: c.contribution).axis
        b = min(neg, key=lambda c: c.contribution).axis
        return [
            (
                AttentionReason.VALUE_CONFLICT,
                f"Your values conflict here: {a} pulls toward support, {b} against.",
            )
        ]
    return []


def _vote_reasons(
    topic: Topic,
    interests: Interests,
    ledger: StandingVoteLedger | None,
    voter_id: str | None,
) -> list[tuple[AttentionReason, str]]:
    out: list[tuple[AttentionReason, str]] = []
    if ledger is None or voter_id is None:
        if matches_interests(topic, interests):
            out.append(
                (
                    AttentionReason.NOT_YET_HEARD,
                    "This concerns you and you haven't weighed in.",
                )
            )
        return out

    mine = ledger.current(topic.id, voter_id)
    if mine is None:
        if topic.allow_votes and matches_interests(topic, interests):
            out.append(
                (
                    AttentionReason.NOT_YET_HEARD,
                    "This concerns you and you haven't weighed in.",
                )
            )
        return out

    # Peers moving: people who stood where you stand have moved elsewhere.
    moved = sum(m.count for m in ledger.migrations(topic.id) if m.from_choice == mine)
    if moved >= PEER_MOVE_MIN:
        out.append(
            (
                AttentionReason.PEERS_MOVING,
                f"{moved} people who voted {mine!r} have since moved — "
                "see what changed their minds.",
            )
        )

    # Stale vote: the share behind your option has shifted since you chose.
    my_events = ledger.history(topic.id, voter_id)
    since = my_events[-1].at
    then = ledger.tally(topic.id, at=since)
    now = ledger.tally(topic.id)
    if abs(now.share(mine) - then.share(mine)) >= STALE_SHIFT:
        out.append(
            (
                AttentionReason.STALE_VOTE,
                f"Support for {mine!r} moved from {then.share(mine):.0%} to "
                f"{now.share(mine):.0%} since you chose.",
            )
        )
    return out


def _milestone_reasons(
    topic: Topic, ledger: StandingVoteLedger | None, now: datetime
) -> list[tuple[AttentionReason, str]]:
    count = ledger.participant_count(topic.id) if ledger else 0
    status = compute_status(topic, count, now)
    out: list[tuple[AttentionReason, str]] = []
    if status.is_closing_soon:
        out.append((AttentionReason.CLOSING_SOON, "The decision window is closing."))
    if (
        status.quorum_target is not None
        and not status.quorum_reached
        and (status.quorum_fraction or 0.0) >= QUORUM_NEAR_FRACTION
    ):
        out.append(
            (
                AttentionReason.QUORUM_NEAR,
                f"{count}/{status.quorum_target} to quorum — "
                "a few more voices make this legitimate.",
            )
        )
    return out


def what_needs_attention(
    topics: list[Topic],
    interests: Interests,
    profile: PreferenceProfile | None = None,
    ledger: StandingVoteLedger | None = None,
    voter_id: str | None = None,
    now: datetime | None = None,
) -> list[AttentionItem]:
    """Answer *what needs attention?* for one citizen over the open issues.

    Only issues with at least one named reason are returned — silence is a
    valid answer. Ordered by the summed reason weights, then by relevance to
    the citizen's declared interests, then newest first.
    """
    now = _aware(now or datetime.now(tz=UTC))
    items: list[AttentionItem] = []
    for topic in topics:
        if compute_status(topic, 0, now).is_closed:
            continue
        found = (
            _value_reasons(topic, profile)
            + _vote_reasons(topic, interests, ledger, voter_id)
            + _milestone_reasons(topic, ledger, now)
        )
        if not found:
            continue
        items.append(
            AttentionItem(
                topic=topic,
                reasons=[r for r, _ in found],
                explanations=[why for _, why in found],
            )
        )

    def key(item: AttentionItem) -> tuple[float, float, float]:
        return (
            item.score,
            relevance_score(item.topic, interests),
            _aware(item.topic.created_at).timestamp(),
        )

    return sorted(items, key=key, reverse=True)
