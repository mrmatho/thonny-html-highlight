"""Tokenizers for HTML, CSS, and JavaScript syntax highlighting."""
from __future__ import annotations

import re
from typing import Dict, List, NamedTuple


class Token(NamedTuple):
    """A single syntax token within a document."""

    type: str
    start: int
    end: int


_TOP_LEVEL_RE = re.compile(
    r"(?P<comment><!--[\s\S]*?-->)"
    r"|(?P<doctype><!DOCTYPE[^>]*>)"
    r"|(?P<entity>&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);)"
    r'|(?P<tag></?[a-zA-Z][a-zA-Z0-9_:-]*(?:"[^"]*"|\'[^\']*\'|[^>])*>)',
    re.DOTALL | re.IGNORECASE,
)

_TAG_RE = re.compile(
    r'^<(?P<slash>/?)(?P<name>[a-zA-Z][a-zA-Z0-9_:-]*)'
    r'(?P<attrs>(?:"[^"]*"|\'[^\']*\'|(?!/>)[^>])*)'
    r'(?P<end>/?>)$',
    re.DOTALL,
)

_ATTR_RE = re.compile(
    r'(?P<attr_name>[a-zA-Z_:][a-zA-Z0-9_.:-]*)'
    r'(?:\s*=\s*(?P<attr_value>"[^"]*"|\'[^\']*\'|[^\s>]*))?'
)

_CSS_PROPERTY_RE = re.compile(r"(?:--[a-zA-Z0-9_-]+|[a-zA-Z_-][a-zA-Z0-9_-]*)")
_JS_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_JS_NUMBER_RE = re.compile(
    r"(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
)

_TOP_LEVEL_GROUPS = ("comment", "doctype", "entity", "tag")
_RAW_TEXT_TAGS = {
    "script": ("javascript", re.compile(r"</script\s*>", re.IGNORECASE)),
    "style": ("css", re.compile(r"</style\s*>", re.IGNORECASE)),
}

_JS_KEYWORDS = {
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "debugger",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "finally",
    "for",
    "function",
    "if",
    "import",
    "in",
    "instanceof",
    "let",
    "new",
    "return",
    "static",
    "super",
    "switch",
    "this",
    "throw",
    "try",
    "typeof",
    "var",
    "void",
    "while",
    "with",
    "yield",
}

_JS_BUILTINS = {
    "Array",
    "Boolean",
    "Date",
    "JSON",
    "Math",
    "Number",
    "Object",
    "Promise",
    "RegExp",
    "String",
    "console",
    "document",
    "window",
}


def tokenize_document(text: str, language: str) -> List[Token]:
    """Tokenize *text* according to *language*."""
    if language == "css":
        return tokenize_css(text)
    if language == "javascript":
        return tokenize_javascript(text)
    return tokenize_html(text)


def tokenize_html(text: str) -> List[Token]:
    """Return tokens for an HTML document, including style and script blocks."""
    tokens: List[Token] = []
    pos = 0

    while True:
        match = _TOP_LEVEL_RE.search(text, pos)
        if match is None:
            break

        group = _first_matched_group(match, _TOP_LEVEL_GROUPS)

        if group == "comment":
            tokens.append(Token("comment", match.start(), match.end()))
            pos = match.end()
            continue

        if group == "doctype":
            tokens.append(Token("doctype", match.start(), match.end()))
            pos = match.end()
            continue

        if group == "entity":
            tokens.append(Token("entity", match.start(), match.end()))
            pos = match.end()
            continue

        tag_name = _get_tag_name(text[match.start():match.end()])
        _tokenize_tag(text, match.start(), match.end(), tokens)

        if tag_name in _RAW_TEXT_TAGS and not _is_closing_tag(text[match.start():match.end()]):
            raw_language, closing_re = _RAW_TEXT_TAGS[tag_name]
            closing_match = closing_re.search(text, match.end())
            raw_end = closing_match.start() if closing_match else len(text)

            if raw_end > match.end():
                raw_text = text[match.end():raw_end]
                if raw_language == "css":
                    tokens.extend(tokenize_css(raw_text, base_offset=match.end()))
                else:
                    tokens.extend(tokenize_javascript(raw_text, base_offset=match.end()))

            if closing_match is not None:
                _tokenize_tag(text, closing_match.start(), closing_match.end(), tokens)
                pos = closing_match.end()
            else:
                pos = raw_end
        else:
            pos = match.end()

    tokens.sort(key=lambda t: (t.start, t.end))
    return tokens


