from __future__ import annotations

import asyncio
import uuid

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="omoikane", help="AI Workspace Memory Layer")
console = Console()


@app.command()
def init(repo: str = typer.Option(..., help="GitHub repository (e.g., owner/repo)")):
    """Initialize Omoikane for a project."""
    from omoikane.db.models import Project, async_session, init_db

    async def _init():
        await init_db()
        async with async_session() as session:
            project = Project(name=repo, description=f"GitHub: {repo}")
            session.add(project)
            await session.commit()
            await session.refresh(project)
            console.print(f"[green]Project created: {project.id}[/green]")
            console.print(f"[dim]Run `omoikane ingest --repo {repo}` to start.[/dim]")

    asyncio.run(_init())


@app.command()
def ingest(
    repo: str = typer.Option(..., help="GitHub repo (owner/repo)"),
    project_id: str = typer.Option(None, help="Project UUID to ingest into"),
):
    """Ingest data from GitHub."""
    from omoikane.db.models import Project, async_session, init_db
    from omoikane.ingestion.github import GitHubIngestor

    async def _ingest():
        await init_db()
        async with async_session() as session:
            if project_id:
                pid = uuid.UUID(project_id)
            else:
                result = await session.execute(
                    __import__("sqlalchemy").select(Project).where(Project.name == repo)
                )
                project = result.scalar_one_or_none()
                if not project:
                    msg = (
                        f"Project not found for {repo}. "
                        f"Run `omoikane init --repo {repo}` first."
                    )
                    console.print(f"[red]{msg}[/red]")
                    raise typer.Exit(1)
                pid = project.id

            console.print(f"[bold]Ingesting from {repo}...[/bold]")
            ingestor = GitHubIngestor()
            result = await ingestor.ingest_repo(repo, pid)

            commits = result["commits"]
            prs = result["prs"]
            issues = result["issues"]
            console.print(
                f"[green]Processed {commits} commits, {prs} PRs, "
                f"{issues} issues — {result['memories']} memories created[/green]"
            )

    asyncio.run(_ingest())


@app.command(name="ingest-slack")
def ingest_slack(
    channel: str = typer.Option(..., help="Slack channel ID"),
    project_id: str = typer.Option(..., help="Project UUID"),
    max_messages: int = typer.Option(100, help="Max messages to fetch"),
):
    """Ingest data from a Slack channel."""
    from omoikane.db.models import init_db
    from omoikane.ingestion.slack import SlackIngestor

    async def _ingest_slack():
        await init_db()
        console.print(f"[bold]Ingesting from Slack channel {channel}...[/bold]")
        ingestor = SlackIngestor()
        result = await ingestor.ingest_channel(
            channel_id=channel,
            project_id=uuid.UUID(project_id),
            max_messages=max_messages,
        )

        messages = result["messages"]
        decisions = result["decisions"]
        console.print(
            f"[green]Processed {messages} messages, "
            f"found {decisions} decisions — "
            f"{result['memories']} memories created[/green]"
        )

    asyncio.run(_ingest_slack())


@app.command(name="ingest-notion")
def ingest_notion(
    database: str = typer.Option(..., help="Notion database ID"),
    project_id: str = typer.Option(..., help="Project UUID"),
    max_pages: int = typer.Option(100, help="Max pages to fetch"),
):
    """Ingest data from a Notion database."""
    from omoikane.db.models import init_db
    from omoikane.ingestion.notion import NotionIngestor

    async def _ingest_notion():
        await init_db()
        console.print(f"[bold]Ingesting from Notion database {database}...[/bold]")
        ingestor = NotionIngestor()
        result = await ingestor.ingest_database(
            database_id=database,
            project_id=uuid.UUID(project_id),
            max_pages=max_pages,
        )

        pages = result["pages"]
        console.print(
            f"[green]Processed {pages} pages — "
            f"{result['memories']} memories created[/green]"
        )

    asyncio.run(_ingest_notion())


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    project_id: str = typer.Option(None, help="Filter by project UUID"),
    memory_type: str = typer.Option(None, help="Filter by memory type"),
    limit: int = typer.Option(10, help="Max results"),
):
    """Search project memories."""
    from omoikane.db.models import async_session, init_db
    from omoikane.search.engine import SearchEngine

    async def _search():
        await init_db()
        async with async_session() as session:
            engine = SearchEngine(session)
            pid = uuid.UUID(project_id) if project_id else None
            results = await engine.search(
                query=query,
                project_id=pid,
                memory_type=memory_type,
                limit=limit,
            )

            if not results:
                console.print("[dim]No results found.[/dim]")
                return

            table = Table(title=f"Search Results for: {query}")
            table.add_column("Type", style="cyan")
            table.add_column("Title", style="bold")
            table.add_column("Score", style="green")
            table.add_column("Source", style="dim")

            for r in results:
                table.add_row(
                    r.memory.type, r.memory.title,
                    f"{r.score:.2f}", r.memory.source_type,
                )

            console.print(table)

    asyncio.run(_search())


