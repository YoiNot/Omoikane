from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryCreate(BaseModel):
    project_id: uuid.UUID
    type: str
    title: str
    content: str
    summary: str = ""
    source_type: str = ""
    source_url: str = ""
    source_author: str = ""


class MemoryResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    type: str
    title: str
    content: str
    summary: str
    source_type: str
    source_url: str
    source_author: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str
    project_id: uuid.UUID | None = None
    memory_type: str | None = None
    limit: int = 10


class SearchResult(BaseModel):
    memory: MemoryResponse
    score: float
    chunk_text: str


class ContextRequest(BaseModel):
    task: str
    project_id: uuid.UUID
    limit: int = 5


class ContextResponse(BaseModel):
    task: str
    context_block: str
    memories: list[MemoryResponse]


class ADRCreate(BaseModel):
    project_id: uuid.UUID
    title: str
    context: str = ""
    decision: str
    consequences: str = ""
    alternatives: list[str] = []
    participants: list[str] = []


class ADRResponse(BaseModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    context: str
    decision: str
    consequences: str
    alternatives: list[str]
    status: str
    participants: list[str]
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str
    slug: str


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    name: str = ""


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    avatar_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MembershipCreate(BaseModel):
    user_id: uuid.UUID
    role: str = "member"


class MembershipResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    team_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
