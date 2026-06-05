"""Unit tests for the HTML tokenizer.

All tests operate on pure Python data structures — no tkinter, no Thonny.
"""
import pytest

from thonnycontrib.html_highlight.tokenizer import (
    Token,
    offsets_to_tkindices,
    tokenize_html,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def token_types(tokens):
    """Return just the type field of each token as a list."""
    return [t.type for t in tokens]


def tokens_of_type(tokens, type_):
    """Filter tokens by type."""
    return [t for t in tokens if t.type == type_]


def text_for(source, token):
    """Extract the source substring covered by *token*."""
    return source[token.start : token.end]


# ---------------------------------------------------------------------------
# offsets_to_tkindices
# ---------------------------------------------------------------------------


class TestOffsetsToTkindices:
    def test_empty_offsets_returns_empty_dict(self):
        assert offsets_to_tkindices("hello", []) == {}

    def test_offset_zero_is_line1_col0(self):
        result = offsets_to_tkindices("hello", [0])
        assert result[0] == "1.0"

    def test_single_line_offsets(self):
        # "hello" — all on line 1
        result = offsets_to_tkindices("hello", [0, 1, 2, 3, 4, 5])
        assert result == {0: "1.0", 1: "1.1", 2: "1.2", 3: "1.3", 4: "1.4", 5: "1.5"}

    def test_newline_advances_line(self):
        # "hi\nbye"
        source = "hi\nbye"
        result = offsets_to_tkindices(source, [0, 1, 2, 3, 4, 5, 6])
        assert result[0] == "1.0"  # 'h'
        assert result[2] == "1.2"  # '\n'
        assert result[3] == "2.0"  # 'b'
        assert result[6] == "2.3"  # end-of-text

    def test_multiple_newlines(self):
        source = "a\nb\nc"
        result = offsets_to_tkindices(source, [0, 2, 4])
        assert result[0] == "1.0"  # 'a'
        assert result[2] == "2.0"  # 'b'
        assert result[4] == "3.0"  # 'c'

    def test_duplicate_offsets_deduplicated(self):
        result = offsets_to_tkindices("abc", [1, 1, 1])
        assert result == {1: "1.1"}

    def test_unsorted_offsets_handled(self):
        result = offsets_to_tkindices("abc", [2, 0, 1])
        assert result[0] == "1.0"
        assert result[1] == "1.1"
        assert result[2] == "1.2"


# ---------------------------------------------------------------------------
# tokenize_html — empty / trivial input
# ---------------------------------------------------------------------------


class TestTokenizeHtmlTrivial:
    def test_empty_string(self):
        assert tokenize_html("") == []

    def test_plain_text_produces_no_tokens(self):
        assert tokenize_html("Hello, world!") == []

    def test_tokens_sorted_by_start(self):
        source = "<b>text</b>"
        tokens = tokenize_html(source)
        starts = [t.start for t in tokens]
        assert starts == sorted(starts)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


class TestComments:
    def test_simple_comment(self):
        source = "<!-- hello -->"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        assert tokens[0].type == "comment"
        assert text_for(source, tokens[0]) == "<!-- hello -->"

    def test_comment_start_end_offsets(self):
        source = "x<!-- c -->y"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        t = tokens[0]
        assert t.start == 1
        assert t.end == 11

    def test_multiline_comment(self):
        source = "<!--\nline1\nline2\n-->"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        assert tokens[0].type == "comment"
        assert text_for(source, tokens[0]) == source

    def test_comment_with_hyphens_inside(self):
        source = "<!-- a - b -->"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        assert tokens[0].type == "comment"


# ---------------------------------------------------------------------------
# DOCTYPE
# ---------------------------------------------------------------------------


class TestDoctype:
    def test_html5_doctype(self):
        source = "<!DOCTYPE html>"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        assert tokens[0].type == "doctype"
        assert text_for(source, tokens[0]) == "<!DOCTYPE html>"

    def test_doctype_case_insensitive(self):
        source = "<!doctype html>"
        tokens = tokenize_html(source)
        assert any(t.type == "doctype" for t in tokens)


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class TestEntities:
    def test_named_entity(self):
        source = "&amp;"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        assert tokens[0].type == "entity"
        assert text_for(source, tokens[0]) == "&amp;"

    def test_numeric_entity(self):
        source = "&#169;"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        assert tokens[0].type == "entity"

    def test_hex_entity(self):
        source = "&#xA9;"
        tokens = tokenize_html(source)
        assert len(tokens) == 1
        assert tokens[0].type == "entity"

    def test_entity_in_context(self):
        source = "<p>a &lt; b</p>"
        tokens = tokenize_html(source)
        entity_tokens = tokens_of_type(tokens, "entity")
        assert len(entity_tokens) == 1
        assert text_for(source, entity_tokens[0]) == "&lt;"


# ---------------------------------------------------------------------------
# Tags — brackets and tag names
# ---------------------------------------------------------------------------


class TestTagBracketsAndNames:
    def test_opening_tag_bracket(self):
        source = "<div>"
        tokens = tokenize_html(source)
        brackets = tokens_of_type(tokens, "bracket")
        assert len(brackets) == 2
        # Opening '<'
        assert text_for(source, brackets[0]) == "<"
        # Closing '>'
        assert text_for(source, brackets[1]) == ">"

    def test_opening_tag_name(self):
        source = "<div>"
        tokens = tokenize_html(source)
        names = tokens_of_type(tokens, "tag_name")
        assert len(names) == 1
        assert text_for(source, names[0]) == "div"

    def test_closing_tag_bracket(self):
        source = "</div>"
        tokens = tokenize_html(source)
        brackets = tokens_of_type(tokens, "bracket")
        assert text_for(source, brackets[0]) == "</"

    def test_closing_tag_name(self):
        source = "</div>"
        tokens = tokenize_html(source)
        names = tokens_of_type(tokens, "tag_name")
        assert len(names) == 1
        assert text_for(source, names[0]) == "div"

    def test_self_closing_tag(self):
        source = "<br />"
        tokens = tokenize_html(source)
        brackets = tokens_of_type(tokens, "bracket")
        assert text_for(source, brackets[-1]) == "/>"

    def test_void_element_without_slash(self):
        source = "<img>"
        tokens = tokenize_html(source)
        assert any(t.type == "tag_name" and text_for(source, t) == "img" for t in tokens)

    def test_tag_name_with_namespace(self):
        source = "<svg:circle>"
        tokens = tokenize_html(source)
        names = tokens_of_type(tokens, "tag_name")
        assert len(names) == 1
        assert text_for(source, names[0]) == "svg:circle"

    def test_no_false_bracket_outside_tags(self):
        source = "a < b"
        tokens = tokenize_html(source)
        assert token_types(tokens) == []


# ---------------------------------------------------------------------------
# Attributes
# ---------------------------------------------------------------------------


class TestAttributes:
    def test_single_attribute_name(self):
        source = '<div class="foo">'
        tokens = tokenize_html(source)
        attr_names = tokens_of_type(tokens, "attr_name")
        assert len(attr_names) == 1
        assert text_for(source, attr_names[0]) == "class"

    def test_single_attribute_value(self):
        source = '<div class="foo">'
        tokens = tokenize_html(source)
        attr_values = tokens_of_type(tokens, "attr_value")
        assert len(attr_values) == 1
        assert text_for(source, attr_values[0]) == '"foo"'

    def test_multiple_attributes(self):
        source = '<a href="/page" id="nav" class="link">'
        tokens = tokenize_html(source)
        attr_names = tokens_of_type(tokens, "attr_name")
        assert [text_for(source, t) for t in attr_names] == ["href", "id", "class"]

    def test_boolean_attribute_has_no_value(self):
        source = "<input disabled>"
        tokens = tokenize_html(source)
        attr_names = tokens_of_type(tokens, "attr_name")
        assert any(text_for(source, t) == "disabled" for t in attr_names)
        assert tokens_of_type(tokens, "attr_value") == []

    def test_single_quoted_attribute_value(self):
        source = "<div class='bar'>"
        tokens = tokenize_html(source)
        attr_values = tokens_of_type(tokens, "attr_value")
        assert len(attr_values) == 1
        assert text_for(source, attr_values[0]) == "'bar'"

    def test_attribute_value_containing_gt(self):
        # A '>' inside a quoted value must not terminate the tag.
        source = '<div title="a > b">'
        tokens = tokenize_html(source)
        attr_values = tokens_of_type(tokens, "attr_value")
        assert len(attr_values) == 1
        assert text_for(source, attr_values[0]) == '"a > b"'

    def test_hyphenated_attribute_name(self):
        source = '<div data-value="42">'
        tokens = tokenize_html(source)
        attr_names = tokens_of_type(tokens, "attr_name")
        assert any(text_for(source, t) == "data-value" for t in attr_names)

    def test_namespaced_attribute(self):
        source = '<svg xml:lang="en">'
        tokens = tokenize_html(source)
        attr_names = tokens_of_type(tokens, "attr_name")
        assert any(text_for(source, t) == "xml:lang" for t in attr_names)

    def test_mixed_boolean_and_valued_attributes(self):
        source = '<input type="checkbox" checked>'
        tokens = tokenize_html(source)
        attr_names = [text_for(source, t) for t in tokens_of_type(tokens, "attr_name")]
        assert "type" in attr_names
        assert "checked" in attr_names
        attr_values = [text_for(source, t) for t in tokens_of_type(tokens, "attr_value")]
        assert '"checkbox"' in attr_values


# ---------------------------------------------------------------------------
# Full documents
# ---------------------------------------------------------------------------


class TestFullDocument:
    _HTML5 = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Test &amp; Demo</title>
</head>
<body>
  <!-- main content -->
  <p class="intro">Hello <strong>world</strong></p>
</body>
</html>"""

    def test_doctype_present(self):
        tokens = tokenize_html(self._HTML5)
        assert any(t.type == "doctype" for t in tokens)

    def test_comment_present(self):
        tokens = tokenize_html(self._HTML5)
        assert any(t.type == "comment" for t in tokens)

    def test_entity_present(self):
        tokens = tokenize_html(self._HTML5)
        assert any(t.type == "entity" for t in tokens)

    def test_tag_names_include_expected(self):
        tokens = tokenize_html(self._HTML5)
        found = {text_for(self._HTML5, t) for t in tokens_of_type(tokens, "tag_name")}
        assert {"html", "head", "body", "title", "p", "strong", "meta"}.issubset(found)

    def test_no_token_overlaps(self):
        tokens = tokenize_html(self._HTML5)
        for i, a in enumerate(tokens):
            for b in tokens[i + 1 :]:
                assert a.end <= b.start or b.end <= a.start, (
                    f"Tokens overlap: {a!r} and {b!r}"
                )

    def test_all_offsets_within_bounds(self):
        source = self._HTML5
        tokens = tokenize_html(source)
        for t in tokens:
            assert 0 <= t.start < len(source), f"start out of bounds: {t!r}"
            assert 0 < t.end <= len(source), f"end out of bounds: {t!r}"
            assert t.start < t.end, f"zero-length token: {t!r}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_unclosed_tag_produces_no_tokens(self):
        # An unclosed tag is not matched by the regex — no crash.
        tokens = tokenize_html("<div class")
        assert tokens == []

    def test_tag_with_multiline_attributes(self):
        source = '<div\n  class="foo"\n  id="bar"\n>'
        tokens = tokenize_html(source)
        attr_names = [text_for(source, t) for t in tokens_of_type(tokens, "attr_name")]
        assert "class" in attr_names
        assert "id" in attr_names

    def test_adjacent_tags(self):
        source = "<em><strong>"
        tokens = tokenize_html(source)
        names = [text_for(source, t) for t in tokens_of_type(tokens, "tag_name")]
        assert names == ["em", "strong"]

    def test_self_closing_img(self):
        source = '<img src="photo.jpg" alt="A photo" />'
        tokens = tokenize_html(source)
        attr_names = [text_for(source, t) for t in tokens_of_type(tokens, "attr_name")]
        assert "src" in attr_names
        assert "alt" in attr_names
        brackets = tokens_of_type(tokens, "bracket")
        assert text_for(source, brackets[-1]) == "/>"
