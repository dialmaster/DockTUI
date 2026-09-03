"""End-to-end keyboard navigation tests driven through Textual's pilot.

These run the real DockTUIApp headlessly against a fake DockerManager, so
they exercise the actual bindings, focus handling and selection plumbing.
"""

import asyncio
import copy
import os
from typing import Callable, Dict, List
from unittest.mock import Mock, patch

import pytest

from DockTUI.ui.widgets.headers import NetworkHeader, SectionHeader, StackHeader
from DockTUI.ui.widgets.rich_log_viewer import RichLogViewer

REFRESH_INTERVAL = "0.3"


def _container(cid: str, name: str, stack: str, status: str = "running") -> dict:
    return {
        "id": cid,
        "name": name,
        "status": status,
        "uptime": "1m",
        "cpu": "0.00%",
        "memory": "1.0MiB / 1.0GiB",
        "pids": "1",
        "stack": stack,
        "ports": "",
        "image_id": "img1",
        "image_name": "img-one:latest",
    }


def _image(iid: str, tag: str) -> dict:
    return {
        "id": iid,
        "tags": [tag],
        "created": "2024-01-01T00:00:00Z",
        "size": "10.0 MB",
        "containers": 0,
        "container_names": [],
        "has_running": False,
        "architecture": "amd64",
        "os": "linux",
    }


class FakeDockerManager:
    """In-memory stand-in for DockerManager with a small, fixed topology."""

    def __init__(self):
        self.last_error = None
        self.stacks = {
            "alpha": {
                "name": "alpha",
                "config_file": "/tmp/alpha/docker-compose.yml",
                "running": 2,
                "exited": 0,
                "total": 2,
                "can_recreate": True,
                "has_compose_file": True,
            },
            "beta": {
                "name": "beta",
                "config_file": "/tmp/beta/docker-compose.yml",
                "running": 1,
                "exited": 0,
                "total": 1,
                "can_recreate": True,
                "has_compose_file": True,
            },
        }
        self.containers = [
            _container("a1", "alpha-web", "alpha"),
            _container("a2", "alpha-db", "alpha"),
            _container("b1", "beta-api", "beta"),
        ]
        self.images = {
            "i1": _image("i1", "img-one:latest"),
            "i2": _image("i2", "img-two:latest"),
        }
        self.volumes = {
            "vol1": {
                "name": "vol1",
                "driver": "local",
                "mountpoint": "/var/lib/docker/volumes/vol1",
                "created": "2024-01-01",
                "labels": {},
                "stack": None,
                "scope": "local",
                "in_use": False,
                "container_count": 0,
                "container_names": [],
            }
        }
        self.networks = {
            "net1": {
                "id": "n1",
                "name": "net1",
                "driver": "bridge",
                "scope": "local",
                "subnet": "172.18.0.0/16",
                "connected_containers": [
                    {"id": "a1", "name": "alpha-web", "stack": "alpha", "ip": "172.18.0.2"},
                    {"id": "b1", "name": "beta-api", "stack": "beta", "ip": "172.18.0.3"},
                ],
                "connected_stacks": {"alpha", "beta"},
                "total_containers": 2,
            }
        }

    def get_networks(self):
        return copy.deepcopy(self.networks)

    def get_compose_stacks(self):
        return copy.deepcopy(self.stacks)

    def get_images(self):
        return copy.deepcopy(self.images)

    def get_volumes(self):
        return copy.deepcopy(self.volumes)

    def get_containers(self):
        return copy.deepcopy(self.containers)


def _fake_log_client():
    client = Mock()
    client.containers.get.return_value.logs.return_value = []
    client.containers.list.return_value = []
    return client


async def _wait_for_initial_load(app, pilot, timeout: float = 5.0) -> None:
    waited = 0.0
    while waited < timeout:
        await pilot.pause(0.1)
        waited += 0.1
        container_list = app.container_list
        if container_list and container_list.stack_tables and container_list._initial_load_complete:
            await pilot.pause(0.2)
            return
    raise AssertionError("App did not finish its initial load")


