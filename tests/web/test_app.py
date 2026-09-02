"""Tests for the FastAPI web application."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json

import pytest
from httpx import ASGITransport, AsyncClient

from opendemocracy.web.app import (
    app,
    registry,
    submission_store,
    topic_store,
    vote_ledger,
)
from opendemocracy.web.app import findings as finding_store
from opendemocracy.web.app import propositions as proposition_registry


@pytest.fixture(autouse=True)
def _reset_state() -> None:  # type: ignore[misc]
    """Reset in-memory stores between tests."""
    registry._records.clear()
    registry._pubkey_index.clear()
    submission_store._submissions.clear()
    submission_store._submitted.clear()
    vote_ledger._events.clear()
    vote_ledger._current.clear()
    proposition_registry.history.clear()
    finding_store._findings.clear()
    for t in list(topic_store._topics.values()):
        if t.id != "demo-ubi":
            del topic_store._topics[t.id]
        else:
            t.proposition_id = None
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


async def _enrolled(client: AsyncClient) -> dict[str, str]:
    res = await client.post("/api/enroll", json={"factors": ["fingerprint", "iris"]})
    return res.json()  # type: ignore[no-any-return]


async def _vote(
    client: AsyncClient,
    identity: dict[str, str],
    choice: str | None,
    reason: str | None = None,
    topic_id: str = "demo-ubi",
):  # type: ignore[no-untyped-def]
    ch = (
        await client.post(
            "/api/challenge", json={"anonymous_id": identity["anonymous_id"]}
        )
    ).json()
    sig = _hmac_sign(identity["public_key"], ch["nonce"])
    return await client.post(
        "/api/vote",
        json={
            "anonymous_id": identity["anonymous_id"],
            "challenge_id": ch["challenge_id"],
            "signature": sig,
            "topic_id": topic_id,
            "choice": choice,
            "reason": reason,
        },
    )


@pytest.mark.anyio()
async def test_standing_vote_cast_change_withdraw(client: AsyncClient) -> None:
    alice = await _enrolled(client)
    bob = await _enrolled(client)

    res = await _vote(client, alice, "Yes")
    assert res.status_code == 200
    assert res.json()["kind"] == "cast"

    await _vote(client, bob, "Yes")
    res = await _vote(client, alice, "No", reason="the cost report")
    assert res.json()["kind"] == "changed"
    assert res.json()["previous"] == "Yes"

    tally = (await client.get("/api/topics/demo-ubi/tally")).json()
    assert tally["counts"] == {"Yes": 1, "No": 1, "Needs more research": 0}
    assert tally["standing"] == 2
    assert tally["ever_participated"] == 2
    assert tally["changes"] == 1

    res = await _vote(client, bob, None, reason="undecided now")
    assert res.json()["kind"] == "withdrawn"
    tally = (await client.get("/api/topics/demo-ubi/tally")).json()
    assert tally["standing"] == 1
    assert tally["withdrawn"] == 1

    timeline = (await client.get("/api/topics/demo-ubi/timeline")).json()
    assert [t["standing"] for t in timeline] == [1, 2, 2, 1]

    moves = (await client.get("/api/topics/demo-ubi/migrations")).json()
    assert moves[0] == {
        "from_choice": "Yes",
        "to_choice": "No",
        "count": 1,
        "reasons": ["the cost report"],
    }
    assert moves[1]["to_choice"] is None

    stats = (await client.get("/api/stats")).json()
    assert stats["standing_votes"] == 1


@pytest.mark.anyio()
async def test_standing_vote_rejects_invalid_and_unverified(
    client: AsyncClient,
) -> None:
    alice = await _enrolled(client)
    res = await _vote(client, alice, "Maybe")
    assert res.status_code == 400
    assert "Invalid vote choice" in res.json()["detail"]

    res = await _vote(client, alice, None)
    assert res.status_code == 400
    assert "No standing vote" in res.json()["detail"]

    res = await client.post(
        "/api/vote",
        json={
            "anonymous_id": "nobody",
            "challenge_id": "missing",
            "signature": "x",
            "topic_id": "demo-ubi",
            "choice": "Yes",
        },
    )
    assert res.status_code == 404

    res = await client.get("/api/topics/nope/tally")
    assert res.status_code == 404


@pytest.mark.anyio()
async def test_attention_names_its_reasons(client: AsyncClient) -> None:
    from opendemocracy.models import Topic

    topic_store.create(Topic(id="housing-1", title="Rent cap", tags=["housing"]))
    res = await client.post("/api/attention", json={"tags": ["housing"]})
    assert res.status_code == 200
    body = res.json()
    assert "nobody has asked" in body["agenda_prompt"]
    ids = {i["topic_id"]: i for i in body["items"]}
    assert ids["housing-1"]["reasons"] == ["not_yet_heard"]
    assert "demo-ubi" not in ids  # not relevant, no vote of mine: silence

    # Once I've voted, that reason is gone.
    alice = await _enrolled(client)
    await _vote(client, alice, "Yes", topic_id="housing-1")
    res = await client.post(
        "/api/attention",
        json={"tags": ["housing"], "anonymous_id": alice["anonymous_id"]},
    )
    assert res.json()["items"] == []


@pytest.mark.anyio()
async def test_propositions_suggest_merge_and_view(client: AsyncClient) -> None:
    from opendemocracy.models import Topic

    topic_store.create(
        Topic(
            id="ban",
            title="Ban cars from the city centre",
            tags=["transport"],
            vote_options=["Yes", "No"],
        )
    )
    topic_store.create(
        Topic(
            id="free",
            title="Make the city centre car-free",
            tags=["transport"],
            vote_options=["Yes", "No"],
        )
    )
    sug = (await client.get("/api/propositions/suggestions")).json()
    assert [(s["topic_a"], s["topic_b"]) for s in sug] == [("ban", "free")]
    assert "centre" in sug[0]["shared_terms"]

    res = await client.get("/api/topics/ban/proposition")
    assert res.status_code == 404  # not merged yet

    res = await client.post(
        "/api/propositions/merge",
        json={"topic_ids": ["ban", "free"], "reason": "same question"},
    )
    assert res.status_code == 200
    pid = res.json()["proposition_id"]

    alice = await _enrolled(client)
    await _vote(client, alice, "Yes", topic_id="ban")
    await _vote(client, alice, "No", topic_id="free")  # latest stance wins in combined
    view = (await client.get("/api/topics/free/proposition")).json()
    assert view["proposition_id"] == pid
    assert [v["topic_id"] for v in view["variants"]] == ["ban", "free"]
    assert view["combined"]["counts"] == {"Yes": 0, "No": 1}
    assert view["combined"]["standing"] == 1
    assert view["framing_matters"] is False

    res = await client.post(
        "/api/propositions/merge", json={"topic_ids": ["ban", "demo-ubi"]}
    )
    assert res.status_code == 400


@pytest.mark.anyio()
async def test_findings_take_export_and_check(client: AsyncClient) -> None:
    from opendemocracy.models import Topic

    topic_store.create(
        Topic(id="rent", title="Rent cap", quorum=2, vote_options=["Yes", "No"])
    )
    alice = await _enrolled(client)
    bob = await _enrolled(client)
    await _vote(client, alice, "Yes", topic_id="rent")
    await _vote(client, bob, "No", topic_id="rent")
    await _vote(client, bob, "Yes", reason="the numbers", topic_id="rent")

    res = await client.post("/api/topics/rent/findings", json={"note": "Council, Sept"})
    assert res.status_code == 200
    f = res.json()
    assert f["rung"] == "quorum" and f["citable"] is True
    assert f["tally"]["counts"] == {"Yes": 2, "No": 0}
    assert f["migrations"][0]["reasons"] == ["the numbers"]
    assert alice["anonymous_id"] not in json.dumps(f)

    md = (await client.get(f"/api/findings/{f['finding_id']}/markdown")).text
    assert md.startswith("# Finding: Rent cap")
    assert f["content_hash"] in md

    # The world moves on; the finding still checks out.
    await _vote(client, alice, "No", topic_id="rent")
    check = (await client.post(f"/api/findings/{f['finding_id']}/check")).json()
    assert check == {
        "finding_id": f["finding_id"],
        "verified": True,
        "reproduced": True,
    }

    listed = (await client.get("/api/topics/rent/findings")).json()
    assert [x["finding_id"] for x in listed] == [f["finding_id"]]
    assert (await client.get("/api/findings/nope")).status_code == 404
    assert (await client.post("/api/topics/nope/findings", json={})).status_code == 404
