"""Smoke tests for API routes: happy path per endpoint."""

from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


async def test_create_and_list_people(client: AsyncClient) -> None:
    resp = await client.post("/api/people", json={"name": "Alice", "seniority": "P2"})
    assert resp.status_code == 201
    person = resp.json()
    assert person["name"] == "Alice"
    assert person["seniority"] == "P2"

    resp = await client.get("/api/people")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Alice" in names


async def test_get_person_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/people/nonexistent")
    assert resp.status_code == 404


async def test_add_observation(client: AsyncClient) -> None:
    person_resp = await client.post("/api/people", json={"name": "Bob"})
    person_id = person_resp.json()["id"]

    resp = await client.post(
        "/api/observations",
        json={"person_id": person_id, "text": "Doing great.", "tags": ["growth"]},
    )
    assert resp.status_code == 201
    obs = resp.json()
    assert obs["person_id"] == person_id
    assert "growth" in obs["tags"]


async def test_log_one_on_one(client: AsyncClient) -> None:
    person_resp = await client.post("/api/people", json={"name": "Carla"})
    person_id = person_resp.json()["id"]

    resp = await client.post(
        "/api/one-on-ones",
        json={
            "person_id": person_id,
            "scheduled_date": "2026-04-15",
            "notes": "Good meeting.",
            "action_items": [{"text": "Follow up on PR", "owner_role": "manager"}],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["action_items_created"] == 1


async def test_complete_action_item(client: AsyncClient) -> None:
    person_resp = await client.post("/api/people", json={"name": "Dimitri"})
    person_id = person_resp.json()["id"]

    await client.post(
        "/api/one-on-ones",
        json={
            "person_id": person_id,
            "scheduled_date": "2026-04-15",
            "action_items": [{"text": "Task to complete"}],
        },
    )
    items_resp = await client.get(f"/api/action-items?person_id={person_id}")
    items = items_resp.json()
    assert len(items) == 1

    complete_resp = await client.post(f"/api/action-items/{items[0]['id']}/complete")
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "done"


async def test_update_allocation(client: AsyncClient) -> None:
    person_resp = await client.post("/api/people", json={"name": "Eve"})
    person_id = person_resp.json()["id"]

    resp = await client.post(
        "/api/allocations",
        json={"person_id": person_id, "type": "client", "client_or_project": "AcmeCorp"},
    )
    assert resp.status_code == 201
    assert resp.json()["client_or_project"] == "AcmeCorp"
