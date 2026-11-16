import dataclasses

import pytest
from packaging.version import Version

from upgrade_copilot.domain import (
    Claim,
    Confidence,
    Finding,
    Report,
    RunStats,
    TokenUsage,
    Usage,
    UsageKind,
    VersionChange,
)


def _usage() -> Usage:
    return Usage(
        path="app/models.py",
        line=3,
        col=0,
        symbol="pydantic.validator",
        kind=UsageKind.DECORATOR,
        snippet="@validator('name')",
    )


def _finding(confidence: Confidence) -> Finding:
    claim = Claim(
        symbol="pydantic.validator",
        risk_description="Deprecated in V2.",
        quote="`@validator` has been deprecated",
        chunk_id="pydantic:migration:0001",
        suggested_check="Replace with @field_validator.",
        model_uncertain=False,
    )
    return Finding(
        usage=_usage(),
        claim=claim,
        source_url="https://docs.pydantic.dev/2.14/migration/#changes-to-validators",
        confidence=confidence,
    )


def test_version_change_detects_major_upgrade() -> None:
    major = VersionChange("pydantic", Version("1.10.27"), Version("2.14.3"))
    minor = VersionChange("pydantic", Version("2.5.0"), Version("2.14.3"))

    assert major.is_major_upgrade is True
    assert minor.is_major_upgrade is False


def test_domain_objects_are_immutable() -> None:
    usage = _usage()

    with pytest.raises(dataclasses.FrozenInstanceError):
        usage.line = 10  # type: ignore[misc]  # ty: ignore[invalid-assignment]


def test_report_counts_by_confidence_includes_all_levels() -> None:
    report = Report(
        change=VersionChange("pydantic", Version("1.10.27"), Version("2.14.3")),
        findings=(_finding(Confidence.HIGH), _finding(Confidence.HIGH)),
        unconfirmed=(),
        stats=RunStats(
            duration_s=1.0,
            embedding_tokens=0,
            llm_usage=TokenUsage(0, 0),
            rejected_claims=0,
            estimated_cost_usd=0.0,
        ),
    )

    assert report.counts_by_confidence() == {
        Confidence.HIGH: 2,
        Confidence.MEDIUM: 0,
        Confidence.LOW: 0,
    }


def test_token_usage_adds() -> None:
    assert TokenUsage(1, 2) + TokenUsage(3, 4) == TokenUsage(4, 6)
