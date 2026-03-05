"""
cavebot/obstacle_detector.py - Detector de obstáculos en el minimapa.
Detecta campos (fire, energy, poison), parcelas, y tiles no caminables
usando análisis HSV del minimapa.
"""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple


# ======================================================================
# Definiciones de colores de obstáculos en BGR (como se capturan por OpenCV)
# ======================================================================
OBSTACLE_COLORS = {
    "fire_field": {
        "bgr_range": [(0, 100, 200), (50, 180, 255)],   # Naranja/rojo
        "danger_level": 3,
        "description": "Campo de fuego",
    },
    "energy_field": {
        "bgr_range": [(200, 100, 200), (255, 180, 255)],  # Púrpura
        "danger_level": 3,
        "description": "Campo de energía",
    },
    "poison_field": {
        "bgr_range": [(0, 150, 0), (80, 255, 80)],  # Verde brillante
        "danger_level": 2,
        "description": "Campo de veneno",
    },
    "parcel": {
        "bgr_range": [(30, 130, 160), (80, 180, 220)],  # Marrón claro
        "danger_level": 1,
        "description": "Parcela (bloquea paso)",
    },
    "water": {
        "bgr_range": [(180, 100, 0), (255, 160, 60)],  # Azul
        "danger_level": 5,
        "description": "Agua (no caminable)",
    },
    "wall": {
        "bgr_range": [(40, 40, 40), (80, 80, 80)],  # Gris oscuro
        "danger_level": 5,
        "description": "Pared",
    },
}

# Colores HSV para detección más robusta
OBSTACLE_COLORS_HSV = {
    "fire_field": {
        "lower": np.array([5, 150, 150]),
        "upper": np.array([20, 255, 255]),
    },
    "energy_field": {
        "lower": np.array([130, 100, 100]),
        "upper": np.array([160, 255, 255]),
    },
    "poison_field": {
        "lower": np.array([40, 150, 100]),
        "upper": np.array([80, 255, 255]),
    },
    "water": {
        "lower": np.array([95, 100, 100]),
        "upper": np.array([115, 255, 255]),
    },
}


