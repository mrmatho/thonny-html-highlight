"""HTML tokenizer for syntax highlighting.

Contains only pure functions — no tkinter or Thonny imports — so every
function here can be unit-tested in complete isolation.
"""
from __future__ import annotations

import re
from typing import Dict, List, NamedTuple


class Token(NamedTuple):
    """A single syntax token within an HTML document.

    Attributes:
        type:  One of ``'comment'``, ``'doctype'``, ``'entity'``,
               ``'bracket'``, ``'tag_name'``, ``'attr_name'``,
               ``'attr_value'``.
        start: Inclusive start offset in the source string.
        end:   Exclusive end offset in the source string.
    """

    type: str
    start: int
    end: int


# ---------------------------------------------------------------------------
# Compiled regular expressions
# ---------------------------------------------------------------------------

# Matches the four top-level HTML constructs.
#
# The 'tag' alternative handles both opening and closing tags (including
# self-closing).  Quoted attribute values are matched explicitly so that a
# '>' character inside a value does not prematurely end the tag match.
_TOP_LEVEL_RE = re.compile(
    r"(?P<comment><!--[\s\S]*?-->)"
    r"|(?P<doctype><!DOCTYPE[^>]*>)"
    r"|(?P<entity>&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);)"
    r'|(?P<tag></?[a-zA-Z][a-zA-Z0-9_:-]*(?:"[^"]*"|\'[^\']*\'|[^>])*>)',
    re.DOTALL | re.IGNORECASE,
)

# Parses the internal structure of a single matched tag string.
_TAG_RE = re.compile(
    r'^<(?P<slash>/?)(?P<name>[a-zA-Z][a-zA-Z0-9_:-]*)'
    r'(?P<attrs>(?:"[^"]*"|\'[^\']*\'|(?!/>)[^>])*)'
    r'(?P<end>/?>)$',
    re.DOTALL,
)

# Finds individual attribute name + optional value within an attrs string.
# The hyphen is placed at the end of the second character class so it is
# treated as a literal rather than a range operator.
_ATTR_RE = re.compile(
    r'(?P<attr_name>[a-zA-Z_:][a-zA-Z0-9_.:-]*)'
    r'(?:\s*=\s*(?P<attr_value>"[^"]*"|\'[^\']*\'|[^\s>]*))?'
)

# Names of the top-level alternatives, in the order they appear in _TOP_LEVEL_RE.
_TOP_LEVEL_GROUPS = ("comment", "doctype", "entity", "tag")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def tokenize_html(text: str) -> List[Token]:
    """Return a list of :class:`Token` objects for *text*, sorted by ``start``.

    Tokens cover HTML comments, DOCTYPE declarations, entity references, tag
    brackets, tag names, attribute names, and attribute values.

    The function is intentionally lenient: malformed or incomplete HTML
    produces fewer tokens rather than raising an exception.

    .. note::
        Content inside ``<script>`` and ``<style>`` tags is currently treated
        as plain HTML.  Full script/style awareness is planned for a future
        version.
    """
    tokens: List[Token] = []

    for match in _TOP_LEVEL_RE.finditer(text):
        group = _first_matched_group(match, _TOP_LEVEL_GROUPS)

        if group == "comment":
            tokens.append(Token("comment", match.start(), match.end()))

        elif group == "doctype":
            tokens.append(Token("doctype", match.start(), match.end()))

        elif group == "entity":
            tokens.append(Token("entity", match.start(), match.end()))

        elif group == "tag":
            _tokenize_tag(text, match.start(), match.end(), tokens)

    tokens.sort(key=lambda t: t.start)
    return tokens


def offsets_to_tkindices(text: str, offsets: List[int]) -> Dict[int, str]:
    """Convert character offsets into tkinter ``"line.col"`` index strings.

    Returns a :class:`dict` mapping each offset to its index string.  Runs
    in *O(n + k)* where *n* is ``len(text)`` and *k* is ``len(offsets)``.

    Tkinter indices are 1-based for lines and 0-based for columns:
    offset 0 → ``"1.0"``, the position *before* the first character.
    """
    if not offsets:
        return {}

    sorted_offsets = sorted(set(offsets))
    result: Dict[int, str] = {}
    line, col, pos = 1, 0, 0

    for target in sorted_offsets:
        while pos < target:
            if text[pos] == "\n":
                line += 1
                col = 0
            else:
                col += 1
            pos += 1
        result[target] = f"{line}.{col}"

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _first_matched_group(match: re.Match, names: tuple) -> str | None:
    """Return the first name in *names* whose group actually matched."""
    for name in names:
        if match.group(name) is not None:
            return name
    return None


def _tokenize_tag(
    text: str, start: int, end: int, tokens: List[Token]
) -> None:
    """Append bracket/tag_name/attr_name/attr_value tokens for a single tag."""
    tag_str = text[start:end]
    m = _TAG_RE.match(tag_str)
    if m is None:
        # Unrecognised shape — skip rather than crash.
        return

    slash = m.group("slash")
    name = m.group("name")
    attrs = m.group("attrs")
    closing_bracket = m.group("end")

    # Opening bracket: '<' (1 char) or '</' (2 chars)
    prefix_len = 2 if slash else 1
    bracket_end = start + prefix_len
    tokens.append(Token("bracket", start, bracket_end))

    # Tag name
    name_end = bracket_end + len(name)
    tokens.append(Token("tag_name", bracket_end, name_end))

    # Attributes (offsets relative to start of `attrs` within `text`)
    attrs_offset = name_end
    for attr_m in _ATTR_RE.finditer(attrs):
        tokens.append(Token(
            "attr_name",
            attrs_offset + attr_m.start("attr_name"),
            attrs_offset + attr_m.end("attr_name"),
        ))
        if attr_m.group("attr_value") is not None:
            tokens.append(Token(
                "attr_value",
                attrs_offset + attr_m.start("attr_value"),
                attrs_offset + attr_m.end("attr_value"),
            ))

    # Closing bracket: '>' or '/>'
    close_start = end - len(closing_bracket)
    tokens.append(Token("bracket", close_start, end))
