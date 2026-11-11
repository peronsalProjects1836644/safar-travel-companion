"""Pure geometry and time helpers (no I/O)."""

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lng, max_lng) that contains the circle."""
    dlat = radius_km / 110.574
    dlng = radius_km / (111.320 * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def travel_minutes(distance_km: float, speed_kmh: float, detour: float = 1.3, buffer_min: int = 5) -> int:
    """Rough road travel time: straight-line distance x detour factor, plus a buffer."""
    if distance_km <= 0:
        return 0
    minutes = distance_km * detour / speed_kmh * 60 + buffer_min
    return max(5, int(math.ceil(minutes)))


def path_length_km(order: list[int], pts: list[tuple[float, float]]) -> float:
    return sum(
        haversine_km(*pts[order[i]], *pts[order[i + 1]]) for i in range(len(order) - 1)
    )


def nearest_neighbor_order(pts: list[tuple[float, float]], start: int = 0) -> list[int]:
    if not pts:
        return []
    remaining = set(range(len(pts)))
    remaining.discard(start)
    order = [start]
    while remaining:
        last = pts[order[-1]]
        nxt = min(remaining, key=lambda i: (haversine_km(*last, *pts[i]), i))
        order.append(nxt)
        remaining.discard(nxt)
    return order


def two_opt(order: list[int], pts: list[tuple[float, float]]) -> list[int]:
    """Improve an open path by reversing segments. The first stop stays fixed."""
    best = list(order)
    best_len = path_length_km(best, pts)
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                cand_len = path_length_km(cand, pts)
                if cand_len + 1e-9 < best_len:
                    best, best_len, improved = cand, cand_len, True
    return best


def parse_hhmm(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def fmt_hhmm(minutes: int) -> str:
    minutes = max(0, min(int(minutes), 23 * 60 + 59))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
