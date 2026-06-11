# Omoikane

**The persistent memory layer for AI-assisted development.**

Modern developers use Cursor, Claude Code, Codex, ChatGPT, GitHub, Notion, Slack, and other tools. Each tool holds part of the project's knowledge — but no single tool has the full picture.

Omoikane connects them all. It captures decisions, patterns, and context from your tools, then provides semantic search and context assembly so you never have to re-explain your project.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   GitHub    │────▶│  Omoikane   │────▶│  AI Tools   │
│   Slack     │────▶│  Memory     │────▶│  Cursor     │
│   Notion    │────▶│  Layer      │────▶│  Claude     │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Features

- **Semantic Search** — Find decisions, patterns, and context using natural language
- **Context Assembly** — Auto-assemble relevant memories for AI tasks
- **Architecture Decision Records** — Create and query ADRs
- **Cross-Project Memory** — Link projects and search across them
- **MCP Protocol** — Native integration with Claude, Cursor, and compatible tools
- **VS Code Extension** — Search and create memories from your editor
- **Multi-Source Ingestion** — GitHub, Slack, Notion, and more

## Quick Start

### 1. Install

```bash
pip install omoikane
```

### 2. Set up PostgreSQL with pgvector

```bash
# Using Docker
docker run -d --name omoikane-pg \
  -e POSTGRES_USER=omoikane \
  -e POSTGRES_PASSWORD=omoikane \
  -e POSTGRES_DB=omoikane \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

### 3. Configure

```bash
export OMOIKANE_DATABASE_URL="postgresql+asyncpg://omoikane:omoikane@localhost:5432/omoikane"
export OMOIKANE_OPENAI_API_KEY="sk-..."  # For embeddings
```

### 4. Initialize and ingest

```bash
# Create a project
omoikane init --repo owner/repo

# Ingest from GitHub
omoikane ingest --repo owner/repo

# Search your project's memories
omoikane search "how does authentication work"

# Assemble context for an AI task
omoikane context --project-id <uuid> "implement rate limiting"
```

## Usage

### Search memories

```bash
omoikane search "why did we choose postgres"
# ┌──────────┬──────────────────────────────────────┬───────┬────────┐
# │ Type     │ Title                                │ Score │ Source │
# ├──────────┼──────────────────────────────────────┼───────┼────────┤
# │ decision │ Use PostgreSQL for primary database   │ 0.94  │ github │
# │ pattern  │ Connection pooling with pgBouncer    │ 0.87  │ github │
# └──────────┴──────────────────────────────────────┴───────┴────────┘
```

### Create Architecture Decision Records

```bash
omoikane adr create --project-id <uuid> --title "Use Redis for caching"
# Context: Why this decision was needed?
# Decision: What was decided?
# Consequences: Expected outcomes?
```

### Link projects for cross-project memory

```bash
# Link two projects
omoikane link --source <uuid1> --target <uuid2>

# Search across linked projects
omoikane search-all "how did we solve rate limiting"
```

### MCP Integration (Claude, Cursor)

Add to your MCP config:

```json
{
  "mcpServers": {
    "omoikane": {
      "command": "omoikane",
      "args": ["mcp"]
    }
  }
}
```

### VS Code Extension

Install from the `extensions/vscode` directory:

```bash
cd extensions/vscode
npm install
npm run compile
```

Then press `Cmd+Shift+P` and search for "Omoikane".

## API

Start the API server:

```bash
omoikane serve
```

Endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/projects` | Create project |
| GET | `/v1/projects/:id` | Get project |
| POST | `/v1/memories` | Create memory |
| GET | `/v1/projects/:id/memories` | List project memories |
| POST | `/v1/search` | Semantic search |
| POST | `/v1/context` | Context assembly |
| POST | `/v1/decisions` | Create ADR |
| GET | `/v1/decisions/:project_id` | List ADRs |
| POST | `/v1/projects/:id/links` | Link projects |
| GET | `/v1/projects/:id/links` | List project links |
| POST | `/v1/search/cross` | Cross-project search |
| POST | `/v1/context/cross` | Cross-project context |
| POST | `/v1/teams` | Create team |
| GET | `/v1/teams/:id` | Get team |
| GET | `/v1/teams/:id/members` | List team members |
| POST | `/v1/teams/:id/members` | Add team member |
| POST | `/v1/users` | Create user |
| GET | `/v1/users/:id` | Get user |

## Pricing

### Free (Open Source)

- CLI with all core commands
- GitHub, Slack, Notion ingestion
- Semantic search and context assembly
- ADR creation and management
- Cross-project memory
- MCP server
- Self-hosted (unlimited)

### Pro ($19/month)

- Managed cloud hosting (no PostgreSQL setup)
- Web dashboard
- Priority support
- Advanced analytics

### Team ($49/month per seat)

- Shared workspaces
- Role-based permissions
- Team memory
- Cross-project search across team

## Development

```bash
# Clone and install
git clone https://github.com/yoi/omoikane.git
cd omoikane
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run type checker
mypy src/omoikane

# Run tests
pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE)