def run_scenario(scenario: Callable, fake: FakeDockerManager = None) -> None:
    """Run an async scenario(app, pilot) inside a headless DockTUIApp."""
    fake = fake or FakeDockerManager()

    async def _run():
        from DockTUI.app import DockTUIApp

        app = DockTUIApp()
        async with app.run_test(size=(160, 50)) as pilot:
            await _wait_for_initial_load(app, pilot)
            await scenario(app, pilot)

    previous = os.environ.get("DOCKTUI_APP_REFRESH_INTERVAL")
    os.environ["DOCKTUI_APP_REFRESH_INTERVAL"] = REFRESH_INTERVAL
    try:
        with patch("DockTUI.app.DockerManager", return_value=fake), patch(
            "DockTUI.ui.viewers.log_pane.docker.from_env",
            return_value=_fake_log_client(),
        ):
            asyncio.run(_run())
    finally:
        if previous is None:
            os.environ.pop("DOCKTUI_APP_REFRESH_INTERVAL", None)
        else:
            os.environ["DOCKTUI_APP_REFRESH_INTERVAL"] = previous


async def _press(pilot, *keys, settle: float = 0.15):
    for key in keys:
        await pilot.press(key)
        await pilot.pause(settle)


def _in_container_list(app) -> bool:
    focused = app.focused
    return focused is not None and app.container_list in focused.ancestors_with_self


# ---------------------------------------------------------------------------
# Container list navigation
# ---------------------------------------------------------------------------


def test_initial_load_focuses_and_selects_first_stack():
    async def scenario(app, pilot):
        assert app.container_list.selected_item == ("stack", "alpha")
        assert isinstance(app.focused, StackHeader)
        assert app.focused.stack_name == "alpha"

    run_scenario(scenario)


def test_down_and_up_move_selection_through_containers():
    async def scenario(app, pilot):
        cl = app.container_list
        await _press(pilot, "down")
        assert cl.selected_item == ("container", "a1")
        await _press(pilot, "down")
        assert cl.selected_item == ("container", "a2")
        await _press(pilot, "up")
        assert cl.selected_item == ("container", "a1")
        await _press(pilot, "up")
        assert cl.selected_item == ("stack", "alpha")
        assert isinstance(app.focused, StackHeader)

    run_scenario(scenario)


def test_down_continues_into_next_stack_and_section_headers():
    async def scenario(app, pilot):
        cl = app.container_list
        await _press(pilot, "down", "down", "down")
        assert cl.selected_item == ("stack", "beta")
        # stacks start expanded: beta's only container comes next, then the
        # Images section header
        await _press(pilot, "down")
        assert cl.selected_item == ("container", "b1")
        await _press(pilot, "down")
        assert app.focused is cl.images_section_header
        # sections are laid out as Stacks, Images, Networks, Volumes
        await _press(pilot, "down")
        assert app.focused is cl.networks_section_header
        await _press(pilot, "down")
        assert app.focused is cl.volumes_section_header

    run_scenario(scenario)


def test_enter_expands_images_section_and_down_selects_an_image():
    async def scenario(app, pilot):
        cl = app.container_list
        await _press(pilot, *(["down"] * 5))
        assert app.focused is cl.images_section_header
        await _press(pilot, "enter", settle=0.5)
        assert cl.images_section_collapsed is False
        await _press(pilot, "down")
        assert cl.selected_item == ("image", "i1")
        await _press(pilot, "down")
        assert cl.selected_item == ("image", "i2")

    run_scenario(scenario)


def test_volumes_section_is_navigable_by_keyboard():
    async def scenario(app, pilot):
        cl = app.container_list
        await _press(pilot, *(["down"] * 7))
        assert app.focused is cl.volumes_section_header
        await _press(pilot, "enter", settle=0.5)
        await _press(pilot, "down")
        assert cl.selected_item == ("volume", "vol1")

    run_scenario(scenario)