@app.command()
def context(
    task: str = typer.Argument(..., help="Task description"),
    project_id: str = typer.Option(..., help="Project UUID"),
    limit: int = typer.Option(5, help="Max memories to include"),
    output: str = typer.Option("text", help="Output format: text, markdown"),
):
    """Assemble context for an AI task."""
    from omoikane.db.models import async_session, init_db
    from omoikane.search.engine import SearchEngine

    async def _context():
        await init_db()
        async with async_session() as session:
            engine = SearchEngine(session)
            pid = uuid.UUID(project_id)
            context_block = await engine.assemble_context(
                task=task,
                project_id=pid,
                limit=limit,
            )
            console.print(context_block)

    asyncio.run(_context())


@app.command(name="adr")
def adr_command(
    action: str = typer.Argument(..., help="Action: create, list"),
    project_id: str = typer.Option(..., help="Project UUID"),
    title: str = typer.Option(None, help="ADR title"),
):
    """Manage Architecture Decision Records."""
    from omoikane.api.schemas import ADRCreate
    from omoikane.db.models import async_session, init_db

    async def _create_adr():
        await init_db()
        async with async_session() as session:
            from omoikane.search.engine import SearchEngine

            if not title:
                console.print("[red]Provide --title for ADR creation[/red]")
                raise typer.Exit(1)

            console.print(f"[bold]Creating ADR: {title}[/bold]")
            context_text = console.input("[dim]Context (why this decision?): [/dim]")
            decision_text = console.input("[dim]Decision (what was decided?): [/dim]")
            consequences_text = console.input("[dim]Consequences: [/dim]")

            data = ADRCreate(
                project_id=uuid.UUID(project_id),
                title=title,
                context=context_text,
                decision=decision_text,
                consequences=consequences_text,
            )

            engine = SearchEngine(session)
            content = (
                f"## Context\n{data.context}\n\n"
                f"## Decision\n{data.decision}\n\n"
                f"## Consequences\n{data.consequences}"
            )
            from omoikane.db.models import Decision, Memory

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
                status="accepted",
            )
            session.add(decision)
            await session.commit()

            await engine.store_embedding(memory.id, f"{data.title}\n\n{content}")

            console.print(f"[green]ADR created: {decision.id}[/green]")

    async def _list_adrs():
        await init_db()
        async with async_session() as session:
            from sqlalchemy import select

            from omoikane.db.models import Decision

            result = await session.execute(
                select(Decision)
                .where(Decision.project_id == uuid.UUID(project_id))
                .order_by(Decision.created_at.desc())
            )
            decisions = result.scalars().all()

            if not decisions:
                console.print("[dim]No ADRs found.[/dim]")
                return

            table = Table(title="Architecture Decision Records")
            table.add_column("Title", style="bold")
            table.add_column("Status", style="cyan")
            table.add_column("Decision", style="dim")

            for d in decisions:
                table.add_row(d.title, d.status, d.decision[:80])

            console.print(table)

    if action == "create":
        asyncio.run(_create_adr())
    elif action == "list":
        asyncio.run(_list_adrs())
    else:
        console.print(f"[red]Unknown action: {action}[/red]")


@app.command()
def mcp():
    """Start the MCP server (stdio transport)."""
    import asyncio

    from omoikane.mcp.server import run_mcp_server

    asyncio.run(run_mcp_server())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="API host"),
    port: int = typer.Option(8420, help="API port"),
):
    """Start the Omoikane API server."""
    import uvicorn

    from omoikane.api.app import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    app()
