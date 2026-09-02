"""FastAPI application for biometric identity and participation.

Run with:  uvicorn opendemocracy.web.app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from opendemocracy.identity.biometrics import create_template
from opendemocracy.identity.crypto import generate_keypair
from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.identity.verification import issue_challenge, verify
from opendemocracy.models import (
    BiometricFactor,
    EnrollmentRecord,
    SubmissionType,
    Topic,
)
from opendemocracy.participation.attention import AGENDA_PROMPT, what_needs_attention
from opendemocracy.participation.propositions import PropositionRegistry, suggest_merges
from opendemocracy.participation.relevance import Interests
from opendemocracy.participation.submissions import SubmissionStore
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="OpenDemocracy", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory stores (production would use a database).
registry = IdentityRegistry()
topic_store = TopicStore()
submission_store = SubmissionStore(topic_store, registry)
vote_ledger = StandingVoteLedger(topic_store, registry)
propositions = PropositionRegistry(topic_store, vote_ledger)

# Challenge cache: challenge_id → AuthChallenge
_challenges: dict[str, object] = {}

# Seed a demo topic so the UI isn't empty on first load.
_demo_topic = Topic(
    id="demo-ubi",
    title="Universal Basic Income",
    description=(
        "Should the government provide a universal basic income to all "
        "citizens? Share your opinion, propose ideas, or cast your vote."
    ),
    allow_opinions=True,
    allow_ideas=True,
    allow_votes=True,
    vote_options=["Yes", "No", "Needs more research"],
)
topic_store.create(_demo_topic)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class EnrollRequest(BaseModel):
    factors: list[str]  # e.g. ["fingerprint", "face", "iris"]


class EnrollResponse(BaseModel):
    anonymous_id: str
    public_key: str
    private_key: str  # returned to client for local storage
    factors_enrolled: list[str]


class ChallengeRequest(BaseModel):
    anonymous_id: str


class ChallengeResponse(BaseModel):
    challenge_id: str
    nonce: str


class VerifyRequest(BaseModel):
    anonymous_id: str
    challenge_id: str
    signature: str


class VerifyResponse(BaseModel):
    verified: bool
    reason: str


class SubmitRequest(BaseModel):
    anonymous_id: str
    challenge_id: str
    signature: str
    topic_id: str
    submission_type: str  # "opinion", "idea", "vote"
    content: str


class SubmitResponse(BaseModel):
    success: bool
    submission_id: str
    message: str


class TopicOut(BaseModel):
    id: str
    title: str
    description: str
    allow_opinions: bool
    allow_ideas: bool
    allow_votes: bool
    vote_options: list[str]


class SubmissionOut(BaseModel):
    id: str
    submission_type: str
    content: str
    submitted_at: str


class VoteRequest(BaseModel):
    """Cast, change, or withdraw a standing vote. ``choice=None`` withdraws."""

    anonymous_id: str
    challenge_id: str
    signature: str
    topic_id: str
    choice: str | None = None
    reason: str | None = None  # "what changed your mind?" — optional, never inferred


class VoteEventOut(BaseModel):
    kind: str  # "cast" | "changed" | "withdrawn"
    previous: str | None
    choice: str | None
    reason: str | None
    at: str


class TallyOut(BaseModel):
    topic_id: str
    at: str
    counts: dict[str, int]
    standing: int
    ever_participated: int
    withdrawn: int
    changes: int


class MigrationOut(BaseModel):
    from_choice: str | None
    to_choice: str | None
    count: int
    reasons: list[str]


class AttentionRequest(BaseModel):
    """Interests stay on the citizen's device; they are sent only for this answer."""

    tags: list[str] = []
    region: str | None = None
    anonymous_id: str | None = None  # to account for your own standing votes


class AttentionItemOut(BaseModel):
    topic_id: str
    title: str
    reasons: list[str]
    explanations: list[str]
    score: float


class AttentionOut(BaseModel):
    items: list[AttentionItemOut]
    agenda_prompt: str  # the question asked back of the citizen


class MergeRequest(BaseModel):
    """Declare topics to be wordings of one proposition. A human act, with a reason."""

    topic_ids: list[str]
    reason: str | None = None
    anonymous_id: str | None = None


class MergeSuggestionOut(BaseModel):
    topic_a: str
    topic_b: str
    score: float
    shared_terms: list[str]
    shared_tags: list[str]


class FramingVariantOut(BaseModel):
    topic_id: str
    title: str
    tally: TallyOut


class PropositionOut(BaseModel):
    proposition_id: str
    variants: list[FramingVariantOut]
    combined: TallyOut
    divergence: float
    divergence_option: str | None
    framing_matters: bool


