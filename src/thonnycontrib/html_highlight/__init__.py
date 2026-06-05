"""Thonny plugin: HTML syntax highlighting for ``.html`` / ``.htm`` files.

When Thonny loads this plugin it calls :func:`load_plugin`, which binds
event handlers onto the ``EditorCodeViewText`` widget class.  On every text
change in any editor, the handler checks whether the file is HTML (by
inspecting its path) and, if so, keeps an :class:`.HtmlHighlighter` instance
alive on the widget and schedules a re-highlight.

Setting ``file_type = "html"`` on the widget tells Thonny to use plain-text
editing behaviour (simple Return, standard Backspace) rather than Python-aware
behaviour.  It also gives future extensions (auto-indentation, tag
auto-closing) a clean hook point.

Widget hierarchy assumed by :func:`_get_editor_path`:

    ``EditorCodeViewText``  →  ``CodeView``  →  ``BaseEditor``

``BaseEditor.get_target_path()`` returns the file path or ``None`` for
untitled buffers.
"""
from __future__ import annotations

import tkinter as tk

from .highlighter import HtmlHighlighter

_HTML_EXTENSIONS = (".html", ".htm")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_editor_path(text: tk.Text) -> str | None:
    """Return the file path for *text*'s editor, or ``None`` if unavailable."""
    try:
        editor = text.master.master  # CodeView → BaseEditor
        return editor.get_target_path()
    except AttributeError:
        return None


def _is_html_file(text: tk.Text) -> bool:
    """Return ``True`` when *text* is displaying an HTML file."""
    path = _get_editor_path(text)
    return path is not None and path.lower().endswith(_HTML_EXTENSIONS)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _on_text_change(event: tk.Event) -> None:
    """Called on every ``<<TextChange>>`` in any editor text widget."""
    text = event.widget
    if not isinstance(text, tk.Text):
        return

    if not _is_html_file(text):
        return

    # Ensure this widget has a highlighter.
    if not hasattr(text, "_html_highlighter"):
        text._html_highlighter = HtmlHighlighter(text)

    # Keep file_type set to "html" so Thonny uses plain-text editing
    # behaviour.  update_file_type() resets this on save/rename, so we
    # re-assert it on each text change.
    if getattr(text, "file_type", None) != "html":
        if hasattr(text, "set_file_type"):
            text.set_file_type("html")

    text._html_highlighter.schedule_update()


def _on_appearance_change(event: tk.Event) -> None:
    """Called when the user switches Thonny's syntax theme.

    Reconfigures tag colours and re-highlights every open HTML editor so
    that the new theme takes effect immediately.
    """
    from thonny import get_workbench  # noqa: PLC0415 — deferred to avoid import at test time

    try:
        notebook = get_workbench().get_editor_notebook()
        for editor in notebook.get_all_editors():
            try:
                text = editor._code_view.text
                hl: HtmlHighlighter | None = getattr(text, "_html_highlighter", None)
                if hl is not None:
                    hl.configure_tags()
                    hl.schedule_update()
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def load_plugin() -> None:
    """Register the HTML highlighting plugin with Thonny's workbench."""
    from thonny import get_workbench  # noqa: PLC0415 — deferred to avoid import at test time

    wb = get_workbench()
    wb.bind_class("EditorCodeViewText", "<<TextChange>>", _on_text_change, True)
    wb.bind("<<UpdateAppearance>>", _on_appearance_change, True)