def tokenize_css(text: str, base_offset: int = 0) -> List[Token]:
    """Return tokens for CSS source."""
    tokens: List[Token] = []
    length = len(text)
    pos = 0
    depth = 0

    while pos < length:
        if text.startswith("/*", pos):
            end = text.find("*/", pos + 2)
            end = length if end == -1 else end + 2
            tokens.append(Token("css_comment", base_offset + pos, base_offset + end))
            pos = end
            continue

        if depth == 0:
            segment_end = pos
            while segment_end < length and text[segment_end] != "{":
                if text.startswith("/*", segment_end):
                    break
                segment_end += 1

            _append_css_selector_tokens(text, pos, segment_end, base_offset, tokens)

            if segment_end >= length:
                break
            if text.startswith("/*", segment_end):
                pos = segment_end
                continue

            depth += 1
            pos = segment_end + 1
            continue

        if text[pos].isspace() or text[pos] == ";":
            pos += 1
            continue

        if text[pos] == "}":
            depth = max(0, depth - 1)
            pos += 1
            continue

        name_match = _CSS_PROPERTY_RE.match(text, pos)
        if name_match is None:
            next_control = _find_css_control(text, pos)
            if next_control == pos:
                pos += 1
            elif next_control == -1:
                break
            else:
                _append_css_selector_tokens(text, pos, next_control, base_offset, tokens)
                if next_control < length and text[next_control] == "{":
                    depth += 1
                    pos = next_control + 1
                else:
                    pos = next_control
            continue

        cursor = name_match.end()
        while cursor < length and text[cursor].isspace():
            cursor += 1

        if cursor < length and text[cursor] == "{":
            _append_css_selector_tokens(text, pos, cursor, base_offset, tokens)
            depth += 1
            pos = cursor + 1
            continue

        if cursor >= length or text[cursor] != ":":
            pos = cursor + 1
            continue

        tokens.append(Token("css_property", base_offset + name_match.start(), base_offset + name_match.end()))
        value_start = cursor + 1
        value_end = _scan_css_value_end(text, value_start)
        stripped_start, stripped_end = _trim_span(text, value_start, value_end)
        if stripped_start < stripped_end:
            tokens.append(Token("css_value", base_offset + stripped_start, base_offset + stripped_end))

        pos = value_end
        if pos < length and text[pos] == ";":
            pos += 1

    tokens.sort(key=lambda t: (t.start, t.end))
    return tokens


def tokenize_javascript(text: str, base_offset: int = 0) -> List[Token]:
    """Return tokens for JavaScript source."""
    tokens: List[Token] = []
    length = len(text)
    pos = 0

    while pos < length:
        if text.startswith("//", pos):
            end = text.find("\n", pos)
            end = length if end == -1 else end
            tokens.append(Token("js_comment", base_offset + pos, base_offset + end))
            pos = end
            continue

        if text.startswith("/*", pos):
            end = text.find("*/", pos + 2)
            end = length if end == -1 else end + 2
            tokens.append(Token("js_comment", base_offset + pos, base_offset + end))
            pos = end
            continue

        char = text[pos]
        if char in {"'", '"', "`"}:
            end = _scan_quoted_string(text, pos, char)
            tokens.append(Token("js_string", base_offset + pos, base_offset + end))
            pos = end
            continue

        if char.isdigit() or (char == "." and pos + 1 < length and text[pos + 1].isdigit()):
            number_match = _JS_NUMBER_RE.match(text, pos)
            if number_match is not None:
                tokens.append(
                    Token("js_number", base_offset + number_match.start(), base_offset + number_match.end())
                )
                pos = number_match.end()
                continue

        ident_match = _JS_IDENTIFIER_RE.match(text, pos)
        if ident_match is not None:
            ident = ident_match.group(0)
            token_type = None
            if ident in _JS_KEYWORDS:
                token_type = "js_keyword"
            elif ident in _JS_BUILTINS:
                token_type = "js_builtin"

            if token_type is not None:
                tokens.append(Token(token_type, base_offset + ident_match.start(), base_offset + ident_match.end()))

            pos = ident_match.end()
            continue

        pos += 1

    tokens.sort(key=lambda t: (t.start, t.end))
    return tokens


