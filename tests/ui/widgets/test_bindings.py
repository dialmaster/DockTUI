"""Tests for key binding assignments across the log viewer widgets."""

from DockTUI.app import DockTUIApp
from DockTUI.ui.viewers.log_pane import LogPane
from DockTUI.ui.widgets.rich_log_viewer import RichLogViewer


def _keys(bindings):
    return {binding.key for binding in bindings}


def test_log_viewer_keys_do_not_shadow_app_actions():
    """Keys bound inside the log viewer must not collide with app-level actions."""
    app_keys = _keys(DockTUIApp.BINDINGS)
    viewer_keys = _keys(RichLogViewer.BINDINGS)
    pane_keys = _keys(LogPane.BINDINGS)

    assert not (app_keys & viewer_keys), app_keys & viewer_keys
    assert not (app_keys & pane_keys), app_keys & pane_keys


def test_log_viewer_keeps_a_prettify_binding():
    """Prettify stays reachable from the keyboard after moving off 'p'."""
    actions = {binding.action for binding in RichLogViewer.BINDINGS}

    assert "toggle_prettify" in actions
