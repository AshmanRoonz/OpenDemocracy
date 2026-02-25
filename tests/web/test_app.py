"""Tests for the FastAPI web application."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod

import pytest
from httpx import ASGITransport, AsyncClient

from opendemocracy.web.app import app, registry, submission_store, topic_store


@pytest.fixture(autouse=True)
def _reset_state() -> None:  # type: ignore[misc]
    """Reset in-memory stores between tests."""
    registry._records.clear()
    registry._pubkey_index.clear()
    submission_store._submissions.clear()
    submission_store._submitted.clear()
    # Re-seed the demo topic if it got cleared.
    from opendemocracy.models import Topic

    if topic_store.get("demo-ubi") is None:
        topic_store.create(
            Topic(
                id="demo-ubi",
                title="Universal Basic Income",
                description="Should we implement UBI?",
                allow_opinions=True,
                allow_ideas=True,
                allow_votes=True,
                vote_options=["Yes", "No", "Needs more research"],
            )
        )


@pytest.fixture()
def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _hmac_sign(key: str, message: str) -> str:
    """Replicate the browser HMAC-SHA256 signing."""
    return hmac_mod.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


@pytest.mark.anyio()
async def test_index(client: AsyncClient) -> None:
    res = await client.get("/")
    assert res.status_code == 200
    assert "OpenDemocracy" in res.text


@pytest.mark.anyio()
async def test_enroll(client: AsyncClient) -> None:
    res = await client.post(
        "/api/enroll",
        json={"factors": ["fingerprint", "face"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["anonymous_id"]
    assert data["public_key"]
    assert data["private_key"]
    assert set(data["factors_enrolled"]) == {"fingerprint", "face"}


@pytest.mark.anyio()
async def test_enroll_rejects_single_factor(client: AsyncClient) -> None:
    res = await client.post(
        "/api/enroll",
        json={"factors": ["fingerprint"]},
    )
    assert res.status_code == 400


@pytest.mark.anyio()
async def test_list_topics(client: AsyncClient) -> None:
    res = await client.get("/api/topics")
    assert res.status_code == 200
    topics = res.json()
    assert any(t["id"] == "demo-ubi" for t in topics)


@pytest.mark.anyio()
async def test_full_flow_submit_vote(client: AsyncClient) -> None:
    """End-to-end: enroll -> challenge -> sign -> submit vote."""
    # Enroll
    enroll_res = await client.post(
        "/api/enroll",
        json={"factors": ["fingerprint", "iris"]},
    )
    identity = enroll_res.json()

    # Get challenge
    ch_res = await client.post(
        "/api/challenge",
        json={"anonymous_id": identity["anonymous_id"]},
    )
    assert ch_res.status_code == 200
    challenge = ch_res.json()

    # Sign with public key (matches server-side verification)
    signature = _hmac_sign(identity["public_key"], challenge["nonce"])

    # Submit vote
    sub_res = await client.post(
        "/api/submit",
        json={
            "anonymous_id": identity["anonymous_id"],
            "challenge_id": challenge["challenge_id"],
            "signature": signature,
            "topic_id": "demo-ubi",
            "submission_type": "vote",
            "content": "Yes",
        },
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["success"] is True


@pytest.mark.anyio()
async def test_duplicate_vote_blocked(client: AsyncClient) -> None:
    """Same person cannot vote twice on the same topic."""
    enroll_res = await client.post(
        "/api/enroll",
        json={"factors": ["face", "voice"]},
    )
    identity = enroll_res.json()

    # First vote
    ch1 = (
        await client.post(
            "/api/challenge",
            json={"anonymous_id": identity["anonymous_id"]},
        )
    ).json()
    sig1 = _hmac_sign(identity["public_key"], ch1["nonce"])
    res1 = await client.post(
        "/api/submit",
        json={
            "anonymous_id": identity["anonymous_id"],
            "challenge_id": ch1["challenge_id"],
            "signature": sig1,
            "topic_id": "demo-ubi",
            "submission_type": "vote",
            "content": "Yes",
        },
    )
    assert res1.status_code == 200

    # Second vote — should be blocked
    ch2 = (
        await client.post(
            "/api/challenge",
            json={"anonymous_id": identity["anonymous_id"]},
        )
    ).json()
    sig2 = _hmac_sign(identity["public_key"], ch2["nonce"])
    res2 = await client.post(
        "/api/submit",
        json={
            "anonymous_id": identity["anonymous_id"],
            "challenge_id": ch2["challenge_id"],
            "signature": sig2,
            "topic_id": "demo-ubi",
            "submission_type": "vote",
            "content": "No",
        },
    )
    assert res2.status_code == 400
    assert "already submitted" in res2.json()["detail"]


@pytest.mark.anyio()
async def test_submit_without_enrollment_fails(client: AsyncClient) -> None:
    res = await client.post(
        "/api/challenge",
        json={"anonymous_id": "nonexistent"},
    )
    assert res.status_code == 404


@pytest.mark.anyio()
async def test_get_submissions(client: AsyncClient) -> None:
    # Enroll and submit an opinion
    identity = (
        await client.post(
            "/api/enroll",
            json={"factors": ["fingerprint", "face"]},
        )
    ).json()
    ch = (
        await client.post(
            "/api/challenge",
            json={"anonymous_id": identity["anonymous_id"]},
        )
    ).json()
    sig = _hmac_sign(identity["public_key"], ch["nonce"])
    await client.post(
        "/api/submit",
        json={
            "anonymous_id": identity["anonymous_id"],
            "challenge_id": ch["challenge_id"],
            "signature": sig,
            "topic_id": "demo-ubi",
            "submission_type": "opinion",
            "content": "I think UBI would help everyone",
        },
    )

    # Fetch submissions
    res = await client.get("/api/topics/demo-ubi/submissions")
    assert res.status_code == 200
    subs = res.json()
    assert len(subs) == 1
    assert subs[0]["content"] == "I think UBI would help everyone"


@pytest.mark.anyio()
async def test_stats(client: AsyncClient) -> None:
    res = await client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "enrolled_participants" in data
    assert "total_submissions" in data
