"""Resolution of Docker Compose file paths reported by the daemon.

Compose records the project's config files and working directory as host
paths in container labels. When DockTUI runs on the host those paths can be
used directly. When it runs inside its own container, start.sh mounts the host
filesystem read-only at DOCKTUI_HOST_ROOT (``/host``), so the same files are
readable at ``<host root>/<host path>`` while the daemon still expects the
original host paths for relative bind mounts.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("DockTUI.compose_paths")

HOST_ROOT_ENV = "DOCKTUI_HOST_ROOT"
NO_CONFIG_FILES = "N/A"
ENV_FILE_NAME = ".env"


class ComposePathResolver:
    """Maps compose file paths from the daemon to paths readable by DockTUI."""

    def __init__(self, host_root: Optional[str] = None):
        """Create a resolver.

        Args:
            host_root: Directory where the host filesystem is mounted, if any.
                Defaults to the DOCKTUI_HOST_ROOT environment variable.
        """
        if host_root is None:
            host_root = os.environ.get(HOST_ROOT_ENV) or None
        self.host_root = host_root

    @staticmethod
    def split_config_files(config_files: str) -> List[str]:
        """Split the comma-separated config_files label into paths."""
        if not config_files or config_files == NO_CONFIG_FILES:
            return []
        return [path.strip() for path in config_files.split(",") if path.strip()]

    def readable_path(self, host_path: str) -> Optional[str]:
        """Return a path at which host_path can be read here, or None.

        The identical path wins when it exists (for example a directory
        mounted at the same location), otherwise the host-root mirror is tried.
        """
        if not host_path:
            return None
        if Path(host_path).exists():
            return host_path
        if self.host_root and os.path.isabs(host_path):
            mirrored = Path(self.host_root) / host_path.lstrip("/")
            if mirrored.exists():
                return str(mirrored)
        return None

    def is_accessible(self, config_files: str) -> bool:
        """True if at least one of the listed compose files can be read."""
        for path in self.split_config_files(config_files):
            if self.readable_path(path) is not None:
                logger.debug(f"Compose file accessible: {path}")
                return True
        logger.debug(f"No accessible compose files found in: {config_files!r}")
        return False

    def build_compose_command(
        self, stack_name: str, config_files: str, working_dir: Optional[str] = None
    ) -> List[str]:
        """Build the ``docker compose -p <stack> ...`` prefix for a project.

        Each config file is passed at a path readable here (falling back to the
        original path so compose can report a clear error). The project
        directory is always the host-side path, so relative bind mounts resolve
        correctly for the daemon; when the project lives behind the host root,
        its ``.env`` file is passed explicitly since compose would otherwise
        look for it at the host path.
        """
        cmd = ["docker", "compose", "-p", stack_name]
        paths = self.split_config_files(config_files)
        if not paths:
            return cmd

        for path in paths:
            cmd.extend(["-f", self.readable_path(path) or path])

        project_dir = working_dir or os.path.dirname(paths[0])
        if not project_dir:
            return cmd
        cmd.extend(["--project-directory", project_dir])

        env_file = os.path.join(project_dir, ENV_FILE_NAME)
        readable_env = self.readable_path(env_file)
        if readable_env is not None and readable_env != env_file:
            cmd.extend(["--env-file", readable_env])

        return cmd
