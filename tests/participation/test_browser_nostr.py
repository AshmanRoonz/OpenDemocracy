# ruff: noqa: E501
"""The browser's NOSTR MAPPING block: records are Nostr events, verified locally.

docs/index.html maps every Vote record (enrollment, topic, submission,
standing vote) to a signed Nostr event and back. This test extracts that
pure block and runs it under node: builders emit well-formed templates,
`eventToRecord` maps and rejects correctly, and `recordValid` parks records
whose dependencies haven't arrived (relays promise no ordering) while
refusing ones that can never be valid. Skips if node is not installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "index.html"
NODE = shutil.which("node")


def _block() -> str:
    html = PAGE.read_text(encoding="utf-8")
    start = html.index("/* === NOSTR MAPPING START === */")
    end = html.index("/* === NOSTR MAPPING END === */")
    return html[start:end]


HARNESS = r"""
const PK_A = "a".repeat(64), PK_B = "b".repeat(64);
let n = 0;
function signed(tpl, pubkey) { n++; return { ...tpl, id: String(n).padStart(64, "0"), pubkey, sig: "s".repeat(128) }; }

const out = {};
// Builders
const enroll = buildEnrollEvent(["fingerprint", "face"]);
const topicTpl = buildTopicEvent({ title: "Rent cap", description: "d", allow_votes: true,
  vote_options: ["Yes", "No"], tags: ["Housing"], region: "EU/North", closes_at: null, quorum: 3 });
out.enrollKind = enroll.kind; out.enrollTags = enroll.tags;
out.topicTags = topicTpl.tags;
out.voteTpl = buildVoteEvent("t1", "Yes", "  because  ");
out.withdrawTpl = buildVoteEvent("t1", null, null);
out.subTpl = buildSubmissionEvent("t1", "idea", "Try it");

// Mapping
const evEnroll = signed(enroll, PK_A);
const evTopic = signed(topicTpl, PK_A);
const mEnroll = eventToRecord(evEnroll), mTopic = eventToRecord(evTopic);
out.enrollMapped = mEnroll; out.topicMapped = mTopic;
const evVote = signed(buildVoteEvent(evTopic.id, "Yes", "x"), PK_A);
const mVote = eventToRecord(evVote);
out.voteMapped = mVote;
out.subMapped = eventToRecord(signed(buildSubmissionEvent(evTopic.id, "opinion", "hi"), PK_A));

// Rejections at the shape level
out.rejectWrongApp = eventToRecord(signed({ ...enroll, tags: [["t", "other"]] }, PK_A));
out.rejectKind = eventToRecord(signed({ ...enroll, kind: 1 }, PK_A));
out.rejectBadJson = eventToRecord(signed({ ...enroll, content: "{" }, PK_A));
out.rejectOneFactor = eventToRecord(signed({ ...enroll, content: JSON.stringify({ factors: ["face"] }) }, PK_A));
out.rejectNoTopicTag = eventToRecord(signed({ ...buildVoteEvent("t", "Yes"), tags: [["t", APP_TAG]] }, PK_A));
out.rejectEmptyTitle = eventToRecord(signed(buildTopicEvent({ title: "  " }), PK_A));
out.rejectBadSubType = eventToRecord(signed({ ...buildSubmissionEvent("t", "vote", "Yes") }, PK_A));

// Validity against held state
const lookups = { enrollments: new Map(), topics: new Map() };
out.beforeEnroll = recordValid(mVote, lookups);
lookups.enrollments.set(PK_A, mEnroll.record);
out.beforeTopic = recordValid(mVote, lookups);
lookups.topics.set(mTopic.id, mTopic.record);
out.afterBoth = recordValid(mVote, lookups);
out.strangerVote = recordValid(eventToRecord(signed(buildVoteEvent(evTopic.id, "Yes"), PK_B)), lookups);
out.badOption = recordValid(eventToRecord(signed(buildVoteEvent(evTopic.id, "Maybe"), PK_A)), lookups);
out.withdrawOk = recordValid(eventToRecord(signed(buildVoteEvent(evTopic.id, null), PK_A)), lookups);
const noVotes = eventToRecord(signed(buildTopicEvent({ title: "Opinion only" }), PK_A));
lookups.topics.set(noVotes.id, noVotes.record);
out.voteOnOpinionOnly = recordValid(eventToRecord(signed(buildVoteEvent(noVotes.id, "Yes"), PK_A)), lookups);
out.defaultRelaysWss = DEFAULT_RELAYS.every(u => u.startsWith("wss://"));
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def result() -> dict:
    if NODE is None:
        pytest.skip("node not installed")
    out = subprocess.run(
        [NODE, "-e", _block() + HARNESS],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(out.stdout)  # type: ignore[no-any-return]


def test_builders_tag_every_event_for_the_app(result: dict) -> None:
    assert result["enrollKind"] == 1401
    assert result["enrollTags"] == [["t", "opendemocracy"]]
    # Topic tags are lower-cased and become relay-indexed hashtags after the app tag.
    assert result["topicTags"] == [["t", "opendemocracy"], ["t", "housing"]]
    assert result["voteTpl"]["tags"] == [["t", "opendemocracy"], ["e", "t1"]]
    assert json.loads(result["voteTpl"]["content"]) == {
        "choice": "Yes",
        "reason": "  because  ",
    }
    assert json.loads(result["withdrawTpl"]["content"]) == {
        "choice": None,
        "reason": None,
    }
    assert json.loads(result["subTpl"]["content"]) == {
        "submission_type": "idea",
        "content": "Try it",
    }


def test_mapping_uses_pubkey_as_anonymous_id_and_event_id_as_record_id(
    result: dict,
) -> None:
    e = result["enrollMapped"]
    assert e["store"] == "enrollments" and e["id"] == "a" * 64
    assert e["record"]["factors"] == ["fingerprint", "face"]
    t = result["topicMapped"]
    assert t["store"] == "topics" and t["id"] == t["record"]["id"]
    assert t["record"]["created_by"] == "a" * 64
    assert t["record"]["allow_votes"] is True and t["record"]["quorum"] == 3
    v = result["voteMapped"]
    assert v["store"] == "votes"
    assert v["record"]["topic_id"] == t["id"]
    assert v["record"]["anonymous_id"] == "a" * 64
    assert v["record"]["choice"] == "Yes" and v["record"]["reason"] == "x"
    assert (
        "previous" not in v["record"] and "kind" not in v["record"]
    )  # derived at replay
    assert result["subMapped"]["record"]["submission_type"] == "opinion"


def test_shape_rejections(result: dict) -> None:
    for key in (
        "rejectWrongApp",
        "rejectKind",
        "rejectBadJson",
        "rejectOneFactor",
        "rejectNoTopicTag",
        "rejectEmptyTitle",
        "rejectBadSubType",
    ):
        assert result[key] is None, key


def test_validity_parks_on_missing_dependencies_and_refuses_the_impossible(
    result: dict,
) -> None:
    assert result["beforeEnroll"] == "enrollment"
    assert result["beforeTopic"] == "topic"
    assert result["afterBoth"] == "ok"
    assert result["strangerVote"] == "enrollment"
    assert result["badOption"] == "invalid"
    assert result["withdrawOk"] == "ok"
    assert result["voteOnOpinionOnly"] == "invalid"
    assert result["defaultRelaysWss"] is True
