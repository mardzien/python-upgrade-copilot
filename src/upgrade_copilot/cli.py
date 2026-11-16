"""Command-line interface: ``upgrade-copilot``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import httpx
import typer

from upgrade_copilot.sources import pydantic_docs
from upgrade_copilot.sources.storage import save_documents

DOC_SETS: dict[str, tuple[pydantic_docs.DocPage, ...]] = {
    "1_to_2": pydantic_docs.PYDANTIC_1_TO_2_DOCS,
}

app = typer.Typer(no_args_is_help=True, help="Auditable dependency-upgrade risk reports.")
docs_app = typer.Typer(no_args_is_help=True, help="Manage pinned documentation sources.")
app.add_typer(docs_app, name="docs")


@docs_app.command("fetch")
def docs_fetch(
    tag: Annotated[str, typer.Option(help="Pydantic release tag to fetch, e.g. v2.14.3.")],
    migration: Annotated[str, typer.Option(help="Migration the pages belong to.")] = "1_to_2",
    out: Annotated[
        Path | None,
        typer.Option(help="Output directory (default: data/sources/pydantic/<migration>)."),
    ] = None,
) -> None:
    """Fetch the documentation set for a migration, pinned to the tag's commit."""
    pages = DOC_SETS.get(migration)
    if pages is None:
        raise typer.BadParameter(
            f"unknown migration {migration!r}; known: {', '.join(sorted(DOC_SETS))}",
            param_hint="--migration",
        )
    out_dir = out if out is not None else Path("data/sources/pydantic") / migration

    try:
        with httpx.Client(timeout=30) as client:
            docs = pydantic_docs.fetch_documents(client, tag, pages, migration)
    except pydantic_docs.DocsFetchError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    save_documents(docs, out_dir, fetched_at=datetime.now(UTC))
    typer.echo(f"Fetched {len(docs)} documents from {docs[0].source_ref} into {out_dir}")
