"""Findings — the citable, reproducible snapshot at the top of the ladder.

A voice that is counted and ignored is a poll. A **Finding** is what makes
Vote's signal undeniable: a frozen, self-describing record of where an issue
stood at one moment — the tally with its denominator, who reached quorum,
what scope it was asked in, how the wordings disagreed, what moved people —
plus everything needed to check it.

Two properties do the work:

* **Reproducible.** Every number in a finding is a pure replay of the ledger
  up to ``taken_at``. :meth:`FindingStore.reproduce` re-derives the whole
  snapshot from the ledger and compares it byte for byte. Anyone with the
  ledger gets the same finding.
* **Tamper-evident.** The finding carries a SHA-256 of its canonical content.
  Change a number and the hash no longer matches; :meth:`FindingStore.verify`
  says so.

A finding is exportable as JSON (for machines) and Markdown (for a council
agenda). It never contains a person: only anonymous counts and the reasons
people chose to give.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from opendemocracy.models import Topic
from opendemocracy.participation.propositions import (
    DIVERGENCE_MIN_STANDING,
    FRAMING_DIVERGENCE_MIN,
    PropositionRegistry,
)
from opendemocracy.participation.relevance import _aware
from opendemocracy.participation.status import compute_status
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger, Tally

# Bump when the method (what a finding contains, how it's hashed) changes,
# so old findings stay verifiable against the method that produced them.
METHOD_VERSION = 1
# How many of the largest migrations a finding records.
MIGRATIONS_KEPT = 5


class LadderRung(StrEnum):
    """How far up the legitimacy ladder an issue had climbed when snapshotted."""

    SIGNAL = "signal"  # votes flowing; raw and exploratory
    QUORUM = "quorum"  # enough distinct verified people
    SCOPED = "scoped"  # quorum reached on an issue tied to a place/community


RUNG_ORDER = [LadderRung.SIGNAL, LadderRung.QUORUM, LadderRung.SCOPED]


def ladder_rung(topic: Topic, participant_count: int, now: datetime) -> LadderRung:
    """Highest rung reached. Quorum is the gate; scope lifts it one more."""
    status = compute_status(topic, participant_count, now)
    if not status.quorum_reached:
        return LadderRung.SIGNAL
    return LadderRung.SCOPED if topic.region else LadderRung.QUORUM


def _tally_dict(t: Tally) -> dict[str, Any]:
    return {
        "counts": dict(t.counts),
        "shares": {o: round(t.share(o), 4) for o in t.counts},
        "standing": t.standing,
        "ever_participated": t.ever_participated,
        "withdrawn": t.withdrawn,
        "changes": t.changes,
    }


@dataclass
class Finding:
    """A frozen, hashed snapshot of one issue at one moment."""

    finding_id: str
    topic_id: str
    title: str
    taken_at: datetime
    rung: LadderRung
    region: str | None
    quorum_target: int | None
    tally: dict[str, Any]
    migrations: list[dict[str, Any]]
    proposition: dict[str, Any] | None
    ledger_events: int  # how many ledger entries the snapshot replays
    note: str | None = None  # why it was taken, in the taker's words
    taken_by: str | None = None  # anonymous id, if known
    method_version: int = METHOD_VERSION
    content_hash: str = field(default="")

    @property
    def citable(self) -> bool:
        """Findings below quorum are exportable, but they are signal, not findings."""
        return RUNG_ORDER.index(self.rung) >= RUNG_ORDER.index(LadderRung.QUORUM)

    # -- canonical form ---------------------------------------------------- #

    def payload(self) -> dict[str, Any]:
        """Everything that is hashed: the evidence, not the labels around it."""
        return {
            "method_version": self.method_version,
            "topic_id": self.topic_id,
            "title": self.title,
            "taken_at": _aware(self.taken_at).isoformat(),
            "rung": self.rung.value,
            "region": self.region,
            "quorum_target": self.quorum_target,
            "tally": self.tally,
            "migrations": self.migrations,
            "proposition": self.proposition,
            "ledger_events": self.ledger_events,
        }

    def compute_hash(self) -> str:
        canonical = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload(),
            "finding_id": self.finding_id,
            "citable": self.citable,
            "note": self.note,
            "taken_by": self.taken_by,
            "content_hash": self.content_hash,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        """A one-page record a council, board, or assembly can put on an agenda."""
        t = self.tally
        lines = [
            f"# Finding: {self.title}",
            "",
            f"*Taken {_aware(self.taken_at).strftime('%Y-%m-%d %H:%M UTC')} · "
            f"rung: **{self.rung.value}** · "
            f"{'citable' if self.citable else 'signal only — quorum not reached'}*",
            "",
        ]
        if self.note:
            lines += [f"> {self.note}", ""]
        lines += [
            "## Where people stand",
            "",
            "| Option | People | Share |",
            "|---|---|---|",
        ]
        for option, n in t["counts"].items():
            lines.append(f"| {option} | {n} | {t['shares'][option]:.0%} |")
        scope = self.region or "unscoped"
        quorum = (
            f"{t['standing']}/{self.quorum_target} to quorum"
            if self.quorum_target
            else "no quorum set"
        )
        lines += [
            "",
            f"**Denominator:** {t['standing']} verified people standing, "
            f"{t['ever_participated']} ever took part, {t['withdrawn']} withdrew, "
            f"{t['changes']} changed their vote. Scope: {scope}. {quorum}.",
            "",
        ]
        if self.migrations:
            lines += ["## What moved people", ""]
            for m in self.migrations:
                to = m["to"] if m["to"] is not None else "withdrew"
                why = f' — "{m["reasons"][0]}"' if m["reasons"] else ""
                lines.append(f"- {m['count']} moved {m['from']} → {to}{why}")
            lines.append("")
        if self.proposition:
            p = self.proposition
            lines += ["## Wordings of this question", ""]
            for v in p["variants"]:
                shares = ", ".join(
                    f"{o} {s:.0%}" for o, s in v["tally"]["shares"].items()
                )
                lines.append(
                    f"- **{v['title']}** — {v['tally']['standing']} standing: {shares}"
                )
            gap = p["divergence"]
            verdict = (
                f"Wordings disagree by {gap:.0%} on {p['divergence_option']!r} — "
                "the framing is doing work."
                if p["framing_matters"]
                else f"Wordings agree (largest gap {gap:.0%})."
            )
            lines += ["", verdict, ""]
        lines += [
            "## Method",
            "",
            f"Pure replay of {self.ledger_events} ledger events up to the moment "
            f"above (method v{self.method_version}). Counts are people, not votes; "
            "one person, one standing vote. Anyone with the ledger reproduces this "
            "exactly.",
            "",
            f"`sha256:{self.content_hash}`",
        ]
        return "\n".join(lines)


class FindingStore:
    """Take, keep, verify, and reproduce findings."""

    def __init__(
        self,
        topic_store: TopicStore,
        ledger: StandingVoteLedger,
        propositions: PropositionRegistry | None = None,
    ) -> None:
        self._topics = topic_store
        self._ledger = ledger
        self._propositions = propositions
        self._findings: dict[str, Finding] = {}

    def _build(
        self,
        topic: Topic,
        at: datetime,
        finding_id: str,
        note: str | None,
        taken_by: str | None,
    ) -> Finding:
        tally = self._ledger.tally(topic.id, at=at)
        rung = ladder_rung(topic, tally.standing, at)
        migrations = [
            {
                "from": m.from_choice,
                "to": m.to_choice,
                "count": m.count,
                "reasons": list(m.reasons),
            }
            for m in self._ledger.migrations(topic.id, at=at)[:MIGRATIONS_KEPT]
        ]
        proposition: dict[str, Any] | None = None
        if self._propositions is not None:
            view = self._propositions.view(topic.id, at=at)
            if view is not None:
                proposition = {
                    "proposition_id": view.proposition_id,
                    "variants": [
                        {
                            "topic_id": v.topic_id,
                            "title": v.title,
                            "tally": _tally_dict(v.tally),
                        }
                        for v in view.variants
                    ],
                    "combined": _tally_dict(view.combined),
                    "divergence": view.divergence,
                    "divergence_option": view.divergence_option,
                    "framing_matters": view.framing_matters,
                    "thresholds": {
                        "min_standing": DIVERGENCE_MIN_STANDING,
                        "framing_matters_at": FRAMING_DIVERGENCE_MIN,
                    },
                }
        target = topic.quorum if (topic.quorum and topic.quorum > 0) else None
        f = Finding(
            finding_id=finding_id,
            topic_id=topic.id,
            title=topic.title,
            taken_at=_aware(at),
            rung=rung,
            region=topic.region,
            quorum_target=target,
            tally=_tally_dict(tally),
            migrations=migrations,
            proposition=proposition,
            ledger_events=len(self._ledger.history(topic.id, at=at)),
            note=(note or "").strip() or None,
            taken_by=taken_by,
        )
        f.content_hash = f.compute_hash()
        return f

    def take(
        self,
        topic_id: str,
        note: str | None = None,
        taken_by: str | None = None,
        at: datetime | None = None,
    ) -> Finding:
        """Freeze the issue as it stands now (or at ``at``) and keep the record."""
        topic = self._topics.get(topic_id)
        if topic is None:
            raise ValueError(f"Topic {topic_id!r} does not exist")
        now = _aware(at or datetime.now(tz=UTC))
        f = self._build(topic, now, uuid.uuid4().hex[:12], note, taken_by)
        self._findings[f.finding_id] = f
        return f

    def get(self, finding_id: str) -> Finding | None:
        return self._findings.get(finding_id)

    def list_for(self, topic_id: str) -> list[Finding]:
        return sorted(
            (f for f in self._findings.values() if f.topic_id == topic_id),
            key=lambda f: _aware(f.taken_at),
        )

    @staticmethod
    def verify(finding: Finding) -> bool:
        """Tamper check: does the content still match its hash?"""
        return finding.compute_hash() == finding.content_hash

    def reproduce(self, finding: Finding) -> bool:
        """Re-derive the finding from the ledger at ``taken_at``; must match exactly."""
        topic = self._topics.get(finding.topic_id)
        if topic is None:
            return False
        fresh = self._build(
            topic, finding.taken_at, finding.finding_id, finding.note, finding.taken_by
        )
        return fresh.content_hash == finding.content_hash == finding.compute_hash()
