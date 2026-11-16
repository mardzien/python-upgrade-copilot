"""Checks against the real GitHub repository and documentation site.

Run with: ``uv run pytest -m live tests/sources``.
"""

import httpx
import pytest

from upgrade_copilot.sources.anchors import heading_anchor
from upgrade_copilot.sources.pydantic_docs import (
    USER_AGENT,
    DocPage,
    fetch_documents,
)

pytestmark = pytest.mark.live


@pytest.mark.parametrize(
    ("page", "heading"),
    [
        (DocPage("docs/migration.md", "Migration Guide"), "Changes to `pydantic.BaseModel`"),
        (
            DocPage("docs/migration.md", "Migration Guide"),
            "`@validator` and `@root_validator` are deprecated",
        ),
        (
            DocPage("docs/concepts/json_schema.md", "JSON Schema"),
            "Implementing `__get_pydantic_core_schema__` "
            '<a name="implementing_get_pydantic_core_schema"></a>',
        ),
    ],
)
def test_anchor_exists_on_site(page: DocPage, heading: str) -> None:
    with httpx.Client(timeout=30) as client:
        (doc,) = fetch_documents(client, "v2.14.3", [page], "1_to_2")
        assert f" {heading}\n" in doc.text

        response = client.get(
            doc.canonical_url, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        )

    assert response.status_code == 200
    assert f'id="{heading_anchor(heading)}"' in response.text
