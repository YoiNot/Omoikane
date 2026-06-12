from __future__ import annotations

import uuid
from datetime import datetime

from omoikane.api.schemas import (
    ADRCreate,
    ADRResponse,
    ContextRequest,
    ContextResponse,
    MembershipCreate,
    MembershipResponse,
    MemoryCreate,
    MemoryResponse,
    ProjectCreate,
    ProjectResponse,
    SearchRequest,
    SearchResult,
    TeamCreate,
    TeamResponse,
    UserCreate,
    UserResponse,
)


def test_project_create():
    p = ProjectCreate(name="test", description="desc")
    assert p.name == "test"
    assert p.description == "desc"


def test_project_response():
    p = ProjectResponse(
        id=uuid.uuid4(), name="x", description="y", created_at=datetime.utcnow()
    )
    assert p.name == "x"


def test_memory_create():
    m = MemoryCreate(
        project_id=uuid.uuid4(),
        type="decision",
        title="title",
        content="content",
    )
    assert m.type == "decision"
    assert m.summary == ""


def test_memory_response_from_attributes():
    m = MemoryResponse(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        type="pattern",
        title="t",
        content="c",
        summary="s",
        source_type="github",
        source_url="",
        source_author="",
        created_at=datetime.utcnow(),
    )
    assert m.source_type == "github"


def test_search_request_defaults():
    s = SearchRequest(query="hello")
    assert s.project_id is None
    assert s.memory_type is None
    assert s.limit == 10


def test_search_result():
    mem = MemoryResponse(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        type="context",
        title="t",
        content="c",
        summary="s",
        source_type="",
        source_url="",
        source_author="",
        created_at=datetime.utcnow(),
    )
    sr = SearchResult(memory=mem, score=0.95, chunk_text="chunk")
    assert sr.score == 0.95


def test_context_request():
    cr = ContextRequest(task="do something", project_id=uuid.uuid4())
    assert cr.limit == 5


def test_adr_create():
    adr = ADRCreate(
        project_id=uuid.uuid4(),
        title="Use X",
        decision="Use X for Y",
    )
    assert adr.context == ""
    assert adr.alternatives == []


def test_adr_response():
    adr = ADRResponse(
        id=uuid.uuid4(),
        memory_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="t",
        context="c",
        decision="d",
        consequences="con",
        alternatives=["a"],
        status="accepted",
        participants=["p"],
        decided_at=None,
    )
    assert adr.status == "accepted"
    assert adr.alternatives == ["a"]


def test_team_create():
    t = TeamCreate(name="backend", slug="backend")
    assert t.slug == "backend"


def test_team_response():
    t = TeamResponse(
        id=uuid.uuid4(), name="x", slug="y", created_at=datetime.utcnow()
    )
    assert t.name == "x"


def test_user_create():
    u = UserCreate(email="a@b.com")
    assert u.name == ""


def test_user_response():
    u = UserResponse(
        id=uuid.uuid4(),
        email="a@b.com",
        name="A",
        avatar_url="",
        created_at=datetime.utcnow(),
    )
    assert u.email == "a@b.com"


def test_membership_create():
    m = MembershipCreate(user_id=uuid.uuid4())
    assert m.role == "member"


def test_membership_response():
    m = MembershipResponse(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        role="admin",
        created_at=datetime.utcnow(),
    )
    assert m.role == "admin"


def test_context_response():
    cr = ContextResponse(
        task="t",
        context_block="block",
        memories=[],
    )
    assert cr.memories == []
