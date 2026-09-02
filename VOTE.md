# Vote — Founding Document

> *Anyone can vote for anything, at any time. AI helps connect voters, organize
> our concerns, and make sure every voice matters.*

**Vote** is the citizen-facing app of OpenDemocracy: the place where the
project's principles become something a person can open on their phone and use
today. This document is its founding statement — what Vote is, what it refuses
to be, and how it earns legitimacy one decision at a time.

## Why

We don't live in a democracy — not in the sense the word promises. The voice of
the people is distorted, twisted, and divided, and the distortion doesn't happen
at the ballot box. Counting works. The damage is done upstream of the count, in
three places:

| Where | What happens |
|---|---|
| **Agenda** | Someone else decides *what* you get to vote on, and *when* — a handful of pre-bundled choices, once every few years. |
| **Framing** | Someone else words the question and bundles unrelated positions into a single yes/no. |
| **Aggregation** | Afterward, someone else narrates "what the people want" — parties, media, pollsters. |

Ballots on paper cannot fix this. AI, used right, can: it makes hearing every
voice, on every issue, every day, cheap enough to actually do. Used wrong, it
becomes a better-designed version of the same machine. Vote exists to do the
first and structurally refuse the second.

## What Vote is

**Anyone can vote for anything, at any time.** The people set the questions.
That is the radical part — not frequency, but taking back the agenda.

**A vote is standing, not final.** You can change it whenever you like. Public
opinion becomes a living curve, not a snapshot. When you change your mind, Vote
asks what changed it — so arguments are measured by who they actually moved,
not by applause.

**Every voice is a signal, and the signal is credible.** Votes come from
verified humans (anonymous proof-of-personhood, never identity). Tallies are
deterministic and auditable. Results always show the denominator and who
showed up — never "the public thinks", always "61% of 48,000 verified
participants, skewing urban".

**Every voice matters — including the ones that lost.** Vote shows full
distributions, not verdicts. Minority views stay visible as data. Intensity is
shown next to headcount. Dissent is a first-class output. Majority rule at
daily speed would be tyranny at speed for anyone in the 30%; Vote is built so
that it isn't.

**AI connects and organizes; humans decide.** AI in Vote does exactly three
jobs, and no others:

1. **Connect** — bring each issue to the people it concerns, when their input
   can still matter (the *frequent democracy* feed), and bridge people across
   disagreement so the strongest opposing reasons meet — individual to
   individual, reasons attached to votes. Vote deliberately does **not**
   cluster people, whether they agree or disagree: grouping people who agree
   is the outrage-machine primitive, and grouping at all is a model of who
   belongs with whom that Vote refuses to build.
2. **Organize** — merge duplicate propositions so the signal doesn't fragment,
   while keeping wording variants visible, because "ban X" and "allow X"
   polling differently is framing data worth showing.
3. **Explain** — narrate trends in plain language on top of the numbers. The
   AI never produces a number. Every figure comes from published, rerunnable
   aggregation code.

Beneath that, the preference layer ([AI_MEDIATION.md](AI_MEDIATION.md)) makes
continuous participation low-effort: Vote learns your values from your own
votes and suggests where you'd likely stand on new issues — as a suggestion
you confirm or override, never a vote cast for you.

## What Vote refuses to be

- **Not a company that owns the interpreter.** Whoever tunes the organizer
  shapes the will. Vote's code, ranking constants, and aggregation are open,
  governed by the community, and forkable. It is a commons or it is nothing.
- **Not a poll.** Polls collapse; Vote preserves. Polls are consumed by others;
  Vote's signal is citable by the people who produced it.
- **Not an engagement product.** No metric anywhere in the loop rewards
  attention capture. Ranking uses fixed, readable constants.
- **Not a weapon.** Propositions are about policies and choices — never about
  persons or groups as targets. This is a founding rule, not a moderation
  patch.
- **Not a sorter of people.** This is individual voting. Vote never clusters,
  segments, or models people into groups — not in the interface and not as an
  internal step. Every number is a count of individuals. "People who voted
  Yes" is a tally, not a group; nothing is ever inferred about who belongs
  with whom.
- **Not a forum.** Reasons are attached to votes, never addressed to people.
  There are no replies, no threads, no escalation.

## Flow, attention, choice

Everything in Vote flows automatically until attention makes part of the flow
available for choice. Projected preferences and standing votes are the flow —
they are what make daily participation possible without fatigue. Attention is
the interruption, and it is only legitimate when it names its cause.

Vote asks two **standard questions**:

