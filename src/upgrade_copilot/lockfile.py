"""Reading locked versions from ``uv.lock`` and diffing them between branches."""

from __future__ import annotations

import tomllib
from collections import defaultdict
from typing import Any

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from upgrade_copilot.domain import VersionChange


class LockfileError(ValueError):
    """Raised when a lockfile cannot be read as a ``uv.lock`` file."""


def read_locked_versions(lock_text: str) -> dict[str, tuple[Version, ...]]:
    """Return every locked version of every package in a ``uv.lock`` file.

    uv may lock the same package more than once when the resolution is split by
    environment markers, so each package maps to all of its locked versions.

    Args:
        lock_text: Contents of a ``uv.lock`` file.

    Returns:
        Normalised package names mapped to their distinct versions, ascending.
        Entries without a ``version`` field (e.g. dynamic workspace members) are
        skipped.

    Raises:
        LockfileError: If the text is not valid TOML, does not look like a
            ``uv.lock`` file, or contains an invalid version.
    """
    try:
        data = tomllib.loads(lock_text)
    except tomllib.TOMLDecodeError as exc:
        raise LockfileError(f"uv.lock is not valid TOML: {exc}") from exc

    packages = data.get("package")
    if not isinstance(data.get("version"), int) or not isinstance(packages, list):
        raise LockfileError(
            "uv.lock format not recognised: expected a top-level 'version' and [[package]] entries"
        )

    versions: defaultdict[str, set[Version]] = defaultdict(set)
    for entry in packages:
        name, raw_version = _name_and_version(entry)
        if raw_version is None:
            continue
        try:
            versions[name].add(Version(raw_version))
        except InvalidVersion as exc:
            raise LockfileError(
                f"uv.lock has an invalid version for {name!r}: {raw_version!r}"
            ) from exc

    return {name: tuple(sorted(found)) for name, found in versions.items()}


def diff_package(base_lock: str, head_lock: str, package: str) -> VersionChange | None:
    """Compare the locked version of ``package`` between two ``uv.lock`` files.

    When a package is locked more than once, the highest version on each side is
    compared.

    Args:
        base_lock: Contents of ``uv.lock`` on the base branch.
        head_lock: Contents of ``uv.lock`` on the pull request branch.
        package: Package name, in any spelling (``"Pydantic"`` works).

    Returns:
        The change, or ``None`` when the package is missing on either side or its
        version did not change.

    Raises:
        LockfileError: If either file cannot be read.
    """
    name = canonicalize_name(package)
    base_versions = read_locked_versions(base_lock).get(name)
    head_versions = read_locked_versions(head_lock).get(name)
    if not base_versions or not head_versions:
        return None

    base, head = max(base_versions), max(head_versions)
    if base == head:
        return None
    return VersionChange(package=name, base=base, head=head)


def _name_and_version(entry: Any) -> tuple[str, str | None]:
    if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
        raise LockfileError("uv.lock has a [[package]] entry without a 'name'")
    raw_version = entry.get("version")
    if raw_version is not None and not isinstance(raw_version, str):
        raise LockfileError(f"uv.lock has a non-string version for {entry['name']!r}")
    return canonicalize_name(entry["name"]), raw_version
