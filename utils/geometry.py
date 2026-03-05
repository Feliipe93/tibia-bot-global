"""
utils/geometry.py - Cálculos geométricos y conversiones de coordenadas.
Maneja la relación entre coordenadas de mapa, minimapa y pantalla de Tibia.
"""

import math
from typing import List, Optional, Tuple


# Tibia grid constants
TILE_SIZE_MINIMAP = 4       # Píxeles por tile en minimapa (zoom estándar)
TILE_SIZE_GAME = 32         # Píxeles por tile en la vista de juego (aprox.)
GAME_VIEW_TILES_X = 15      # Tiles visibles horizontalmente
GAME_VIEW_TILES_Y = 11      # Tiles visibles verticalmente
CENTER_TILE_X = 7           # Tile central X (jugador)
CENTER_TILE_Y = 5           # Tile central Y (jugador)


def distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Distancia euclidiana entre dos puntos."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def manhattan_distance(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Distancia Manhattan (para movimiento en grid 4 direcciones)."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def chebyshev_distance(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Distancia Chebyshev (para movimiento en grid 8 direcciones)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def direction_to(
    from_pos: Tuple[int, int], to_pos: Tuple[int, int]
) -> Optional[str]:
    """
    Calcula la dirección cardinal para ir de from_pos a to_pos.
    Retorna: "norte", "sur", "este", "oeste" o None si están en el mismo punto.
    """
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]

    if dx == 0 and dy == 0:
        return None

    # Priorizar el eje con mayor diferencia
    if abs(dx) >= abs(dy):
        return "este" if dx > 0 else "oeste"
    else:
        return "sur" if dy > 0 else "norte"


def direction_to_8(
    from_pos: Tuple[int, int], to_pos: Tuple[int, int]
) -> Optional[str]:
    """
    Dirección en 8 direcciones (incluye diagonales).
    Retorna: "n", "ne", "e", "se", "s", "sw", "w", "nw" o None.
    """
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]

    if dx == 0 and dy == 0:
        return None

    # Normalizar a -1, 0, 1
    sx = 0 if dx == 0 else (1 if dx > 0 else -1)
    sy = 0 if dy == 0 else (1 if dy > 0 else -1)

    direction_map = {
        (0, -1): "n",
        (1, -1): "ne",
        (1, 0): "e",
        (1, 1): "se",
        (0, 1): "s",
        (-1, 1): "sw",
        (-1, 0): "w",
        (-1, -1): "nw",
    }
    return direction_map.get((sx, sy))


def tile_to_minimap_pixel(
    tile_x: int,
    tile_y: int,
    origin_x: int = 0,
    origin_y: int = 0,
    tile_size: int = TILE_SIZE_MINIMAP,
) -> Tuple[int, int]:
    """Convierte coordenadas de tile a píxeles en el minimapa."""
    px = (tile_x - origin_x) * tile_size
    py = (tile_y - origin_y) * tile_size
    return px, py


def minimap_pixel_to_tile(
    pixel_x: int,
    pixel_y: int,
    origin_x: int = 0,
    origin_y: int = 0,
    tile_size: int = TILE_SIZE_MINIMAP,
) -> Tuple[int, int]:
    """Convierte píxeles del minimapa a coordenadas de tile."""
    tx = (pixel_x // tile_size) + origin_x
    ty = (pixel_y // tile_size) + origin_y
    return tx, ty


def game_tile_to_screen(
    tile_offset_x: int,
    tile_offset_y: int,
    game_area_x: int,
    game_area_y: int,
    game_area_w: int,
    game_area_h: int,
) -> Tuple[int, int]:
    """
    Convierte un offset de tile respecto al jugador (centro)
    a coordenadas de pantalla dentro del área de juego.

    tile_offset_x, tile_offset_y: offset desde jugador (-7 a +7 en X, -5 a +5 en Y)
    game_area_x/y/w/h: rectángulo del área de juego en la ventana
    """
    tile_w = game_area_w / GAME_VIEW_TILES_X
    tile_h = game_area_h / GAME_VIEW_TILES_Y

    screen_x = game_area_x + (CENTER_TILE_X + tile_offset_x) * tile_w + tile_w / 2
    screen_y = game_area_y + (CENTER_TILE_Y + tile_offset_y) * tile_h + tile_h / 2

    return int(screen_x), int(screen_y)


def screen_to_game_tile(
    screen_x: int,
    screen_y: int,
    game_area_x: int,
    game_area_y: int,
    game_area_w: int,
    game_area_h: int,
) -> Tuple[int, int]:
    """
    Convierte coordenadas de pantalla a offset de tile respecto al jugador.
    """
    tile_w = game_area_w / GAME_VIEW_TILES_X
    tile_h = game_area_h / GAME_VIEW_TILES_Y

    offset_x = int((screen_x - game_area_x) / tile_w) - CENTER_TILE_X
    offset_y = int((screen_y - game_area_y) / tile_h) - CENTER_TILE_Y

    return offset_x, offset_y


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Limita un valor dentro de un rango."""
    return max(min_val, min(value, max_val))


def rect_center(x: int, y: int, w: int, h: int) -> Tuple[int, int]:
    """Centro de un rectángulo."""
    return x + w // 2, y + h // 2


def point_in_rect(
    px: int, py: int, rx: int, ry: int, rw: int, rh: int
) -> bool:
    """Verifica si un punto está dentro de un rectángulo."""
    return rx <= px < rx + rw and ry <= py < ry + rh


def interpolate_points(
    start: Tuple[int, int],
    end: Tuple[int, int],
    steps: int,
) -> List[Tuple[int, int]]:
    """Genera puntos intermedios entre start y end."""
    points = []
    for i in range(steps + 1):
        t = i / steps if steps > 0 else 1.0
        x = int(start[0] + (end[0] - start[0]) * t)
        y = int(start[1] + (end[1] - start[1]) * t)
        points.append((x, y))
    return points
