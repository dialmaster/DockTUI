"""Tests for compose file path resolution, including the in-container case."""

from pathlib import Path

import pytest

from DockTUI.docker_mgmt.compose_paths import ComposePathResolver


@pytest.fixture
def host_root(tmp_path):
    """A fake host filesystem mounted read-only at <tmp>/host."""
    root = tmp_path / "host"
    root.mkdir()
    return root


def _host_file(host_root: Path, host_path: str, content: str = "services: {}\n") -> str:
    """Create host_path underneath host_root and return the host-side path."""
    mirrored = host_root / host_path.lstrip("/")
    mirrored.parent.mkdir(parents=True, exist_ok=True)
    mirrored.write_text(content)
    return host_path


class TestReadablePath:
    def test_returns_local_path_when_it_exists(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}\n")

        resolver = ComposePathResolver(host_root=None)

        assert resolver.readable_path(str(compose)) == str(compose)

    def test_maps_through_host_root_when_only_mirror_exists(self, host_root):
        host_path = _host_file(host_root, "/opt/stacks/app/docker-compose.yml")

        resolver = ComposePathResolver(host_root=str(host_root))

        assert resolver.readable_path(host_path) == str(
            host_root / "opt/stacks/app/docker-compose.yml"
        )

    def test_prefers_identical_local_path_over_host_root(self, host_root, tmp_path):
        local = tmp_path / "home" / "user" / "docker-compose.yml"
        local.parent.mkdir(parents=True)
        local.write_text("services: {}\n")
        _host_file(host_root, str(local))

        resolver = ComposePathResolver(host_root=str(host_root))

        assert resolver.readable_path(str(local)) == str(local)

    def test_returns_none_when_nothing_matches(self, host_root):
        resolver = ComposePathResolver(host_root=str(host_root))

        assert resolver.readable_path("/opt/missing/docker-compose.yml") is None

    def test_host_root_defaults_to_environment(self, host_root, monkeypatch):
        monkeypatch.setenv("DOCKTUI_HOST_ROOT", str(host_root))
        host_path = _host_file(host_root, "/srv/app/compose.yaml")

        resolver = ComposePathResolver()

        assert resolver.readable_path(host_path) is not None


class TestIsAccessible:
    def test_any_readable_file_in_list_counts(self, host_root):
        readable = _host_file(host_root, "/opt/app/docker-compose.yml")
        resolver = ComposePathResolver(host_root=str(host_root))

        assert resolver.is_accessible(f"/opt/app/missing.yml,{readable}") is True

    def test_placeholder_and_empty_values_are_not_accessible(self):
        resolver = ComposePathResolver(host_root=None)

        assert resolver.is_accessible("") is False
        assert resolver.is_accessible("N/A") is False

    def test_unreadable_files_are_not_accessible(self, host_root):
        resolver = ComposePathResolver(host_root=str(host_root))

        assert resolver.is_accessible("/opt/app/docker-compose.yml") is False


class TestBuildComposeCommand:
    def test_local_files_are_passed_through_with_project_directory(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}\n")
        resolver = ComposePathResolver(host_root=None)

        cmd = resolver.build_compose_command(
            "app", str(compose), working_dir=str(tmp_path)
        )

        assert cmd == [
            "docker",
            "compose",
            "-p",
            "app",
            "-f",
            str(compose),
            "--project-directory",
            str(tmp_path),
        ]

    def test_translated_files_keep_the_host_project_directory(self, host_root):
        host_path = _host_file(host_root, "/opt/stacks/app/docker-compose.yml")
        resolver = ComposePathResolver(host_root=str(host_root))

        cmd = resolver.build_compose_command(
            "app", host_path, working_dir="/opt/stacks/app"
        )

        # The file is read from the mirror, but relative bind mounts inside it
        # must still resolve against the real host directory for the daemon.
        assert cmd[4:6] == ["-f", str(host_root / "opt/stacks/app/docker-compose.yml")]
        assert cmd[6:8] == ["--project-directory", "/opt/stacks/app"]

    def test_translated_project_uses_mirrored_env_file(self, host_root):
        host_path = _host_file(host_root, "/opt/stacks/app/docker-compose.yml")
        _host_file(host_root, "/opt/stacks/app/.env", "TAG=1\n")
        resolver = ComposePathResolver(host_root=str(host_root))

        cmd = resolver.build_compose_command(
            "app", host_path, working_dir="/opt/stacks/app"
        )

        assert "--env-file" in cmd
        assert cmd[cmd.index("--env-file") + 1] == str(host_root / "opt/stacks/app/.env")

    def test_project_directory_falls_back_to_first_file_directory(self, host_root):
        host_path = _host_file(host_root, "/opt/stacks/app/docker-compose.yml")
        resolver = ComposePathResolver(host_root=str(host_root))

        cmd = resolver.build_compose_command("app", host_path)

        assert cmd[cmd.index("--project-directory") + 1] == "/opt/stacks/app"

    def test_multiple_files_are_all_included(self, host_root):
        first = _host_file(host_root, "/opt/app/docker-compose.yml")
        second = _host_file(host_root, "/opt/app/docker-compose.override.yml")
        resolver = ComposePathResolver(host_root=str(host_root))

        cmd = resolver.build_compose_command("app", f"{first}, {second}")

        assert cmd.count("-f") == 2

    def test_unreadable_files_are_passed_through_unchanged(self, host_root):
        resolver = ComposePathResolver(host_root=str(host_root))

        cmd = resolver.build_compose_command("app", "/opt/app/docker-compose.yml")

        assert cmd[4:6] == ["-f", "/opt/app/docker-compose.yml"]

    def test_no_config_files_gives_bare_project_command(self):
        resolver = ComposePathResolver(host_root=None)

        assert resolver.build_compose_command("app", "N/A") == [
            "docker",
            "compose",
            "-p",
            "app",
        ]
