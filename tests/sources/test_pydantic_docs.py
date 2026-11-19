from collections.abc import Callable

import httpx
import pytest
from packaging.version import Version

from upgrade_copilot.sources.pydantic_docs import (
    PYDANTIC_1_TO_2_DOCS,
    DocPage,
    DocsFetchError,
    canonical_url,
    fetch_documents,
)

API_URL = "https://api.github.com/repos/pydantic/pydantic/commits/v2.14.3"
PAGES = (
    DocPage("docs/migration.md", "Migration Guide"),
    DocPage("docs/concepts/models.md", "Models"),
)

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok_handler(seen: list[httpx.Request]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"sha": "abc123"})
        return httpx.Response(200, text=f"## Section\n\nbody of {request.url.path}")

    return handler


def test_canonical_url_strips_prefix_and_suffix() -> None:
    version = Version("2.14.3")

    assert canonical_url(version, "docs/concepts/models.md") == (
        "https://docs.pydantic.dev/2.14/concepts/models/"
    )
    assert (
        canonical_url(version, "docs/migration.md") == "https://docs.pydantic.dev/2.14/migration/"
    )
    assert canonical_url(version, "docs/index.md") == "https://docs.pydantic.dev/2.14/"
    assert canonical_url(version, "docs/concepts/index.md") == (
        "https://docs.pydantic.dev/2.14/concepts/"
    )


def test_doc_set_has_unique_paths_and_titles() -> None:
    paths = [page.path for page in PYDANTIC_1_TO_2_DOCS]

    assert paths[0] == "docs/migration.md"
    assert len(set(paths)) == len(paths) == 9
    assert all(page.title for page in PYDANTIC_1_TO_2_DOCS)


def test_fetch_pins_commit_sha() -> None:
    seen: list[httpx.Request] = []

    docs = fetch_documents(_client(_ok_handler(seen)), "v2.14.3", PAGES, "1_to_2")

    raw_requests = [r for r in seen if r.url.host == "raw.githubusercontent.com"]
    assert [r.url.path for r in raw_requests] == [
        "/pydantic/pydantic/abc123/docs/migration.md",
        "/pydantic/pydantic/abc123/docs/concepts/models.md",
    ]
    first = docs[0]
    assert first.library == "pydantic"
    assert first.migration_key == "1_to_2"
    assert first.doc_version == "2.14.3"
    assert first.doc_path == "docs/migration.md"
    assert first.title == "Migration Guide"
    assert first.canonical_url == "https://docs.pydantic.dev/2.14/migration/"
    assert first.source_ref == "v2.14.3@abc123"
    assert first.text == "## Section\n\nbody of /pydantic/pydantic/abc123/docs/migration.md"


def test_fetch_sends_identifying_user_agent() -> None:
    seen: list[httpx.Request] = []

    fetch_documents(_client(_ok_handler(seen)), "v2.14.3", PAGES, "1_to_2")

    assert {r.headers["User-Agent"] for r in seen} == {"python-upgrade-copilot"}


def test_github_token_is_sent_only_to_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    seen: list[httpx.Request] = []

    fetch_documents(_client(_ok_handler(seen)), "v2.14.3", PAGES, "1_to_2")

    api = [r for r in seen if r.url.host == "api.github.com"]
    raw = [r for r in seen if r.url.host == "raw.githubusercontent.com"]
    assert api[0].headers["Authorization"] == "Bearer secret-token"
    assert all("Authorization" not in r.headers for r in raw)


def test_fetch_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"sha": "abc123"})
        if request.url.path.endswith("models.md"):
            return httpx.Response(404, text="Not Found")
        return httpx.Response(200, text="ok")

    with pytest.raises(DocsFetchError, match=r"docs/concepts/models\.md.*404"):
        fetch_documents(_client(handler), "v2.14.3", PAGES, "1_to_2")


def test_fetch_raises_on_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "API rate limit exceeded"})

    with pytest.raises(DocsFetchError, match="403"):
        fetch_documents(_client(handler), "v2.14.3", PAGES, "1_to_2")


def test_fetch_raises_on_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(DocsFetchError, match=r"api\.github\.com"):
        fetch_documents(_client(handler), "v2.14.3", PAGES, "1_to_2")


def test_fetch_raises_when_api_response_has_no_sha() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "unexpected"})

    with pytest.raises(DocsFetchError, match="sha"):
        fetch_documents(_client(handler), "v2.14.3", PAGES, "1_to_2")
