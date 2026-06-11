# Contributing to Omoikane

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/yoi/omoikane.git
cd omoikane

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Set up database (requires PostgreSQL with pgvector)
docker run -d --name omoikane-pg \
  -e POSTGRES_USER=omoikane \
  -e POSTGRES_PASSWORD=omoikane \
  -e POSTGRES_DB=omoikane \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Configure
export OMOIKANE_DATABASE_URL="postgresql+asyncpg://omoikane:omoikane@localhost:5432/omoikane"
export OMOIKANE_OPENAI_API_KEY="sk-..."
```

## Code Style

- Python 3.11+
- Formatter/Linter: `ruff check src/`
- Type checker: `mypy src/omoikane`
- Max line length: 100 characters

## Project Structure

```
src/omoikane/
├── api/          # FastAPI routes and schemas
├── cli/          # Typer CLI commands
├── config/       # Settings (pydantic-settings)
├── db/           # SQLAlchemy models
├── ingestion/    # GitHub, Slack, Notion integrations
├── mcp/          # MCP protocol server
├── search/       # Semantic search engine
└── web/          # Web dashboard
```

## Making Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run linter and type checker
5. Commit with a clear message
6. Push and create a Pull Request

## Commit Messages

Use conventional commits:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code restructuring
- `test:` adding tests
- `chore:` maintenance

Examples:
```
feat: add Notion ingestion support
fix: handle empty search results
docs: update README quickstart
```

## Adding a New Integration

1. Create `src/omoikane/ingestion/your_source.py`
2. Implement the ingestor class with `ingest_*` method
3. Add CLI command in `src/omoikane/cli/main.py`
4. Add API endpoint in `src/omoikane/api/routes.py`
5. Update README with usage instructions

## Questions?

Open a GitHub issue for discussion.
