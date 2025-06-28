import os
import tempfile
import threading
from typing import Dict, List
from unittest.mock import MagicMock, Mock, call, patch

import docker
import pytest

from DockTUI.docker_mgmt.manager import DockerManager


class TestDockerManager:
    @pytest.fixture
    def mock_docker_client(self):
        """Create a mock Docker client."""
        return Mock(spec=docker.DockerClient)

    @pytest.fixture
    def manager(self, mock_docker_client):
        """Create a DockerManager instance with mock client."""
        with patch("DockTUI.docker_mgmt.manager.docker.from_env") as mock_from_env:
            mock_from_env.return_value = mock_docker_client
            return DockerManager()

    def test_init_success(self):
        """Test successful DockerManager initialization."""
        mock_client = Mock(spec=docker.DockerClient)
        with patch("DockTUI.docker_mgmt.manager.docker.from_env") as mock_from_env:
            mock_from_env.return_value = mock_client
            manager = DockerManager()
            assert manager.client == mock_client
            assert manager._transition_states == {}
            assert isinstance(manager._transition_lock, type(threading.Lock()))

    def test_init_connection_error(self):
        """Test DockerManager initialization with connection error."""
        with patch("DockTUI.docker_mgmt.manager.docker.from_env") as mock_from_env:
            mock_from_env.side_effect = docker.errors.DockerException("Connection failed")
            with pytest.raises(docker.errors.DockerException):
                DockerManager()

    def test_check_compose_file_accessible_single_file(self, manager):
        """Test checking accessibility of a single compose file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_file = os.path.join(tmpdir, "docker-compose.yml")
            with open(compose_file, "w") as f:
                f.write("version: '3'")

            assert manager._check_compose_file_accessible(compose_file) is True

    def test_check_compose_file_accessible_multiple_files(self, manager):
        """Test checking accessibility of multiple comma-separated compose files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "docker-compose.yml")
            file2 = os.path.join(tmpdir, "docker-compose.override.yml")

            with open(file1, "w") as f:
                f.write("version: '3'")
            with open(file2, "w") as f:
                f.write("version: '3'")

            config_path = f"{file1},{file2}"
            assert manager._check_compose_file_accessible(config_path) is True

    def test_check_compose_file_accessible_missing_file(self, manager):
        """Test checking accessibility when file doesn't exist."""
        assert manager._check_compose_file_accessible("/nonexistent/file.yml") is False

    def test_check_compose_file_accessible_empty_path(self, manager):
        """Test checking accessibility with empty path."""
        assert manager._check_compose_file_accessible("") is False

    def test_get_compose_stacks(self, manager, mock_docker_client):
        """Test getting Docker Compose stacks."""
        mock_container1 = Mock()
        mock_container1.id = "container1"
        mock_container1.name = "stack1_service1_1"
        mock_container1.labels = {
            "com.docker.compose.project": "stack1",
            "com.docker.compose.service": "service1",
            "com.docker.compose.project.config_files": "/path/to/compose.yml"
        }

        mock_container2 = Mock()
        mock_container2.id = "container2"
        mock_container2.name = "stack2_service2_1"
        mock_container2.labels = {
            "com.docker.compose.project": "stack2",
            "com.docker.compose.service": "service2",
            "com.docker.compose.project.config_files": "/path/to/compose2.yml"
        }

        mock_container3 = Mock()
        mock_container3.id = "container3"
        mock_container3.name = "regular_container"
        mock_container3.labels = {}

        mock_docker_client.containers.list.return_value = [
            mock_container1, mock_container2, mock_container3
        ]

        with patch.object(manager, "_check_compose_file_accessible") as mock_check:
            mock_check.return_value = True
            stacks = manager.get_compose_stacks()

        assert "stack1" in stacks
        assert "stack2" in stacks
        assert len(stacks["stack1"]["containers"]) == 1
        assert stacks["stack1"]["containers"][0] == mock_container1
        assert len(stacks["stack2"]["containers"]) == 1
        assert stacks["stack2"]["containers"][0] == mock_container2
        assert stacks["stack1"]["config_file"] == "/path/to/compose.yml"
        assert stacks["stack2"]["config_file"] == "/path/to/compose2.yml"

    def test_get_compose_stacks_api_error(self, manager, mock_docker_client):
        """Test get_compose_stacks with Docker API error."""
        mock_docker_client.containers.list.side_effect = docker.errors.APIError("API error")

        stacks = manager.get_compose_stacks()
        assert stacks == {}

    def test_get_all_container_stats(self, manager, mock_docker_client):
        """Test getting container stats for all running containers."""
        mock_container1 = Mock()
        mock_container1.id = "container1"
        mock_container1.short_id = "cont1"
        mock_container1.status = "running"

        mock_container2 = Mock()
        mock_container2.id = "container2"
        mock_container2.short_id = "cont2"
        mock_container2.status = "running"

        mock_docker_client.containers.list.return_value = [mock_container1, mock_container2]

        mock_stats1 = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 2000000000, "percpu_usage": [1000000000, 1000000000]},
                "system_cpu_usage": 100000000000
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 90000000000
            },
            "memory_stats": {
                "usage": 104857600,
                "limit": 1073741824
            }
        }

        mock_stats2 = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 3000000000, "percpu_usage": [1500000000, 1500000000]},
                "system_cpu_usage": 100000000000
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 2000000000},
                "system_cpu_usage": 90000000000
            },
            "memory_stats": {
                "usage": 209715200,
                "limit": 2147483648
            }
        }

        mock_container1.stats.return_value = mock_stats1
        mock_container2.stats.return_value = mock_stats2

        with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
            threads = []

            def capture_thread(target=None, args=None, **kwargs):
                thread = Mock()
                thread.target = target
                thread.args = args
                threads.append(thread)

                if target:
                    target(*args)

                return thread

            mock_thread.side_effect = capture_thread

            stats = manager.get_all_container_stats()

        assert "cont1" in stats
        assert "cont2" in stats
        # Check that stats were calculated (exact values depend on implementation)
        assert "cpu" in stats["cont1"]
        assert "memory" in stats["cont1"]
        assert "memory_percent" in stats["cont1"]
        assert "cpu" in stats["cont2"]
        assert "memory" in stats["cont2"]

    def test_get_all_container_stats_error_handling(self, manager, mock_docker_client):
        """Test get_all_container_stats with container error."""
        mock_container = Mock()
        mock_container.id = "container1"
        mock_container.short_id = "cont1"
        mock_container.status = "running"
        mock_container.stats.side_effect = docker.errors.APIError("Stats error")

        mock_docker_client.containers.list.return_value = [mock_container]

        with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
            def capture_thread(target=None, args=None, **kwargs):
                thread = Mock()
                thread.target = target
                thread.args = args

                if target:
                    target(*args)

                return thread

            mock_thread.side_effect = capture_thread

            stats = manager.get_all_container_stats()

        # When stats collection fails, we still get a basic entry with zeroed values
        assert "cont1" in stats
        assert stats["cont1"]["cpu"] == "0%"
        assert stats["cont1"]["memory"] == "0B / 0B"

    def test_get_containers(self, manager, mock_docker_client):
        """Test getting all containers with stats."""
        mock_container = Mock()
        mock_container.id = "container1"
        mock_container.short_id = "cont1"
        mock_container.name = "test_container"
        mock_container.status = "running"
        mock_container.image.tags = ["test:latest"]
        mock_container.labels = {}
        mock_container.attrs = {
            "State": {"Health": {"Status": "healthy"}},
            "Created": "2023-01-01T00:00:00.000000000Z"
        }

        mock_docker_client.containers.list.return_value = [mock_container]

        with patch.object(manager, "get_all_container_stats") as mock_stats:
            mock_stats.return_value = {
                "cont1": {"cpu": "10%", "memory": "100MB", "memory_percent": "5", "pids": "10"}
            }
            with patch.object(manager, "get_compose_stacks") as mock_stacks:
                # Put the container in a stack so it gets processed
                mock_stacks.return_value = {
                    "ungrouped": {
                        "containers": [mock_container],
                        "name": "ungrouped"
                    }
                }
                with patch.object(manager, "_format_ports") as mock_ports:
                    mock_ports.return_value = "80:80"

                    containers = manager.get_containers()

        assert len(containers) == 1
        assert containers[0]["id"] == "cont1"  # Uses short_id
        assert containers[0]["name"] == "test_container"
        assert containers[0]["status"] == "running"
        assert containers[0]["cpu"] == "10%"
        assert containers[0]["memory"] == "100MB"

    def test_get_containers_with_transition_state(self, manager, mock_docker_client):
        """Test getting containers with transition states."""
        mock_container = Mock()
        mock_container.id = "container1"
        mock_container.short_id = "cont1"
        mock_container.name = "test_container"
        mock_container.status = "running"
        mock_container.image.tags = ["test:latest"]
        mock_container.labels = {}
        mock_container.attrs = {
            "Created": "2023-01-01T00:00:00.000000000Z"
        }

        mock_docker_client.containers.list.return_value = [mock_container]

        manager._transition_states["cont1"] = "stopping"  # Use short_id

        with patch.object(manager, "get_all_container_stats") as mock_stats:
            mock_stats.return_value = {}
            with patch.object(manager, "get_compose_stacks") as mock_stacks:
                # Put the container in a stack so it gets processed
                mock_stacks.return_value = {
                    "ungrouped": {
                        "containers": [mock_container],
                        "name": "ungrouped"
                    }
                }
                with patch.object(manager, "_format_ports") as mock_ports:
                    mock_ports.return_value = ""

                    containers = manager.get_containers()

        assert containers[0]["status"] == "stopping"

    def test_format_ports(self, manager):
        """Test formatting container ports."""
        mock_container = Mock()
        mock_container.short_id = "cont1"
        mock_container.ports = {
            "80/tcp": [{"HostPort": "8080"}],
            "443/tcp": None,
            "3000/tcp": [{"HostPort": "3000"}]
        }

        ports = manager._format_ports(mock_container)
        # The method returns ports in the format "HostPort->ContainerPort"
        assert "8080->80" in ports
        assert "3000->3000" in ports
        assert "443" not in ports

    def test_execute_container_command_start(self, manager, mock_docker_client):
        """Test executing start command on container."""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container

        with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
            def run_target(target=None, args=None, **kwargs):
                thread = Mock()
                thread.start = Mock()
                if target and args is None:
                    target()
                return thread

            mock_thread.side_effect = run_target

            success, container_id = manager.execute_container_command("container1", "start")

        assert success is True
        assert container_id == "container1"
        mock_container.start.assert_called_once()

    def test_execute_container_command_stop(self, manager, mock_docker_client):
        """Test executing stop command on container."""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container

        with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
            def run_target(target=None, args=None, **kwargs):
                thread = Mock()
                thread.start = Mock()
                if target and args is None:
                    target()
                return thread

            mock_thread.side_effect = run_target

            success, container_id = manager.execute_container_command("container1", "stop")

        assert success is True
        assert container_id == "container1"
        mock_container.stop.assert_called_once()

    def test_execute_container_command_restart(self, manager, mock_docker_client):
        """Test executing restart command on container."""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container

        with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
            def run_target(target=None, args=None, **kwargs):
                thread = Mock()
                thread.start = Mock()
                if target and args is None:
                    target()
                return thread

            mock_thread.side_effect = run_target

            success, container_id = manager.execute_container_command("container1", "restart")

        assert success is True
        assert container_id == "container1"
        mock_container.restart.assert_called_once()

    def test_execute_container_command_recreate(self, manager, mock_docker_client):
        """Test executing recreate command on container."""
        mock_container = Mock()
        mock_container.name = "test_container"
        mock_container.labels = {
            "com.docker.compose.project": "stack1",
            "com.docker.compose.service": "service1",
            "com.docker.compose.project.config_files": "/path/to/compose.yml"
        }
        mock_docker_client.containers.get.return_value = mock_container

        with patch.object(manager, "_check_compose_file_accessible") as mock_check:
            mock_check.return_value = True

            with patch("DockTUI.docker_mgmt.manager.subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")

                with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
                    def run_target(target=None, args=None, **kwargs):
                        thread = Mock()
                        thread.start = Mock()
                        if target and args is None:
                            target()
                        return thread

                    mock_thread.side_effect = run_target

                    success, container_id = manager.execute_container_command("container1", "recreate")

        assert success is True
        assert container_id == mock_container.short_id

    def test_execute_container_command_invalid(self, manager):
        """Test executing invalid command."""
        success, container_id = manager.execute_container_command("container1", "invalid")
        assert success is True  # The method returns True for unknown commands
        assert container_id == "container1"

    def test_execute_container_command_not_found(self, manager, mock_docker_client):
        """Test executing command on non-existent container."""
        # For start/stop/restart commands, the container.get happens inside the thread
        # so the method returns True before the error occurs
        success, container_id = manager.execute_container_command("container1", "start")
        assert success is True
        assert container_id == "container1"

    def test_get_networks(self, manager, mock_docker_client):
        """Test getting Docker networks."""
        mock_network = Mock()
        mock_network.id = "network1"
        mock_network.name = "test_network"
        mock_network.attrs = {
            "Driver": "bridge",
            "Scope": "local",
            "IPAM": {"Config": [{"Subnet": "172.17.0.0/16", "Gateway": "172.17.0.1"}]},
            "Containers": {
                "container1": {"Name": "test_container", "IPv4Address": "172.17.0.2/16"}
            }
        }

        mock_docker_client.networks.list.return_value = [mock_network]

        networks = manager.get_networks()

        assert "test_network" in networks
        assert networks["test_network"]["name"] == "test_network"
        assert networks["test_network"]["driver"] == "bridge"
        assert networks["test_network"]["total_containers"] == 1
        assert len(networks["test_network"]["connected_containers"]) == 1

    def test_get_networks_error(self, manager, mock_docker_client):
        """Test get_networks with error."""
        mock_docker_client.networks.list.side_effect = docker.errors.APIError("Network error")

        networks = manager.get_networks()
        assert networks == {}

    def test_get_volumes(self, manager, mock_docker_client):
        """Test getting Docker volumes."""
        mock_volume = Mock()
        mock_volume.id = "volume1"
        mock_volume.name = "test_volume"
        mock_volume.attrs = {
            "Driver": "local",
            "Mountpoint": "/var/lib/docker/volumes/test_volume/_data",
            "Labels": {"com.docker.compose.project": "stack1"},
            "Scope": "local"
        }

        mock_container = Mock()
        mock_container.id = "container1"
        mock_container.name = "test_container"
        mock_container.attrs = {
            "Mounts": [{
                "Type": "volume",
                "Name": "test_volume"
            }]
        }

        mock_docker_client.volumes.list.return_value = [mock_volume]
        mock_docker_client.containers.list.return_value = [mock_container]

        volumes = manager.get_volumes()

        assert "test_volume" in volumes
        assert volumes["test_volume"]["name"] == "test_volume"
        assert volumes["test_volume"]["driver"] == "local"
        assert volumes["test_volume"]["stack"] == "stack1"

    def test_get_images(self, manager, mock_docker_client):
        """Test getting Docker images."""
        mock_image = Mock()
        mock_image.id = "sha256:image1"
        mock_image.short_id = "sha256:image1"[:12]
        mock_image.tags = ["test:latest", "test:v1.0"]
        mock_image.attrs = {
            "Size": 104857600,
            "Created": "2023-01-01T00:00:00Z"
        }

        mock_container = Mock()
        mock_container.image.id = "sha256:image1"
        mock_container.name = "test_container"
        mock_container.attrs = {"Image": "sha256:image1"}  # Images are matched by attrs["Image"]

        # Need to set up both the initial list call and the all=True call
        mock_docker_client.images.list.return_value = [mock_image]
        mock_docker_client.containers.list.return_value = [mock_container]

        with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
            mock_future = Mock()
            mock_future.result.return_value = mock_image.attrs
            mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future

            images = manager.get_images()

        # The image id is stored without the sha256: prefix and only the first 12 chars
        assert "image1" in images
        assert images["image1"]["tags"] == ["test:latest", "test:v1.0"]
        assert images["image1"]["size"] == "100.0 MB"
        assert images["image1"]["containers"] == 1
        assert images["image1"]["container_names"] == ["test_container"]

    def test_remove_image(self, manager, mock_docker_client):
        """Test removing a Docker image."""
        mock_image = Mock()
        mock_docker_client.images.get.return_value = mock_image

        success, message = manager.remove_image("image1", force=True)

        assert success is True
        assert "removed successfully" in message
        mock_image.remove.assert_called_once_with(force=True)

    def test_remove_image_not_found(self, manager, mock_docker_client):
        """Test removing non-existent image."""
        mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

        success, message = manager.remove_image("image1")

        assert success is False
        assert "not found" in message

    def test_get_unused_images(self, manager, mock_docker_client):
        """Test getting unused (dangling) images."""
        # Mock get_images to return unused images
        with patch.object(manager, 'get_images') as mock_get_images:
            mock_get_images.return_value = {
                "unused1": {
                    "id": "unused1",
                    "tags": ["<none>:<none>"],
                    "size": "50.0 MB",
                    "container_names": [],  # No containers using this image
                    "containers": 0
                },
                "used1": {
                    "id": "used1",
                    "tags": ["test:latest"],
                    "size": "100.0 MB",
                    "container_names": ["container1"],  # Has container using it
                    "containers": 1
                }
            }

            unused = manager.get_unused_images()

        assert len(unused) == 1
        assert unused[0]["id"] == "unused1"
        assert unused[0]["size"] == "50.0 MB"

    def test_remove_unused_images(self, manager, mock_docker_client):
        """Test removing all unused images."""
        mock_image1 = Mock()
        mock_image1.id = "sha256:unused1"
        mock_image1.attrs = {"Size": 52428800}

        mock_image2 = Mock()
        mock_image2.id = "sha256:unused2"
        mock_image2.attrs = {"Size": 104857600}

        # Mock get_unused_images to return our test images
        with patch.object(manager, 'get_unused_images') as mock_get_unused:
            mock_get_unused.return_value = [
                {"id": "sha256:unused1", "size_mb": "50.00"},
                {"id": "sha256:unused2", "size_mb": "100.00"}
            ]

            mock_docker_client.images.get.side_effect = [mock_image1, mock_image2]

            success, message, count = manager.remove_unused_images()

        assert success is True
        assert count == 2
        assert "removed 2 unused images" in message
        mock_image1.remove.assert_called_once()
        mock_image2.remove.assert_called_once()

    def test_execute_stack_command_start(self, manager, mock_docker_client):
        """Test executing start command on stack."""
        mock_container1 = Mock()
        mock_container1.name = "container1"
        mock_container2 = Mock()
        mock_container2.name = "container2"

        # Mock get_compose_stacks to return our test stack
        with patch.object(manager, 'get_compose_stacks') as mock_get_stacks:
            mock_get_stacks.return_value = {
                "stack1": {
                    "containers": [mock_container1, mock_container2]
                }
            }

            with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
                mock_thread_instance = Mock()
                mock_thread.return_value = mock_thread_instance

                result = manager.execute_stack_command("stack1", "/path/to/compose.yml", "start")

        # The method returns True immediately, commands run in thread
        assert result is True
        # Verify that a thread was created and started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_execute_stack_command_stop(self, manager, mock_docker_client):
        """Test executing stop command on stack."""
        mock_container1 = Mock()
        mock_container1.name = "container1"
        mock_container2 = Mock()
        mock_container2.name = "container2"

        # Mock get_compose_stacks to return our test stack
        with patch.object(manager, 'get_compose_stacks') as mock_get_stacks:
            mock_get_stacks.return_value = {
                "stack1": {
                    "containers": [mock_container1, mock_container2]
                }
            }

            with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
                mock_thread_instance = Mock()
                mock_thread.return_value = mock_thread_instance

                result = manager.execute_stack_command("stack1", "/path/to/compose.yml", "stop")

        # The method returns True immediately, commands run in thread
        assert result is True
        # Verify that a thread was created and started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_execute_stack_command_recreate(self, manager):
        """Test executing recreate command on stack."""
        with patch.object(manager, "_check_compose_file_accessible") as mock_check:
            mock_check.return_value = True

            with patch("DockTUI.docker_mgmt.manager.subprocess.Popen") as mock_popen:
                mock_process = Mock()
                mock_process.stdout = Mock()
                mock_process.stderr = Mock()
                mock_popen.return_value = mock_process

                result = manager.execute_stack_command("stack1", "/path/to/compose.yml", "recreate")

        assert result is True
        # Check that Popen was called with the correct command
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "docker" in cmd
        assert "compose" in cmd
        assert "-p" in cmd
        assert "stack1" in cmd
        assert "up" in cmd
        assert "-d" in cmd

    def test_execute_stack_command_down(self, manager):
        """Test executing down command on stack."""
        with patch("DockTUI.docker_mgmt.manager.subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.stdout = Mock()
            mock_process.stderr = Mock()
            mock_popen.return_value = mock_process

            result = manager.execute_stack_command("stack1", "/path/to/compose.yml", "down")

        assert result is True
        # Check that Popen was called with the correct command
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "docker" in cmd
        assert "compose" in cmd
        assert "-p" in cmd
        assert "stack1" in cmd
        assert "down" in cmd

    def test_execute_stack_command_invalid(self, manager):
        """Test executing invalid command on stack."""
        result = manager.execute_stack_command("stack1", "/path/to/compose.yml", "invalid")
        assert result is False

    def test_execute_stack_command_restart(self, manager, mock_docker_client):
        """Test executing restart command on stack."""
        mock_container1 = Mock()
        mock_container1.name = "container1"
        mock_container2 = Mock()
        mock_container2.name = "container2"

        # Mock get_compose_stacks to return our test stack
        with patch.object(manager, 'get_compose_stacks') as mock_get_stacks:
            mock_get_stacks.return_value = {
                "stack1": {
                    "containers": [mock_container1, mock_container2]
                }
            }

            with patch("DockTUI.docker_mgmt.manager.threading.Thread") as mock_thread:
                mock_thread_instance = Mock()
                mock_thread.return_value = mock_thread_instance

                result = manager.execute_stack_command("stack1", "/path/to/compose.yml", "restart")

        # The method returns True immediately, commands run in thread
        assert result is True
        # Verify that a thread was created and started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_execute_stack_command_recreate_no_compose_file(self, manager):
        """Test executing recreate command without accessible compose file."""
        with patch.object(manager, "_check_compose_file_accessible") as mock_check:
            mock_check.return_value = False

            result = manager.execute_stack_command("stack1", "/nonexistent/compose.yml", "recreate")

        assert result is False

    def test_execute_stack_command_down_with_volumes(self, manager):
        """Test executing down command with volume removal."""
        with patch("DockTUI.docker_mgmt.manager.subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.stdout = Mock()
            mock_process.stderr = Mock()
            mock_popen.return_value = mock_process

            result = manager.execute_stack_command("stack1", "/path/to/compose.yml", "down:remove_volumes")

        assert result is True
        # Check that Popen was called with the correct command
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "docker" in cmd
        assert "compose" in cmd
        assert "-p" in cmd
        assert "stack1" in cmd
        assert "down" in cmd
        assert "--volumes" in cmd

    def test_execute_stack_command_stack_not_found(self, manager):
        """Test executing command on non-existent stack."""
        with patch.object(manager, 'get_compose_stacks') as mock_get_stacks:
            mock_get_stacks.return_value = {}

            result = manager.execute_stack_command("nonexistent", "/path/to/compose.yml", "start")

        assert result is False

    def test_execute_container_command_recreate_no_labels(self, manager, mock_docker_client):
        """Test executing recreate command on container without compose labels."""
        mock_container = Mock()
        mock_container.short_id = "cont1"
        mock_container.labels = {}  # No compose labels
        mock_docker_client.containers.get.return_value = mock_container

        success, container_id = manager.execute_container_command("container1", "recreate")

        assert success is False
        assert container_id == ""

    def test_execute_container_command_recreate_compose_file_not_accessible(self, manager, mock_docker_client):
        """Test executing recreate command when compose file is not accessible."""
        mock_container = Mock()
        mock_container.short_id = "cont1"
        mock_container.labels = {
            "com.docker.compose.project": "stack1",
            "com.docker.compose.service": "service1",
            "com.docker.compose.project.config_files": "/nonexistent/compose.yml"
        }
        mock_docker_client.containers.get.return_value = mock_container

        with patch.object(manager, "_check_compose_file_accessible") as mock_check:
            mock_check.return_value = False

            success, container_id = manager.execute_container_command("container1", "recreate")

        assert success is False
        assert container_id == ""

    def test_remove_image_api_error(self, manager, mock_docker_client):
        """Test remove_image with API error."""
        mock_image = Mock()
        mock_docker_client.images.get.return_value = mock_image
        mock_image.remove.side_effect = docker.errors.APIError("API error")

        success, message = manager.remove_image("image1")

        assert success is False
        assert "API error" in message

    def test_get_volumes_no_containers(self, manager, mock_docker_client):
        """Test get_volumes when no containers are using volumes."""
        mock_volume = Mock()
        mock_volume.id = "volume1"
        mock_volume.name = "test_volume"
        mock_volume.attrs = {
            "Driver": "local",
            "Mountpoint": "/var/lib/docker/volumes/test_volume/_data",
            "Labels": {},
            "Scope": "local"
        }

        mock_docker_client.volumes.list.return_value = [mock_volume]
        mock_docker_client.containers.list.return_value = []

        volumes = manager.get_volumes()

        assert "test_volume" in volumes
        assert volumes["test_volume"]["stack"] is None
