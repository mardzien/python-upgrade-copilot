"""Interfaces between the pipeline and its RAG core components.

Each protocol describes one stage of the RAG core. The orchestration code
depends only on these protocols, so implementations can be swapped (e.g. a
BM25 retriever for a vector one) and tested independently.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from upgrade_copilot.domain import (
    Claim,
    DocChunk,
    RetrievedChunk,
    SourceDocument,
    TokenUsage,
    Usage,
    VersionChange,
)


class Chunker(Protocol):
    """Splits a documentation page into retrievable chunks."""

    def chunk(self, doc: SourceDocument) -> list[DocChunk]:
        """Split ``doc`` into chunks.

        Contract:
            * Chunks follow the page's section structure; ``section_path``
              lists the headings from the page title down to the chunk.
            * ``canonical_url`` points at the chunk's section, using the same
              anchor the published documentation uses.
            * Lines inside fenced code blocks are never treated as headings,
              and a chunk never splits a code fence open.
            * ``chunk_id`` is unique within the document and deterministic:
              chunking the same document twice yields the same identifiers.
            * Metadata (``library``, ``migration_key``, ``doc_version``,
              ``source_ref``) is copied from ``doc``.

        Args:
            doc: The page to split.

        Returns:
            Chunks in document order.
        """
        ...


class Embedder(Protocol):
    """Turns texts into dense vectors.

    Attributes:
        model: Identifier of the embedding model.
        dim: Dimensionality of the returned vectors.
    """

    model: str
    dim: int

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        """Embed ``texts``.

        Args:
            texts: Texts to embed, in order.

        Returns:
            Array of shape ``(len(texts), dim)``; each row is L2-normalised,
            so a dot product equals cosine similarity.
        """
        ...


class Retriever(Protocol):
    """Finds the chunks most relevant to a query."""

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        """Return up to ``k`` chunks relevant to ``query``.

        Args:
            query: Natural-language or keyword query.
            k: Maximum number of results.

        Returns:
            Results sorted by ``score`` in descending order.
        """
        ...


class QueryBuilder(Protocol):
    """Builds a retrieval query for one symbol used in user code."""

    def build(self, symbol: str, usages: Sequence[Usage], change: VersionChange) -> str:
        """Build the query used to retrieve documentation about ``symbol``.

        Args:
            symbol: Fully qualified symbol (e.g. ``"pydantic.validator"``).
            usages: Every usage of ``symbol`` found in user code.
            change: The version change being analysed.

        Returns:
            The query text.
        """
        ...


class Generator(Protocol):
    """Asks an LLM which risks the retrieved documentation supports."""

    def assess(
        self,
        symbol: str,
        usages: Sequence[Usage],
        context: Sequence[RetrievedChunk],
        change: VersionChange,
    ) -> tuple[list[Claim], TokenUsage]:
        """Produce risk claims for ``symbol``, grounded in ``context``.

        Every claim must quote ``context`` verbatim and name the chunk the
        quote comes from. An empty list means the documentation supports no
        risk for this symbol.

        Args:
            symbol: Fully qualified symbol.
            usages: Every usage of ``symbol`` found in user code.
            context: Retrieved chunks the claims may cite.
            change: The version change being analysed.

        Returns:
            The claims and the token usage of the call(s).
        """
        ...


class Verifier(Protocol):
    """Checks a claim against the context it was generated from."""

    def verify(self, claim: Claim, context: Sequence[RetrievedChunk]) -> DocChunk | None:
        """Return the chunk that confirms ``claim``, or ``None``.

        A claim is confirmed only when its ``chunk_id`` belongs to a chunk in
        ``context`` and its quote appears in that chunk's text.

        Args:
            claim: Claim produced by a :class:`Generator`.
            context: The chunks the generator was given.

        Returns:
            The confirming chunk, or ``None`` if the claim is rejected.
        """
        ...
