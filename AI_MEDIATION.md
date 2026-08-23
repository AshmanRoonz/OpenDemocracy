# AI Mediation — Design Note

Counting and routing votes stopped being the hard limit years ago. Paper — even
pure digital ballots — still forces coarse, infrequent, high-friction input
because the real bottlenecks were always **human attention, coordination costs,
and trust in the aggregation layer**. AI changes the feasible surface area of
that problem — and it also relocates power. This note states what this project
builds from that new surface area, and the rules that keep the relocated power
visible and contestable.

The design stance in one sentence: **the interesting space is not "AI runs the
vote" — it is using AI to make continuous, high-bandwidth preference revelation
and deliberation cheaper and more honest, while keeping final authority and
auditability firmly human and distributed.**

## What becomes newly possible — and where it lives here

### 1. Continuous, low-effort preference elicitation

Instead of periodic binary choices, the system learns a person's value
hierarchy through lightweight interactions, then *projects* those preferences
onto novel issues without demanding daily re-deliberation from scratch.

Implemented in
[`src/opendemocracy/participation/preferences.py`](src/opendemocracy/participation/preferences.py):

- A **citizen-owned `PreferenceProfile`** (local, erasable — same custody model
  as `Interests` in the frequent-democracy feed) learns positions on named
  value axes from explicit signals only. Confidence is derived from observation
  counts, never asserted.
- Issues declare their **value alignments openly** (like tags). Projection is a
  confidence-weighted dot product — small enough to read, deterministic enough
  to reproduce, explainable axis-by-axis in one screen.
- A projection **abstains** when confidence is low. "We don't know your view
  yet" is the honest answer, not a guess.
- A projection is **never a vote**. Only an explicit human confirmation or
  override produces a stance that counts, and the record keeps both the
  suggestion and the decision — so drift between what the model says people
  want and what people actually choose is *measurable*, permanently.
- An **override is training data**: when the citizen corrects the suggestion,
  the correction feeds back as signal. Contesting the model improves it.

### 2. Liquid / delegated decision weight

People should be able to hand temporary decision weight to others — or to
specialized models — on specific domains, with transparent revocation and audit
trails. Design constraints for when this lands:

- Delegation is **per-domain** (tag-scoped), **time-boxed by default**, and
  **revocable instantly**, with every grant and revocation in the audit trail.
- Delegating to a model is delegating to a *published, versioned artifact* —
  the delegate's reasoning must be as inspectable as a human delegate's public
  record.
- Delegation chains resolve transparently: anyone can trace where their weight
  went on any decision. No hidden re-delegation.

### 3. Real-time synthesis of argument space

Instead of raw polling noise, the processing layer
([ARCHITECTURE.md](ARCHITECTURE.md), Layer 2) surfaces the strongest
conflicting reasons, flags where the public is poorly informed, and separates
**intensity from headcount** — clustering
(`opendemocracy.processing.clustering`) and tradeoff analysis
(`opendemocracy.modeling.tradeoffs`) exist for exactly this. The output
contract stays the project's core principle: **full distributions, never a
collapsed "singular truth"**. Disagreement is data, not a bug.

### 4. Outcome simulation before decisions lock in

Counterfactuals and consequence modeling (`opendemocracy.modeling.simulation`,
`scenarios`, `temporal`) bring prediction-market discipline to deliberation:
assumptions declared, uncertainty quantified, models falsifiable against
real-world outcomes.

## Where the power relocates — and the standing answers

Once an AI sits between raw signals and the official "will", three questions
decide legitimacy. They are requirements here, not open questions:

**Who trains, owns, and can override the models that interpret public input?**
Everything is open — code, weights, pipelines ([README](README.md), Principle
1) — under community governance ([GOVERNANCE.md](GOVERNANCE.md)). At the
individual level, *every citizen* holds override authority over every
interpretation of their own input: that is the `decide()` step in the
preferences module, and it is not optional plumbing.

**How do you stop the system from quietly optimizing for engagement, its
operators, or institutional continuity?** By construction, not by promise:
ranking and projection use **fixed, readable constants** (see
`relevance.py` and `preferences.py`) rather than learned engagement
objectives; there is no metric in the loop that rewards attention capture. The
confirmed-vs-suggested record is the standing detector: if projections
systematically diverge from what humans confirm, that divergence is public
data.

**What happens to legitimacy when the voice-to-output mapping is opaque
statistical machinery?** Then legitimacy is lost — so the mapping is required
to *not* be that. Every step from a submission to an aggregate must be
reproducible from published code and explainable to the person whose voice it
carries. Where a component can't meet that bar, it can inform deliberation
(surface arguments, simulate outcomes) but cannot sit on the path that produces
the official count.

## The honest caveat

AI does not magically produce high-quality democratic will. It lowers the cost
of listening at higher resolution and reduces some noise and fatigue — and it
can just as easily become a more sophisticated filter between people and
outcomes, harder to see and harder to contest than the old party machines.
That is why every mechanism in this repo is small, constant-weighted, and
audited: the engineering problem worth solving is keeping the filter
transparent, not making it powerful.
