"""Tests for Findings — citable, reproducible, tamper-evident snapshots."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import (
    BiometricFactor,
    EnrollmentRecord,
    Topic,
    VerificationResult,
)
from opendemocracy.participation.findings import FindingStore, LadderRung, ladder_rung
from opendemocracy.participation.propositions import PropositionRegistry
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _world(n: int = 12):  # type: ignore[no-untyped-def]
    reg = IdentityRegistry()
    ids = []
    for i in range(n):
        vid = f"v{i}"
        reg.register(
            EnrollmentRecord(
                anonymous_id=vid,
                public_key=f"pk{i}",
                factors_enrolled=[BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
            )
        )
        ids.append(vid)
    topics = TopicStore()
    ledger = StandingVoteLedger(topics, reg)
    props = PropositionRegistry(topics, ledger)
    return topics, ledger, props, FindingStore(topics, ledger, props), ids


def _v(vid: str) -> VerificationResult:
    return VerificationResult(verified=True, anonymous_id=vid)


def _topic(**kw: object) -> Topic:
    d: dict[str, object] = {
        "id": "t1",
        "title": "Rent cap",
        "vote_options": ["Yes", "No"],
    }
    d.update(kw)
    return Topic(**d)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Ladder                                                                      #
# --------------------------------------------------------------------------- #


def test_ladder_rungs() -> None:
    assert ladder_rung(_topic(), 100, NOW) is LadderRung.SIGNAL  # no quorum set
    assert ladder_rung(_topic(quorum=5), 4, NOW) is LadderRung.SIGNAL
    assert ladder_rung(_topic(quorum=5), 5, NOW) is LadderRung.QUORUM
    assert ladder_rung(_topic(quorum=5, region="EU/North"), 5, NOW) is LadderRung.SCOPED
    assert ladder_rung(_topic(region="EU/North"), 50, NOW) is LadderRung.SIGNAL


# --------------------------------------------------------------------------- #
# Taking                                                                      #
# --------------------------------------------------------------------------- #


def test_finding_freezes_tally_with_denominator() -> None:
    topics, ledger, _, findings, ids = _world()
    topics.create(_topic(quorum=3))
    ledger.cast(_v(ids[0]), "t1", "Yes")
    ledger.cast(_v(ids[1]), "t1", "Yes")
    ledger.cast(_v(ids[2]), "t1", "No")
    ledger.cast(_v(ids[2]), "t1", "Yes", reason="the cost report")
    ledger.cast(_v(ids[3]), "t1", "No")
    ledger.withdraw(_v(ids[3]), "t1")
    f = findings.take("t1", note="For the council meeting", taken_by=ids[0])
    assert f.rung is LadderRung.QUORUM
    assert f.citable
    assert f.tally["counts"] == {"Yes": 3, "No": 0}
    assert f.tally["standing"] == 3
    assert f.tally["ever_participated"] == 4
    assert f.tally["withdrawn"] == 1
    assert f.tally["changes"] == 1
    assert f.migrations[0] == {
        "from": "No",
        "to": "Yes",
        "count": 1,
        "reasons": ["the cost report"],
    }
    assert f.ledger_events == 6
    assert f.note == "For the council meeting"
    assert len(f.content_hash) == 64
    assert findings.get(f.finding_id) is f
    assert findings.list_for("t1") == [f]


def test_below_quorum_is_exportable_but_not_citable() -> None:
    topics, ledger, _, findings, ids = _world()
    topics.create(_topic(quorum=10))
    ledger.cast(_v(ids[0]), "t1", "Yes")
    f = findings.take("t1")
    assert f.rung is LadderRung.SIGNAL
    assert not f.citable
    assert "signal only" in f.to_markdown()


def test_missing_topic_is_rejected() -> None:
    _, _, _, findings, _ = _world()
    with pytest.raises(ValueError):
        findings.take("ghost")


# --------------------------------------------------------------------------- #
# Reproducible and tamper-evident                                             #
# --------------------------------------------------------------------------- #


def test_finding_is_reproducible_after_the_ledger_moves_on() -> None:
    topics, ledger, _, findings, ids = _world()
    topics.create(_topic())
    ledger.cast(_v(ids[0]), "t1", "Yes")
    f = findings.take("t1")
    # The world keeps voting; the finding must still re-derive exactly.
    ledger.cast(_v(ids[1]), "t1", "No")
    ledger.cast(_v(ids[0]), "t1", "No")
    assert findings.verify(f)
    assert findings.reproduce(f)
    assert findings.take("t1").tally["counts"] == {"Yes": 0, "No": 2}


def test_same_moment_same_hash() -> None:
    topics, ledger, _, findings, ids = _world()
    topics.create(_topic())
    ledger.cast(_v(ids[0]), "t1", "Yes")
    a = findings.take("t1", at=NOW + timedelta(days=1))
    b = findings.take("t1", at=NOW + timedelta(days=1), note="different label")
    assert a.finding_id != b.finding_id
    assert a.content_hash == b.content_hash  # labels aren't evidence


def test_tampering_is_detected() -> None:
    topics, ledger, _, findings, ids = _world()
    topics.create(_topic())
    ledger.cast(_v(ids[0]), "t1", "Yes")
    f = findings.take("t1")
    f.tally["counts"]["Yes"] = 500
    assert not findings.verify(f)
    assert not findings.reproduce(f)


# --------------------------------------------------------------------------- #
# Propositions inside a finding                                               #
# --------------------------------------------------------------------------- #


def test_finding_records_wordings_and_divergence() -> None:
    topics, ledger, props, findings, ids = _world()
    topics.create(_topic(id="a", title="Ban cars"))
    topics.create(_topic(id="b", title="Car-free centre"))
    props.merge(["a", "b"], reason="same question")
    for vid in ids[:5]:
        ledger.cast(_v(vid), "a", "Yes")
    for vid in ids[5:8]:
        ledger.cast(_v(vid), "b", "Yes")
    for vid in ids[8:10]:
        ledger.cast(_v(vid), "b", "No")
    f = findings.take("a")
    assert f.proposition is not None
    assert [v["title"] for v in f.proposition["variants"]] == [
        "Ban cars",
        "Car-free centre",
    ]
    assert f.proposition["framing_matters"] is True
    assert f.proposition["divergence"] == pytest.approx(0.4)
    assert f.proposition["combined"]["standing"] == 10
    md = f.to_markdown()
    assert "Wordings of this question" in md
    assert "framing is doing work" in md
    assert findings.reproduce(f)


# --------------------------------------------------------------------------- #
# Export                                                                      #
# --------------------------------------------------------------------------- #


def test_json_round_trips_and_markdown_reads_like_a_record() -> None:
    topics, ledger, _, findings, ids = _world()
    topics.create(_topic(quorum=2, region="EU/North"))
    ledger.cast(_v(ids[0]), "t1", "Yes")
    ledger.cast(_v(ids[1]), "t1", "No")
    ledger.cast(_v(ids[1]), "t1", "Yes", reason="talked to my neighbour")
    f = findings.take("t1", note="Ward 3 budget line")
    data = json.loads(f.to_json())
    assert data["content_hash"] == f.content_hash
    assert data["rung"] == "scoped"
    assert data["citable"] is True
    md = f.to_markdown()
    assert md.startswith("# Finding: Rent cap")
    assert "| Yes | 2 | 100% |" in md
    assert "Scope: EU/North" in md
    assert "2/2 to quorum" in md
    assert 'moved No → Yes — "talked to my neighbour"' in md
    assert f"sha256:{f.content_hash}" in md
    # Never a person: only the method version mentions a "v".
    assert "v0" not in md
    assert "v1" not in md.replace(f"method v{f.method_version}", "")
