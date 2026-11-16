import pytest

from upgrade_copilot.sources.anchors import AnchorRegistry, heading_anchor


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("Changes to `pydantic.BaseModel`", "changes-to-pydanticbasemodel"),
        (
            "`@validator` and `@root_validator` are deprecated",
            "validator-and-root_validator-are-deprecated",
        ),
        ("Changes to Handling of Standard Types", "changes-to-handling-of-standard-types"),
        ("Introduction of `TypeAdapter`", "introduction-of-typeadapter"),
        (
            'Implementing `__get_pydantic_core_schema__` <a name="implementing_get"></a>',
            "implementing-__get_pydantic_core_schema__",
        ),
        ("See [the API docs](https://example.com) for more", "see-the-api-docs-for-more"),
        ("Using **bold** and *emphasis*", "using-bold-and-emphasis"),
        ("Types &amp; aliases", "types-aliases"),
        ("Café — naïve", "cafe-naive"),
    ],
)
def test_heading_anchor_matches_published_ids(heading: str, expected: str) -> None:
    assert heading_anchor(heading) == expected


def test_registry_suffixes_duplicates() -> None:
    registry = AnchorRegistry()

    assert [registry.unique("x") for _ in range(3)] == ["x", "x_1", "x_2"]


def test_registry_keeps_distinct_slugs_and_avoids_collisions() -> None:
    registry = AnchorRegistry()

    assert registry.unique("x_1") == "x_1"
    assert registry.unique("x") == "x"
    assert registry.unique("x") == "x_2"
