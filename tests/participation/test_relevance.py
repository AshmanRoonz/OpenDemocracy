"""Tests for the frequent-democracy relevance / urgency / ranking logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from opendemocracy.models import Topic
from opendemocracy.participation.relevance import (
    URGENCY_WINDOW_HOURS,
    Interests,
    activity_score,
    composite_score,
    matches_interests,
    rank_topics,
    relevance_score,
    urgency_score,
)
from opendemocracy.participation.topics import TopicStore

NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)


def _topic(**kwargs: object) -> Topic:
    defaults: dict[str, object] = {"title": "T", "created_at": NOW}
    defaults.update(kwargs)
    return Topic(**defaults)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Relevance                                                                    #
# --------------------------------------------------------------------------- #


def test_tag_overlap_scores_higher_than_no_overlap() -> None:
    interests = Interests(tags=["housing"])
    match = _topic(tags=["housing", "tax"])
    miss = _topic(tags=["climate"])
    assert relevance_score(match, interests) > relevance_score(miss, interests)


def test_tag_matching_is_case_insensitive() -> None:
    interests = Interests(tags=["Housing"])
    topic = _topic(tags=["HOUSING"])
    assert relevance_score(topic, interests) > 0
    assert matches_interests(topic, interests)


def test_region_match_contributes() -> None:
    interests = Interests(region="EU-North")
    same = _topic(region="EU-North")
    other = _topic(region="US-West")
    assert relevance_score(same, interests) > relevance_score(other, interests)
    assert matches_interests(same, interests)
    assert not matches_interests(other, interests)


def test_region_hierarchy_matches_broader_and_narrower_scopes() -> None:
    from opendemocracy.participation.relevance import region_matches

    # Citizen in EU/North is concerned by an EU-wide issue (broader)…
    assert region_matches("EU/North", "EU")
    # …and by a Sweden-specific one within their area (narrower).
    assert region_matches("EU/North", "EU/North/Sweden")
    # Sibling regions do not match.
    assert not region_matches("EU/North", "EU/South")
    assert not region_matches("EU/North", "US/West")
    # A blank on either side is not a concrete match (handled as global).
    assert not region_matches("", "EU")
    assert not region_matches("EU", None)


def test_hierarchical_region_drives_relevance_and_alerts() -> None:
    interests = Interests(region="EU/North")
    eu_wide = _topic(region="EU")
    assert relevance_score(eu_wide, interests) > 0.25
    assert matches_interests(eu_wide, interests)


def test_universal_topic_has_baseline_relevance() -> None:
    # No tags, no region: concerns everyone, so it gets a non-zero floor.
    topic = _topic()
    assert relevance_score(topic, Interests()) == 0.25


def test_matches_interests_requires_concrete_match_not_baseline() -> None:
    # A universal topic scores > 0 for relevance but must NOT trigger an alert.
    topic = _topic()
    assert relevance_score(topic, Interests(tags=["housing"])) > 0
    assert not matches_interests(topic, Interests(tags=["housing"]))


def test_relevance_score_is_bounded() -> None:
    interests = Interests(tags=["a", "b", "c"], region="EU-North")
    topic = _topic(tags=["a", "b", "c"], region="EU-North")
    assert 0.0 <= relevance_score(topic, interests) <= 1.0


# --------------------------------------------------------------------------- #
# Urgency                                                                      #
# --------------------------------------------------------------------------- #


def test_open_ended_topic_has_zero_urgency() -> None:
    assert urgency_score(_topic(closes_at=None), NOW) == 0.0


def test_urgency_rises_as_deadline_approaches() -> None:
    soon = _topic(closes_at=NOW + timedelta(hours=6))
    later = _topic(closes_at=NOW + timedelta(hours=48))
    assert urgency_score(soon, NOW) > urgency_score(later, NOW) > 0.0


def test_topic_outside_window_is_not_urgent() -> None:
    far = _topic(closes_at=NOW + timedelta(hours=URGENCY_WINDOW_HOURS + 10))
    assert urgency_score(far, NOW) == 0.0


def test_closed_topic_has_zero_urgency() -> None:
    past = _topic(closes_at=NOW - timedelta(hours=1))
    assert urgency_score(past, NOW) == 0.0


def test_urgency_handles_naive_datetime() -> None:
    naive_now = datetime(2026, 6, 13, 12, 0)  # noqa: DTZ001 - intentional
    topic = _topic(closes_at=datetime(2026, 6, 13, 15, 0))  # noqa: DTZ001
    assert urgency_score(topic, naive_now) > 0.0


# --------------------------------------------------------------------------- #
# Activity                                                                     #
# --------------------------------------------------------------------------- #


def test_activity_score_saturates_and_is_monotonic() -> None:
    assert activity_score(0) == 0.0
    assert activity_score(1) < activity_score(10) < activity_score(1000)
    assert activity_score(10_000) < 1.0


# --------------------------------------------------------------------------- #
# Ranking                                                                      #
# --------------------------------------------------------------------------- #


def test_relevant_topic_outranks_irrelevant_one() -> None:
    interests = Interests(tags=["housing"])
    relevant = _topic(id="r", tags=["housing"])
    irrelevant = _topic(id="i", tags=["sports"])
    ranked = rank_topics([irrelevant, relevant], interests, now=NOW)
    assert ranked[0].id == "r"


def test_urgent_topic_outranks_quiet_open_ended_one() -> None:
    interests = Interests()
    urgent = _topic(id="u", closes_at=NOW + timedelta(hours=2))
    quiet = _topic(id="q")
    ranked = rank_topics([quiet, urgent], interests, now=NOW)
    assert ranked[0].id == "u"


def test_ties_fall_back_to_most_recent() -> None:
    interests = Interests()
    older = _topic(id="old", created_at=NOW - timedelta(days=2))
    newer = _topic(id="new", created_at=NOW)
    ranked = rank_topics([older, newer], interests, now=NOW)
    assert [t.id for t in ranked] == ["new", "old"]


def test_activity_breaks_tie_between_equal_relevance() -> None:
    interests = Interests()
    busy = _topic(id="busy", created_at=NOW)
    quiet = _topic(id="quiet", created_at=NOW)
    ranked = rank_topics(
        [quiet, busy], interests, submission_counts={"busy": 25}, now=NOW
    )
    assert ranked[0].id == "busy"


def test_composite_score_blends_all_signals() -> None:
    interests = Interests(tags=["housing"], region="EU-North")
    topic = _topic(
        tags=["housing"],
        region="EU-North",
        closes_at=NOW + timedelta(hours=1),
    )
    score = composite_score(topic, interests, submission_count=20, now=NOW)
    # Relevance (~1.0 * 3) + urgency (~1.0 * 2) + activity (>0) should be high.
    assert score > 4.0


# --------------------------------------------------------------------------- #
# TopicStore integration                                                       #
# --------------------------------------------------------------------------- #


def test_topic_store_list_live_ranks_relevant_first() -> None:
    store = TopicStore()
    store.create(_topic(id="sports", tags=["sports"]))
    store.create(_topic(id="housing", tags=["housing"]))
    live = store.list_live(interests=Interests(tags=["housing"]))
    assert live[0].id == "housing"


def test_topic_store_list_live_excludes_closed() -> None:
    store = TopicStore()
    store.create(_topic(id="closed", closes_at=NOW - timedelta(days=1)))
    store.create(_topic(id="open"))
    live = store.list_live()
    assert [t.id for t in live] == ["open"]
