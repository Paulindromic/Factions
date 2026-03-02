# hex_grid.py – offset-coordinate hex grid utilities

import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from .constants import (
    HEX_SIZE, MAP_COLS, MAP_ROWS, MAP_X, MAP_Y,
    TERRAIN_MOVE_COST, TERRAIN_CONCEAL, TERRAIN_COLORS, TERRAIN_NAMES
)


@dataclass
class HexTile:
    col: int
    row: int
    terrain: str = "plain"
    # ownership
    owner: Optional[str] = None          # faction ID or None
    # units present (list of unit IDs)
    units: List[str] = field(default_factory=list)
    # point of interest name
    poi: Optional[str] = None
    # population (for villages/cities)
    population: int = 0
    # is this hex visible to player?
    visible: bool = False
    # fog-of-war: has ever been seen?
    explored: bool = False

    @property
    def color(self):
        return TERRAIN_COLORS.get(self.terrain, (80, 80, 80))

    @property
    def move_cost(self):
        return TERRAIN_MOVE_COST.get(self.terrain, 1)

    @property
    def conceal_bonus(self):
        return TERRAIN_CONCEAL.get(self.terrain, 0)

    @property
    def name(self):
        return TERRAIN_NAMES.get(self.terrain, self.terrain.title())

    @property
    def coord(self):
        return (self.col, self.row)


def hex_to_pixel(col: int, row: int) -> Tuple[int, int]:
    """Convert hex grid coords to pixel centre, with map offset."""
    x = MAP_X + HEX_SIZE * math.sqrt(3) * (col + 0.5 * (row % 2))
    y = MAP_Y + HEX_SIZE * 1.5 * row
    return int(x), int(y)


def pixel_to_hex(px: int, py: int) -> Tuple[int, int]:
    """Convert pixel coords to nearest hex col/row."""
    # Adjust for map offset
    px -= MAP_X
    py -= MAP_Y
    row = py / (HEX_SIZE * 1.5)
    col = px / (HEX_SIZE * math.sqrt(3)) - 0.5 * (int(round(row)) % 2)
    # Round to nearest hex
    col_r = int(round(col))
    row_r = int(round(row))
    # Clamp
    col_r = max(0, min(MAP_COLS - 1, col_r))
    row_r = max(0, min(MAP_ROWS - 1, row_r))
    return col_r, row_r


def hex_neighbors(col: int, row: int) -> List[Tuple[int, int]]:
    """Return valid neighbouring hex coords (offset grid)."""
    if row % 2 == 0:
        offsets = [(-1, 0), (1, 0), (0, -1), (-1, -1), (0, 1), (-1, 1)]
    else:
        offsets = [(-1, 0), (1, 0), (0, -1), (1, -1), (0, 1), (1, 1)]
    result = []
    for dc, dr in offsets:
        nc, nr = col + dc, row + dr
        if 0 <= nc < MAP_COLS and 0 <= nr < MAP_ROWS:
            result.append((nc, nr))
    return result


def hex_distance(c1: int, r1: int, c2: int, r2: int) -> int:
    """Hex grid distance using cube coordinates."""
    def offset_to_cube(c, r):
        x = c - (r - (r & 1)) // 2
        z = r
        y = -x - z
        return x, y, z
    ax, ay, az = offset_to_cube(c1, r1)
    bx, by, bz = offset_to_cube(c2, r2)
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))


def hex_reachable(start_col: int, start_row: int, move_points: int,
                  grid: Dict[Tuple[int, int], HexTile],
                  blocked_fn=None) -> List[Tuple[int, int]]:
    """BFS to find all hexes reachable within move_points."""
    visited = {(start_col, start_row): 0}
    frontier = [(start_col, start_row, 0)]
    reachable = []
    while frontier:
        c, r, cost = frontier.pop(0)
        for nc, nr in hex_neighbors(c, r):
            tile = grid.get((nc, nr))
            if tile is None:
                continue
            if blocked_fn and blocked_fn(nc, nr):
                continue
            new_cost = cost + tile.move_cost
            if new_cost <= move_points and new_cost < visited.get((nc, nr), 9999):
                visited[(nc, nr)] = new_cost
                reachable.append((nc, nr))
                frontier.append((nc, nr, new_cost))
    return reachable


def hex_path(start: Tuple[int,int], goal: Tuple[int,int],
             grid: Dict[Tuple[int,int], HexTile],
             blocked_fn=None) -> List[Tuple[int,int]]:
    """A* path between two hexes. Returns list of coords including goal, excl. start."""
    import heapq
    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}

    def h(c):
        return hex_distance(c[0], c[1], goal[0], goal[1])

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
        for nc, nr in hex_neighbors(current[0], current[1]):
            nb = (nc, nr)
            if nb not in grid:
                continue
            if blocked_fn and blocked_fn(nc, nr):
                continue
            tile = grid[nb]
            tentative = g_score[current] + tile.move_cost
            if tentative < g_score.get(nb, 9999):
                came_from[nb] = current
                g_score[nb] = tentative
                heapq.heappush(open_set, (tentative + h(nb), nb))
    return []


def hexagon_points(cx: int, cy: int, size: int) -> List[Tuple[int, int]]:
    """Return 6 vertices of a flat-top hexagon for drawing."""
    pts = []
    for i in range(6):
        angle = math.pi / 180 * (60 * i + 30)
        pts.append((int(cx + size * math.cos(angle)),
                    int(cy + size * math.sin(angle))))
    return pts
