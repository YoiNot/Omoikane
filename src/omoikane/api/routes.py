from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omoikane.api.schemas import (
    ADRCreate,
    ADRResponse,
    ContextRequest,
    ContextResponse,
    MemoryCreate,
    MemoryResponse,
    ProjectCreate,
    ProjectResponse,
    SearchRequest,
    SearchResult,
)
from omoikane.db.models import Memory, Project, get_session
from omoikane.search.engine import SearchEngine

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/projects", response_model=ProjectResponse)
async def create_project(data: ProjectCreate, session: SessionDep):
    project = Project(name=data.name, description=data.description)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, session: SessionDep):
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/memories", response_model=MemoryResponse)
async def create_memory(data: MemoryCreate, session: SessionDep):
    memory = Memory(
        project_id=data.project_id,
        type=data.type,
        title=data.title,
        content=data.content,
        summary=data.summary,
        source_type=data.source_type,
        source_url=data.source_url,
        source_author=data.source_author,
    )
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory


@router.get("/projects/{project_id}/memories", response_model=list[MemoryResponse])
async def list_memories(project_id: uuid.UUID, session: SessionDep):
    result = await session.execute(
        select(Memory)
        .where(Memory.project_id == project_id)
        .order_by(Memory.created_at.desc())
    )
    return result.scalars().all()


@router.post("/search", response_model=list[SearchResult])
async def search_memories(data: SearchRequest, session: SessionDep):
    engine = SearchEngine(session)
    results = await engine.search(
        query=data.query,
        project_id=data.project_id,
        memory_type=data.memory_type,
        limit=data.limit,
    )
    return results


@router.post("/context", response_model=ContextResponse)
async def assemble_context(data: ContextRequest, session: SessionDep):
    engine = SearchEngine(session)
    results = await engine.search(
        query=data.task,
        project_id=data.project_id,
        limit=data.limit,
    )
    context_lines = [f"## Task: {data.task}\n"]
    for r in results:
        context_lines.append(f"### [{r.memory.type}] {r.memory.title}")
        context_lines.append(f"Score: {r.score:.2f}")
        context_lines.append(f"\n{r.memory.content}\n")
    context_block = "\n".join(context_lines)
    return ContextResponse(
        task=data.task,
        context_block=context_block,
        memories=[r.memory for r in results],
    )


@router.post("/decisions", response_model=ADRResponse)
async def create_adr(data: ADRCreate, session: SessionDep):
    content = (
        f"## Context\n{data.context}\n\n"
        f"## Decision\n{data.decision}\n\n"
        f"## Consequences\n{data.consequences}"
    )
    memory = Memory(
        project_id=data.project_id,
        type="decision",
        title=data.title,
        content=content,
        summary=data.decision,
    )
    session.add(memory)
    await session.flush()

    import sqlalchemy as sa

    from omoikane.db.models import Base

    adr = sa.Table("decisions", Base.metadata, autoload_with=session.bind)
    insert_stmt = adr.insert().values(
        memory_id=memory.id,
        project_id=data.project_id,
        title=data.title,
        context=data.context,
        decision=data.decision,
        consequences=data.consequences,
        alternatives=data.alternatives,
        status="accepted",
        participants=data.participants,
    )
    result = await session.execute(insert_stmt.returning(adr))
    row = result.fetchone()
    await session.commit()

    return ADRResponse(
        id=row["id"],
        memory_id=memory.id,
        project_id=data.project_id,
        title=data.title,
        context=data.context,
        decision=data.decision,
        consequences=data.consequences,
        alternatives=data.alternatives,
        status="accepted",
        participants=data.participants,
        decided_at=None,
    )


@router.get("/decisions/{project_id}", response_model=list[ADRResponse])
async def list_adrs(project_id: uuid.UUID, session: SessionDep):
    import sqlalchemy as sa

    from omoikane.db.models import Base

    adr = sa.Table("decisions", Base.metadata, autoload_with=session.bind)
    result = await session.execute(
        select(adr)
        .where(adr.c.project_id == project_id)
        .order_by(adr.c.decided_at.desc())
    )
    rows = result.fetchall()
    return [
        ADRResponse(
            id=row["id"],
            memory_id=row["memory_id"],
            project_id=row["project_id"],
            title=row["title"],
            context=row["context"] or "",
            decision=row["decision"],
            consequences=row["consequences"] or "",
            alternatives=row["alternatives"] or [],
            status=row["status"],
            participants=row["participants"] or [],
            decided_at=row["decided_at"],
        )
        for row in rows
    ]
