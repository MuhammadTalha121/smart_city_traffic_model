"""
Edge Failover Simulation.

Simulates the behavior of an intersection controller when the central API
becomes unreachable. Provides a testable specification for future physical
deployment on Saudi highway signal cabinets.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from src.config import HEARTBEAT_TIMEOUT_S, OFFLINE_CYCLE_LENGTH_S, DEFAULT_OFFLINE_PHASES


class EdgeCabinetSimulator:
    """
    Simulates an edge signal controller with heartbeat monitoring
    and peer-to-peer coordination logic.
    """

    def __init__(self, zone_id: str, adjacent_zones: List[str]):
        self.zone_id = zone_id
        self.adjacent_zones = adjacent_zones
        self.online = True
        self.last_heartbeat = datetime.now()
        self.local_queue_len = 0
        self.current_mode = 'online'  # online | offline | p2p

    def simulate_heartbeat_loss(self) -> Dict:
        """
        Simulate loss of connection to the central API.
        Returns a failover plan using DEFAULT_OFFLINE_PHASES.
        """
        self.online = False
        self.current_mode = 'offline'
        return {
            'zone_id': self.zone_id,
            'online': False,
            'failover_plan': DEFAULT_OFFLINE_PHASES.copy(),
            'mode': 'offline',
            'timestamp': datetime.now().isoformat(),
        }

    def restore_heartbeat(self) -> Dict:
        """Restore the connection to the central API."""
        self.online = True
        self.current_mode = 'online'
        return {
            'zone_id': self.zone_id,
            'online': True,
            'mode': 'online',
            'timestamp': datetime.now().isoformat(),
        }

    def compute_p2p_coordination(self, neighbor_queue_lengths: Dict[str, int]) -> Dict:
        """
        Adjust phase timing based on neighbor queue lengths.
        If any neighbor's queue > 50 vehicles, reduce own green time.

        Returns:
            dict with zone_id, adjusted_phases, coordination_basis
        """
        if not self.online:
            # If offline, use a conservative fallback (already handled)
            return {
                'zone_id': self.zone_id,
                'adjusted_phases': DEFAULT_OFFLINE_PHASES.copy(),
                'coordination_basis': 'offline_fallback',
                'neighbors_consulted': neighbor_queue_lengths,
            }

        # Start with a base phase: use the default, but adjust if needed
        base = DEFAULT_OFFLINE_PHASES.copy()
        green_main = base['main_green_s']
        green_cross = base['cross_green_s']
        ped = base['pedestrian_s']

        # Check for neighbor overload
        overloaded = any(q > 50 for q in neighbor_queue_lengths.values())
        if overloaded:
            # Reduce own main green by 10 seconds to let neighbors clear
            green_main = max(20, green_main - 10)
            green_cross = green_cross + 5  # give cross more time
            ped = max(7, ped - 2)

        adjusted = {
            'main_green_s': green_main,
            'cross_green_s': green_cross,
            'pedestrian_s': ped,
        }

        return {
            'zone_id': self.zone_id,
            'adjusted_phases': adjusted,
            'coordination_basis': 'neighbor_overload' if overloaded else 'normal',
            'neighbors_consulted': neighbor_queue_lengths,
        }

    def get_status(self) -> Dict:
        """Return current status of the edge cabinet."""
        return {
            'zone_id': self.zone_id,
            'online': self.online,
            'mode': self.current_mode,
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'local_queue_len': self.local_queue_len,
            'adjacent_zones': self.adjacent_zones,
        }

    def set_local_queue_len(self, length: int):
        """Simulate setting the local queue length (e.g., from a sensor)."""
        self.local_queue_len = length