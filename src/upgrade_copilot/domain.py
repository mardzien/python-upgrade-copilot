"""Domain model shared by every stage of the pipeline.

All objects are immutable value objects. They carry no behaviour beyond small,
pure derived properties, so any stage can be tested in isolation by building
its inputs by hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from packaging.version import Version


@dataclass(frozen=True, slots=True)
class VersionChange:
    """A single package whose locked version differs between two lockfiles.

    Attributes:
        package: Normalised distribution name (e.g. ``"pydantic"``).
        base: Version locked on the base branch.
        head: Version locked on the pull request branch.
    """

    package: str
    base: Version
    head: Version

    @property
    def is_major_upgrade(self) -> bool:
        """Whether the change crosses a major version upwards."""
        return self.head.major > self.base.major


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """One page of official documentation, fetched at a pinned commit.

    Attributes:
        library: Library the page documents (e.g. ``"pydantic"``).
        migration_key: Migration the page belongs to (e.g. ``"1_to_2"``).
        doc_version: Library release the page was taken from (e.g. ``"2.14.3"``).
        doc_path: Path of the Markdown source inside the library repository.
        title: Page title.
        canonical_url: Public URL of the rendered page, without an anchor.
        source_ref: ``"<tag>@<commit_sha>"`` the page was fetched from.
        text: Raw Markdown source.
    """

    library: str
    migration_key: str
    doc_version: str
    doc_path: str
    title: str
    canonical_url: str
    source_ref: str
    text: str


@dataclass(frozen=True, slots=True)
class DocChunk:
    """A retrievable fragment of a :class:`SourceDocument`.

    Attributes:
        chunk_id: Stable, unique identifier of the chunk.
        library: Copied from the source document.
        migration_key: Copied from the source document.
        doc_version: Copied from the source document.
        doc_title: Title of the source document.
        section_path: Headings from the page title down to the chunk's section.
        canonical_url: Public URL of the chunk's section, including the anchor.
        source_ref: Copied from the source document.
        text: Chunk content (Markdown).
    """

    chunk_id: str
    library: str
    migration_key: str
    doc_version: str
    doc_title: str
    section_path: tuple[str, ...]
    canonical_url: str
    source_ref: str
    text: str


class UsageKind(StrEnum):
    """How a library symbol is used at a given location in user code."""

    IMPORT = "import"
    CALL = "call"
    ATTRIBUTE = "attribute"
    DECORATOR = "decorator"
    BASE_CLASS = "base_class"
    CONFIG_CLASS = "config_class"


@dataclass(frozen=True, slots=True)
class Usage:
    """A single place in user code that uses a library symbol.

    Attributes:
        path: File path relative to the repository root.
        line: 1-based line number.
        col: 0-based column offset.
        symbol: Fully qualified symbol (e.g. ``"pydantic.validator"``).
        kind: How the symbol is used.
        snippet: The source line, stripped.
        heuristic: True when the match relies on a heuristic rather than on a
            resolved import (e.g. a ``class Config`` inside a model).
    """

    path: str
    line: int
    col: int
    symbol: str
    kind: UsageKind
    snippet: str
    heuristic: bool = False


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk returned by a retriever together with its score.

    Attributes:
        chunk: The retrieved chunk.
        score: Retriever-specific relevance score; higher is better.
        retriever: Name of the retriever that produced the score.
    """

    chunk: DocChunk
    score: float
    retriever: str


class Confidence(StrEnum):
    """Confidence level of a verified finding."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Claim:
    """A raw risk claim produced by the generator, before verification.

    Attributes:
        symbol: Symbol the claim is about.
        risk_description: What may break, in one or two sentences.
        quote: Verbatim quote from the documentation supporting the claim.
        chunk_id: Identifier of the chunk the quote was taken from.
        suggested_check: What the developer should verify or change.
        model_uncertain: True when the model itself flagged low certainty.
    """

    symbol: str
    risk_description: str
    quote: str
    chunk_id: str
    suggested_check: str
    model_uncertain: bool


@dataclass(frozen=True, slots=True)
class Finding:
    """A verified claim attached to a concrete usage in user code.

    Attributes:
        usage: Location in user code.
        claim: The verified claim.
        source_url: Canonical URL of the section that contains the quote.
        confidence: Confidence level assigned by the rules.
    """

    usage: Usage
    claim: Claim
    source_url: str
    confidence: Confidence


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token counts reported by an LLM call."""

    input_tokens: int
    output_tokens: int

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True, slots=True)
class RunStats:
    """Cost and quality counters for one analysis run.

    Attributes:
        duration_s: Wall-clock duration of the run in seconds.
        embedding_tokens: Tokens sent to the embedding model (queries only).
        llm_usage: Aggregated LLM token usage.
        rejected_claims: Claims dropped by the verifier.
        estimated_cost_usd: Estimated API cost of the run.
    """

    duration_s: float
    embedding_tokens: int
    llm_usage: TokenUsage
    rejected_claims: int
    estimated_cost_usd: float


@dataclass(frozen=True, slots=True)
class Report:
    """Result of analysing one version change.

    Attributes:
        change: The analysed version change.
        findings: Verified findings, one per affected usage.
        unconfirmed: Usages for which no claim could be verified.
        stats: Cost and quality counters.
    """

    change: VersionChange
    findings: tuple[Finding, ...]
    unconfirmed: tuple[Usage, ...]
    stats: RunStats

    def counts_by_confidence(self) -> dict[Confidence, int]:
        """Number of findings per confidence level, always with every level."""
        counts = dict.fromkeys(Confidence, 0)
        for finding in self.findings:
            counts[finding.confidence] += 1
        return counts
