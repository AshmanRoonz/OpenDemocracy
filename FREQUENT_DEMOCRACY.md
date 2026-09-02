# Frequent Democracy — Design Note

> *"A democracy considers every citizen's voice, frequently — not once every
> four or five years on party C or party D. We need technology that can hear
> every voice **when it matters to those voices**."*

This document turns that principle into a concrete, buildable design. It is the
spec the rest of the project builds against. It is deliberately small: every
mechanism here should be transparent enough that a citizen can understand why
they're seeing what they're seeing.

## The problem with infrequency

Representative democracy collects your voice on a fixed, rare schedule — an
election every few years — and bundles thousands of unrelated positions into a
single yes/no choice between parties. Between those moments your voice has
nowhere to go. The result:

- **Latency.** By the time you can respond, the decision is made.
- **Bundling.** You can't support one position and oppose another.
- **Irrelevance.** You're asked about everything at once, or nothing at all —
  never *this issue, now, because it affects you*.

Frequency alone isn't the fix. Asking everyone about everything, constantly, is
just noise — it produces fatigue, not participation. The real target is
**relevant frequency**: surface each issue to each person *when it concerns
them and while their input can still change the outcome.*

## Three signals

Every open issue is ranked, per citizen, by a transparent blend of three
signals. No hidden model decides what you see — the weights are constants you
can read in the source.

| Signal | Question it answers | Source of truth |
|---|---|---|
| **Relevance** | Does this concern *me*? | The citizen's self-declared interest tags + region, matched against the issue's tags + region. Stored locally, never shared. |
| **Urgency** | Can my input still matter? | How close the issue's decision deadline is. Ramps from 0 to 1 across a 72-hour window; closed issues drop to 0. |
| **Activity** | Is deliberation live? | Submission count, with diminishing returns so a viral issue can't bury quieter ones. |

The composite score is `3·relevance + 2·urgency + 1·activity`. Relevance leads:
the whole premise is that the issues *you* care about reach *you* first.

On top of ranking, each issue shows **decision milestones** so people can see —
and reach — the point where an outcome becomes legitimate: progress toward an
optional **quorum** (counted in distinct participants, not raw submissions),
whether quorum has been reached, and how that composes with the closing window
(`"Quorum reached — closing soon"`). Region matching is **hierarchical**: scopes
are `/`-separated paths, and a citizen is concerned by any issue whose scope
nests with their own in either direction.

This logic lives in exactly one place per runtime, kept in lockstep:

- **Backend:** [`src/opendemocracy/participation/relevance.py`](src/opendemocracy/participation/relevance.py)
- **In-browser P2P app:** the *frequent-democracy relevance engine* block in
  [`docs/index.html`](docs/index.html)

Both produce identical orderings for identical inputs (covered by
`tests/participation/test_relevance.py` and a cross-runtime numeric check).
The same page also mirrors Vote's standing-vote ledger, attention reasons, and
Finding hash — see [VOTE.md](VOTE.md) and
`tests/participation/test_browser_parity.py`, which runs the browser block
under node against the Python modules.

## What a citizen experiences

1. **Declare interests once.** Pick the topics you care about and your region.
   This is local to your device — relevance is computed in your own browser, so
   nobody learns what you care about.
2. **A live feed, not a ballot.** Open issues are ordered "for you" by default,
   with one-tap re-sorting by *closing soon*, *most active*, or *newest*. Each
   card shows why it surfaced: a ⭐ "for you" pill, a ⏱ countdown when a
   deadline is near, an activity marker, and matched tags highlighted.
3. **Invited in when it matters.** When a new issue that matches your declared
   interests appears on the mesh, a quiet "a new issue matters to you" banner
   appears — the digital equivalent of being personally invited to the meeting
   that affects you. Backlog from initial sync never triggers alerts; only
   genuinely new issues do.
4. **Participate granularly.** Opinion, idea, or vote — per issue, one entry per
   verified person, your voice joining humanity's shared record.

## Design constraints

- **Local-first relevance.** Interests and feed preferences are stored only on
  the device (`localStorage`). They are never broadcast to peers. Personalized
  ranking must never become surveillance.
- **Transparent ranking.** Constants over learned models. A citizen — or an
  auditor — can read exactly why an issue is ranked where it is.
- **No dark-pattern urgency.** "Closing soon" reflects a real, creator-set
  decision deadline, never a manufactured one. Urgency is a service to the
  voter, not a lever on them.
- **Backward compatible.** Issues without tags, region, or a deadline remain
  first-class — they're treated as universal and open-ended, and still rank and
  render correctly.

## Roadmap

### Now (shipped)
- [x] Relevance / urgency / activity ranking, shared by backend and P2P app
- [x] Per-citizen "live issues" feed with for-you / closing-soon / active /
      newest sorting
- [x] Local-only interest tags + region
- [x] "A new issue matters to you" alerts for newly-arriving relevant issues
- [x] Issue metadata: tags, region, decision deadline

### Now (shipped, second pass)
- [x] **Hierarchical region matching** — regions are `/`-separated paths
      (`EU/North/Sweden`); a citizen matches any issue whose scope is a prefix
      of, or prefixed by, their own. Flat names (`EU-North`) stay valid as
      one-segment paths.
- [x] **Decision milestones** — issues carry an optional quorum target; the feed
      shows progress toward it (`12/50 to quorum`), flags `Quorum reached`, and
      composes that with the closing window (`Quorum reached — closing soon`).
      Quorum counts *distinct participants*, not raw submissions.

### Next
- [ ] Notifications beyond the open tab (Web Push / opt-in) so "when it matters"
      reaches you even when you're away
- [ ] Learned-but-auditable interest inference from past participation, strictly
      on-device, always overridable
- [ ] Digest mode: a periodic, batched summary of what mattered to you, for
      citizens who don't want a live feed

### Later
- [ ] Cross-jurisdiction issue routing (an issue raised locally that turns out
      to matter regionally surfaces to the wider mesh)
- [ ] Accessibility parity for offline / assembly formats — representing the
      unconnected is an explicit goal, not an afterthought

## Why this is the right increment

Everything else in OpenDemocracy — verified identity, the P2P mesh, the local
collective-intelligence engine — answers *"can every voice be heard, safely and
without a gatekeeper?"* Frequent Democracy answers the question the manifesto
actually leads with: *"will every voice be heard **when it matters to that
voice**?"* Without it, the system is a better ballot box. With it, it's the
shared cortex the project set out to build.

---

*Every voice is signal. The goal isn't to ask everyone about everything — it's
to make sure no one is left out of the decisions that shape their life.*
