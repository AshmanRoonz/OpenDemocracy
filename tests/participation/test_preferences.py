"""Tests for continuous preference elicitation and human-confirmed projection."""

from __future__ import annotations

import pytest

from opendemocracy.participation.preferences import (
    MIN_PROJECTION_CONFIDENCE,
    PreferenceProfile,
    StanceStatus,
)

# --------------------------------------------------------------------------- #
# Learning                                                                    #
# --------------------------------------------------------------------------- #


def test_signals_accumulate_as_running_mean() -> None:
    p = PreferenceProfile()
    p.record_signal("housing", 1.0, source="survey")
    p.record_signal("housing", 0.0, source="survey")
    b = p.belief("housing")
    assert b is not None
    assert b.position == pytest.approx(0.5)
    assert b.observations == 2


def test_confidence_grows_with_observations_but_never_reaches_one() -> None:
    p = PreferenceProfile()
    for _ in range(3):
        p.record_signal("climate", 1.0, source="survey")
    b = p.belief("climate")
    assert b is not None
    assert 0.4 < b.confidence < 1.0
    prev = b.confidence
    p.record_signal("climate", 1.0, source="survey")
    assert b.confidence > prev


def test_signals_are_clamped_and_axes_normalized() -> None:
    p = PreferenceProfile()
    p.record_signal("  Housing ", 5.0, source="survey")
    b = p.belief("housing")
    assert b is not None
    assert b.position == 1.0


def test_every_learning_event_is_audited() -> None:
    p = PreferenceProfile()
    p.record_signal("tax", -1.0, source="survey")
    p.record_signal("tax", 1.0, source="confirmed-vote")
    assert [e.source for e in p.history] == ["survey", "confirmed-vote"]
    assert p.history[-1].position_after == pytest.approx(0.0)


def test_erase_forgets_everything() -> None:
    p = PreferenceProfile()
    p.record_signal("tax", 1.0, source="survey")
    p.erase()
    assert p.belief("tax") is None
    assert p.history == []


# --------------------------------------------------------------------------- #
# Projection                                                                  #
# --------------------------------------------------------------------------- #


def _confident_profile() -> PreferenceProfile:
    p = PreferenceProfile()
    for _ in range(5):
        p.record_signal("public-services", 1.0, source="survey")
        p.record_signal("taxes-low", -0.5, source="survey")
    return p


def test_projection_points_where_values_point() -> None:
    p = _confident_profile()
    # Topic: expand public transit — aligns with public-services, against low taxes.
    proj = p.project("t1", {"public-services": 1.0, "taxes-low": 1.0})
    assert proj.stance is not None
    assert proj.stance > 0
    assert proj.leaning == "support"


def test_unknown_axes_cause_abstention_not_a_guess() -> None:
    p = PreferenceProfile()
    proj = p.project("t1", {"defense": 1.0})
    assert proj.stance is None
    assert proj.leaning == "abstain"
    assert proj.confidence == 0.0


def test_low_confidence_abstains() -> None:
    p = PreferenceProfile()
    p.record_signal("defense", 1.0, source="survey")  # one observation only
    proj = p.project("t1", {"defense": 1.0})
    # With the default constants, a single observation is below threshold.
    assert proj.confidence < MIN_PROJECTION_CONFIDENCE
    assert proj.stance is None


def test_explanation_covers_every_contributing_axis() -> None:
    p = _confident_profile()
    proj = p.project("t1", {"public-services": 1.0, "taxes-low": -0.5})
    lines = proj.explain()
    assert len(lines) == 2
    assert any("public-services" in line for line in lines)
    assert all("→" in line for line in lines)


def test_stance_is_bounded() -> None:
    p = _confident_profile()
    proj = p.project("t1", {"public-services": 1.0})
    assert proj.stance is not None
    assert -1.0 <= proj.stance <= 1.0


# --------------------------------------------------------------------------- #
# Human authority                                                             #
# --------------------------------------------------------------------------- #


def test_projection_starts_provisional() -> None:
    p = _confident_profile()
    proj = p.project("t1", {"public-services": 1.0})
    assert proj.status is StanceStatus.PROVISIONAL


def test_confirm_records_suggestion_and_final_together() -> None:
    p = _confident_profile()
    proj = p.project("t1", {"public-services": 1.0})
    d = p.decide(proj)
    assert d.status is StanceStatus.CONFIRMED
    assert d.final_stance == proj.stance
    assert d.suggested_stance == proj.stance
    assert p.decisions == [d]


def test_override_wins_and_feeds_back_as_learning() -> None:
    p = _confident_profile()
    proj = p.project("t1", {"public-services": 1.0})
    events_before = len(p.history)
    d = p.decide(proj, final_stance=-1.0)
    assert d.status is StanceStatus.OVERRIDDEN
    assert d.final_stance == -1.0
    assert d.suggested_stance == proj.stance
    # The correction became new signal on the contributing axis.
    assert len(p.history) > events_before
    assert p.history[-1].source == "correction"


def test_cannot_confirm_an_abstention() -> None:
    p = PreferenceProfile()
    proj = p.project("t1", {"defense": 1.0})
    with pytest.raises(ValueError):
        p.decide(proj)


def test_override_of_abstention_is_allowed() -> None:
    p = PreferenceProfile()
    proj = p.project("t1", {"defense": 1.0})
    d = p.decide(proj, final_stance=0.5)
    assert d.status is StanceStatus.OVERRIDDEN
    assert d.final_stance == 0.5
    assert d.suggested_stance is None
