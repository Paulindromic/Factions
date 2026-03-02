# map_gen.py – Procedural map generation for the Cold War shadow war

import random
from typing import Dict, Tuple
from .hex_grid import HexTile
from .constants import MAP_COLS, MAP_ROWS, F_GOV


def generate_map(seed: int = 42) -> Dict[Tuple[int, int], HexTile]:
    """Generate a Congo/Vietnam-inspired map."""
    rng = random.Random(seed)
    grid: Dict[Tuple[int, int], HexTile] = {}

    # 1. Fill with base terrain using noise-like blobs
    for r in range(MAP_ROWS):
        for c in range(MAP_COLS):
            grid[(c, r)] = HexTile(col=c, row=r, terrain="plain")

    # 2. Place jungle – dominant in left half (like Congo basin)
    _place_blob(grid, rng, "jungle", n=5, size=12, cols=(0, MAP_COLS//2 + 2),
                rows=(0, MAP_ROWS))

    # 3. Savanna – right half and south
    _place_blob(grid, rng, "savanna", n=4, size=10, cols=(MAP_COLS//3, MAP_COLS),
                rows=(MAP_ROWS//2, MAP_ROWS))

    # 4. Mountains – scattered
    _place_blob(grid, rng, "mountain", n=3, size=5, cols=(MAP_COLS//4, MAP_COLS*3//4),
                rows=(0, MAP_ROWS//2))

    # 5. Rivers – snaking bands
    _place_rivers(grid, rng)

    # 6. Coasts – edges
    _place_coast(grid)

    # 7. Place cities (government-held)
    cities = _place_pois(grid, rng, "city", n=4, terrain_ok={"plain","savanna"},
                         min_dist=5)
    for (c, r), name in zip(cities, ["Kinshasa", "Luanda", "Brazzaville", "Bangui"]):
        tile = grid[(c, r)]
        tile.poi = name
        tile.owner = F_GOV
        tile.population = rng.randint(40, 100) * 1000

    # 8. Place villages
    village_positions = _place_pois(grid, rng, "village", n=16,
                                    terrain_ok={"plain","savanna","jungle"},
                                    min_dist=2)
    village_names = [
        "Mbandaka", "Kisangani", "Goma", "Bunia", "Kananga",
        "Mbuji-Mayi", "Kolwezi", "Likasi", "Uvira", "Beni",
        "Gemena", "Lisala", "Boende", "Ilebo", "Tshikapa", "Kabalo"
    ]
    for i, (c, r) in enumerate(village_positions):
        tile = grid[(c, r)]
        tile.terrain = "village"
        tile.poi = village_names[i % len(village_names)]
        tile.population = rng.randint(2, 20) * 1000
        # Some start government-controlled, some neutral
        if rng.random() < 0.4:
            tile.owner = F_GOV

    # 9. Starting positions – mark player start zone (top-left jungle)
    # (actual unit placement done in GameState)

    return grid


def _place_blob(grid, rng, terrain, n, size, cols, rows):
    """Place n blob seeds of given terrain."""
    for _ in range(n):
        sc = rng.randint(cols[0], cols[1] - 1)
        sr = rng.randint(rows[0], rows[1] - 1)
        _flood_terrain(grid, rng, sc, sr, terrain, size)


def _flood_terrain(grid, rng, sc, sr, terrain, size):
    """BFS flood fill with randomisation."""
    from .hex_grid import hex_neighbors
    frontier = [(sc, sr)]
    visited = {(sc, sr)}
    count = 0
    while frontier and count < size:
        idx = rng.randint(0, len(frontier) - 1)
        c, r = frontier.pop(idx)
        if (c, r) in grid:
            grid[(c, r)].terrain = terrain
            count += 1
        for nc, nr in hex_neighbors(c, r):
            if (nc, nr) not in visited and (nc, nr) in grid:
                if rng.random() < 0.7:
                    frontier.append((nc, nr))
                    visited.add((nc, nr))


def _place_rivers(grid, rng):
    """Draw 2 snaking river paths."""
    from .hex_grid import hex_neighbors
    for _ in range(2):
        # Start from top edge
        c = rng.randint(2, MAP_COLS - 3)
        r = 0
        for step in range(rng.randint(8, MAP_ROWS)):
            if r >= MAP_ROWS:
                break
            if (c, r) in grid:
                grid[(c, r)].terrain = "river"
            # Drift sideways
            dc = rng.choice([-1, 0, 0, 1])
            c = max(0, min(MAP_COLS - 1, c + dc))
            r += 1


def _place_coast(grid):
    """Mark border hexes as coast."""
    for c in range(MAP_COLS):
        if (c, 0) in grid:
            grid[(c, 0)].terrain = "coast"
        if (c, MAP_ROWS - 1) in grid:
            grid[(c, MAP_ROWS - 1)].terrain = "coast"
    for r in range(MAP_ROWS):
        if (0, r) in grid:
            grid[(0, r)].terrain = "coast"
        if (MAP_COLS - 1, r) in grid:
            grid[(MAP_COLS - 1, r)].terrain = "coast"


def _place_pois(grid, rng, terrain_type, n, terrain_ok, min_dist) -> list:
    """Place n points of interest, returning list of (col, row) positions."""
    placed = []
    attempts = 0
    candidates = [(c, r) for (c, r), t in grid.items()
                  if t.terrain in terrain_ok and t.poi is None]
    rng.shuffle(candidates)
    for (c, r) in candidates:
        if len(placed) >= n:
            break
        # Check minimum distance from existing
        too_close = False
        for pc, pr in placed:
            from .hex_grid import hex_distance
            if hex_distance(c, r, pc, pr) < min_dist:
                too_close = True
                break
        if not too_close:
            placed.append((c, r))
    return placed
