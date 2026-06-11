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
from omoikane.db.models import Decision, Memory, Project, get_session
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

    decision = Decision(
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
    session.add(decision)
    await session.commit()
    await session.refresh(decision)

    return ADRResponse(
        id=decision.id,
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
    result = await session.execute(
        select(Decision)
        .where(Decision.project_id == project_id)
        .order_by(Decision.created_at.desc())
    )
    decisions = result.scalars().all()
    return [
        ADRResponse(
            id=d.id,
            memory_id=d.memory_id,
            project_id=d.project_id,
            title=d.title,
            context=d.context,
            decision=d.decision,
            consequences=d.consequences,
            alternatives=d.alternatives or [],
            status=d.status,
            participants=d.participants or [],
            decided_at=d.decided_at,
        )
        for d in decisions
    ]


@router.post("/projects/{project_id}/links")
async def link_projects(
    project_id: uuid.UUID,
    target_id: uuid.UUID,
    relation: str = "related",
    session: SessionDep = Depends(get_session),  # noqa: B008
):
    from omoikane.db.models import ProjectLink

    link = ProjectLink(
        source_project_id=project_id,
        target_project_id=target_id,
        relation=relation,
    )
    session.add(link)
    await session.commit()
    return {"status": "linked", "source": project_id, "target": target_id}


@router.get("/projects/{project_id}/links")
async def list_links(project_id: uuid.UUID, session: SessionDep):
    from omoikane.db.models import ProjectLink

    result = await session.execute(
        select(ProjectLink).where(
            (ProjectLink.source_project_id == project_id)
            | (ProjectLink.target_project_id == project_id)
        )
    )
    links = result.scalars().all()
    return [
        {
            "id": str(link.id),
            "source": str(link.source_project_id),
            "target": str(link.target_project_id),
            "relation": link.relation,
        }
        for link in links
    ]


@router.post("/search/cross", response_model=list[SearchResult])
async def search_cross_project(
    data: SearchRequest,
    session: SessionDep,
):
    engine = SearchEngine(session)
    results = await engine.search_cross_project(
        query=data.query,
        project_id=data.project_id,
        memory_type=data.memory_type,
        limit=data.limit,
    )
    return results


@router.post("/context/cross", response_model=ContextResponse)
async def assemble_cross_context(
    data: ContextRequest,
    session: SessionDep,
):
    engine = SearchEngine(session)
    context_block = await engine.assemble_cross_project_context(
        task=data.task,
        project_id=data.project_id,
        limit=data.limit,
    )
    results = await engine.search_cross_project(
        query=data.task,
        project_id=data.project_id,
        limit=data.limit,
    )
    return ContextResponse(
        task=data.task,
        context_block=context_block,
        memories=[r.memory for r in results],
    )
