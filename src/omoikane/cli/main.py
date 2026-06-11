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
):
    """Assemble context for an AI task."""
    from omoikane.db.models import async_session, init_db
    from omoikane.search.engine import SearchEngine

    async def _context():
        await init_db()
        async with async_session() as session:
            engine = SearchEngine(session)
            pid = uuid.UUID(project_id)
            results = await engine.search(query=task, project_id=pid, limit=limit)

            console.print(f"[bold]Context for: {task}[/bold]\n")
            for r in results:
                score = f"{r.score:.2f}"
                console.print(
                    f"[cyan][{r.memory.type}][/cyan] "
                    f"{r.memory.title} (score: {score})"
                )
                console.print(f"  {r.memory.content[:200]}...\n")

    asyncio.run(_context())


@app.command(name="adr")
def adr_command(
    action: str = typer.Argument(..., help="Action: create, list"),
    project_id: str = typer.Option(None, help="Project UUID"),
    title: str = typer.Option(None, help="ADR title"),
):
    """Manage Architecture Decision Records."""
    if action == "create":
        if not title:
            console.print("[red]Provide --title for ADR creation[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Creating ADR: {title}[/bold]")
        console.print("[dim]Interactive ADR creation coming soon.[/dim]")
    elif action == "list":
        console.print("[dim]ADR listing coming soon.[/dim]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")


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
