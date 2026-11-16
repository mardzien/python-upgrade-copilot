# Python Upgrade Copilot

When a pull request bumps a Python dependency, Python Upgrade Copilot points to the exact lines of code that may break and backs every claim with a verbatim quote from the library's official documentation, or says plainly that there is no confirmed risk.

> **Status:** work in progress towards v0.1 (Pydantic 1 → 2, projects managed with `uv`).

## Documentation

- [Project brief](docs/project-brief.md): the problem, scope, non-goals and quality criteria.
- [Technical design](docs/design.md): the architecture and key decisions.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

## How this project was built

Infrastructure modules were developed with AI assistance (Claude). The RAG core (chunking, embeddings, retrieval, grounded generation and evaluation) is written by the author.

## License

[MIT](LICENSE)
