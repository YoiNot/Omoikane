# Omoikane

AI Workspace Memory Layer — persistent memory for AI-assisted development.

## Quick Start

```bash
# Install
pip install -e .

# Set environment variables
export OMOIKANE_DATABASE_URL="postgresql+asyncpg://omoikane:omoikane@localhost:5432/omoikane"
export OMOIKANE_OPENAI_API_KEY="sk-..."

# Initialize a project
omoikane init --repo owner/repo

# Ingest from GitHub
omoikane ingest --repo owner/repo

# Search memories
omoikane search "how does authentication work"

# Assemble context for AI
omoikane context --project-id <uuid> "implement rate limiting"
```

## Development

```bash
pip install -e ".[dev]"
ruff check src/
mypy src/
pytest
```

## License

MIT
