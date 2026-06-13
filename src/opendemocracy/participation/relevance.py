"""Relevance, urgency, and ranking for the *frequent democracy* feed.

Representative democracy asks for your voice once every few years. The point of
OpenDemocracy is the opposite: surface each issue to each person *when it
matters to them*. That requires three signals, computed here as small, pure,
testable functions so the Python backend and the in-browser P2P app stay in
agreement about how issues are ordered:

* **Relevance** — does this issue match the citizen's declared interests
  (topic tags) and region? A voice should be *invited in* when an issue
  concerns it.
* **Urgency** — is the issue closing soon? Deadlines are how "frequently" turns
  into "right now".
* **Activity** — are other people engaging? Live deliberation pulls in more
  voices.

These are deliberately simple, transparent, and auditable — no hidden ranking
model deciding what you see. The weights are constants you can read and change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from opendemocracy.models import Topic

# How soon (in hours) a deadline has to be before an issue counts as "closing
# soon" / urgent. Anything inside this window ramps from 0 -> 1 as it nears.
URGENCY_WINDOW_HOURS = 72.0

# Relative weights for the composite ranking score. Relevance dominates: the
# whole premise is that the issues *you* care about reach *you* first.
WEIGHT_RELEVANCE = 3.0
WEIGHT_URGENCY = 2.0
WEIGHT_ACTIVITY = 1.0


@dataclass
class Interests:
    """A citizen's self-declared interests, stored locally and never shared.

    Both fields are optional. An empty ``Interests`` matches nothing in
    particular, so the feed falls back to urgency + activity ordering.
    """

    tags: list[str] = field(default_factory=list)
    region: str | None = None

    def normalized_tags(self) -> set[str]:
        return {t.strip().lower() for t in self.tags if t.strip()}


def _aware(dt: datetime) -> datetime:
    """Coerce a possibly-naive datetime to UTC for safe comparison."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _region_segments(region: str) -> list[str]:
    """Split a region path into normalized segments.

    Regions are hierarchical paths separated by ``/`` — e.g. ``"EU/North"`` or
    ``"US/West/CA"``. A flat name like ``"EU-North"`` is simply a one-segment
    path, so existing data keeps working unchanged.
    """
    return [seg.strip().lower() for seg in region.split("/") if seg.strip()]


def region_matches(interest_region: str | None, topic_region: str | None) -> bool:
    """True when a citizen's region and a topic's region overlap hierarchically.

    Real geography nests: a person in ``"EU/North"`` is concerned by an issue
    scoped to ``"EU"`` (their area sits inside it), and equally by one scoped to
    ``"EU/North/Sweden"`` (it sits inside their area). So a match holds when one
    path is a prefix of the other. Both sides must be concrete — a global topic
    (no region) is handled separately as a universal baseline, not here.
    """
    if not interest_region or not topic_region:
        return False
    a = _region_segments(interest_region)
    b = _region_segments(topic_region)
    if not a or not b:
        return False
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def relevance_score(topic: Topic, interests: Interests) -> float:
    """Return a 0-1 score for how well ``topic`` matches ``interests``.

    Region match and tag overlap each contribute. A topic with no tags and no
    region is treated as universally mildly relevant (it concerns everyone),
    scoring a small baseline rather than zero.
    """
    want_tags = interests.normalized_tags()
    topic_tags = {t.strip().lower() for t in topic.tags if t.strip()}

    # Universal topics (no scope) concern everyone — give them a gentle floor.
    if not topic_tags and not topic.region:
        return 0.25

    score = 0.0

    if want_tags and topic_tags:
        overlap = want_tags & topic_tags
        if overlap:
            # Fraction of the topic's tags the citizen cares about.
            score += 0.7 * (len(overlap) / len(topic_tags))

    if interests.region and topic.region:
        if region_matches(interests.region, topic.region):
            score += 0.3
    elif not topic.region:
        # Topic is global in scope — partially relevant to everyone.
        score += 0.1

    return min(score, 1.0)


def matches_interests(topic: Topic, interests: Interests) -> bool:
    """True when a topic is relevant enough to actively alert the citizen.

    This is the trigger for "a new issue matters to you" notifications, so it is
    intentionally stricter than a non-zero :func:`relevance_score`: it requires
    a concrete tag or region match, not just the universal baseline.
    """
    want_tags = interests.normalized_tags()
    topic_tags = {t.strip().lower() for t in topic.tags if t.strip()}
    if want_tags and (want_tags & topic_tags):
        return True
    return region_matches(interests.region, topic.region)


def urgency_score(topic: Topic, now: datetime | None = None) -> float:
    """Return a 0-1 urgency score driven by how close the deadline is.

    Open-ended topics (no ``closes_at``) score 0. A topic ramps from 0 at the
    edge of the urgency window up to 1 at the moment it closes. Already-closed
    topics score 0 — they are no longer actionable.
    """
    if topic.closes_at is None:
        return 0.0
    now = now or datetime.now(tz=UTC)
    closes = _aware(topic.closes_at)
    now = _aware(now)
    remaining_hours = (closes - now).total_seconds() / 3600.0
    if remaining_hours <= 0:
        return 0.0
    if remaining_hours >= URGENCY_WINDOW_HOURS:
        return 0.0
    return 1.0 - (remaining_hours / URGENCY_WINDOW_HOURS)


def activity_score(submission_count: int) -> float:
    """Map a raw submission count to a saturating 0-1 activity score.

    Uses diminishing returns so a runaway-popular topic can't completely bury
    quieter issues — every voice still needs a chance to be seen.
    """
    if submission_count <= 0:
        return 0.0
    # Saturates: 1 -> 0.1, 10 -> ~0.5, 50 -> ~0.83, 100 -> ~0.91.
    return submission_count / (submission_count + 10.0)


def composite_score(
    topic: Topic,
    interests: Interests,
    submission_count: int = 0,
    now: datetime | None = None,
) -> float:
    """Weighted blend of relevance, urgency, and activity for feed ordering."""
    return (
        WEIGHT_RELEVANCE * relevance_score(topic, interests)
        + WEIGHT_URGENCY * urgency_score(topic, now)
        + WEIGHT_ACTIVITY * activity_score(submission_count)
    )


def rank_topics(
    topics: list[Topic],
    interests: Interests,
    submission_counts: dict[str, int] | None = None,
    now: datetime | None = None,
) -> list[Topic]:
    """Order topics for the *live issues* feed, most pressing first.

    Ties (and the fully-default case where every score is equal) fall back to
    most-recently-created, so a fresh issue is never stranded at the bottom.
    """
    counts = submission_counts or {}
    now = now or datetime.now(tz=UTC)

    def key(t: Topic) -> tuple[float, float]:
        score = composite_score(t, interests, counts.get(t.id, 0), now)
        return (score, _aware(t.created_at).timestamp())

    return sorted(topics, key=key, reverse=True)