class ObstacleDetector:
    """
    Detecta obstáculos en el minimapa de Tibia.
    Analiza regiones del frame para encontrar campos,
    objetos bloqueantes y tiles peligrosos.
    """

    def __init__(self):
        # Región del minimapa dentro del frame (se configura)
        self.minimap_region: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)

        # Tamaño de tile en píxeles del minimapa
        self.tile_size: int = 4

        # Cache de obstáculos detectados
        self._detected_obstacles: Dict[Tuple[int, int], str] = {}

        # Configuración
        self.enabled_detections: Dict[str, bool] = {
            "fire_field": True,
            "energy_field": True,
            "poison_field": True,
            "parcel": True,
            "water": True,
            "wall": True,
        }

    def set_minimap_region(self, x: int, y: int, w: int, h: int) -> None:
        """Configura la región del minimapa dentro del frame."""
        self.minimap_region = (x, y, w, h)

    def detect_obstacles(
        self,
        frame: np.ndarray,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict[Tuple[int, int], str]:
        """
        Detecta obstáculos en la región del minimapa.

        Args:
            frame: Frame completo de OBS.
            region: Región a analizar (x, y, w, h). Si None, usa minimap_region.

        Returns:
            Dict mapeando (tile_x, tile_y) → tipo de obstáculo.
        """
        roi_region = region or self.minimap_region
        if roi_region is None:
            return {}

        x, y, w, h = roi_region
        if frame is None or frame.size == 0:
            return {}

        # Extraer ROI
        roi = frame[y:y + h, x:x + w]
        if roi.size == 0:
            return {}

        obstacles: Dict[Tuple[int, int], str] = {}

        # Convertir a HSV una vez
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Detectar cada tipo de obstáculo
        for obs_type, hsv_range in OBSTACLE_COLORS_HSV.items():
            if not self.enabled_detections.get(obs_type, True):
                continue

            mask = cv2.inRange(hsv, hsv_range["lower"], hsv_range["upper"])
            tiles = self._mask_to_tiles(mask)
            for tile in tiles:
                obstacles[tile] = obs_type

        # Para detecciones BGR (parcel, wall)
        for obs_type, info in OBSTACLE_COLORS.items():
            if obs_type in OBSTACLE_COLORS_HSV:
                continue  # Ya detectado por HSV
            if not self.enabled_detections.get(obs_type, True):
                continue

            lower = np.array(info["bgr_range"][0])
            upper = np.array(info["bgr_range"][1])
            mask = cv2.inRange(roi, lower, upper)
            tiles = self._mask_to_tiles(mask)
            for tile in tiles:
                if tile not in obstacles:  # No sobreescribir
                    obstacles[tile] = obs_type

        self._detected_obstacles = obstacles
        return obstacles

    def _mask_to_tiles(self, mask: np.ndarray) -> List[Tuple[int, int]]:
        """
        Convierte una máscara binaria a coordenadas de tiles.
        Cada tile es un bloque de tile_size × tile_size píxeles.
        """
        tiles = []
        h, w = mask.shape
        ts = self.tile_size

        tiles_y = h // ts
        tiles_x = w // ts

        for ty in range(tiles_y):
            for tx in range(tiles_x):
                # Extraer bloque del tile
                block = mask[ty * ts:(ty + 1) * ts, tx * ts:(tx + 1) * ts]
                # Si más del 50% de los píxeles coinciden, es un obstáculo
                if np.count_nonzero(block) > (ts * ts * 0.5):
                    tiles.append((tx, ty))

        return tiles

    def get_blocked_tiles(self) -> set:
        """Retorna set de tiles bloqueados (para el pathfinder)."""
        blocked = set()
        for tile, obs_type in self._detected_obstacles.items():
            info = OBSTACLE_COLORS.get(obs_type, {})
            if info.get("danger_level", 0) >= 3:  # Solo bloquear peligrosos
                blocked.add(tile)
        return blocked

    def get_dangerous_tiles(self) -> Dict[Tuple[int, int], int]:
        """Retorna tiles con su nivel de peligro (para pathfinding con pesos)."""
        dangerous = {}
        for tile, obs_type in self._detected_obstacles.items():
            info = OBSTACLE_COLORS.get(obs_type, {})
            danger = info.get("danger_level", 0)
            if danger > 0:
                dangerous[tile] = danger
        return dangerous

    def is_tile_safe(self, tile_x: int, tile_y: int) -> bool:
        """Verifica si un tile es seguro para caminar."""
        return (tile_x, tile_y) not in self._detected_obstacles

    def get_obstacle_at(self, tile_x: int, tile_y: int) -> Optional[str]:
        """Retorna el tipo de obstáculo en un tile, o None si es libre."""
        return self._detected_obstacles.get((tile_x, tile_y))

    def draw_debug(self, frame: np.ndarray) -> np.ndarray:
        """Dibuja los obstáculos detectados sobre el frame para debug."""
        debug = frame.copy()
        if self.minimap_region is None:
            return debug

        mx, my, _, _ = self.minimap_region
        ts = self.tile_size

        color_map = {
            "fire_field": (0, 0, 255),     # Rojo
            "energy_field": (255, 0, 255),   # Magenta
            "poison_field": (0, 255, 0),     # Verde
            "parcel": (0, 165, 255),         # Naranja
            "water": (255, 200, 0),          # Azul claro
            "wall": (100, 100, 100),         # Gris
        }

        for (tx, ty), obs_type in self._detected_obstacles.items():
            color = color_map.get(obs_type, (255, 255, 255))
            x1 = mx + tx * ts
            y1 = my + ty * ts
            x2 = x1 + ts
            y2 = y1 + ts
            cv2.rectangle(debug, (x1, y1), (x2, y2), color, 1)

        return debug

    @property
    def obstacle_count(self) -> int:
        return len(self._detected_obstacles)

    @property
    def last_detected(self) -> Dict[Tuple[int, int], str]:
        return self._detected_obstacles.copy()
