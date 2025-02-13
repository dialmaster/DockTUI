import docker
import subprocess
import json
import logging
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger('dockerview.docker')

class DockerManager:
    """Manages Docker interactions."""

    def __init__(self):
        logger.info("Initializing DockerManager")
        try:
            self.client = docker.from_env()
            logger.debug("Docker client initialized successfully")
            self.last_error = None
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {str(e)}", exc_info=True)
            raise

    def get_compose_stacks(self) -> Dict[str, Dict]:
        """Get all Docker Compose stacks with their containers."""
        logger.info("Fetching Docker Compose stacks")
        stacks = defaultdict(lambda: {
            'name': '',
            'config_file': '',
            'containers': [],
            'running': 0,
            'exited': 0,
            'total': 0
        })

        try:
            # Get all containers including their labels
            logger.debug("Listing all containers")
            containers = self.client.containers.list(all=True)
            logger.debug(f"Found {len(containers)} total containers")

            for container in containers:
                try:
                    # Get compose project from labels
                    project = container.labels.get('com.docker.compose.project', 'ungrouped')
                    config_file = container.labels.get('com.docker.compose.project.config_files', 'N/A')
                    logger.debug(f"Processing container {container.name} (ID: {container.short_id}) - Project: {project}")

                    if project not in stacks:
                        logger.debug(f"Creating new stack entry for project {project}")
                        stacks[project]['name'] = project
                        stacks[project]['config_file'] = config_file

                    stacks[project]['containers'].append(container)
                    stacks[project]['total'] += 1
                    if container.status == 'running':
                        stacks[project]['running'] += 1
                        logger.debug(f"Container {container.name} is running")
                    elif 'exited' in container.status:
                        stacks[project]['exited'] += 1
                        logger.debug(f"Container {container.name} has exited")
                except Exception as container_error:
                    logger.error(f"Error processing container {container.name}: {str(container_error)}", exc_info=True)
                    continue

            logger.info(f"Successfully processed {len(stacks)} stacks")
            for stack_name, info in stacks.items():
                logger.debug(f"Stack {stack_name}: Running={info['running']}, Exited={info['exited']}, Total={info['total']}")

        except Exception as e:
            error_msg = f"Error getting compose stacks: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.last_error = error_msg
            return {}

        return dict(stacks)

    def get_all_container_stats(self) -> Dict[str, Dict[str, str]]:
        """
        Get stats for all containers in a single operation.

        PERFORMANCE NOTE: This method uses 'docker stats --no-stream' to get stats for all containers
        in a single CLI call, which is MUCH faster than making individual API calls per container.
        The previous individual container.stats() calls would make one request per container,
        leading to poor performance with many containers. This batch approach reduces the overhead
        significantly, especially in environments with many containers.
        """
        logger.info("Fetching stats for all containers")
        stats_dict = {}
        try:
            # Get stats for all containers in one CLI call
            logger.debug("Executing docker stats command")
            stats_output = subprocess.check_output(
                ['docker', 'stats', '--no-stream', '--format', '{{.Container}}\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}'],
                universal_newlines=True,
                stderr=subprocess.PIPE
            )

            # Parse the stats output
            for line in stats_output.strip().split('\n'):
                if not line:
                    continue
                try:
                    container_id, name, cpu, memory, mem_perc, pids = line.split('\t')
                    # Clean up memory percentage string
                    mem_perc = mem_perc.rstrip('%')
                    logger.debug(f"Got stats for container {name} (ID: {container_id}): CPU={cpu}, Memory={memory}")

                    stats_dict[container_id] = {
                        'cpu': cpu,
                        'memory': memory,
                        'memory_percent': mem_perc,
                        'pids': pids
                    }
                except Exception as e:
                    logger.error(f"Error parsing stats line '{line}': {str(e)}", exc_info=True)
                    continue

            logger.info(f"Successfully fetched stats for {len(stats_dict)} containers")

        except Exception as e:
            error_msg = f"Error getting container stats: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {}

        return stats_dict

    def get_containers(self) -> List[Dict]:
        """Get all containers with their stats."""
        logger.info("Getting containers with stats")
        containers = []
        try:
            logger.debug("Fetching compose stacks")
            stacks = self.get_compose_stacks()
            logger.debug(f"Found {len(stacks)} stacks")

            # Get all container stats in one batch operation
            logger.debug("Fetching container stats")
            all_stats = self.get_all_container_stats()
            logger.debug(f"Got stats for {len(all_stats)} containers")

            for stack_name, stack_info in stacks.items():
                logger.debug(f"Processing containers for stack {stack_name}")
                for container in stack_info['containers']:
                    try:
                        # Get the pre-fetched stats for this container
                        stats = all_stats.get(container.id, {
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
                        logger.debug(f"Added container {container.name} to list with stats: {stats}")
                    except Exception as container_error:
                        logger.error(f"Error processing container {container.name}: {str(container_error)}", exc_info=True)
                        continue

            logger.info(f"Successfully processed {len(containers)} containers")

        except Exception as e:
            error_msg = f"Error getting container stats: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.last_error = error_msg
            return []

        return containers

    def _format_ports(self, container) -> str:
        """Format container ports for display."""
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