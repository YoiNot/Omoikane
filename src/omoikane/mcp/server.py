from __future__ import annotations

import uuid
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from omoikane.db.models import async_session, init_db
from omoikane.search.engine import SearchEngine


def create_mcp_server() -> Server:
    server = Server("omoikane")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_memories",
                description=(
                    "Search project memories using semantic search. "
                    "Returns relevant decisions, patterns, and context."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID to search within",
                        },
                        "memory_type": {
                            "type": "string",
                            "description": "Filter by type",
                            "enum": ["decision", "pattern", "constraint", "context", "discussion"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query", "project_id"],
                },
            ),
            Tool(
                name="assemble_context",
                description=(
                    "Assemble relevant context for an AI task. "
                    "Returns a structured context block with the most relevant memories."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Description of the task or question",
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max memories to include (default 5)",
                            "default": 5,
                        },
                    },
                    "required": ["task", "project_id"],
                },
            ),
            Tool(
                name="create_memory",
                description=(
                    "Create a new memory in the project. "
                    "Use this to store important decisions, patterns, or context."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID",
                        },
                        "type": {
                            "type": "string",
                            "description": "Memory type",
                            "enum": ["decision", "pattern", "constraint", "context", "discussion"],
                        },
                        "title": {
                            "type": "string",
                            "description": "Short title for the memory",
                        },
                        "content": {
                            "type": "string",
                            "description": "Full content in markdown",
                        },
                        "summary": {
                            "type": "string",
                            "description": "One-line summary",
                        },
                    },
                    "required": ["project_id", "type", "title", "content"],
                },
            ),
            Tool(
                name="create_adr",
                description=(
                    "Create an Architecture Decision Record (ADR). "
                    "Use this to document important technical decisions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID",
                        },
                        "title": {
                            "type": "string",
                            "description": "Decision title",
                        },
                        "context": {
                            "type": "string",
                            "description": "Why this decision was needed",
                        },
                        "decision": {
                            "type": "string",
                            "description": "What was decided",
                        },
                        "consequences": {
                            "type": "string",
                            "description": "Expected outcomes of this decision",
                        },
                        "alternatives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Alternatives that were considered",
                        },
                    },
                    "required": ["project_id", "title", "decision"],
                },
            ),
            Tool(
                name="list_memories",
                description="List all memories in a project, ordered by recency.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID",
                        },
                        "memory_type": {
                            "type": "string",
                            "description": "Filter by type",
                            "enum": ["decision", "pattern", "constraint", "context", "discussion"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 20)",
                            "default": 20,
                        },
                    },
                    "required": ["project_id"],
                },
            ),
            Tool(
                name="list_adrs",
                description="List all Architecture Decision Records in a project.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID",
                        },
                    },
                    "required": ["project_id"],
                },
            ),
            Tool(
                name="link_projects",
                description="Link two projects for cross-project memory sharing.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_project_id": {
                            "type": "string",
                            "description": "Source project UUID",
                        },
                        "target_project_id": {
                            "type": "string",
                            "description": "Target project UUID",
                        },
                        "relation": {
                            "type": "string",
                            "description": "Relation type (default: related)",
                            "default": "related",
                        },
                    },
                    "required": ["source_project_id", "target_project_id"],
                },
            ),
            Tool(
                name="search_cross_project",
                description=(
                    "Search across linked projects. "
                    "Finds memories from the project and all linked projects."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID (searches linked projects too)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query", "project_id"],
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        await init_db()
        async with async_session() as session:
            engine = SearchEngine(session)

            if name == "search_memories":
                results = await engine.search(
                    query=arguments["query"],
                    project_id=uuid.UUID(arguments["project_id"]),
                    memory_type=arguments.get("memory_type"),
                    limit=arguments.get("limit", 10),
                )
                output = []
                for r in results:
                    output.append(
                        f"[{r.memory.type}] {r.memory.title} "
                        f"(score: {r.score:.2f})\n{r.memory.content}\n"
                    )
                return [
                    TextContent(
                        type="text",
                        text="\n---\n".join(output) or "No results found.",
                    )
                ]

            elif name == "assemble_context":
                context_block = await engine.assemble_context(
                    task=arguments["task"],
                    project_id=uuid.UUID(arguments["project_id"]),
                    limit=arguments.get("limit", 5),
                )
                return [TextContent(type="text", text=context_block)]

            elif name == "create_memory":
                from omoikane.db.models import Memory

                memory = Memory(
                    project_id=uuid.UUID(arguments["project_id"]),
                    type=arguments["type"],
                    title=arguments["title"],
                    content=arguments["content"],
                    summary=arguments.get("summary", ""),
                )
                session.add(memory)
                await session.flush()
                await engine.store_embedding(
                    memory.id,  # type: ignore[arg-type]
                    f"{arguments['title']}\n\n{arguments['content']}",
                )
                await session.commit()
                return [TextContent(type="text", text=f"Memory created: {memory.id}")]

            elif name == "create_adr":
                from omoikane.db.models import Decision, Memory

                content = (
                    f"## Context\n{arguments.get('context', '')}\n\n"
                    f"## Decision\n{arguments['decision']}\n\n"
                    f"## Consequences\n{arguments.get('consequences', '')}"
                )
                memory = Memory(
                    project_id=uuid.UUID(arguments["project_id"]),
                    type="decision",
                    title=arguments["title"],
                    content=content,
                    summary=arguments["decision"],
                )
                session.add(memory)
                await session.flush()

                decision = Decision(
                    memory_id=memory.id,
                    project_id=uuid.UUID(arguments["project_id"]),
                    title=arguments["title"],
                    context=arguments.get("context", ""),
                    decision=arguments["decision"],
                    consequences=arguments.get("consequences", ""),
                    alternatives=arguments.get("alternatives", []),
                    status="accepted",
                )
                session.add(decision)
                await session.commit()
                await engine.store_embedding(memory.id, f"{arguments['title']}\n\n{content}")  # type: ignore[arg-type]
                return [TextContent(type="text", text=f"ADR created: {decision.id}")]

            elif name == "list_memories":
                from sqlalchemy import select

                from omoikane.db.models import Memory

                stmt = (
                    select(Memory)
                    .where(Memory.project_id == uuid.UUID(arguments["project_id"]))
                )
                if arguments.get("memory_type"):
                    stmt = stmt.where(Memory.type == arguments["memory_type"])
                stmt = stmt.order_by(Memory.created_at.desc()).limit(
                    arguments.get("limit", 20)
                )
                result = await session.execute(stmt)
                memories = result.scalars().all()

                if not memories:
                    return [TextContent(type="text", text="No memories found.")]

                lines = []
                for m in memories:
                    lines.append(f"[{m.type}] {m.title}\n{m.content[:200]}...\n")
                return [TextContent(type="text", text="\n---\n".join(lines))]

            elif name == "list_adrs":
                from sqlalchemy import select

                from omoikane.db.models import Decision

                result = await session.execute(
                    select(Decision)
                    .where(Decision.project_id == uuid.UUID(arguments["project_id"]))
                    .order_by(Decision.created_at.desc())
                )
                decisions = result.scalars().all()

                if not decisions:
                    return [TextContent(type="text", text="No ADRs found.")]

                lines = []
                for d in decisions:
                    lines.append(
                        f"## {d.title}\nStatus: {d.status}\n"  # type: ignore[attr-defined]
                        f"Decision: {d.decision}\n"  # type: ignore[attr-defined]
                    )
                return [TextContent(type="text", text="\n---\n".join(lines))]

            elif name == "link_projects":
                from omoikane.db.models import ProjectLink

                link = ProjectLink(
                    source_project_id=uuid.UUID(arguments["source_project_id"]),
                    target_project_id=uuid.UUID(arguments["target_project_id"]),
                    relation=arguments.get("relation", "related"),
                )
                session.add(link)
                await session.commit()
                return [
                    TextContent(
                        type="text",
                        text=(
                            f"Linked projects: "
                            f"{arguments['source_project_id']} <-> "
                            f"{arguments['target_project_id']}"
                        ),
                    )
                ]

            elif name == "search_cross_project":
                results = await engine.search_cross_project(
                    query=arguments["query"],
                    project_id=uuid.UUID(arguments["project_id"]),
                    limit=arguments.get("limit", 10),
                )
                output = []
                for r in results:
                    output.append(
                        f"[{r.memory.type}] {r.memory.title} "
                        f"(score: {r.score:.2f}, "
                        f"project: {str(r.memory.project_id)[:8]})\n"
                        f"{r.memory.content}\n"
                    )
                return [
                    TextContent(
                        type="text",
                        text="\n---\n".join(output) or "No results found.",
                    )
                ]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def run_mcp_server() -> None:
    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