class TopicCreateRequest(BaseModel):
    title: str
    description: str
    allow_opinions: bool = True
    allow_ideas: bool = True
    allow_votes: bool = True
    vote_options: list[str] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    """Serve the main HTML page."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/enroll", response_model=EnrollResponse)
def api_enroll(req: EnrollRequest) -> EnrollResponse:
    """Enroll a new participant with multi-factor biometrics.

    In production the keypair is generated on-device and only the public
    key is sent.  For the prototype the server generates it and returns
    both so the browser can store the private key locally.
    """
    # Validate factor names.
    factor_map = {f.value: f for f in BiometricFactor}
    factors: list[BiometricFactor] = []
    for name in req.factors:
        if name not in factor_map:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown biometric factor: {name!r}",
            )
        factors.append(factor_map[name])

    if len(factors) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 biometric factors are required",
        )

    if len(factors) != len(set(factors)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate biometric factors are not allowed",
        )

    # Simulate local template creation (in production this happens on-device).
    templates = [
        create_template(f"simulated-{f.value}".encode(), f, 0.95) for f in factors
    ]
    _ = templates  # templates stay local — not stored server-side

    # Generate keypair.
    private_key, public_key = generate_keypair()

    # Register in the server-side registry.
    record = EnrollmentRecord(
        public_key=public_key,
        factors_enrolled=factors,
    )
    try:
        registry.register(record)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return EnrollResponse(
        anonymous_id=record.anonymous_id,
        public_key=public_key,
        private_key=private_key,
        factors_enrolled=[f.value for f in factors],
    )


@app.post("/api/challenge", response_model=ChallengeResponse)
def api_challenge(req: ChallengeRequest) -> ChallengeResponse:
    """Issue a cryptographic challenge for identity verification."""
    if not registry.is_enrolled(req.anonymous_id):
        raise HTTPException(status_code=404, detail="Participant not enrolled")

    challenge = issue_challenge()
    _challenges[challenge.challenge_id] = challenge

    return ChallengeResponse(
        challenge_id=challenge.challenge_id,
        nonce=challenge.nonce,
    )


@app.post("/api/verify", response_model=VerifyResponse)
def api_verify(req: VerifyRequest) -> VerifyResponse:
    """Verify a signed challenge response."""
    challenge = _challenges.get(req.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    result = verify(challenge, req.signature, req.anonymous_id, registry)  # type: ignore[arg-type]
    return VerifyResponse(verified=result.verified, reason=result.reason)


@app.post("/api/submit", response_model=SubmitResponse)
def api_submit(req: SubmitRequest) -> SubmitResponse:
    """Submit an opinion, idea, or vote after biometric verification."""
    # Verify identity first.
    challenge = _challenges.get(req.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    verification = verify(
        challenge,
        req.signature,
        req.anonymous_id,
        registry,  # type: ignore[arg-type]
    )
    if not verification.verified:
        raise HTTPException(
            status_code=403,
            detail=f"Verification failed: {verification.reason}",
        )

    # Map submission type.
    type_map = {t.value: t for t in SubmissionType}
    sub_type = type_map.get(req.submission_type)
    if sub_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown submission type: {req.submission_type!r}",
        )

    try:
        submission = submission_store.submit(
            verification, req.topic_id, sub_type, req.content
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SubmitResponse(
        success=True,
        submission_id=submission.id,
        message=f"{sub_type.value.title()} submitted successfully",
    )


@app.get("/api/topics", response_model=list[TopicOut])
def api_topics() -> list[TopicOut]:
    """List all open topics."""
    return [
        TopicOut(
            id=t.id,
            title=t.title,
            description=t.description,
            allow_opinions=t.allow_opinions,
            allow_ideas=t.allow_ideas,
            allow_votes=t.allow_votes,
            vote_options=t.vote_options,
        )
        for t in topic_store.list_open()
    ]


@app.post("/api/topics", response_model=TopicOut)
def api_create_topic(req: TopicCreateRequest) -> TopicOut:
    """Create a new topic for participation."""
    topic = Topic(
        title=req.title,
        description=req.description,
        allow_opinions=req.allow_opinions,
        allow_ideas=req.allow_ideas,
        allow_votes=req.allow_votes,
        vote_options=req.vote_options,
    )
    topic_store.create(topic)
    return TopicOut(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        allow_opinions=topic.allow_opinions,
        allow_ideas=topic.allow_ideas,
        allow_votes=topic.allow_votes,
        vote_options=topic.vote_options,
    )


@app.get("/api/topics/{topic_id}/submissions", response_model=list[SubmissionOut])
def api_topic_submissions(topic_id: str) -> list[SubmissionOut]:
    """Get all submissions for a topic."""
    topic = topic_store.get(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    subs = submission_store.get_submissions(topic_id)
    return [
        SubmissionOut(
            id=s.id,
            submission_type=s.submission_type.value,
            content=s.content,
            submitted_at=s.submitted_at.isoformat(),
        )
        for s in subs
    ]


# ---------------------------------------------------------------------------
# Standing votes (Vote)
# ---------------------------------------------------------------------------


def _verify_or_403(req: VoteRequest):  # type: ignore[no-untyped-def]
    challenge = _challenges.get(req.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    verification = verify(challenge, req.signature, req.anonymous_id, registry)  # type: ignore[arg-type]
    if not verification.verified:
        raise HTTPException(
            status_code=403, detail=f"Verification failed: {verification.reason}"
        )
    return verification


def _tally_out(t) -> TallyOut:  # type: ignore[no-untyped-def]
    return TallyOut(
        topic_id=t.topic_id,
        at=t.at.isoformat(),
        counts=t.counts,
        standing=t.standing,
        ever_participated=t.ever_participated,
        withdrawn=t.withdrawn,
        changes=t.changes,
    )


@app.post("/api/vote", response_model=VoteEventOut)
def api_vote(req: VoteRequest) -> VoteEventOut:
    """Cast a standing vote, change it, or withdraw it (``choice`` null)."""
    verification = _verify_or_403(req)
    try:
        if req.choice is None:
            event = vote_ledger.withdraw(verification, req.topic_id, req.reason)
        else:
            event = vote_ledger.cast(verification, req.topic_id, req.choice, req.reason)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VoteEventOut(
        kind=event.kind,
        previous=event.previous,
        choice=event.choice,
        reason=event.reason,
        at=event.at.isoformat(),
    )


@app.get("/api/topics/{topic_id}/tally", response_model=TallyOut)
def api_topic_tally(topic_id: str) -> TallyOut:
    """Deterministic current tally, denominator included."""
    if topic_store.get(topic_id) is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return _tally_out(vote_ledger.tally(topic_id))


@app.get("/api/topics/{topic_id}/timeline", response_model=list[TallyOut])
def api_topic_timeline(topic_id: str) -> list[TallyOut]:
    """The living curve: a tally after every vote event."""
    if topic_store.get(topic_id) is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return [_tally_out(t) for t in vote_ledger.timeline(topic_id)]


@app.get("/api/topics/{topic_id}/migrations", response_model=list[MigrationOut])
def api_topic_migrations(topic_id: str) -> list[MigrationOut]:
    """Who moved where, and what they said changed their mind."""
    if topic_store.get(topic_id) is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return [
        MigrationOut(
            from_choice=m.from_choice,
            to_choice=m.to_choice,
            count=m.count,
            reasons=m.reasons,
        )
        for m in vote_ledger.migrations(topic_id)
    ]


# ---------------------------------------------------------------------------
# Propositions (framing variants)
# ---------------------------------------------------------------------------


@app.get("/api/propositions/suggestions", response_model=list[MergeSuggestionOut])
def api_merge_suggestions() -> list[MergeSuggestionOut]:
    """Pairs of open topics that look like the same question. Suggests only."""
    return [
        MergeSuggestionOut(
            topic_a=s.topic_a,
            topic_b=s.topic_b,
            score=s.score,
            shared_terms=s.shared_terms,
            shared_tags=s.shared_tags,
        )
        for s in suggest_merges(topic_store.list_open())
    ]


@app.post("/api/propositions/merge")
def api_merge(req: MergeRequest) -> dict[str, str]:
    """Merge wordings into one proposition. Every wording keeps its own tally."""
    try:
        pid = propositions.merge(req.topic_ids, req.reason, req.anonymous_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"proposition_id": pid}


@app.get("/api/topics/{topic_id}/proposition", response_model=PropositionOut)
def api_topic_proposition(topic_id: str) -> PropositionOut:
    """The proposition this topic belongs to: wordings, tallies, divergence."""
    if topic_store.get(topic_id) is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    view = propositions.view(topic_id)
    if view is None:
        raise HTTPException(
            status_code=404, detail="Topic is not part of a proposition"
        )
    return PropositionOut(
        proposition_id=view.proposition_id,
        variants=[
            FramingVariantOut(
                topic_id=v.topic_id, title=v.title, tally=_tally_out(v.tally)
            )
            for v in view.variants
        ],
        combined=_tally_out(view.combined),
        divergence=view.divergence,
        divergence_option=view.divergence_option,
        framing_matters=view.framing_matters,
    )


@app.post("/api/attention", response_model=AttentionOut)
def api_attention(req: AttentionRequest) -> AttentionOut:
    """*What needs attention?* — issues where flow should hand over to choice."""
    items = what_needs_attention(
        topic_store.list_open(),
        Interests(tags=req.tags, region=req.region),
        ledger=vote_ledger,
        voter_id=req.anonymous_id,
        registry=propositions,
    )
    return AttentionOut(
        items=[
            AttentionItemOut(
                topic_id=i.topic.id,
                title=i.topic.title,
                reasons=[r.value for r in i.reasons],
                explanations=i.explanations,
                score=i.score,
            )
            for i in items
        ],
        agenda_prompt=AGENDA_PROMPT,
    )


@app.get("/api/stats")
def api_stats() -> dict[str, int]:
    """Quick stats for the dashboard."""
    return {
        "enrolled_participants": registry.active_count,
        "total_topics": topic_store.count,
        "total_submissions": submission_store.total_count,
        "standing_votes": sum(
            vote_ledger.tally(t.id).standing for t in topic_store.list_open()
        ),
    }
