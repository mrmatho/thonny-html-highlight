"""Applies HTML, CSS, and JavaScript syntax highlighting to a Thonny editor.

The :class:`HtmlHighlighter` owns all interaction with the tkinter Text
widget.  It reads tokens from :mod:`.tokenizer` and applies named tags.

Colours are resolved in priority order:

1. Thonny's active syntax theme, via ``get_workbench().get_syntax_options_for_tag()``.
   HTML token types are mapped to semantically equivalent Python token names so
   that any Thonny theme (light or dark) produces readable colours automatically.
2. Hard-coded fallback colours selected for readability on both light and dark
   backgrounds.  The appropriate set is chosen by measuring the luminance of the
   text widget's background colour.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, List

from .tokenizer import Token, offsets_to_tkindices, tokenize_document

if TYPE_CHECKING:
    pass  # kept for future type-only imports (e.g. SyntaxText)


# ---------------------------------------------------------------------------
# Tag configuration helpers
# ---------------------------------------------------------------------------

# Maps each HTML tkinter tag to the Thonny Python-syntax tag whose colour
# is semantically appropriate.  Tags with no natural mapping (html_bracket)
# are omitted and handled via the fallback tables.
_THONNY_TAG_MAP: dict[str, str] = {
    "html_comment":    "comment",
    "html_doctype":    "comment",
    "html_tag_name":   "keyword",
    "html_attr_name":  "builtin",
    "html_attr_value": "string",
    "html_entity":     "string",
    "css_comment":     "comment",
    "css_selector":    "keyword",
    "css_property":    "builtin",
    "css_value":       "string",
    "js_comment":      "comment",
    "js_keyword":      "keyword",
    "js_builtin":      "builtin",
    "js_string":       "string",
    "js_number":       "number",
}

# Fallback palettes used when Thonny's theme API is unavailable.
_LIGHT_FALLBACKS: dict[str, str] = {
    "html_comment":    "#6A9955",   # muted green
    "html_doctype":    "#808080",   # grey
    "html_tag_name":   "#0000CC",   # dark blue
    "html_attr_name":  "#912B6C",   # magenta/purple
    "html_attr_value": "#007A00",   # dark green
    "html_entity":     "#007070",   # teal
    "html_bracket":    "#606060",   # dark grey
    "css_comment":     "#6A9955",
    "css_selector":    "#7A3E9D",
    "css_property":    "#912B6C",
    "css_value":       "#007A00",
    "js_comment":      "#6A9955",
    "js_keyword":      "#0000CC",
    "js_builtin":      "#267F99",
    "js_string":       "#A31515",
    "js_number":       "#098658",
}

_DARK_FALLBACKS: dict[str, str] = {
    "html_comment":    "#6A9955",   # same green (readable on dark)
    "html_doctype":    "#888888",   # grey
    "html_tag_name":   "#569CD6",   # light blue
    "html_attr_name":  "#9CDCFE",   # pale blue
    "html_attr_value": "#CE9178",   # orange/salmon
    "html_entity":     "#4EC9B0",   # teal
    "html_bracket":    "#AAAAAA",   # light grey
    "css_comment":     "#6A9955",
    "css_selector":    "#C586C0",
    "css_property":    "#9CDCFE",
    "css_value":       "#CE9178",
    "js_comment":      "#6A9955",
    "js_keyword":      "#569CD6",
    "js_builtin":      "#4FC1FF",
    "js_string":       "#CE9178",
    "js_number":       "#B5CEA8",
}


def _get_theme_color(thonny_tag: str) -> str | None:
    """Return the foreground colour for a Thonny syntax tag, or ``None``."""
    try:
        from thonny import get_workbench  # noqa: PLC0415
        opts = get_workbench().get_syntax_options_for_tag(thonny_tag)
        return opts.get("foreground") if opts else None
    except Exception:
        return None


def _background_is_dark(text: tk.Text) -> bool:
    """Return ``True`` if *text*'s background colour has low luminance."""
    try:
        bg = text.cget("background")
        r, g, b = text.winfo_rgb(bg)
        # winfo_rgb returns 16-bit values (0–65535); threshold at 50 %
        return (0.299 * r + 0.587 * g + 0.114 * b) < 32768
    except Exception:
        return False

