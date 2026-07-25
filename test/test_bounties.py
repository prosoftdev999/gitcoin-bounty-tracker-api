from datetime import datetime, timedelta, timezone


def create_payload(title="Build Web3 analytics API", reward=500, status="open"):
    return {
        "title": title,
        "platform": "Gitcoin",
        "reward_usd": reward,
        "status": status,
        "url": "https://example.com/bounty",
        "skills": "Python, FastAPI, Web3",
        "notes": "Prepare proposal and implementation plan.",
        "deadline": (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).isoformat(),
    }


def test_requires_authentication(client):
    response = client.get("/bounties")
    assert response.status_code == 401


def test_create_list_update_delete(client, auth_headers):
    created = client.post(
        "/bounties",
        json=create_payload(),
        headers=auth_headers,
    )
    assert created.status_code == 201
    bounty_id = created.json()["id"]

    listed = client.get("/bounties", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    updated = client.patch(
        f"/bounties/{bounty_id}",
        json={"status": "applied"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "applied"

    deleted = client.delete(
        f"/bounties/{bounty_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204


def test_search_filter_pagination_and_stats(client, auth_headers):
    client.post(
        "/bounties",
        json=create_payload("Python indexer", 300, "open"),
        headers=auth_headers,
    )
    client.post(
        "/bounties",
        json=create_payload("React dashboard", 700, "won"),
        headers=auth_headers,
    )

    response = client.get(
        "/bounties?search=Python&min_reward=100&max_reward=500",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1

    stats = client.get("/bounties/stats", headers=auth_headers)
    assert stats.status_code == 200
    assert stats.json()["total_bounties"] == 2
    assert stats.json()["won_reward_usd"] == 700


def test_csv_export(client, auth_headers):
    client.post(
        "/bounties",
        json=create_payload(),
        headers=auth_headers,
    )
    response = client.get("/bounties/export.csv", headers=auth_headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Build Web3 analytics API" in response.text


def test_past_deadline_is_rejected(client, auth_headers):
    payload = create_payload()
    payload["deadline"] = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).isoformat()

    response = client.post(
        "/bounties",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 422
