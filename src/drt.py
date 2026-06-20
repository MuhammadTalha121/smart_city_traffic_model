import heapq
from itertools import permutations
from typing import List, Dict, Tuple

from src.config import ZONE_ADJACENCY, DRT_SHUTTLE_CAPACITY, DRT_MAX_WAIT_MINS, DRT_MAX_DETOUR_FACTOR, DRT_ELIGIBLE_ZONES


class DRTAllocator:
    def __init__(self):
        self.shuttle_counter = 0

    def allocate(
        self,
        requests: List[Dict],
        available_shuttles: int,
        congestion_map: Dict[str, float]
    ) -> Dict:
        """
        Group ride requests into shared shuttle trips.

        requests: list of dicts with keys: origin_zone, destination_zone, passengers
        available_shuttles: number of shuttles available for dispatch
        congestion_map: {zone: congestion_score} for routing weights

        Returns:
            dict with keys:
                trips: list of dicts (shuttle_id, passengers, route, estimated_wait_mins, estimated_journey_mins)
                ungrouped_requests: list of requests that could not be grouped
                utilization_pct: percentage of seats filled
        """
        if not requests:
            return {
                'trips': [],
                'ungrouped_requests': [],
                'utilization_pct': 0.0
            }

        # Group by destination
        groups = {}
        for req in requests:
            dest = req.get('destination_zone')
            groups.setdefault(dest, []).append(req)

        trips = []
        ungrouped = []
        total_seats = 0
        used_seats = 0

        for dest, req_list in groups.items():
            req_list.sort(key=lambda x: -x.get('passengers', 1))
            current_trip = []
            current_passengers = 0
            for req in req_list:
                pax = req.get('passengers', 1)
                if current_passengers + pax <= DRT_SHUTTLE_CAPACITY:
                    current_trip.append(req)
                    current_passengers += pax
                else:
                    if current_trip:
                        trips.append((current_trip, current_passengers))
                        current_trip = [req]
                        current_passengers = pax
                    else:
                        current_trip = [req]
                        current_passengers = pax
            if current_trip:
                trips.append((current_trip, current_passengers))

        trip_results = []
        for trip_group, pax_total in trips:
            origins = [req.get('origin_zone') for req in trip_group]
            unique_origins = list(set(origins))
            route = self._compute_route(unique_origins, dest, congestion_map)
            wait_mins = min(2 + len(trip_group), DRT_MAX_WAIT_MINS)
            journey_score = sum(congestion_map.get(z, 0.1) for z in route)
            journey_mins = 5 + len(route) * 2 + int(journey_score * 5)

            trip_results.append({
                'shuttle_id': f'DRT_{self.shuttle_counter}',
                'passengers': pax_total,
                'route': route,
                'estimated_wait_mins': min(wait_mins, DRT_MAX_WAIT_MINS),
                'estimated_journey_mins': journey_mins,
                'requests': trip_group,
            })
            self.shuttle_counter += 1
            total_seats += DRT_SHUTTLE_CAPACITY
            used_seats += pax_total

        if available_shuttles and len(trip_results) > available_shuttles:
            ungrouped_trips = trip_results[available_shuttles:]
            trip_results = trip_results[:available_shuttles]
            for trip in ungrouped_trips:
                ungrouped.extend(trip['requests'])

        utilization_pct = (used_seats / total_seats * 100) if total_seats > 0 else 0.0

        return {
            'trips': trip_results,
            'ungrouped_requests': ungrouped,
            'utilization_pct': round(utilization_pct, 2)
        }

    def _compute_route(self, origins: List[str], destination: str, congestion_map: Dict[str, float]) -> List[str]:
        """Compute a route that visits all origins (in any order) and ends at destination."""
        if not origins:
            return []
        if len(origins) == 1:
            path = self._bfs(origins[0], destination, congestion_map)
            return path if path else [origins[0], destination]

        best_route = None
        best_cost = float('inf')
        for perm in permutations(origins):
            full_route = []
            current = perm[0]
            full_route.append(current)
            feasible = True
            for next_node in perm[1:]:
                path = self._bfs(current, next_node, congestion_map)
                if not path:
                    feasible = False
                    break
                full_route.extend(path[1:])
                current = next_node
            if not feasible:
                continue
            path = self._bfs(current, destination, congestion_map)
            if not path:
                continue
            full_route.extend(path[1:])
            cost = sum(congestion_map.get(z, 0.1) for z in full_route)
            if cost < best_cost:
                best_cost = cost
                best_route = full_route

        return best_route if best_route else [origins[0], destination]

    def _bfs(self, start: str, target: str, congestion_map: Dict[str, float]) -> List[str]:
        if start == target:
            return [start]
        visited = {start}
        queue = [(start, [start])]
        while queue:
            node, path = queue.pop(0)
            for neighbor in ZONE_ADJACENCY.get(node, []):
                if neighbor == target:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return []