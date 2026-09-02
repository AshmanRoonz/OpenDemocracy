# Prior Art — Homework for Vote

Five outside sources, read against what Vote has built so far, with concrete
suggestions and the tensions each one forces. The point is not to copy any of
them; it is to steal what has already been proven and to know where Vote
deliberately differs.

| Source | What it is | What Vote takes from it |
|---|---|---|
| [LiquidFeedback](https://liquidfeedback.com/en/) | The reference implementation of liquid democracy (transitive, revocable delegation) with a four-phase proposal process and preferential voting | Delegation design, a *frozen wording* phase, alternatives voted preferentially, and an argument about transparency Vote must answer |
| [Polis](https://pol.is/) | Open-source (AGPL) opinion mapping: agree/disagree/pass on short statements, PCA + k-means opinion groups, group-informed consensus, no replies | The `pass` stance and the no-replies rule. **Not** the groups: Vote counts individuals and never clusters people |
| [Fung, Gilman & Shkabatur, *Six Models for the Internet + Politics* (2013)](https://academic.oup.com/isr/article/15/1/30/1792440) | Six models of how digital technology could change democracy, with a sober verdict on which are likely | A legitimacy strategy: why the MVP is scoped the way it is |
| [tFHE Kotlin example](https://github.com/brooksdubois/tFHEKotlinExample) (Zama TFHE) | Demo of encrypted one-hot ballots tallied homomorphically and decrypted by threshold | A way to remove the operator from the trust chain of the tally — and a real tension with reproducibility |
| [Trystero](https://github.com/dmotz/trystero) and [Rakis](https://github.com/hrishioa/rakis) | Serverless WebRTC signaling (BitTorrent, Nostr, MQTT, IPFS); and a browser-only inference network on top of it with embedding-based verification | The move that became "Nostr relays carry the ledger" (built); and the only place Vote's AI "explain" and "organize" jobs can honestly run — with verification, so an AI sentence is auditable the way a tally is |

---

## 1. LiquidFeedback

**What it does.** Members join *subject areas* and can delegate their vote per
area (or per issue) to another member; delegations are transitive (a proxy can
delegate onward), revocable at any time, and a direct vote always overrides a
delegation. An issue moves through **admission** (an initiative needs a first
supporter quorum), **discussion** (competing *initiatives* and *suggestions*
improve drafts), **verification** (drafts are frozen; nothing can change), and
**voting** (a preferential ballot, Schulze method, with the status quo as a
candidate). LiquidFeedback names four principles: scalability through division
of labour (delegation), proportional representation of minorities (collective
moderation via supporter quorums), protection against non-transparent lobbying
(a fully transparent process), and equal treatment of competing alternatives
(preferential voting).

**Suggestions for Vote.**

- **Delegation, when we build it, is per-domain, transitive, revocable, and
  beaten by a direct vote.** This is exactly the design sketched in
  [VOTE.md](VOTE.md); LiquidFeedback proves it works and adds one rule worth
  copying verbatim: *casting your own standing vote on a topic silently
  suspends your delegation for that topic.* Attention already knows when to ask
  you to look; delegation is what flows when you don't.
- **A frozen-wording step before a Finding.** Today a topic's title can be
  edited while votes stand, which would make a Finding cite a question nobody
  answered. Borrow verification: once a topic has votes (or is merged into a
  proposition), its wording is frozen; a new wording is a new variant. The
  proposition layer already models wordings, so this is a small rule, not a
  new module.
- **Competing initiatives, not just yes/no.** LiquidFeedback's real unit is
  "several answers to one question", ranked. Vote's propositions currently
  require identical vote options; the natural extension is a proposition whose
  variants are *alternatives* rather than *wordings*, with a preferential
  ballot (Schulze, status quo included) and the same denominator rules.
- **Supporter quorum before an issue takes attention.** Vote's quorum is on the
  *result*; LiquidFeedback also has one on *admission*, which stops a single
  person's proposition from claiming everyone's attention. A small admission
  quorum (first *n* supporters) before a topic enters other people's
  "what needs attention?" is cheap and honest.

**The tension Vote must answer.** LiquidFeedback rejects the secret ballot on
principle: *if you delegate to someone, you must be able to see how they voted,
and if the process is to resist lobbying, everyone must see everything.* Vote
is built on anonymous verified identity. Both are right about something.
Proposed resolution: **citizens are anonymous; delegates are not.** Accepting
delegated weight is an opt-in into transparency — a delegate's votes, and the
chain of weight behind them, are public. That keeps the LiquidFeedback
accountability argument intact exactly where power concentrates, and nowhere
else.

## 2. Polis

**What it does.** Participants write short statements and vote
agree/disagree/pass on others'. There are deliberately **no replies**. A
participant-by-statement matrix is reduced with PCA and clustered with k-means
(silhouette picks the number of groups); the result is a map of *opinion
groups*, the statements that best distinguish them, and **group-informed
consensus**: statements that every group agrees with, scored so that a
statement must carry each group, not just the majority. Comment routing decides
which statements a participant sees next. Used by vTaiwan for Uber, Airbnb,
and online alcohol sales; AGPL-licensed.

**Suggestions for Vote.**

- **Add a `pass` stance.** Standing votes are currently choose-an-option or
  withdraw. "Pass" is different from "withdraw": it says *I saw this and have
  no view*, which is signal about where the public is uninformed. It also
  feeds the `unknown_values` attention reason honestly.
- **Keep the no-replies rule.** Vote's "what changed your mind?" reasons are
  attached to a vote change, not addressed to a person. That is the same
  choice Polis made for the same reason (no threads, no escalation). Write it
  down as a rule so a future "discussion" feature doesn't undo it.
- **Common ground without groups.** Polis finds consensus by first sorting
  people into opinion groups and then asking what every group agrees on. Vote
  does not sort people. Common ground in Vote is counted directly over
  individuals: a statement is common ground when a large share of *all*
  standing voters agree with it and few pass. "Connecting voters across
  disagreement" is likewise individual: show each person the reasons given by
  individuals who voted differently, attached to their votes, never to a
  segment.

**Where Vote refuses to follow.** Polis's core move is to cluster *people*.
Vote's rule is stricter than "don't show people their group": **no groups at
all.** Vote never clusters, segments, or models people into groups, not in
the interface and not as an internal intermediate. Every number is a count of
individuals. This costs Vote Polis's group-informed consensus metric; it buys
the guarantee that the system can never learn, store, or act on who belongs
with whom.

## 3. Fung, Gilman & Shkabatur — Six Models for the Internet + Politics

**What it says.** Digital technology could change democracy through six
models: an *empowered public sphere*, *displacement of traditional
organisations* by self-organised groups, *digitally direct democracy*,
*truth-based advocacy*, *constituent mobilisation*, and *crowd-sourced social
monitoring*. Their verdict: the first three (the transformative ones) are
unlikely; the last three (incremental ones, where technology helps existing
actors do what they already do, better) are where the internet has actually
changed politics.

**What this means for Vote.** Vote is, by name, a digitally-direct-democracy
project — the model these authors think is least likely to arrive. Rather than
argue, take the paper as a route map:

- **Vote's legitimacy ladder is a walk up their list.** A *Finding* — an
  auditable, undeniable record of where verified people stand, with the
  denominator shown — is **truth-based advocacy** and **crowd-sourced
  monitoring** first: something a council can't dismiss. Only after that is
  earned does *Bound* (a body committing in advance to act) become direct
  democracy. Say this out loud in the pitch: Vote wins as advocacy and
  monitoring before it wins as a vote.
- **Their skepticism is mostly about participation skew and the gap between
  voice and power.** Vote's answers are the always-shown denominator and
  composition, and the pilot rule of one community and one real decision. Those
  are the right answers; the paper says why they are necessary rather than
  nice.
- **Constituent mobilisation is a warning, not a feature.** Mobilising people
  who already agree is the model Vote refuses (no groups, no clustering).
  The paper shows it is also the model most easily captured by whoever runs the
  tool.

## 4. TFHE (Zama) — encrypted ballots

**What the demo shows.** Each ballot is encrypted as a one-hot vector; the
server adds ciphertexts homomorphically and never sees a single vote; the
final totals are decrypted by combining several keys (threshold / MPC), so no
single party can decrypt an individual ballot, and voters get receipts to
verify their ballot was counted. It is a portfolio demo, not a production
system — but the shape is right.

**What it fixes.** Vote's threat model today: the identity layer keeps voters
*anonymous* (no name is ever stored), but the ledger holds each anonymous id's
stance in plaintext. Whoever runs the server can see how `v0` votes on
everything. Anonymity is not privacy from the operator. FHE removes the
operator from the trust chain of the tally: the server can compute totals it
cannot read.

**The tension with reproducibility.** Vote's Findings are honest *because* the
ledger is a plaintext replay anyone can rerun. An encrypted ledger breaks that
in its naive form. Proposed shape, for later, not the MVP:

- The ledger stores **ciphertext events** (encrypted stance, plaintext
  metadata: topic, time, kind). Tallies are homomorphic sums.
- A Finding hashes the ciphertext ledger plus the threshold-decrypted totals
  plus a decryption proof, so "reproduce" means *re-sum the ciphertexts and
  check the proof* rather than *re-count plaintext*.
- Migrations (who moved from what to what) become per-voter differences of
  ciphertexts — computable, but reasons stay plaintext by the citizen's choice.
- Standing/revocable votes fit naturally: a change is a new ciphertext that
  replaces the old one in the sum.

The design decision to make now is small: keep the ledger's event type and the
tally function behind an interface so an encrypted implementation can slot in
without touching Findings, attention, or propositions.

## 5. Trystero and Rakis — the mesh without a server, and AI inside it

**What they are.** [Trystero](https://github.com/dmotz/trystero) (MIT) makes
WebRTC connections between browsers with **no signaling server**: peers find
each other through BitTorrent trackers, Nostr relays (the default), MQTT
brokers, or IPFS, and session descriptions are encrypted with a key derived
from the app and room id. [Rakis](https://github.com/hrishioa/rakis) is "a
permissionless inference network where nodes can accept AI inference
requests, run local models, verify each other's results and arrive at
consensus — all in the browser": WebGPU models in the page, redundant P2P
transports underneath, and an **embedding-based consensus** in which several
peers run the same request and embedding clusters separate valid results from
invalid ones — a route to verifiable inference before zero-knowledge ML or
trusted hardware.

**Suggestions for Vote.**

- **Done — and one step further: Nostr relays carry the ledger itself.** The
  browser app used PeerJS, whose hosted signaling server was the last thing
  in the mesh that could be switched off or made to log who talks to whom.
  Rather than swap signaling and keep a WebRTC full mesh, the app now makes
  every record a signed Nostr event and uses relays as dumb replicated
  storage: the ledger outlives every open tab, phones need no STUN or TURN,
  and the per-topic ceiling is thousands rather than dozens. The claim
  changes from "no server" to "no server you have to trust, and no single one
  you depend on" — the page reads from several relays, anyone can add one,
  and a community can run its own. Every browser still verifies every
  signature and replays the ledger; relays only carry. Trystero's Nostr
  strategy remains the natural route if a direct WebRTC path is ever wanted
  as an accelerator on top.
- **Vote's AI has to live where the ledger lives.** [VOTE.md](VOTE.md) gives
  the AI three jobs — connect, organize, explain — and forbids it from
  producing a number or casting a vote. Two of those jobs (semantic
  duplicate-wording suggestions, plain-language narration of a trend) will
  eventually want a language model. Run centrally, that model is exactly the
  owned interpreter Vote refuses to be. Distributed in-browser inference is
  the only version consistent with the rest of the design.
- **Verification is the part that matters.** A tally is auditable because
  every peer replays one ledger and gets one number. A model's sentence is
  not reproducible that way, so an explanation produced by a single peer is a
  manipulation surface. Rakis's shape is the right one: fan a request out to
  several peers, compare results, accept only what a quorum agrees on. That is
  how an AI-produced sentence becomes auditable in a mesh — and the rule that
  the AI still never produces a number stays untouched.

**The honest limits.** In-browser inference is heavy (WebGPU, hundreds of
megabytes of weights) and a civic app must run on an old phone; that argues
for keeping the model's job small, not for skipping it. And a verified
explanation is still less inspectable than a readable constant, which is why
the lexical duplicate-suggestion stays the default until a verified one can
show its evidence just as plainly.

---

## What changes now

Cheap, in scope, and consistent with everything already built:

1. **Freeze wording once votes stand** (LiquidFeedback).
2. **Add `pass`** as a stance distinct from withdraw (Polis).
3. **Write the no-replies rule into VOTE.md** (Polis).
4. **Admission quorum** before a topic enters others' attention (LiquidFeedback).
5. ~~Trystero for signaling~~ **Done as Nostr-carried ledger** — the browser app now stores and syncs every record as a signed Nostr event through relays; no signaling server, no WebRTC mesh (see [VOTE.md](VOTE.md)).

Next, as their own pieces of work:

6. **Common ground on Findings**, counted over individuals, no clustering
   (Polis, minus the groups).
7. **Delegation**: per-domain, transitive, revocable, beaten by a direct vote,
   with delegates transparent and citizens anonymous (LiquidFeedback).
8. **Alternatives with preferential voting** inside a proposition
   (LiquidFeedback, Schulze).
9. **Encrypted ledger** behind the existing interface (TFHE).
10. **Verified distributed inference** for the explain and organize jobs —
    several peers, one accepted answer, never a number (Rakis).

And one sentence for the pitch, from Fung: Vote earns the right to be direct
democracy by first being undeniable evidence.