# Map from tokenizer token type → tkinter tag name.
_TOKEN_TO_TAG: dict[str, str] = {
    "comment":   "html_comment",
    "doctype":   "html_doctype",
    "tag_name":  "html_tag_name",
    "attr_name": "html_attr_name",
    "attr_value":"html_attr_value",
    "entity":    "html_entity",
    "bracket":   "html_bracket",
    "css_comment": "css_comment",
    "css_selector": "css_selector",
    "css_property": "css_property",
    "css_value": "css_value",
    "js_comment": "js_comment",
    "js_keyword": "js_keyword",
    "js_builtin": "js_builtin",
    "js_string": "js_string",
    "js_number": "js_number",
}

ALL_HTML_TAGS: List[str] = list(_TOKEN_TO_TAG.values())
ALL_HIGHLIGHT_TAGS: List[str] = ALL_HTML_TAGS


# ---------------------------------------------------------------------------
# Highlighter
# ---------------------------------------------------------------------------


class HtmlHighlighter:
    """Manages HTML syntax highlighting for a single editor text widget.

    One instance is created per text widget the first time an HTML file is
    opened in that widget.  It is stored as ``text._html_highlighter`` so
    that it is garbage-collected when the widget is destroyed.

    Updating is *scheduled* rather than immediate: when :meth:`schedule_update`
    is called (e.g. on every keystroke), it posts a single ``after_idle``
    callback, deduplicating rapid successive calls.
    """

    def __init__(self, text: tk.Text, language: str = "html") -> None:
        self._text = text
        self.language = language
        self._update_scheduled = False
        self.configure_tags()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def configure_tags(self) -> None:
        """Configure tkinter tag colours from Thonny's active theme.

        Called once on initialisation and again whenever the Thonny
        appearance changes (``<<UpdateAppearance>>`` event).

        Colours are read from Thonny's syntax-theme API where possible so
        that both light and dark themes produce readable results.  When the
        API is unavailable a built-in palette is selected based on the
        widget's background luminance.
        """
        fallbacks = _DARK_FALLBACKS if _background_is_dark(self._text) else _LIGHT_FALLBACKS

        for tag in ALL_HTML_TAGS:
            thonny_tag = _THONNY_TAG_MAP.get(tag)
            color = _get_theme_color(thonny_tag) if thonny_tag else None
            if not color:
                color = fallbacks[tag]
            self._text.tag_configure(tag, foreground=color)

        # HTML tags must be raised above the default text tag so they are
        # visible, but below the selection tag so selections look normal.
        for tag in ALL_HTML_TAGS:
            try:
                self._text.tag_raise(tag)
            except tk.TclError:
                pass  # tag may not exist yet on first call

    def schedule_update(self) -> None:
        """Schedule a re-highlight to run when the event loop is idle.

        Multiple calls before the idle callback fires are collapsed into
        one update, preventing redundant work during rapid typing.
        """
        if not self._update_scheduled:
            self._update_scheduled = True
            self._text.after_idle(self._do_update)

    def update(self) -> None:
        """Re-tokenise and re-highlight the full widget content immediately."""
        self._update_scheduled = False
        self._apply_highlighting()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _do_update(self) -> None:
        """Idle callback — delegates to :meth:`update`."""
        self.update()

    def _apply_highlighting(self) -> None:
        # Remove all existing HTML tags in one pass before adding new ones.
        for tag in ALL_HTML_TAGS:
            self._text.tag_remove(tag, "1.0", "end")

        content = self._text.get("1.0", "end-1c")
        if not content:
            return

        tokens: List[Token] = tokenize_document(content, self.language)
        if not tokens:
            return

        # Collect every start/end offset so we can compute all tkinter
        # indices in a single O(n) pass rather than one pass per token.
        all_offsets = []
        for token in tokens:
            all_offsets.append(token.start)
            all_offsets.append(token.end)

        index_map = offsets_to_tkindices(content, all_offsets)

        for token in tokens:
            tag = _TOKEN_TO_TAG.get(token.type)
            if tag is None:
                continue
            start_idx = index_map[token.start]
            end_idx = index_map[token.end]
            if start_idx != end_idx:
                self._text.tag_add(tag, start_idx, end_idx)
