"""Official Pydantic documentation, fetched from GitHub at a pinned commit.

A release tag is resolved to its commit SHA first and every file is then read
from that SHA, so the stored text can always be traced back to an immutable
revision, even if the tag is later moved.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

import httpx
from packaging.version import Version

from upgrade_copilot.domain import SourceDocument

LIBRARY = "pydantic"
USER_AGENT = "python-upgrade-copilot"

_REPO = "pydantic/pydantic"
_API_COMMIT_URL = "https://api.github.com/repos/{repo}/commits/{ref}"
_RAW_URL = "https://raw.githubusercontent.com/{repo}/{sha}/{path}"
_DOCS_SITE = "https://docs.pydantic.dev"


@dataclass(frozen=True, slots=True)
class DocPage:
    """A documentation page to fetch.

    Attributes:
        path: Markdown source path inside the Pydantic repository.
        title: Page title as shown in the site navigation. Pages do not start
            with a ``#`` heading; MkDocs takes the title from ``mkdocs.yml``.
    """

    path: str
    title: str


# Titles copied from the `nav` section of mkdocs.yml at the pinned tag (v2.14.3).
PYDANTIC_1_TO_2_DOCS: tuple[DocPage, ...] = (
    DocPage("docs/migration.md", "Migration Guide"),
    DocPage("docs/concepts/models.md", "Models"),
    DocPage("docs/concepts/validators.md", "Validators"),
    DocPage("docs/concepts/config.md", "Configuration"),
    DocPage("docs/concepts/fields.md", "Fields"),
    DocPage("docs/concepts/serialization.md", "Serialization"),
    DocPage("docs/concepts/json_schema.md", "JSON Schema"),
    DocPage("docs/concepts/dataclasses.md", "Dataclasses"),
    DocPage("docs/concepts/pydantic_settings.md", "Settings Management"),
)


class DocsFetchError(RuntimeError):
    """Raised when documentation cannot be fetched completely."""


def canonical_url(doc_version: Version, doc_path: str) -> str:
    """Return the public URL of a documentation page, without an anchor.

    Args:
        doc_version: Library version the page documents; only major.minor is
            used, matching the versioned documentation site.
        doc_path: Markdown source path, e.g. ``"docs/concepts/models.md"``.

    Returns:
        E.g. ``"https://docs.pydantic.dev/2.14/concepts/models/"``.
    """
    page = doc_path.removeprefix("docs/").removesuffix(".md")
    page = "" if page == "index" else page.removesuffix("/index")
    base = f"{_DOCS_SITE}/{doc_version.major}.{doc_version.minor}/"
    return f"{base}{page}/" if page else base


def fetch_documents(
    client: httpx.Client,
    tag: str,
    pages: Sequence[DocPage],
    migration_key: str,
) -> list[SourceDocument]:
    """Fetch documentation pages at the commit a release tag points to.

    Nothing is returned unless every page was fetched successfully.

    Args:
        client: HTTP client to use.
        tag: Release tag, e.g. ``"v2.14.3"``.
        pages: Pages to fetch.
        migration_key: Migration the pages belong to, e.g. ``"1_to_2"``.

    Returns:
        One document per page, in the order of ``pages``.

    Raises:
        DocsFetchError: On any network error, non-200 response, or an API
            response without a commit SHA. The message names the URL.
    """
    sha = _resolve_commit(client, tag)
    doc_version = tag.removeprefix("v")
    version = Version(doc_version)
    return [
        SourceDocument(
            library=LIBRARY,
            migration_key=migration_key,
            doc_version=doc_version,
            doc_path=page.path,
            title=page.title,
            canonical_url=canonical_url(version, page.path),
            source_ref=f"{tag}@{sha}",
            text=_get(client, _RAW_URL.format(repo=_REPO, sha=sha, path=page.path)).text,
        )
        for page in pages
    ]


def _resolve_commit(client: httpx.Client, tag: str) -> str:
    url = _API_COMMIT_URL.format(repo=_REPO, ref=tag)
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        sha = _get(client, url, headers).json().get("sha")
    except ValueError as exc:
        raise DocsFetchError(f"GET {url}: response is not JSON") from exc
    if not isinstance(sha, str) or not sha:
        raise DocsFetchError(f"GET {url}: response has no commit sha")
    return sha


def _get(client: httpx.Client, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
    try:
        response = client.get(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    except httpx.HTTPError as exc:
        raise DocsFetchError(f"GET {url}: {type(exc).__name__}: {exc}") from exc
    if response.status_code != 200:
        raise DocsFetchError(f"GET {url}: HTTP {response.status_code}")
    return response
