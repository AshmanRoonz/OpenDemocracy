"""Cross-runtime parity: the browser's VOTE ENGINE block vs the Python modules.

docs/index.html carries a pure-JS mirror of the standing-vote ledger,
attention weights, and Finding payload/hash. This test extracts that block,
runs it under node with a fixed ledger, and checks that tallies, migrations,
the canonical JSON, and the SHA-256 match what Python produces from the same
events. If node is not installed the test is skipped.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import Topic
from opendemocracy.participation.findings import FindingStore
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger, VoteEvent

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "index.html"
NODE = shutil.which("node")

T0 = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
TAKEN_AT = T0 + timedelta(hours=3, milliseconds=250)

# (event id, voter, choice, reason, minutes after T0). Includes a change, a
# withdrawal, a return after withdrawal, a same-timestamp pair (ordered by
# id), and a non-ASCII reason to exercise ensure_ascii.
EVENTS = [
    ("e01", "v0", "Yes", None, 0),
    ("e02", "v1", "Yes", "seems right", 1),
    ("e03", "v2", "No", None, 2),
    ("e04", "v3", "Yes", None, 3),
    ("e05", "v4", "Yes", None, 3),  # same minute as e04 — replay orders by id
    ("e06", "v0", "No", "the cost report", 10),
    ("e07", "v1", "No", "the cost report", 11),
    ("e08", "v3", None, "undecided now — café talk", 12),
    ("e09", "v3", "No", None, 20),
    ("e10", "v5", "Yes", None, 30),
]

TOPIC = Topic(
    id="t-parity",
    title="Car-free centre — “pilot”",
    vote_options=["Yes", "No", "Undecided"],
    quorum=4,
    region="EU/North",
    created_at=T0,
)


def _python_side() -> dict:
    reg = IdentityRegistry()
    topics = TopicStore()
    topics.create(TOPIC)
    ledger = StandingVoteLedger(topics, reg)
    # Feed the ledger directly with fixed timestamps (cast() would stamp now()).
    current: dict[tuple[str, str], str | None] = {}
    for _eid, voter, choice, reason, minutes in EVENTS:
        key = (TOPIC.id, voter)
        ev = VoteEvent(
            topic_id=TOPIC.id,
            anonymous_voter_id=voter,
            previous=current.get(key),
            choice=choice,
            reason=reason,
            at=T0 + timedelta(minutes=minutes),
        )
        ledger._events.append(ev)
        current[key] = choice
        ledger._current[key] = choice
    findings = FindingStore(topics, ledger)
    f = findings.take(TOPIC.id, at=TAKEN_AT)
    tally = ledger.tally(TOPIC.id)
    return {
        "tally": {
            "counts": tally.counts,
            "standing": tally.standing,
            "ever_participated": tally.ever_participated,
            "withdrawn": tally.withdrawn,
            "changes": tally.changes,
        },
        "migrations": [
            {
                "from": m.from_choice,
                "to": m.to_choice,
                "count": m.count,
                "reasons": m.reasons,
            }
            for m in ledger.migrations(TOPIC.id)
        ],
        "timeline": [t.standing for t in ledger.timeline(TOPIC.id)],
        "canonical": json.dumps(f.payload(), sort_keys=True, separators=(",", ":")),
        "hash": f.content_hash,
    }


def _engine_block() -> str:
    html = PAGE.read_text(encoding="utf-8")
    start = html.index("/* === VOTE ENGINE START === */")
    end = html.index("/* === VOTE ENGINE END === */")
    return html[start:end]


HARNESS = r"""
const [topic, events, takenAtMs] = JSON.parse(process.argv[1]);
const tally = ledgerTally(events, topic);
const status = {
  closed: false, closing: false,
  target: topic.quorum, count: tally.standing,
  reached: tally.standing >= topic.quorum,
  fraction: Math.min(tally.standing / topic.quorum, 1),
};
const payload = findingPayload(events, topic, takenAtMs, status);
const canonical = canonicalJSON(payload);
sha256Hex(canonical).then(hash => {
  console.log(JSON.stringify({
    tally: {
      counts: Object.fromEntries(tally.counts),
      standing: tally.standing, ever_participated: tally.ever_participated,
      withdrawn: tally.withdrawn, changes: tally.changes,
    },
    migrations: ledgerMigrations(events, topic.id),
    timeline: ledgerTimeline(events, topic).map(t => t.standing),
    canonical, hash,
  }));
});
"""


def _js_side() -> dict:
    events = [
        {
            "id": eid,
            "topic_id": TOPIC.id,
            "anonymous_id": voter,
            "choice": choice,
            "reason": reason,
            "at": (T0 + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z"),
        }
        for eid, voter, choice, reason, minutes in EVENTS
    ]
    # Shuffle arrival order: a G-Set makes no promise about it.
    events = events[::-1]
    topic = {
        "id": TOPIC.id,
        "title": TOPIC.title,
        "vote_options": TOPIC.vote_options,
        "quorum": TOPIC.quorum,
        "region": TOPIC.region,
        "allow_votes": True,
    }
    script = _engine_block() + HARNESS
    arg = json.dumps([topic, events, int(TAKEN_AT.timestamp() * 1000)])
    out = subprocess.run(
        [NODE, "-e", script, arg],  # type: ignore[list-item]
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(out.stdout)  # type: ignore[no-any-return]


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_browser_engine_matches_python() -> None:
    py = _python_side()
    js = _js_side()
    assert js["tally"] == py["tally"]
    assert js["migrations"] == py["migrations"]
    assert js["timeline"] == py["timeline"]
    assert js["canonical"] == py["canonical"]
    assert js["hash"] == py["hash"]


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_browser_engine_has_no_grouping() -> None:
    block = _engine_block().lower()
    for word in ("kmeans", "cluster", "pca", "segment"):
        assert word not in block
