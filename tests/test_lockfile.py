from pathlib import Path

import pytest
from packaging.version import Version

from upgrade_copilot.domain import VersionChange
from upgrade_copilot.lockfile import LockfileError, diff_package, read_locked_versions

FIXTURES = Path(__file__).parent / "fixtures" / "lock"


def _lock(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_diff_detects_pydantic_major_upgrade() -> None:
    change = diff_package(_lock("base_v1.lock"), _lock("head_v2.lock"), "pydantic")

    assert change == VersionChange("pydantic", Version("1.10.27"), Version("2.14.3"))


def test_package_name_is_normalized() -> None:
    expected = diff_package(_lock("base_v1.lock"), _lock("head_v2.lock"), "pydantic")

    assert diff_package(_lock("base_v1.lock"), _lock("head_v2.lock"), "Pydantic") == expected
    assert "typing-extensions" in read_locked_versions(_lock("head_v2.lock"))


def test_multiple_entries_use_highest_version() -> None:
    versions = read_locked_versions(_lock("multi_version.lock"))
    change = diff_package(_lock("base_v1.lock"), _lock("multi_version.lock"), "pydantic")

    assert versions["pydantic"] == (Version("2.13.0"), Version("2.14.3"))
    assert change is not None
    assert change.head == Version("2.14.3")


def test_missing_package_returns_none() -> None:
    assert diff_package(_lock("no_pydantic.lock"), _lock("head_v2.lock"), "pydantic") is None
    assert diff_package(_lock("head_v2.lock"), _lock("no_pydantic.lock"), "pydantic") is None


def test_unchanged_version_returns_none() -> None:
    assert diff_package(_lock("head_v2.lock"), _lock("head_v2.lock"), "pydantic") is None


def test_entries_without_version_are_skipped() -> None:
    lock = (
        'version = 1\nrevision = 3\n\n[[package]]\nname = "workspace-member"\n'
        'source = { editable = "." }\n\n[[package]]\nname = "pydantic"\n'
        'version = "2.14.3"\nsource = { registry = "https://pypi.org/simple" }\n'
    )

    assert read_locked_versions(lock) == {"pydantic": (Version("2.14.3"),)}


def test_broken_toml_raises_lockfile_error() -> None:
    with pytest.raises(LockfileError, match=r"uv\.lock"):
        read_locked_versions(_lock("broken.lock"))


def test_toml_without_package_table_raises_lockfile_error() -> None:
    with pytest.raises(LockfileError, match=r"uv\.lock"):
        read_locked_versions('[tool.poetry]\nname = "x"\n')


def test_poetry_lock_raises_lockfile_error() -> None:
    poetry_lock = (
        '[[package]]\nname = "pydantic"\nversion = "1.10.27"\n\n[metadata]\nlock-version = "2.0"\n'
    )

    with pytest.raises(LockfileError, match=r"uv\.lock"):
        read_locked_versions(poetry_lock)


def test_invalid_version_raises_lockfile_error() -> None:
    lock = 'version = 1\n\n[[package]]\nname = "pydantic"\nversion = "not a version"\n'

    with pytest.raises(LockfileError, match="pydantic"):
        read_locked_versions(lock)
