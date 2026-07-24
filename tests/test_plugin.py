"""Tests for the plugin entry point (__init__.py).

These tests verify the event-handler wiring without requiring a running Thonny
instance or a real tkinter display.

Test doubles use ``types.SimpleNamespace`` rather than bare ``MagicMock`` so
that ``hasattr`` and ``isinstance`` behave like they do on real widgets.
``MagicMock`` auto-creates every attribute on access, which would make
``hasattr(text, "_html_highlighter")`` permanently True and break all
"not yet created" assertions.
"""
from __future__ import annotations

import types
from unittest.mock import MagicMock

import pytest

from thonnycontrib.html_highlight import (
    _highlight_editor,
    _is_html_file,
    _on_file_open,
    _on_text_change,
)
from thonnycontrib.html_highlight.highlighter import HtmlHighlighter


# ---------------------------------------------------------------------------
# Test-double factories
# ---------------------------------------------------------------------------


def _make_text(path: str | None = None, content: str = "") -> types.SimpleNamespace:
    """Minimal text-widget test double with explicit, finite attributes.

    Unlike a bare ``MagicMock``, this object only has the attributes we
    explicitly set, so ``hasattr(text, "_html_highlighter")`` starts as
    ``False`` and ``isinstance`` checks work correctly.
    """
    text = types.SimpleNamespace()
    text.file_type = None
    text.get = MagicMock(return_value=content)
    text.tag_configure = MagicMock()
    text.tag_add = MagicMock()
    text.tag_remove = MagicMock()
    text.tag_raise = MagicMock()
    text.after_idle = MagicMock()
    text.cget = MagicMock(return_value="TkFixedFont")

    def _set_file_type(ft):
        text.file_type = ft

    text.set_file_type = MagicMock(side_effect=_set_file_type)

    # Widget hierarchy (Thonny 5.0): text.master → CodeView, CodeView.home_widget → Editor
    base_editor = types.SimpleNamespace()
    base_editor.get_filename = MagicMock(return_value=path)
    code_view = types.SimpleNamespace()
    code_view.home_widget = base_editor
    text.master = code_view

    return text


def _make_editor(path: str | None = None, content: str = "") -> types.SimpleNamespace:
    """Minimal Editor test double (Thonny 5.0 API)."""
    editor = types.SimpleNamespace()
    editor.get_filename = MagicMock(return_value=path)
    text = _make_text(path, content)
    code_view = types.SimpleNamespace()
    code_view.text = text
    editor._code_view = code_view
    return editor


def _make_text_event(path: str | None = None, content: str = "") -> types.SimpleNamespace:
    """Fake <<TextChange>> event pointing at a text test double."""
    event = types.SimpleNamespace()
    event.widget = _make_text(path, content)
    return event


# ---------------------------------------------------------------------------
# _is_html_file
# ---------------------------------------------------------------------------


class TestIsHtmlFile:
    def test_html_extension_returns_true(self):
        assert _is_html_file(_make_text("/project/index.html")) is True

    def test_htm_extension_returns_true(self):
        assert _is_html_file(_make_text("/project/page.htm")) is True

    def test_uppercase_extension_returns_true(self):
        assert _is_html_file(_make_text("/project/INDEX.HTML")) is True

    def test_python_file_returns_false(self):
        assert _is_html_file(_make_text("/project/app.py")) is False

    def test_untitled_returns_false(self):
        assert _is_html_file(_make_text(None)) is False

    def test_missing_hierarchy_returns_false(self):
        # A bare SimpleNamespace with no .master raises AttributeError inside
        # _get_editor_path, which should be swallowed and return False.
        text = types.SimpleNamespace()
        assert _is_html_file(text) is False


# ---------------------------------------------------------------------------
# _on_file_open  (the fix for direct_insert bypassing <<TextChange>>)
# ---------------------------------------------------------------------------


class TestOnFileOpen:
    def test_highlights_html_editor_on_open(self):
        editor = _make_editor("/project/index.html", "<h1>Hi</h1>")
        event = types.SimpleNamespace(editor=editor)

        _on_file_open(event)

        # after_idle is used; invoke the deferred callback manually
        text = editor._code_view.text
        text.after_idle.assert_called_once()
        cb = text.after_idle.call_args[0][0]
        cb()

        assert isinstance(text._html_highlighter, HtmlHighlighter)
        text.tag_add.assert_called()

    def test_skips_non_html_editor(self):
        editor = _make_editor("/project/app.py", "print('hi')")
        event = types.SimpleNamespace(editor=editor)

        _on_file_open(event)

        editor._code_view.text.after_idle.assert_not_called()
        assert not hasattr(editor._code_view.text, "_html_highlighter")

    def test_highlights_css_editor_on_open(self):
        editor = _make_editor("/project/site.css", "body { color: red; }")
        event = types.SimpleNamespace(editor=editor)

        _on_file_open(event)

        text = editor._code_view.text
        text.after_idle.assert_called_once()
        cb = text.after_idle.call_args[0][0]
        cb()

        assert isinstance(text._html_highlighter, HtmlHighlighter)
        assert text.file_type == "css"

    def test_highlights_javascript_editor_on_open(self):
        editor = _make_editor("/project/app.js", 'const total = 42; console.log("ok");')
        event = types.SimpleNamespace(editor=editor)

        _on_file_open(event)

        text = editor._code_view.text
        text.after_idle.assert_called_once()
        cb = text.after_idle.call_args[0][0]
        cb()

        assert isinstance(text._html_highlighter, HtmlHighlighter)
        assert text.file_type == "javascript"

    def test_no_editor_attribute_is_safe(self):
        event = types.SimpleNamespace()  # no .editor attribute
        _on_file_open(event)             # must not raise


