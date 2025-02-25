import docker
import subprocess
import json
import logging
from typing import Dict, List, Optional
from collections import defaultdict
import time

logger = logging.getLogger('dockerview.docker_mgmt')

class DockerManager:
    """Manages Docker interactions."""

    def __init__(self):
        """Initialize the Docker client connection."""
        try:
            self.client = docker.from_env()
            self.last_error = None
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {str(e)}", exc_info=True)
            raise

    def get_compose_stacks(self) -> Dict[str, Dict]:
        """Retrieve all Docker Compose stacks and their containers.

        Returns:
            Dict[str, Dict]: A dictionary mapping stack names to their details including:
                - name: Stack name
                - config_file: Path to compose config file
                - containers: List of container objects
                - running: Count of running containers
                - exited: Count of exited containers
                - total: Total container count
        """
        stacks = defaultdict(lambda: {
            'name': '',
            'config_file': '',
            'containers': [],
            'running': 0,
            'exited': 0,
            'total': 0
        })

        try:
            containers = self.client.containers.list(all=True)

            for container in containers:
                try:
                    project = container.labels.get('com.docker.compose.project', 'ungrouped')
                    config_file = container.labels.get('com.docker.compose.project.config_files', 'N/A')

                    if project not in stacks:
                        stacks[project]['name'] = project
                        stacks[project]['config_file'] = config_file

                    stacks[project]['containers'].append(container)
                    stacks[project]['total'] += 1
                    if container.status == 'running':
                        stacks[project]['running'] += 1
                    elif 'exited' in container.status:
                        stacks[project]['exited'] += 1

                except Exception as container_error:
                    logger.error(f"Error processing container {container.name}: {str(container_error)}", exc_info=True)
                    continue

        except Exception as e:
            error_msg = f"Error getting compose stacks: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.last_error = error_msg
            return {}

        return dict(stacks)

    def get_all_container_stats(self) -> Dict[str, Dict[str, str]]:
        """Retrieve stats for all containers in a single operation.

        Returns:
            Dict[str, Dict[str, str]]: A dictionary mapping container IDs to their stats including:
                - cpu: CPU usage percentage
                - memory: Memory usage and limit
                - memory_percent: Memory usage percentage
                - pids: Number of processes

        PERFORMANCE NOTE: This method uses 'docker stats --no-stream' to get stats for all containers
        in a single CLI call, which is MUCH faster than making individual API calls per container.
        The previous individual container.stats() calls would make one request per container,
        leading to poor performance with many containers. This batch approach reduces the overhead
        significantly, especially in environments with many containers.
        """
        stats_dict = {}
        try:
            logger.debug("Starting docker stats subprocess call")
            subprocess_start = time.time()

            stats_output = subprocess.check_output(
                ['docker', 'stats', '--no-stream', '--format', '{{.ID}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}'],
                universal_newlines=True,
                stderr=subprocess.PIPE
            )

            subprocess_end = time.time()
            logger.debug(f"Docker stats subprocess call completed in {subprocess_end - subprocess_start:.3f}s")

            parsing_start = time.time()
            container_count = 0

            for line in stats_output.strip().split('\n'):
                if not line:
                    continue
                try:
                    container_count += 1
                    cid, cpu, mem_usage, mem_perc, pids = line.split('\t')
                    short_id = cid[:12]

                    stats_dict[short_id] = {
                        'cpu': cpu,
                        'memory': mem_usage,
                        'memory_percent': mem_perc.rstrip('%'),
                        'pids': pids
                    }
                except ValueError as e:
                    logger.error(f"Error parsing stats line '{line}': wrong number of fields: {str(e)}", exc_info=True)
                    continue
                except Exception as e:
                    logger.error(f"Error parsing stats line '{line}': {str(e)}", exc_info=True)
                    continue

            parsing_end = time.time()
            logger.debug(f"Parsed stats for {container_count} containers in {parsing_end - parsing_start:.3f}s")
            logger.debug(f"Total get_all_container_stats time: {parsing_end - subprocess_start:.3f}s")

        except Exception as e:
            error_msg = f"Error getting container stats: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {}

        return stats_dict

    def get_containers(self) -> List[Dict]:
        """Retrieve all containers with their current stats.

        Returns:
            List[Dict]: A list of container information dictionaries including:
                - id: Container short ID
                - name: Container name
                - status: Current status
                - cpu: CPU usage percentage
                - memory: Memory usage
                - pids: Number of processes
                - stack: Docker Compose stack name
        """
        containers = []
        try:
            # Get all container stats in a single call first (this is the most time-consuming operation)
            all_stats = self.get_all_container_stats()

            # Then get the stacks information
            stacks = self.get_compose_stacks()

            # Process the containers with their stats
            for stack_name, stack_info in stacks.items():
                for container in stack_info['containers']:
                    try:
                        stats = all_stats.get(container.short_id, {
                            'cpu': '0%',
                            'memory': '0B / 0B',
                            'memory_percent': '0',
                            'pids': '0'
                        })

                        container_info = {
                            "id": container.short_id,
                            "name": container.name,
                            "status": container.status,
                            "cpu": stats['cpu'],
                            "memory": stats['memory'],
                            "pids": stats['pids'],
                            "stack": stack_name
                        }
                        containers.append(container_info)
                    except Exception as container_error:
                        logger.error(f"Error processing container {container.name}: {str(container_error)}", exc_info=True)
                        continue

        except Exception as e:
            error_msg = f"Error getting container stats: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.last_error = error_msg
            return []

        return containers

    def _format_ports(self, container) -> str:
        """Format container port mappings for display.

        Args:
            container: Docker container object

        Returns:
            str: Formatted string of port mappings (e.g. "8080->80/tcp, 443->443/tcp")
        """
        try:
            ports = []
            for port in container.ports.items():
                if port[1]:
                    for binding in port[1]:
                        ports.append(f"{binding['HostPort']}->{port[0]}")
            return ", ".join(ports) if ports else ""
        except Exception as e:
            logger.error(f"Error formatting ports for container {container.short_id}: {str(e)}", exc_info=True)
            return ""