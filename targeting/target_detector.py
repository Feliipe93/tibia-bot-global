"""
targeting/target_detector.py - Detector de objetivos en pantalla.
Detecta monstruos y criaturas en el game window usando
análisis de color, contornos y HP bars sobre las criaturas.
"""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple

from utils.geometry import CENTER_TILE_X, CENTER_TILE_Y, TILE_SIZE_GAME


class ScreenTarget:
    """Representa un objetivo detectado en pantalla."""

    def __init__(
        self,
        screen_x: int = 0,
        screen_y: int = 0,
        width: int = 0,
        height: int = 0,
        hp_percent: int = 100,
        name: str = "",
        distance: float = 0.0,
    ):
        self.screen_x = screen_x  # Centro X en pantalla
        self.screen_y = screen_y  # Centro Y en pantalla
        self.width = width
        self.height = height
        self.hp_percent = hp_percent
        self.name = name
        self.distance = distance  # Distancia al jugador en tiles

    @property
    def center(self) -> Tuple[int, int]:
        return (self.screen_x, self.screen_y)

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Bounding box (x1, y1, x2, y2)."""
        half_w = self.width // 2
        half_h = self.height // 2
        return (
            self.screen_x - half_w,
            self.screen_y - half_h,
            self.screen_x + half_w,
            self.screen_y + half_h,
        )

    def to_dict(self) -> Dict:
        return {
            "screen_x": self.screen_x,
            "screen_y": self.screen_y,
            "width": self.width,
            "height": self.height,
            "hp_percent": self.hp_percent,
            "name": self.name,
            "distance": round(self.distance, 1),
        }

    def __repr__(self) -> str:
        return f"<Target '{self.name}' ({self.screen_x},{self.screen_y}) HP={self.hp_percent}%>"


class TargetDetector:
    """
    Detecta objetivos (monstruos) en el game window de Tibia.
    Busca HP bars sobre las criaturas para localizarlas.
    Las HP bars de criaturas son pequeñas barras negras con relleno de color.
    """

    # HP bar de criaturas en game window
    CREATURE_HP_BAR_WIDTH = 27    # Ancho típico de la barra
    CREATURE_HP_BAR_HEIGHT = 3    # Altura típica
    CREATURE_HP_BAR_BORDER = 1    # Borde negro

    # Colores del borde de la HP bar (negro)
    HP_BAR_BORDER_COLOR_MIN = np.array([0, 0, 0])
    HP_BAR_BORDER_COLOR_MAX = np.array([40, 40, 40])

    def __init__(self):
        # Región del game window
        self.game_region: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)

        # Cache de detecciones
        self._targets: List[ScreenTarget] = []

        # Configuración
        self.min_hp_bar_width: int = 20
        self.max_hp_bar_width: int = 35
        self.detection_enabled: bool = True

    def set_game_region(self, x: int, y: int, w: int, h: int) -> None:
        """Configura la región del game window."""
        self.game_region = (x, y, w, h)

    def detect(self, frame: np.ndarray) -> List[ScreenTarget]:
        """
        Detecta criaturas en el game window buscando HP bars.

        Args:
            frame: Frame BGR de OBS.

        Returns:
            Lista de ScreenTarget detectados.
        """
        if not self.detection_enabled or self.game_region is None:
            return []

        gx, gy, gw, gh = self.game_region
        roi = frame[gy:gy + gh, gx:gx + gw]
        if roi.size == 0:
            return []

        targets = []

        # Método 1: Buscar HP bars de criaturas (barras negras con relleno)
        hp_bar_targets = self._detect_by_hp_bars(roi, gx, gy)
        targets.extend(hp_bar_targets)

        # Calcular distancia al centro (jugador)
        center_x = gw // 2
        center_y = gh // 2
        for t in targets:
            dx = abs(t.screen_x - gx - center_x) / max(TILE_SIZE_GAME, 1)
            dy = abs(t.screen_y - gy - center_y) / max(TILE_SIZE_GAME, 1)
            t.distance = (dx ** 2 + dy ** 2) ** 0.5

        # Ordenar por distancia
        targets.sort(key=lambda t: t.distance)

        self._targets = targets
        return targets

    def _detect_by_hp_bars(
        self, roi: np.ndarray, offset_x: int, offset_y: int
    ) -> List[ScreenTarget]:
        """
        Detecta criaturas buscando sus HP bars (barras con borde negro).
        """
        targets = []
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Buscar líneas horizontales negras (borde superior de HP bar)
        # Las HP bars de criaturas tienen un borde negro de 1px
        black_mask = gray < 30

        # Buscar líneas horizontales usando erosión horizontal
        kernel_h = np.ones((1, self.min_hp_bar_width), np.uint8)
        horizontal_lines = cv2.erode(black_mask.astype(np.uint8) * 255, kernel_h)
        horizontal_lines = cv2.dilate(horizontal_lines, kernel_h)

        # Encontrar contornos de las líneas
        contours, _ = cv2.findContours(
            horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        processed_positions = set()

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)

            # Filtrar por tamaño de HP bar
            if bw < self.min_hp_bar_width or bw > self.max_hp_bar_width:
                continue
            if bh > 6:
                continue

            # Evitar duplicados cercanos
            grid_key = (bx // 10, by // 10)
            if grid_key in processed_positions:
                continue
            processed_positions.add(grid_key)

            # Verificar que debajo de la línea negra hay color de HP
            bar_y = by + 1
            bar_h = 3
            if bar_y + bar_h >= h:
                continue

            bar_region = roi[bar_y:bar_y + bar_h, bx + 1:bx + bw - 1]
            if bar_region.size == 0:
                continue

            # Verificar que hay color de HP (no es fondo oscuro)
            hsv_bar = cv2.cvtColor(bar_region, cv2.COLOR_BGR2HSV)
            saturation = np.mean(hsv_bar[:, :, 1])
            if saturation < 50:
                continue

            # Estimar HP
            hp_pct = self._estimate_creature_hp(bar_region, bw - 2)

            # La criatura está debajo de la HP bar (aproximadamente 1 tile)
            creature_center_x = offset_x + bx + bw // 2
            creature_center_y = offset_y + by + TILE_SIZE_GAME // 2

            target = ScreenTarget(
                screen_x=creature_center_x,
                screen_y=creature_center_y,
                width=TILE_SIZE_GAME,
                height=TILE_SIZE_GAME,
                hp_percent=hp_pct,
            )
            targets.append(target)

        return targets

    def _estimate_creature_hp(self, bar_roi: np.ndarray, total_width: int) -> int:
        """Estima el HP% de una criatura por su barra."""
        if bar_roi.size == 0 or total_width <= 0:
            return 100

        hsv = cv2.cvtColor(bar_roi, cv2.COLOR_BGR2HSV)

        # Contar píxeles con saturación alta (parte coloreada de la barra)
        colored_mask = hsv[:, :, 1] > 80
        colored_cols = set()
        for col in range(bar_roi.shape[1]):
            if np.any(colored_mask[:, col]):
                colored_cols.add(col)

        filled_width = len(colored_cols)
        hp_pct = int((filled_width / max(total_width, 1)) * 100)
        return max(1, min(100, hp_pct))

    # ==================================================================
    # Acceso a datos
    # ==================================================================
    @property
    def targets(self) -> List[ScreenTarget]:
        return self._targets

    @property
    def target_count(self) -> int:
        return len(self._targets)

    def get_closest(self) -> Optional[ScreenTarget]:
        """Retorna el objetivo más cercano al jugador."""
        if self._targets:
            return self._targets[0]  # Ya ordenados por distancia
        return None

    def get_lowest_hp(self) -> Optional[ScreenTarget]:
        """Retorna el objetivo con menor HP."""
        if not self._targets:
            return None
        return min(self._targets, key=lambda t: t.hp_percent)

    def get_targets_in_range(self, max_tiles: float = 3.0) -> List[ScreenTarget]:
        """Retorna objetivos dentro de un rango de tiles."""
        return [t for t in self._targets if t.distance <= max_tiles]

    def has_targets(self) -> bool:
        return len(self._targets) > 0

    def draw_debug(self, frame: np.ndarray) -> np.ndarray:
        """Dibuja las detecciones sobre el frame."""
        debug = frame.copy()
        for i, t in enumerate(self._targets):
            x1, y1, x2, y2 = t.bbox
            # Color basado en HP
            if t.hp_percent > 70:
                color = (0, 255, 0)
            elif t.hp_percent > 30:
                color = (0, 255, 255)
            else:
                color = (0, 0, 255)

            cv2.rectangle(debug, (x1, y1), (x2, y2), color, 2)
            label = f"#{i+1} HP:{t.hp_percent}% D:{t.distance:.1f}"
            cv2.putText(debug, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        return debug