def offsets_to_tkindices(text: str, offsets: List[int]) -> Dict[int, str]:
    """Convert character offsets into tkinter ``"line.col"`` index strings."""
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


def _first_matched_group(match: re.Match, names: tuple[str, ...]) -> str | None:
    for name in names:
        if match.group(name) is not None:
            return name
    return None


def _tokenize_tag(text: str, start: int, end: int, tokens: List[Token]) -> None:
    tag_str = text[start:end]
    match = _TAG_RE.match(tag_str)
    if match is None:
        return

    slash = match.group("slash")
    name = match.group("name")
    attrs = match.group("attrs")
    closing_bracket = match.group("end")

    prefix_len = 2 if slash else 1
    bracket_end = start + prefix_len
    tokens.append(Token("bracket", start, bracket_end))

    name_end = bracket_end + len(name)
    tokens.append(Token("tag_name", bracket_end, name_end))

    attrs_offset = name_end
    for attr_match in _ATTR_RE.finditer(attrs):
        tokens.append(
            Token(
                "attr_name",
                attrs_offset + attr_match.start("attr_name"),
                attrs_offset + attr_match.end("attr_name"),
            )
        )
        if attr_match.group("attr_value") is not None:
            tokens.append(
                Token(
                    "attr_value",
                    attrs_offset + attr_match.start("attr_value"),
                    attrs_offset + attr_match.end("attr_value"),
                )
            )

    close_start = end - len(closing_bracket)
    tokens.append(Token("bracket", close_start, end))


def _get_tag_name(tag_text: str) -> str | None:
    match = _TAG_RE.match(tag_text)
    if match is None:
        return None
    return match.group("name").lower()


def _is_closing_tag(tag_text: str) -> bool:
    match = _TAG_RE.match(tag_text)
    return bool(match and match.group("slash"))


def _append_css_selector_tokens(
    text: str, start: int, end: int, base_offset: int, tokens: List[Token]
) -> None:
    segment = text[start:end]
    if not segment:
        return

    cursor = 0
    while cursor < len(segment):
        comma = segment.find(",", cursor)
        part_end = len(segment) if comma == -1 else comma
        part_start = cursor
        while part_start < part_end and segment[part_start].isspace():
            part_start += 1
        while part_end > part_start and segment[part_end - 1].isspace():
            part_end -= 1
        if part_start < part_end:
            tokens.append(
                Token("css_selector", base_offset + start + part_start, base_offset + start + part_end)
            )
        if comma == -1:
            break
        cursor = comma + 1


def _find_css_control(text: str, start: int) -> int:
    pos = start
    while pos < len(text):
        if text.startswith("/*", pos) or text[pos] in "{};":
            return pos
        pos += 1
    return -1


def _scan_css_value_end(text: str, start: int) -> int:
    pos = start
    length = len(text)
    paren_depth = 0

    while pos < length:
        if text.startswith("/*", pos):
            end = text.find("*/", pos + 2)
            pos = length if end == -1 else end + 2
            continue

        char = text[pos]
        if char in {"'", '"'}:
            pos = _scan_quoted_string(text, pos, char)
            continue
        if char == "(":
            paren_depth += 1
        elif char == ")" and paren_depth > 0:
            paren_depth -= 1
        elif paren_depth == 0 and char in {";", "}"}:
            break
        pos += 1

    return pos


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _scan_quoted_string(text: str, start: int, quote: str) -> int:
    pos = start + 1
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            pos += 2
            continue
        if char == quote:
            return pos + 1
        pos += 1
    return len(text)