# ---------------------------------------------------------------------------
# _on_text_change
# ---------------------------------------------------------------------------


class TestOnTextChange:
    def test_html_file_gets_highlighter_attached(self):
        event = _make_text_event("/project/index.html", "<p>hello</p>")

        _on_text_change(event)

        assert isinstance(event.widget._html_highlighter, HtmlHighlighter)

    def test_non_html_file_skipped(self):
        event = _make_text_event("/project/app.py")

        _on_text_change(event)

        assert not hasattr(event.widget, "_html_highlighter")

    def test_css_file_gets_highlighter_attached(self):
        event = _make_text_event("/project/site.css", "body { color: red; }")

        _on_text_change(event)

        assert isinstance(event.widget._html_highlighter, HtmlHighlighter)
        assert event.widget.file_type == "css"

    def test_javascript_file_gets_highlighter_attached(self):
        event = _make_text_event("/project/app.js", 'const total = 42; console.log("ok");')

        _on_text_change(event)

        assert isinstance(event.widget._html_highlighter, HtmlHighlighter)
        assert event.widget.file_type == "javascript"

    def test_sets_file_type_to_html(self):
        event = _make_text_event("/project/index.html", "<p/>")

        _on_text_change(event)

        event.widget.set_file_type.assert_called_with("html")
        assert event.widget.file_type == "html"

    def test_does_not_reset_file_type_if_already_html(self):
        event = _make_text_event("/project/index.html", "<p/>")
        event.widget.file_type = "html"

        _on_text_change(event)

        event.widget.set_file_type.assert_not_called()

    def test_schedules_update_not_immediate(self):
        event = _make_text_event("/project/index.html", "<p/>")

        _on_text_change(event)

        # schedule_update defers via after_idle; tag_add must NOT be called yet
        event.widget.after_idle.assert_called_once()
        event.widget.tag_add.assert_not_called()

    def test_existing_highlighter_reused(self):
        event = _make_text_event("/project/index.html", "<p/>")
        existing = MagicMock(spec=HtmlHighlighter)
        event.widget._html_highlighter = existing
        event.widget.file_type = "html"

        _on_text_change(event)

        existing.schedule_update.assert_called_once()

    def test_existing_highlighter_language_updated(self):
        event = _make_text_event("/project/app.js", "let count = 1;")
        existing = MagicMock(spec=HtmlHighlighter)
        event.widget._html_highlighter = existing

        _on_text_change(event)

        assert existing.language == "javascript"
        existing.schedule_update.assert_called_once()


# ---------------------------------------------------------------------------
# _highlight_editor
# ---------------------------------------------------------------------------


class TestHighlightEditor:
    def test_applies_tags_to_html_editor(self):
        editor = _make_editor("/project/index.html", "<h1>Hi</h1>")

        _highlight_editor(editor)

        editor._code_view.text.tag_add.assert_called()

    def test_skips_editor_with_no_path(self):
        editor = _make_editor(None)

        _highlight_editor(editor)

        editor._code_view.text.tag_add.assert_not_called()

    def test_applies_tags_to_css_editor(self):
        editor = _make_editor("/project/site.css", "body { color: red; }")

        _highlight_editor(editor)

        assert editor._code_view.text.file_type == "css"
        editor._code_view.text.tag_add.assert_called()

    def test_applies_tags_to_javascript_editor(self):
        editor = _make_editor("/project/app.js", 'const total = 42; console.log("ok");')

        _highlight_editor(editor)

        assert editor._code_view.text.file_type == "javascript"
        editor._code_view.text.tag_add.assert_called()

    def test_creates_highlighter_on_first_call(self):
        editor = _make_editor("/page.html", "")
        assert not hasattr(editor._code_view.text, "_html_highlighter")

        _highlight_editor(editor)

        assert isinstance(editor._code_view.text._html_highlighter, HtmlHighlighter)

    def test_reuses_existing_highlighter(self):
        editor = _make_editor("/page.html", "")
        existing = MagicMock(spec=HtmlHighlighter)
        editor._code_view.text._html_highlighter = existing

        _highlight_editor(editor)

        existing.update.assert_called_once()

    def test_missing_code_view_is_safe(self):
        editor = types.SimpleNamespace()
        editor.get_target_path = MagicMock(return_value="/page.html")
        # no _code_view attribute
        _highlight_editor(editor)  # must not raise
