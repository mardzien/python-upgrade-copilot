"""Storing a fetched documentation set on disk.

A set is two files: ``documents.jsonl`` (one :class:`SourceDocument` per line)
and ``manifest.json`` (provenance and a checksum of the documents file). Both
are written to temporary files first and moved into place with
``os.replace``, so an interrupted save never leaves a half-written file. The
manifest is moved last and its checksum lets :func:`load_documents` detect a
documents file that does not belong to it.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from upgrade_copilot.domain import SourceDocument

DOCUMENTS_FILE = "documents.jsonl"
MANIFEST_FILE = "manifest.json"


def save_documents(docs: Sequence[SourceDocument], out_dir: Path, *, fetched_at: datetime) -> None:
    """Write a documentation set to ``out_dir``, replacing any previous one.

    Args:
        docs: Documents of a single library and migration.
        out_dir: Target directory; created if missing.
        fetched_at: When the documents were fetched; must be timezone-aware.

    Raises:
        ValueError: If ``docs`` is empty, mixes libraries or migrations, or
            ``fetched_at`` is naive.
        OSError: If writing fails; files already in ``out_dir`` are left as
            they were.
    """
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")
    library, migration_key = _single_set(docs)

    documents = "".join(
        json.dumps(dataclasses.asdict(doc), ensure_ascii=False) + "\n" for doc in docs
    ).encode("utf-8")
    manifest = {
        "library": library,
        "migration_key": migration_key,
        "source_refs": sorted({doc.source_ref for doc in docs}),
        "paths": [doc.doc_path for doc in docs],
        "fetched_at": fetched_at.astimezone(UTC).isoformat(),
        "count": len(docs),
        "documents_sha256": hashlib.sha256(documents).hexdigest(),
    }
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    pending = [
        (_write_temp(out_dir, documents), out_dir / DOCUMENTS_FILE),
        (_write_temp(out_dir, manifest_bytes), out_dir / MANIFEST_FILE),
    ]
    try:
        for temp, target in pending:
            os.replace(temp, target)
    finally:
        for temp, _ in pending:
            with contextlib.suppress(FileNotFoundError):
                temp.unlink()


def load_documents(out_dir: Path) -> list[SourceDocument]:
    """Read a documentation set written by :func:`save_documents`.

    Raises:
        ValueError: If the documents file does not match the manifest checksum.
        OSError: If either file cannot be read.
    """
    manifest = json.loads((out_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
    documents = (out_dir / DOCUMENTS_FILE).read_bytes()
    if hashlib.sha256(documents).hexdigest() != manifest["documents_sha256"]:
        raise ValueError(f"{out_dir / DOCUMENTS_FILE} does not match the manifest checksum")
    return [
        SourceDocument(**json.loads(line))
        for line in documents.decode("utf-8").splitlines()
        if line
    ]


def _single_set(docs: Sequence[SourceDocument]) -> tuple[str, str]:
    if not docs:
        raise ValueError("cannot save an empty documentation set")
    libraries = {doc.library for doc in docs}
    migrations = {doc.migration_key for doc in docs}
    if len(libraries) != 1 or len(migrations) != 1:
        raise ValueError(
            f"documents mix libraries {sorted(libraries)} or migrations {sorted(migrations)}"
        )
    return libraries.pop(), migrations.pop()


def _write_temp(directory: Path, data: bytes) -> Path:
    fd, name = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".part")
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return Path(name)
