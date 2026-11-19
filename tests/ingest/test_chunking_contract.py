"""Contract tests for the Markdown chunker.

They define when ``upgrade_copilot.ingest.chunking.MarkdownChunker`` is done
and are skipped until that module exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from upgrade_copilot.domain import DocChunk, SourceDocument
from upgrade_copilot.ports import Chunker

chunking = pytest.importorskip("upgrade_copilot.ingest.chunking")

FIXTURE = Path(__file__).parents[1] / "fixtures" / "docs" / "sample_migration.md"
TITLE = "Migration Guide"
PAGE_URL = "https://docs.pydantic.dev/2.14/migration/"
MAX_CHARS = 2000


def make_doc(doc_path: str = "docs/migration.md") -> SourceDocument:
    return SourceDocument(
        library="pydantic",
        migration_key="1_to_2",
        doc_version="2.14.3",
        doc_path=doc_path,
        title=TITLE,
        canonical_url=PAGE_URL,
        source_ref="v2.14.3@ea492e04654ab7f7a1f9287ea912419452ead4dd",
        text=FIXTURE.read_text(encoding="utf-8"),
    )


def chunk_doc(doc: SourceDocument, max_chars: int = MAX_CHARS) -> list[DocChunk]:
    chunker: Chunker = chunking.MarkdownChunker(max_chars=max_chars)
    return chunker.chunk(doc)


def first_containing(chunks: list[DocChunk], phrase: str) -> DocChunk:
    matches = [c for c in chunks if phrase in c.text]
    assert matches, f"no chunk contains {phrase!r}"
    return matches[0]


@pytest.fixture(scope="module")
def doc() -> SourceDocument:
    return make_doc()


@pytest.fixture(scope="module")
def chunks(doc: SourceDocument) -> list[DocChunk]:
    return chunk_doc(doc)


def test_returns_chunks(chunks: list[DocChunk]) -> None:
    assert chunks
    assert all(isinstance(c, DocChunk) for c in chunks)
    assert all(c.text.strip() for c in chunks)


def test_chunks_preserve_metadata(chunks: list[DocChunk], doc: SourceDocument) -> None:
    for c in chunks:
        assert (c.library, c.migration_key, c.doc_version, c.source_ref, c.doc_title) == (
            doc.library,
            doc.migration_key,
            doc.doc_version,
            doc.source_ref,
            doc.title,
        )


def test_section_path_starts_with_page_title(chunks: list[DocChunk]) -> None:
    assert all(c.section_path[0] == TITLE for c in chunks)


def test_front_matter_is_not_content(chunks: list[DocChunk]) -> None:
    assert not any("description: A sample migration page" in c.text for c in chunks)


def test_intro_links_to_the_page_itself(chunks: list[DocChunk]) -> None:
    intro = first_containing(chunks, "This sample page mimics")

    assert intro.section_path == (TITLE,)
    assert intro.canonical_url == PAGE_URL


@pytest.mark.parametrize(
    ("phrase", "section_path", "anchor"),
    [
        (
            "pip install -U sample",
            (TITLE, "Install the new version"),
            "install-the-new-version",
        ),
        (
            "lists the renamed methods",
            (TITLE, "Changes to models", "Changes to pydantic.BaseModel"),
            "changes-to-pydanticbasemodel",
        ),
        (
            "inherited fields first",
            (TITLE, "Changes to models", "Example", "Field order in .dict() output"),
            "field-order-in-dict-output",
        ),
        (
            "switch to the new schema hook",
            (TITLE, "Changes to validators", "Implementing __get_validators__"),
            "implementing-__get_validators__",
        ),
    ],
)
def test_section_path_and_url_follow_headings(
    chunks: list[DocChunk], phrase: str, section_path: tuple[str, ...], anchor: str
) -> None:
    chunk = first_containing(chunks, phrase)

    assert chunk.section_path == section_path
    assert chunk.canonical_url == f"{PAGE_URL}#{anchor}"


def test_duplicate_headings_get_unique_anchors(chunks: list[DocChunk]) -> None:
    first = first_containing(chunks, "keeps working for now")
    second = first_containing(chunks, "search and replace")

    assert first.section_path[-1] == second.section_path[-1] == "Example"
    assert first.canonical_url == f"{PAGE_URL}#example"
    assert second.canonical_url == f"{PAGE_URL}#example_1"


def test_hash_lines_inside_code_are_not_headings(chunks: list[DocChunk]) -> None:
    code_comments = (
        "Models are declared",
        "Calling the old method",
        "This decorator is deprecated",
        "Use the dedicated decorator",
    )

    for c in chunks:
        for heading in c.section_path:
            assert not heading.startswith(code_comments), c.section_path


def test_code_in_tabs_stays_with_its_section(chunks: list[DocChunk]) -> None:
    chunk = first_containing(chunks, '@field_validator("name")')

    assert chunk.section_path[-1] == "@validator and @root_validator are deprecated"


@pytest.mark.parametrize(
    "phrase",
    [
        "| `parse_obj()` | `model_validate()` |",
        "emit a deprecation warning on every call",
        'User(name="Ada").dict()',
        "# This decorator is deprecated",
        "model_config = ConfigDict(from_attributes=True)",
        "since that no longer clears anything",
    ],
)
def test_no_content_is_lost(chunks: list[DocChunk], phrase: str) -> None:
    first_containing(chunks, phrase)


def test_chunks_are_in_document_order(chunks: list[DocChunk]) -> None:
    phrases = (
        "This sample page mimics",
        "pip install -U sample",
        "lists the renamed methods",
        "inherited fields first",
        '@field_validator("name")',
        "since that no longer clears anything",
    )
    positions = [chunks.index(first_containing(chunks, p)) for p in phrases]

    assert positions == sorted(positions)


@pytest.mark.parametrize("max_chars", [MAX_CHARS, 800])
def test_respects_max_chars(doc: SourceDocument, max_chars: int) -> None:
    assert all(len(c.text) <= max_chars for c in chunk_doc(doc, max_chars))


def test_long_section_is_split_within_its_section(chunks: list[DocChunk]) -> None:
    config_chunks = [c for c in chunks if c.section_path[-1] == "Changes to Config"]

    assert len(config_chunks) >= 2
    assert {c.canonical_url for c in config_chunks} == {f"{PAGE_URL}#changes-to-config"}


@pytest.mark.parametrize("max_chars", [MAX_CHARS, 800])
def test_code_fences_are_balanced(doc: SourceDocument, max_chars: int) -> None:
    for c in chunk_doc(doc, max_chars):
        fences = [line for line in c.text.splitlines() if line.lstrip().startswith("```")]
        assert len(fences) % 2 == 0, c.text


def test_chunk_ids_are_unique_and_deterministic(
    chunks: list[DocChunk], doc: SourceDocument
) -> None:
    ids = [c.chunk_id for c in chunks]

    assert len(set(ids)) == len(ids)
    assert [c.chunk_id for c in chunk_doc(doc)] == ids


def test_chunk_ids_differ_between_pages(chunks: list[DocChunk]) -> None:
    other = chunk_doc(make_doc("docs/other.md"))

    assert not {c.chunk_id for c in chunks} & {c.chunk_id for c in other}
