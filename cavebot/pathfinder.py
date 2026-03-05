"""
cavebot/pathfinder.py - Algoritmo A* para pathfinding en el minimapa.
Encuentra rutas entre tiles evitando obstáculos.

Basado en el patrón de oldbot: A* con heurística Manhattan, 4 direcciones,
colores de minimapa para determinar walkability.
"""

import heapq
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np


# Colores del minimapa de Tibia que NO son caminables (en BGR)
# Adaptado de oldbot findobject.cpp
NON_WALKABLE_COLORS_BGR = {
    "black":       (0, 0, 0),        # Vacío / no explorado
    "dark_gray":   (40, 40, 40),     # Muros
    "red":         (0, 0, 200),      # PZ / zona peligrosa
    "blue":        (200, 0, 0),      # Agua profunda
    "dark_green":  (0, 80, 0),       # Árboles densos
    "brown":       (30, 60, 100),    # Montañas
    "orange":      (0, 120, 255),    # Lava
}

# Umbral de similitud para considerar un color como no-caminable
COLOR_THRESHOLD = 40


class Node:
    """Nodo para el algoritmo A*."""

    __slots__ = ("x", "y", "g", "h", "parent")

    def __init__(self, x: int, y: int, g: float = 0, h: float = 0, parent: Optional["Node"] = None):
        self.x = x
        self.y = y
        self.g = g  # Costo desde el inicio
        self.h = h  # Heurística al destino
        self.parent = parent

    @property
    def f(self) -> float:
        return self.g + self.h

    def __lt__(self, other: "Node") -> bool:
        return self.f < other.f

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


