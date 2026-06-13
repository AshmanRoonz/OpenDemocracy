"""Decision milestones for the *frequent democracy* feed.

Surfacing an issue at the right moment is only half the job; people also need to
see *where the decision stands* — is it still gathering voices, has it reached
the threshold that makes the outcome legitimate, is the window about to close?
These are the milestones that turn "your voice matters" into "your voice matters
*right now*".

This module derives that status from data the system already replicates: how
many distinct people have participated, and the issue's optional deadline and
quorum target. It is pure and small, mirrored by the in-browser P2P app so every
peer shows the same milestones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from opendemocracy.models import Topic
from opendemocracy.participation.relevance import _aware, urgency_score


class TopicState(Enum):
    """Where an issue sits in its decision lifecycle."""

    OPEN = "open"  # gathering voices, no deadline pressure yet
    CLOSING_SOON = "closing_soon"  # deadline inside the urgency window
    CLOSED = "closed"  # deadline passed; no longer actionable


@dataclass
class TopicStatus:
    """A snapshot of an issue's decision milestones."""

    state: TopicState
    is_closed: bool
    is_closing_soon: bool
    participant_count: int
    quorum_target: int | None
    quorum_reached: bool
    quorum_fraction: float | None  # 0-1, capped; None when no quorum is set
    headline: str  # short human-readable status line


def is_closed(topic: Topic, now: datetime | None = None) -> bool:
    """True when the issue's deadline has passed."""
    if topic.closes_at is None:
        return False
    now = _aware(now or datetime.now(tz=UTC))
    return _aware(topic.closes_at) <= now


def quorum_fraction(topic: Topic, participant_count: int) -> float | None:
    """Progress toward quorum as a 0-1 fraction, or ``None`` if no quorum set."""
    if not topic.quorum or topic.quorum <= 0:
        return None
    return min(participant_count / topic.quorum, 1.0)


def compute_status(
    topic: Topic,
    participant_count: int,
    now: datetime | None = None,
) -> TopicStatus:
    """Derive the decision milestones for one issue.

    ``participant_count`` is the number of *distinct* people who have
    participated (not raw submissions) — quorum is about reach across people,
    not volume from a few.
    """
    now = _aware(now or datetime.now(tz=UTC))
    closed = is_closed(topic, now)
    closing = (not closed) and urgency_score(topic, now) > 0.0

    target = topic.quorum if (topic.quorum and topic.quorum > 0) else None
    reached = target is not None and participant_count >= target
    fraction = quorum_fraction(topic, participant_count)

    if closed:
        state = TopicState.CLOSED
    elif closing:
        state = TopicState.CLOSING_SOON
    else:
        state = TopicState.OPEN

    headline = _headline(state, reached, target, participant_count)

    return TopicStatus(
        state=state,
        is_closed=closed,
        is_closing_soon=closing,
        participant_count=participant_count,
        quorum_target=target,
        quorum_reached=reached,
        quorum_fraction=fraction,
        headline=headline,
    )


def _voices(n: int) -> str:
    return f"{n} voice" if n == 1 else f"{n} voices"


def _headline(
    state: TopicState,
    reached: bool,
    target: int | None,
    count: int,
) -> str:
    if state is TopicState.CLOSED:
        if target is not None:
            return "Closed — quorum reached" if reached else "Closed — quorum not met"
        return "Closed"

    closing = state is TopicState.CLOSING_SOON
    if reached:
        return "Quorum reached — closing soon" if closing else "Quorum reached"
    if target is not None:
        suffix = " — closing soon" if closing else ""
        return f"{count}/{target} to quorum{suffix}"
    return "Closing soon" if closing else _voices(count)