def test_enter_on_network_row_jumps_to_that_container():
    async def scenario(app, pilot):
        cl = app.container_list
        await _press(pilot, *(["down"] * 6))
        assert app.focused is cl.networks_section_header
        await _press(pilot, "enter", settle=0.5)
        await _press(pilot, "down")
        assert isinstance(app.focused, NetworkHeader)
        assert cl.selected_item == ("network", "net1")
        await _press(pilot, "enter")  # expand the network's container table
        await _press(pilot, "down")
        # Moving through connected containers keeps the network selected
        assert cl.selected_item == ("network", "net1")
        await _press(pilot, "enter")
        assert cl.selected_item == ("container", "a1")

    run_scenario(scenario)


def test_left_and_right_collapse_and_expand_the_focused_stack():
    async def scenario(app, pilot):
        cl = app.container_list
        header = cl.stack_headers["alpha"]
        assert header.expanded is True
        await _press(pilot, "left")
        assert header.expanded is False
        assert cl.stack_tables["alpha"].styles.display == "none"
        await _press(pilot, "right")
        assert header.expanded is True
        assert cl.stack_tables["alpha"].styles.display == "block"

    run_scenario(scenario)


# ---------------------------------------------------------------------------
# Pane switching and log pane keys
# ---------------------------------------------------------------------------


def test_tab_switches_to_log_pane_and_shift_tab_returns():
    async def scenario(app, pilot):
        await _press(pilot, "tab")
        assert isinstance(app.focused, RichLogViewer)
        await _press(pilot, "shift+tab")
        assert _in_container_list(app)
        assert isinstance(app.focused, StackHeader)

    run_scenario(scenario)


def test_slash_focuses_filter_and_escape_returns_to_list():
    async def scenario(app, pilot):
        await _press(pilot, "slash")
        assert getattr(app.focused, "id", None) == "search-input"
        await _press(pilot, "escape")
        assert _in_container_list(app)

    run_scenario(scenario)


def test_refresh_does_not_steal_focus_from_log_pane():
    async def scenario(app, pilot):
        await _press(pilot, "down")  # select a container so logs are shown
        await _press(pilot, "tab")
        assert isinstance(app.focused, RichLogViewer)
        await pilot.pause(1.2)  # several refresh cycles at 0.3s
        assert isinstance(app.focused, RichLogViewer)

    run_scenario(scenario)


def test_follow_and_mark_keys_work_from_the_log_pane():
    async def scenario(app, pilot):
        await _press(pilot, "down")  # select container a1
        await _press(pilot, "tab", settle=0.3)
        log_pane = app.log_pane
        before = log_pane.auto_follow_checkbox.value
        await _press(pilot, "f")
        assert log_pane.auto_follow_checkbox.value is (not before)
        await _press(pilot, "m", settle=0.3)
        lines = log_pane.log_filter_manager.get_all_lines()
        assert any("------ MARKED " in line for line in lines)

    run_scenario(scenario)


# ---------------------------------------------------------------------------
# Refresh behaviour
# ---------------------------------------------------------------------------


def test_removed_image_keeps_remaining_rows_visible():
    fake = FakeDockerManager()

    async def scenario(app, pilot):
        cl = app.container_list
        await _press(pilot, *(["down"] * 5))
        assert app.focused is cl.images_section_header
        await _press(pilot, "enter", settle=0.5)
        table = cl.image_manager.images_table
        assert table.row_count == 2

        fake.images.pop("i1")
        samples: List[int] = []
        for _ in range(10):
            await pilot.pause(0.15)
            samples.append(table.row_count)

        assert 0 not in samples, samples
        assert samples[-1] == 1
        assert cl.image_manager.image_rows == {"i2": 0}

    run_scenario(scenario, fake)
