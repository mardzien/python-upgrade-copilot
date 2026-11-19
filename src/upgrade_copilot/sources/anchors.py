"""Heading anchors identical to the ones on the published documentation site.

Pydantic's documentation is built with MkDocs, whose ``toc`` extension
(Python-Markdown) turns each heading into an ``id``. Reproducing that algorithm
lets every chunk link straight to its section on the live site.
"""

from __future__ import annotations

import html
import re
import unicodedata

_CODE_SPAN = re.compile(r"`+([^`]*)`+")
_LINK = re.compile(r"!?\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])")
_HTML_TAG = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"[^\w\s-]")
_SEPARATORS = re.compile(r"[-\s]+")
_WHITESPACE = re.compile(r"\s+")
_NUMBERED = re.compile(r"^(.*)_([0-9]+)$")


def heading_text(heading: str) -> str:
    """Return a Markdown heading as the reader sees it on the page.

    Code spans keep their content, links keep their label, HTML tags are
    dropped, entities are decoded and runs of whitespace collapse to one space.

    Args:
        heading: Heading text without the leading ``#`` characters.

    Returns:
        E.g. ``"Changes to pydantic.BaseModel"`` for
        ``"Changes to `pydantic.BaseModel`"``.
    """
    text = _CODE_SPAN.sub(r"\1", heading)
    text = _LINK.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    text = html.unescape(text)
    return _WHITESPACE.sub(" ", text).strip()


def heading_anchor(heading: str) -> str:
    """Return the anchor MkDocs generates for a Markdown heading.

    The heading is first reduced to what the reader sees (see
    :func:`heading_text`), then slugified the way
    ``markdown.extensions.toc.slugify`` does it.

    Args:
        heading: Heading text without the leading ``#`` characters.

    Returns:
        The anchor, e.g. ``"changes-to-pydanticbasemodel"`` for
        ``"Changes to `pydantic.BaseModel`"``.
    """
    text = heading_text(heading)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = _NON_WORD.sub("", text).strip().lower()
    return _SEPARATORS.sub("-", text)


class AnchorRegistry:
    """Makes anchors unique within one page, like MkDocs does.

    The first occurrence of a slug is kept as is; later ones get ``_1``,
    ``_2``, ... appended. Use one registry per document.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def unique(self, slug: str) -> str:
        """Return ``slug``, suffixed if needed so it was not returned before."""
        candidate = slug
        while candidate in self._seen or not candidate:
            match = _NUMBERED.match(candidate)
            candidate = f"{match[1]}_{int(match[2]) + 1}" if match else f"{candidate}_1"
        self._seen.add(candidate)
        return candidate
