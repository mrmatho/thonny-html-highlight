"""Applies HTML syntax highlighting to a Thonny editor text widget.

The :class:`HtmlHighlighter` owns all interaction with the tkinter Text
widget.  It reads tokens from :mod:`.tokenizer` and applies named tags so
that Thonny's theme system can override colours in the future.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, List

from .tokenizer import Token, offsets_to_tkindices, tokenize_html

if TYPE_CHECKING:
    pass  # kept for future type-only imports (e.g. SyntaxText)


# ---------------------------------------------------------------------------
# Tag configuration
# ---------------------------------------------------------------------------

# Default colours for each token category.  These are intentionally chosen
# to complement Thonny's built-in light theme; a future version will read
# values from Thonny's syntax-theme API so that dark themes work correctly.
_TAG_COLORS: dict[str, dict] = {
    "html_comment":   {"foreground": "#808080"},
    "html_doctype":   {"foreground": "#999999"},
    "html_tag_name":  {"foreground": "#000080"},
    "html_attr_name": {"foreground": "#912B6C"},
    "html_attr_value":{"foreground": "#007A00"},
    "html_entity":    {"foreground": "#007070"},
    "html_bracket":   {"foreground": "#606060"},
}

# Map from tokenizer token type → tkinter tag name.
_TOKEN_TO_TAG: dict[str, str] = {
    "comment":   "html_comment",
    "doctype":   "html_doctype",
    "tag_name":  "html_tag_name",
    "attr_name": "html_attr_name",
    "attr_value":"html_attr_value",
    "entity":    "html_entity",
    "bracket":   "html_bracket",
}

ALL_HTML_TAGS: List[str] = list(_TOKEN_TO_TAG.values())


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

    def __init__(self, text: tk.Text) -> None:
        self._text = text
        self._update_scheduled = False
        self.configure_tags()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def configure_tags(self) -> None:
        """Configure tkinter tag appearance.

        Called once on initialisation and again whenever the Thonny
        appearance changes (``<<UpdateAppearance>>`` event).

        .. todo::
            Read colours from Thonny's syntax-theme API so that dark
            themes are respected automatically.
        """
        for tag, opts in _TAG_COLORS.items():
            self._text.tag_configure(tag, **opts)

        # HTML tags must be raised above the default text tag so they
        # are visible.  They sit below the selection tag so selections
        # still look normal.
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

        tokens: List[Token] = tokenize_html(content)
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
