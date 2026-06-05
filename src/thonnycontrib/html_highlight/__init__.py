"""Thonny plugin: HTML syntax highlighting for ``.html`` / ``.htm`` files.

When Thonny loads this plugin it calls :func:`load_plugin`, which binds
event handlers onto the ``EditorCodeViewText`` widget class and onto the
workbench itself.

Two triggers are required to cover all the ways a file can appear in the
editor:

* **``"Open"``** workbench event — fired by Thonny 5.0 *before*
  ``set_content_as_bytes()`` loads the file into the text widget.  The
  handler therefore uses ``after_idle`` to defer highlighting until the
  current event-loop tick completes (by which point
  ``set_content_as_bytes()`` has run synchronously and the widget is
  populated).

* **``"Opened"``** workbench event — fired by newer Thonny releases
  *after* content is loaded.  The same handler is bound; ``after_idle``
  is harmless here (just a single extra frame of delay).

* **``<<TextChange>>``** — fires on every edit after the file is open.
  Thonny uses ``direct_insert()`` to load file content, which deliberately
  bypasses this event, so ``<<TextChange>>`` alone is insufficient for
  initial highlighting.

Widget hierarchy in Thonny 5.0
-------------------------------
``EditorCodeViewText``
    ``.master``  →  ``CodeView``  (an ``EnhancedTextFrame``)
    ``.master.home_widget``  →  ``Editor``
    ``Editor.get_filename()``  →  the file path (``str | None``)

Newer Thonny adds ``BaseEditor.get_target_path()`` as a replacement for
the deprecated ``get_filename()``.  :func:`_get_editor_path` tries both.
"""
from __future__ import annotations

import tkinter as tk

from .highlighter import HtmlHighlighter

_HTML_EXTENSIONS = (".html", ".htm")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_editor_path(text: tk.Text) -> str | None:
    """Return the file path shown in *text*'s editor, or ``None``.

    Tries the Thonny 5.0 API first (``home_widget.get_filename()``), then
    falls back to the newer ``get_target_path()`` introduced in a later
    release.  All exceptions are suppressed so that a missing attribute or
    unexpected widget hierarchy simply returns ``None``.
    """
    # Thonny 5.0: text.master is CodeView; home_widget is the owning Editor.
    try:
        return text.master.home_widget.get_filename()
    except Exception:
        pass
    # Newer Thonny: text.master.master is BaseEditor.
    try:
        return text.master.master.get_target_path()
    except Exception:
        pass
    return None


def _get_filename(editor) -> str | None:
    """Return *editor*'s file path using whichever API is available."""
    # Thonny 5.0
    try:
        return editor.get_filename()
    except Exception:
        pass
    # Newer Thonny
    try:
        return editor.get_target_path()
    except Exception:
        pass
    return None


def _is_html_file(text: tk.Text) -> bool:
    """Return ``True`` when *text* is displaying an HTML file."""
    path = _get_editor_path(text)
    return path is not None and path.lower().endswith(_HTML_EXTENSIONS)


def _highlight_editor(editor) -> None:
    """Apply highlighting to *editor* if it contains an HTML file."""
    try:
        text = editor._code_view.text
    except AttributeError:
        return

    filename = _get_filename(editor)
    if filename is None or not filename.lower().endswith(_HTML_EXTENSIONS):
        return

    if not isinstance(getattr(text, "_html_highlighter", None), HtmlHighlighter):
        text._html_highlighter = HtmlHighlighter(text)

    if getattr(text, "file_type", None) != "html":
        if hasattr(text, "set_file_type"):
            text.set_file_type("html")

    text._html_highlighter.update()


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _on_file_open(event: tk.Event) -> None:
    """Bound to both ``"Open"`` (Thonny 5.0) and ``"Opened"`` (newer).

    In Thonny 5.0 ``"Open"`` fires *before* ``set_content_as_bytes()``, so
    we use ``after_idle`` to defer highlighting until after that synchronous
    call completes.  In newer versions ``"Opened"`` fires after content is
    loaded; ``after_idle`` is harmless there (one extra frame of delay).

    The event carries an ``editor`` attribute pointing to the ``Editor``
    instance that owns the file.
    """
    editor = getattr(event, "editor", None)
    if editor is None:
        return
    filename = _get_filename(editor)
    if filename is None or not filename.lower().endswith(_HTML_EXTENSIONS):
        return
    try:
        editor._code_view.text.after_idle(lambda: _highlight_editor(editor))
    except Exception:
        pass


def _on_text_change(event: tk.Event) -> None:
    """Called on every ``<<TextChange>>`` in any editor text widget.

    Handles all edits after the file is open (typing, paste, undo, etc.).
    The binding is on the ``EditorCodeViewText`` class, so ``event.widget``
    is always a text widget; no isinstance guard is needed.
    """
    text = event.widget

    if not _is_html_file(text):
        return

    if not isinstance(getattr(text, "_html_highlighter", None), HtmlHighlighter):
        text._html_highlighter = HtmlHighlighter(text)

    # Re-assert file_type each time: update_file_type() resets it on
    # save/rename, so we correct it on the next keypress.
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
                if isinstance(hl, HtmlHighlighter):
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
    # "Open"   — Thonny 5.0: fires before content is loaded (we use after_idle).
    # "Opened" — newer Thonny: fires after content is loaded.
    # Binding both is harmless; whichever doesn't exist is silently ignored.
    wb.bind("Open", _on_file_open, True)
    wb.bind("Opened", _on_file_open, True)
    # Fired on every edit after the file is open.
    wb.bind_class("EditorCodeViewText", "<<TextChange>>", _on_text_change, True)
    # Fired when the user changes Thonny's syntax theme.
    wb.bind("<<UpdateAppearance>>", _on_appearance_change, True)
