from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    resp = await client.post("/v1/projects", json={"name": "my-project", "description": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "my-project"
    assert data["description"] == "test"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient, project_id: uuid.UUID):
    resp = await client.get(f"/v1/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-project"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v1/projects/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_memory(client: AsyncClient, project_id: uuid.UUID):
    resp = await client.post("/v1/memories", json={
        "project_id": str(project_id),
        "type": "decision",
        "title": "Use asyncpg",
        "content": "We chose asyncpg for async PostgreSQL support.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Use asyncpg"
    assert data["type"] == "decision"
    assert data["project_id"] == str(project_id)


@pytest.mark.asyncio
async def test_list_memories(client: AsyncClient, project_id: uuid.UUID):
    await client.post("/v1/memories", json={
        "project_id": str(project_id),
        "type": "context",
        "title": "Auth flow",
        "content": "JWT-based auth with refresh tokens.",
    })
    resp = await client.get(f"/v1/projects/{project_id}/memories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(m["title"] == "Auth flow" for m in data)


@pytest.mark.asyncio
async def test_create_adr(client: AsyncClient, project_id: uuid.UUID):
    resp = await client.post("/v1/decisions", json={
        "project_id": str(project_id),
        "title": "Use PostgreSQL",
        "context": "Need a reliable database",
        "decision": "PostgreSQL with pgvector",
        "consequences": "Need to manage pgvector extension",
        "alternatives": ["MongoDB", "SQLite"],
        "participants": ["alice", "bob"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Use PostgreSQL"
    assert data["decision"] == "PostgreSQL with pgvector"
    assert data["status"] == "accepted"
    assert data["alternatives"] == ["MongoDB", "SQLite"]


@pytest.mark.asyncio
async def test_list_adrs(client: AsyncClient, project_id: uuid.UUID):
    await client.post("/v1/decisions", json={
        "project_id": str(project_id),
        "title": "ADR for caching",
        "decision": "Use Redis",
    })
    resp = await client.get(f"/v1/decisions/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_link_projects(client: AsyncClient, project_id: uuid.UUID):
    resp2 = await client.post("/v1/projects", json={"name": "other-project"})
    other_id = resp2.json()["id"]

    resp = await client.post(
        f"/v1/projects/{project_id}/links",
        params={"target_id": other_id, "relation": "depends-on"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "linked"


@pytest.mark.asyncio
async def test_list_links(client: AsyncClient, project_id: uuid.UUID):
    resp2 = await client.post("/v1/projects", json={"name": "linked-project"})
    other_id = resp2.json()["id"]

    await client.post(
        f"/v1/projects/{project_id}/links",
        params={"target_id": other_id},
    )
    resp = await client.get(f"/v1/projects/{project_id}/links")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_create_team(client: AsyncClient):
    resp = await client.post("/v1/teams", json={"name": "backend", "slug": "backend"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "backend"
    assert data["slug"] == "backend"


@pytest.mark.asyncio
async def test_get_team(client: AsyncClient):
    resp = await client.post("/v1/teams", json={"name": "frontend", "slug": "frontend"})
    team_id = resp.json()["id"]

    resp = await client.get(f"/v1/teams/{team_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "frontend"


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    resp = await client.post("/v1/users", json={"email": "alice@example.com", "name": "Alice"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["name"] == "Alice"


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient):
    resp = await client.post("/v1/users", json={"email": "bob@example.com", "name": "Bob"})
    user_id = resp.json()["id"]

    resp = await client.get(f"/v1/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_add_member(client: AsyncClient):
    team_resp = await client.post("/v1/teams", json={"name": "dev", "slug": "dev"})
    team_id = team_resp.json()["id"]

    user_resp = await client.post("/v1/users", json={"email": "charlie@example.com"})
    user_id = user_resp.json()["id"]

    resp = await client.post(f"/v1/teams/{team_id}/members", json={
        "user_id": user_id,
        "role": "admin",
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient):
    team_resp = await client.post("/v1/teams", json={"name": "qa", "slug": "qa"})
    team_id = team_resp.json()["id"]

    user_resp = await client.post("/v1/users", json={"email": "dave@example.com"})
    user_id = user_resp.json()["id"]

    await client.post(f"/v1/teams/{team_id}/members", json={"user_id": user_id})

    resp = await client.get(f"/v1/teams/{team_id}/members")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, project_id: uuid.UUID):
    mock_search = patch(
        "omoikane.search.engine.SearchEngine.search",
        new_callable=AsyncMock,
        return_value=[],
    )
    with mock_search:
        resp = await client.post("/v1/search", json={
            "query": "nonexistent topic",
            "project_id": str(project_id),
        })
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_context_no_results(client: AsyncClient, project_id: uuid.UUID):
    mock_search = patch(
        "omoikane.search.engine.SearchEngine.search",
        new_callable=AsyncMock,
        return_value=[],
    )
    with mock_search:
        resp = await client.post("/v1/context", json={
            "task": "something unrelated",
            "project_id": str(project_id),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "task" in data
        assert "context_block" in data
