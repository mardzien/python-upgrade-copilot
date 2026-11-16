import dataclasses
import json
import os
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from upgrade_copilot.domain import SourceDocument
from upgrade_copilot.sources.storage import (
    DOCUMENTS_FILE,
    MANIFEST_FILE,
    load_documents,
    save_documents,
)

FETCHED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _doc(path: str, text: str = "## Section\n\nZażółć gęślą jaźń") -> SourceDocument:
    return SourceDocument(
        library="pydantic",
        migration_key="1_to_2",
        doc_version="2.14.3",
        doc_path=path,
        title=path.rsplit("/", 1)[-1],
        canonical_url="https://docs.pydantic.dev/2.14/x/",
        source_ref="v2.14.3@abc123",
        text=text,
    )


DOCS = [_doc("docs/migration.md"), _doc("docs/concepts/models.md")]


def test_roundtrip(tmp_path: Path) -> None:
    save_documents(DOCS, tmp_path, fetched_at=FETCHED_AT)

    assert load_documents(tmp_path) == DOCS
    manifest = json.loads((tmp_path / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest["library"] == "pydantic"
    assert manifest["migration_key"] == "1_to_2"
    assert manifest["source_refs"] == ["v2.14.3@abc123"]
    assert manifest["paths"] == ["docs/migration.md", "docs/concepts/models.md"]
    assert manifest["fetched_at"] == "2026-01-02T03:04:05+00:00"
    assert manifest["count"] == 2


def test_saved_files_are_world_readable(tmp_path: Path) -> None:
    save_documents(DOCS, tmp_path, fetched_at=FETCHED_AT)

    modes = {p.name: p.stat().st_mode & 0o777 for p in tmp_path.iterdir()}
    assert modes == {DOCUMENTS_FILE: 0o644, MANIFEST_FILE: 0o644}


def test_fetched_at_is_stored_in_utc(tmp_path: Path) -> None:
    warsaw = timezone(timedelta(hours=1))

    save_documents(DOCS, tmp_path, fetched_at=datetime(2026, 1, 2, 4, 4, 5, tzinfo=warsaw))

    manifest = json.loads((tmp_path / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest["fetched_at"] == "2026-01-02T03:04:05+00:00"


def test_naive_datetime_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone"):
        save_documents(DOCS, tmp_path, fetched_at=datetime(2026, 1, 2))


def test_mixed_doc_sets_are_rejected(tmp_path: Path) -> None:
    other = dataclasses.replace(_doc("docs/a.md"), migration_key="2_to_3")

    with pytest.raises(ValueError, match="migration"):
        save_documents([DOCS[0], other], tmp_path, fetched_at=FETCHED_AT)


def test_existing_files_untouched_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_documents(DOCS, tmp_path, fetched_at=FETCHED_AT)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def failing_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        save_documents([_doc("docs/other.md")], tmp_path, fetched_at=FETCHED_AT)

    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert after == before


def test_load_detects_documents_changed_after_save(tmp_path: Path) -> None:
    save_documents(DOCS, tmp_path, fetched_at=FETCHED_AT)
    documents = tmp_path / DOCUMENTS_FILE
    documents.write_text(documents.read_text(encoding="utf-8")[:-10], encoding="utf-8")

    with pytest.raises(ValueError, match="checksum"):
        load_documents(tmp_path)
