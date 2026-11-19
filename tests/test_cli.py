from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from upgrade_copilot import cli
from upgrade_copilot.domain import SourceDocument
from upgrade_copilot.sources import pydantic_docs
from upgrade_copilot.sources.pydantic_docs import PYDANTIC_1_TO_2_DOCS, DocPage, DocsFetchError
from upgrade_copilot.sources.storage import DOCUMENTS_FILE, MANIFEST_FILE, load_documents

runner = CliRunner()


def _doc(path: str) -> SourceDocument:
    return SourceDocument(
        library="pydantic",
        migration_key="1_to_2",
        doc_version="2.14.3",
        doc_path=path,
        title="Title",
        canonical_url="https://docs.pydantic.dev/2.14/x/",
        source_ref="v2.14.3@abc1234567",
        text="## Section\n",
    )


def _fetch_args(tmp_path: Path) -> list[str]:
    return ["docs", "fetch", "--tag", "v2.14.3", "--migration", "1_to_2", "--out", str(tmp_path)]


def test_docs_fetch_writes_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Sequence[DocPage], str]] = []

    def fake_fetch(
        client: httpx.Client, tag: str, pages: Sequence[DocPage], migration_key: str
    ) -> list[SourceDocument]:
        calls.append((tag, pages, migration_key))
        return [_doc("docs/migration.md"), _doc("docs/concepts/models.md")]

    monkeypatch.setattr(pydantic_docs, "fetch_documents", fake_fetch)

    result = runner.invoke(cli.app, _fetch_args(tmp_path))

    assert result.exit_code == 0, result.output
    assert "Fetched 2 documents from v2.14.3@abc1234567" in result.output
    assert calls == [("v2.14.3", PYDANTIC_1_TO_2_DOCS, "1_to_2")]
    assert len((tmp_path / DOCUMENTS_FILE).read_text(encoding="utf-8").splitlines()) == 2
    assert (tmp_path / MANIFEST_FILE).exists()
    assert len(load_documents(tmp_path)) == 2


def test_docs_fetch_reports_error_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_fetch(
        client: httpx.Client, tag: str, pages: Sequence[DocPage], migration_key: str
    ) -> list[SourceDocument]:
        raise DocsFetchError("GET https://raw.githubusercontent.com/x: HTTP 404")

    monkeypatch.setattr(pydantic_docs, "fetch_documents", failing_fetch)

    result = runner.invoke(cli.app, _fetch_args(tmp_path))

    assert result.exit_code == 1
    assert "HTTP 404" in result.output
    assert list(tmp_path.iterdir()) == []


def test_docs_fetch_rejects_unknown_migration(tmp_path: Path) -> None:
    args = ["docs", "fetch", "--tag", "v3.0.0", "--migration", "2_to_3", "--out", str(tmp_path)]

    result = runner.invoke(cli.app, args)

    assert result.exit_code == 2
    assert "2_to_3" in result.output
