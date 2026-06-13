"""Tests for decision-milestone status (quorum + closing window)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from opendemocracy.models import Topic
from opendemocracy.participation.status import (
    TopicState,
    compute_status,
    is_closed,
    quorum_fraction,
)

NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)


def _topic(**kwargs: object) -> Topic:
    defaults: dict[str, object] = {"title": "T", "created_at": NOW}
    defaults.update(kwargs)
    return Topic(**defaults)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Closure                                                                      #
# --------------------------------------------------------------------------- #


def test_open_ended_topic_is_never_closed() -> None:
    assert not is_closed(_topic(), NOW)


def test_topic_closes_after_deadline() -> None:
    assert is_closed(_topic(closes_at=NOW - timedelta(hours=1)), NOW)
    assert not is_closed(_topic(closes_at=NOW + timedelta(hours=1)), NOW)


# --------------------------------------------------------------------------- #
# Quorum fraction                                                              #
# --------------------------------------------------------------------------- #


def test_quorum_fraction_none_without_target() -> None:
    assert quorum_fraction(_topic(), 5) is None
    assert quorum_fraction(_topic(quorum=0), 5) is None


def test_quorum_fraction_progresses_and_caps() -> None:
    topic = _topic(quorum=10)
    assert quorum_fraction(topic, 0) == 0.0
    assert quorum_fraction(topic, 5) == 0.5
    assert quorum_fraction(topic, 25) == 1.0  # capped at 1.0


# --------------------------------------------------------------------------- #
# Status states                                                                #
# --------------------------------------------------------------------------- #


def test_open_topic_state() -> None:
    s = compute_status(_topic(), participant_count=3, now=NOW)
    assert s.state is TopicState.OPEN
    assert not s.is_closed and not s.is_closing_soon
    assert s.headline == "3 voices"


def test_singular_voice_headline() -> None:
    s = compute_status(_topic(), participant_count=1, now=NOW)
    assert s.headline == "1 voice"


def test_closing_soon_state() -> None:
    topic = _topic(closes_at=NOW + timedelta(hours=2))
    s = compute_status(topic, participant_count=4, now=NOW)
    assert s.state is TopicState.CLOSING_SOON
    assert s.is_closing_soon and not s.is_closed
    assert s.headline == "Closing soon"


def test_closed_state() -> None:
    topic = _topic(closes_at=NOW - timedelta(hours=1))
    s = compute_status(topic, participant_count=4, now=NOW)
    assert s.state is TopicState.CLOSED
    assert s.is_closed and not s.is_closing_soon
    assert s.headline == "Closed"


# --------------------------------------------------------------------------- #
# Quorum milestones                                                            #
# --------------------------------------------------------------------------- #


def test_progress_headline_before_quorum() -> None:
    s = compute_status(_topic(quorum=50), participant_count=12, now=NOW)
    assert not s.quorum_reached
    assert s.quorum_fraction == 12 / 50
    assert s.headline == "12/50 to quorum"


def test_quorum_reached_headline() -> None:
    s = compute_status(_topic(quorum=10), participant_count=10, now=NOW)
    assert s.quorum_reached
    assert s.headline == "Quorum reached"


def test_quorum_reached_and_closing() -> None:
    topic = _topic(quorum=10, closes_at=NOW + timedelta(hours=1))
    s = compute_status(topic, participant_count=15, now=NOW)
    assert s.quorum_reached and s.is_closing_soon
    assert s.headline == "Quorum reached — closing soon"


def test_progress_and_closing_headline() -> None:
    topic = _topic(quorum=50, closes_at=NOW + timedelta(hours=3))
    s = compute_status(topic, participant_count=20, now=NOW)
    assert s.headline == "20/50 to quorum — closing soon"


def test_closed_quorum_met_vs_unmet() -> None:
    met = _topic(quorum=10, closes_at=NOW - timedelta(hours=1))
    unmet = _topic(quorum=10, closes_at=NOW - timedelta(hours=1))
    assert compute_status(met, 12, NOW).headline == "Closed — quorum reached"
    assert compute_status(unmet, 3, NOW).headline == "Closed — quorum not met"