| Question | Direction | What it does |
|---|---|---|
| **What needs attention?** | System → citizen | Surfaces the issues where flow has stopped being trustworthy *for you*: your own values conflict, your profile can't project, people who stood where you stand are moving, the picture shifted since you chose, the wordings of the question disagree, the window is closing, quorum is near, or it concerns you and you haven't spoken. Each is a named reason with a fixed, readable weight. Silence is a valid answer. |
| **What needs attention that nobody has asked about yet?** | Citizen → system | The same question turned around is the agenda. Answering it in one line creates a proposition. |
| **What changed your mind?** | Citizen → everyone | Asked the moment a standing vote changes. Turns changed minds into the most honest measure of an argument. |

One question opens choice, one sets the agenda, one closes the loop.

## The legitimacy ladder

A voice that is counted and ignored is a poll. Vote is designed to become
undeniable, step by step:

| Rung | An issue reaches it when |
|---|---|
| **Signal** | Anyone opens it; votes flow. Raw, exploratory, visible. |
| **Quorum** | Enough distinct verified participants have weighed in (quorum milestones are already built). |
| **Scoped** | The issue is tied to a region or community, and participation reflects the people actually in it. |
| **Finding** | An auditable, exportable snapshot — denominator, composition, distribution, wordings, what moved people, method — carrying a content hash and re-derivable from the ledger by anyone. A council, board, or assembly cannot wave it off as bot noise. Below quorum it exports as *signal only*. |
| **Bound** | A real body has committed in advance to act on findings above a threshold. |

Democracy at national scale is won by being undeniable at small scale first.

## MVP: one community, one real decision

The first release of Vote is not global. It is one community that agrees to
let a real decision ride on it — a co-op, a union local, a school board, a
town budget line. Success is measured by one thing: **did a decision get made
that the people, not the machine, can show they made?**

Scope of the first release:

- Open proposition creation with AI duplicate-merging and visible framing
  variants — built (suggestions are transparent and lexical; a human merges).
- Verified-human, anonymous voting; standing votes with change history and
  "what changed your mind?" — built.
- The live issues feed (relevance · urgency · activity) — built.
- Deterministic tallies with denominator, composition, and full distribution.
- Quorum and scope milestones — built.
- Exportable *Finding* snapshots — built (hashed, reproducible from the
  ledger, JSON and Markdown).

Every item above is built. What remains is not code: **a community, and a
real decision willing to ride on it.** Everything else — delegation,
consequence modeling, cross-community scale — waits until one community has
been heard and answered.

## How this maps to the codebase

The in-browser app ([`docs/index.html`](docs/index.html)) mirrors the
standing-vote ledger, the attention reasons it can compute without a
preference profile, and the Finding payload and hash, as a pure *VOTE ENGINE*
block. Its transport is **Nostr**: every record — enrollment, question,
opinion, standing vote — is a signed Nostr event, and public relays carry
them as dumb replicated storage. There is no server you have to trust and no
single one you depend on: the page reads from several relays, anyone can add
one, a community can run its own, and every browser verifies every signature
and replays the ledger itself. The record outlives every open tab. The pure
*NOSTR MAPPING* block (events ⇄ records, validation, dependency parking) is
exercised by `tests/participation/test_browser_nostr.py`. `tests/participation/test_browser_parity.py` runs that block under node
against the Python modules: same events, same tally, same migrations, same
canonical JSON, same SHA-256.

| Vote concept | Where it lives |
|---|---|
| Connect: live issues feed | `participation/relevance.py` · [FREQUENT_DEMOCRACY.md](FREQUENT_DEMOCRACY.md) |
| Quorum and scoped regions | `participation/topics.py`, `participation/status.py` |
| Verified, anonymous voters | `identity/` |
| Preference suggestions, human-confirmed | `participation/preferences.py` · [AI_MEDIATION.md](AI_MEDIATION.md) |
| What needs attention? / agenda prompt | `participation/attention.py` · `/api/attention` · browser: attention section + create-topic heading |
| Full-distribution output | `output/reports.py` |
| Standing, revocable votes with change history | `participation/votes.py` · `/api/vote`, `/tally`, `/timeline`, `/migrations` · browser: `votes` G-Set + ledger replay |
| Proposition merging and framing variants | `participation/propositions.py` · `/api/propositions/*`, `/api/topics/{id}/proposition` |
| Finding snapshots | `participation/findings.py` · `/api/topics/{id}/findings`, `/api/findings/{id}[/markdown|/check]` · browser: take / copy / check |

---

We have the technology. The hard part is refusing to let the technology hold
the power. **#everyvoicematters**