class Pathfinder:
    """
    Encuentra rutas en el minimapa usando A*.
    Determina walkability por color de píxel del minimapa.
    """

    def __init__(self):
        # Tiles bloqueados dinámicamente (por fallos de caminado)
        self.blocked_tiles: Set[Tuple[int, int]] = set()

        # Direcciones: 4 cardinales (N, S, E, W)
        self.directions = [(0, -1), (0, 1), (1, 0), (-1, 0)]

        # Timeout
        self.max_iterations: int = 5000

    # ==================================================================
    # Walkability por color de minimapa
    # ==================================================================
    @staticmethod
    def is_walkable_color(bgr: Tuple[int, int, int]) -> bool:
        """
        Determina si un color de pixel del minimapa es caminable.
        Colores oscuros, negros, azules (agua), rojos (lava) no son caminables.
        """
        b, g, r = bgr

        # Negro o muy oscuro = no caminable
        if b < 30 and g < 30 and r < 30:
            return False

        # Verificar contra colores conocidos no-caminables
        for color_bgr in NON_WALKABLE_COLORS_BGR.values():
            diff = (
                abs(b - color_bgr[0])
                + abs(g - color_bgr[1])
                + abs(r - color_bgr[2])
            )
            if diff < COLOR_THRESHOLD:
                return False

        return True

    def build_walkability_map(
        self, minimap_img: np.ndarray, tile_size: int = 4
    ) -> np.ndarray:
        """
        Construye un mapa de walkability a partir del minimapa.

        Args:
            minimap_img: Imagen BGR del minimapa.
            tile_size: Píxeles por tile en el minimapa.

        Returns:
            Array 2D bool: True = caminable, False = bloqueado.
        """
        h, w = minimap_img.shape[:2]
        tiles_y = h // tile_size
        tiles_x = w // tile_size

        walkmap = np.ones((tiles_y, tiles_x), dtype=bool)

        for ty in range(tiles_y):
            for tx in range(tiles_x):
                # Color del centro del tile
                px = tx * tile_size + tile_size // 2
                py = ty * tile_size + tile_size // 2
                if px < w and py < h:
                    bgr = tuple(int(c) for c in minimap_img[py, px])
                    walkmap[ty, tx] = self.is_walkable_color(bgr)

        # Aplicar tiles bloqueados dinámicamente
        for bx, by in self.blocked_tiles:
            if 0 <= by < tiles_y and 0 <= bx < tiles_x:
                walkmap[by, bx] = False

        return walkmap

    # ==================================================================
    # A* Pathfinding
    # ==================================================================
    def find_path(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        walkability_map: Optional[np.ndarray] = None,
        minimap_img: Optional[np.ndarray] = None,
    ) -> List[Tuple[int, int]]:
        """
        Encuentra la ruta más corta de start a goal usando A*.

        Args:
            start: (x, y) posición inicial en tiles.
            goal: (x, y) posición destino en tiles.
            walkability_map: Mapa precomputado (optional).
            minimap_img: Imagen del minimapa para generar mapa on-the-fly.

        Returns:
            Lista de (x, y) tiles desde start hasta goal (inclusive).
            Lista vacía si no hay ruta.
        """
        if walkability_map is None and minimap_img is not None:
            walkability_map = self.build_walkability_map(minimap_img)

        if walkability_map is None:
            return []

        map_h, map_w = walkability_map.shape

        # Validar start y goal
        if not (0 <= start[0] < map_w and 0 <= start[1] < map_h):
            return []
        if not (0 <= goal[0] < map_w and 0 <= goal[1] < map_h):
            return []

        # Si goal no es caminable, buscar tile adyacente más cercano
        if not walkability_map[goal[1], goal[0]]:
            goal = self._find_nearest_walkable(goal, walkability_map)
            if goal is None:
                return []

        start_node = Node(start[0], start[1])
        start_node.h = self._heuristic(start, goal)

        open_set: list = [start_node]
        closed_set: Set[Tuple[int, int]] = set()
        open_dict: Dict[Tuple[int, int], Node] = {(start[0], start[1]): start_node}

        iterations = 0

        while open_set and iterations < self.max_iterations:
            iterations += 1
            current = heapq.heappop(open_set)
            current_pos = (current.x, current.y)

            if current_pos in closed_set:
                continue

            # ¿Llegamos al destino?
            if current_pos == goal:
                return self._reconstruct_path(current)

            closed_set.add(current_pos)

            # Explorar vecinos
            for dx, dy in self.directions:
                nx, ny = current.x + dx, current.y + dy

                if not (0 <= nx < map_w and 0 <= ny < map_h):
                    continue
                if (nx, ny) in closed_set:
                    continue
                if not walkability_map[ny, nx]:
                    continue

                new_g = current.g + 1
                neighbor_pos = (nx, ny)

                existing = open_dict.get(neighbor_pos)
                if existing is not None and new_g >= existing.g:
                    continue

                neighbor = Node(
                    nx, ny,
                    g=new_g,
                    h=self._heuristic(neighbor_pos, goal),
                    parent=current,
                )
                heapq.heappush(open_set, neighbor)
                open_dict[neighbor_pos] = neighbor

        return []  # No se encontró ruta

    @staticmethod
    def _heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Heurística Manhattan para A*."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _reconstruct_path(node: Node) -> List[Tuple[int, int]]:
        """Reconstruye la ruta desde el nodo final hasta el inicio."""
        path = []
        current: Optional[Node] = node
        while current is not None:
            path.append((current.x, current.y))
            current = current.parent
        path.reverse()
        return path

    def _find_nearest_walkable(
        self,
        pos: Tuple[int, int],
        walkmap: np.ndarray,
        max_radius: int = 5,
    ) -> Optional[Tuple[int, int]]:
        """Encuentra el tile caminable más cercano a una posición."""
        map_h, map_w = walkmap.shape
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = pos[0] + dx, pos[1] + dy
                    if 0 <= nx < map_w and 0 <= ny < map_h:
                        if walkmap[ny, nx]:
                            return (nx, ny)
        return None

    # ==================================================================
    # Gestión de tiles bloqueados
    # ==================================================================
    def block_tile(self, x: int, y: int) -> None:
        """Bloquea un tile dinámicamente (por fallo de caminado)."""
        self.blocked_tiles.add((x, y))

    def unblock_tile(self, x: int, y: int) -> None:
        """Desbloquea un tile."""
        self.blocked_tiles.discard((x, y))

    def clear_blocked(self) -> None:
        """Limpia todos los tiles bloqueados dinámicamente."""
        self.blocked_tiles.clear()
