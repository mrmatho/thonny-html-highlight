"""Tests for HtmlHighlighter.

The highlighter interacts with a tkinter Text widget, so these tests use a
:class:`unittest.mock.MagicMock` in place of a real widget.  This keeps the
suite runnable in headless / CI environments where no display is available.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from thonnycontrib.html_highlight.highlighter import (
    ALL_HTML_TAGS,
    HtmlHighlighter,
    _TOKEN_TO_TAG,
)
from thonnycontrib.html_highlight.tokenizer import Token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_text():
    """A MagicMock standing in for a tkinter Text widget."""
    text = MagicMock()
    # tag_raise may raise TclError on some Tk versions when the tag
    # doesn't exist yet — simulate that for robustness testing.
    text.tag_raise.return_value = None
    return text


@pytest.fixture
def highlighter(mock_text):
    return HtmlHighlighter(mock_text)


# ---------------------------------------------------------------------------
# configure_tags
# ---------------------------------------------------------------------------


class TestConfigureTags:
    def test_all_tags_configured_on_init(self, mock_text):
        HtmlHighlighter(mock_text)
        configured = {c.args[0] for c in mock_text.tag_configure.call_args_list}
        assert set(ALL_HTML_TAGS).issubset(configured)

    def test_configure_tags_called_again_on_demand(self, highlighter, mock_text):
        mock_text.reset_mock()
        highlighter.configure_tags()
        configured = {c.args[0] for c in mock_text.tag_configure.call_args_list}
        assert set(ALL_HTML_TAGS).issubset(configured)

    def test_tag_raise_called_for_each_tag(self, mock_text):
        HtmlHighlighter(mock_text)
        raised = {c.args[0] for c in mock_text.tag_raise.call_args_list}
        assert set(ALL_HTML_TAGS).issubset(raised)

    def test_tclerror_in_tag_raise_is_suppressed(self, mock_text):
        import tkinter as tk
        mock_text.tag_raise.side_effect = tk.TclError("no such tag")
        # Should not raise.
        HtmlHighlighter(mock_text)


# ---------------------------------------------------------------------------
# schedule_update / update deduplication
# ---------------------------------------------------------------------------


class TestScheduleUpdate:
    def test_schedule_posts_after_idle(self, highlighter, mock_text):
        highlighter.schedule_update()
        mock_text.after_idle.assert_called_once()

    def test_second_schedule_before_idle_is_ignored(self, highlighter, mock_text):
        highlighter.schedule_update()
        highlighter.schedule_update()
        assert mock_text.after_idle.call_count == 1

    def test_schedule_resets_after_update(self, highlighter, mock_text):
        mock_text.get.return_value = ""
        highlighter.schedule_update()
        # Simulate idle callback firing.
        callback = mock_text.after_idle.call_args[0][0]
        callback()
        # Now a new schedule should post again.
        mock_text.after_idle.reset_mock()
        highlighter.schedule_update()
        mock_text.after_idle.assert_called_once()


# ---------------------------------------------------------------------------
# _apply_highlighting (via update())
# ---------------------------------------------------------------------------


class TestApplyHighlighting:
    def test_empty_content_removes_tags_only(self, highlighter, mock_text):
        mock_text.get.return_value = ""
        highlighter.update()
        # tag_remove should be called for each HTML tag.
        removed = {c.args[0] for c in mock_text.tag_remove.call_args_list}
        assert set(ALL_HTML_TAGS).issubset(removed)
        # tag_add should never be called for empty content.
        mock_text.tag_add.assert_not_called()

    def test_simple_tag_produces_tag_add_calls(self, highlighter, mock_text):
        mock_text.get.return_value = "<p>"
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "html_bracket" in added_tags
        assert "html_tag_name" in added_tags

    def test_full_html_produces_comment_and_doctype_tags(self, highlighter, mock_text):
        mock_text.get.return_value = "<!DOCTYPE html><!-- hi --><p>"
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "html_doctype" in added_tags
        assert "html_comment" in added_tags

    def test_attribute_produces_attr_name_and_value_tags(self, highlighter, mock_text):
        mock_text.get.return_value = '<div class="foo">'
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "html_attr_name" in added_tags
        assert "html_attr_value" in added_tags

    def test_entity_produces_entity_tag(self, highlighter, mock_text):
        mock_text.get.return_value = "<p>&amp;</p>"
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "html_entity" in added_tags

    def test_embedded_style_produces_css_tags(self, highlighter, mock_text):
        mock_text.get.return_value = "<style>body { color: red; }</style>"
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "css_selector" in added_tags
        assert "css_property" in added_tags
        assert "css_value" in added_tags

    def test_embedded_script_produces_javascript_tags(self, highlighter, mock_text):
        mock_text.get.return_value = '<script>const total = 42; console.log("ok");</script>'
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "js_keyword" in added_tags
        assert "js_number" in added_tags
        assert "js_builtin" in added_tags
        assert "js_string" in added_tags

    def test_css_file_produces_css_tags(self, mock_text):
        highlighter = HtmlHighlighter(mock_text, language="css")
        mock_text.get.return_value = "body { color: red; }"
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "css_selector" in added_tags
        assert "css_property" in added_tags
        assert "css_value" in added_tags

    def test_javascript_file_produces_javascript_tags(self, mock_text):
        highlighter = HtmlHighlighter(mock_text, language="javascript")
        mock_text.get.return_value = 'const total = 42; console.log("ok");'
        highlighter.update()
        added_tags = {c.args[0] for c in mock_text.tag_add.call_args_list}
        assert "js_keyword" in added_tags
        assert "js_number" in added_tags
        assert "js_builtin" in added_tags
        assert "js_string" in added_tags

    def test_tag_add_uses_correct_tkinter_index_format(self, highlighter, mock_text):
        # Simple one-line case: <p> at the start.
        mock_text.get.return_value = "<p>"
        highlighter.update()
        indices = []
        for c in mock_text.tag_add.call_args_list:
            indices.append(c.args[1])
            indices.append(c.args[2])
        # All indices should match the "line.col" pattern.
        import re
        pattern = re.compile(r'^\d+\.\d+$')
        for idx in indices:
            assert pattern.match(idx), f"Bad index format: {idx!r}"

    def test_no_zero_length_tag_add(self, highlighter, mock_text):
        mock_text.get.return_value = "<br />"
        highlighter.update()
        for c in mock_text.tag_add.call_args_list:
            start, end = c.args[1], c.args[2]
            assert start != end, f"Zero-length tag_add: {c}"


# ---------------------------------------------------------------------------
# TOKEN_TO_TAG completeness
# ---------------------------------------------------------------------------


class TestTokenToTagMapping:
    def test_all_known_token_types_have_a_mapping(self):
        known_types = {
            "comment", "doctype", "entity",
            "bracket", "tag_name", "attr_name", "attr_value",
            "css_comment", "css_selector", "css_property", "css_value",
            "js_comment", "js_keyword", "js_builtin", "js_string", "js_number",
        }
        assert known_types == set(_TOKEN_TO_TAG.keys())

    def test_all_mapped_tags_are_in_all_html_tags(self):
        for tag in _TOKEN_TO_TAG.values():
            assert tag in ALL_HTML_TAGS
