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
from opendemocracy.participation.submissions import SubmissionStore
from opendemocracy.participation.topics import TopicStore

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


@app.get("/api/stats")
def api_stats() -> dict[str, int]:
    """Quick stats for the dashboard."""
    return {
        "enrolled_participants": registry.active_count,
        "total_topics": topic_store.count,
        "total_submissions": submission_store.total_count,
    }
