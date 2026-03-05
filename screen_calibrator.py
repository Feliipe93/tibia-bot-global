"""
screen_calibrator.py - Auto-detecta regiones del juego de Tibia desde un frame OBS.

Usa template matching (OpenCV) para localizar:
- Battle List (header "BattleList.png")
- Minimap (header "MapSettings.png")
- Game Window (bordes izquierdo/derecho/inferior)
- SQMs (9 cuadros alrededor del jugador en el game window)
- Player center (centro del game window)

Basado en los patrones de TibiaAuto12 (Getters.py + HookWindow.py).
Adaptado para trabajar con frames de OBS WebSocket (numpy BGR arrays).
"""

import os
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple

# Directorio base de imágenes de templates
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")


def _load_template(relative_path: str) -> Optional[np.ndarray]:
    """Carga un template PNG como imagen en escala de grises."""
    full_path = os.path.join(IMAGES_DIR, relative_path)
    if not os.path.exists(full_path):
        return None
    return cv2.imread(full_path, cv2.IMREAD_GRAYSCALE)


def _locate_image(
    frame_gray: np.ndarray,
    template: np.ndarray,
    region: Optional[Tuple[int, int, int, int]] = None,
    precision: float = 0.8,
) -> Tuple[int, int]:
    """
    Busca una imagen template en un frame gris.
    Retorna (x, y) de la esquina superior izquierda, o (0, 0) si no se encuentra.

    Args:
        frame_gray: Frame en escala de grises (completo o ROI).
        template: Template en escala de grises.
        region: (x1, y1, x2, y2) para buscar solo en esa región.
        precision: Umbral mínimo de confianza (0.0-1.0).
    """
    if template is None or frame_gray is None:
        return 0, 0

    search = frame_gray
    offset_x, offset_y = 0, 0

    if region is not None:
        x1, y1, x2, y2 = region
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame_gray.shape[1], x2)
        y2 = min(frame_gray.shape[0], y2)
        search = frame_gray[y1:y2, x1:x2]
        offset_x, offset_y = x1, y1

    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        return 0, 0

    res = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val >= precision:
        return max_loc[0] + offset_x, max_loc[1] + offset_y
    return 0, 0


def _locate_center_image(
    frame_gray: np.ndarray,
    template: np.ndarray,
    region: Optional[Tuple[int, int, int, int]] = None,
    precision: float = 0.8,
) -> Tuple[int, int]:
    """
    Busca una imagen template y retorna el CENTRO de la coincidencia.
    Retorna (0, 0) si no se encuentra.
    """
    x, y = _locate_image(frame_gray, template, region, precision)
    if x == 0 and y == 0:
        return 0, 0
    th, tw = template.shape[:2]
    return x + tw // 2, y + th // 2


def _locate_all_images(
    frame_gray: np.ndarray,
    template: np.ndarray,
    region: Optional[Tuple[int, int, int, int]] = None,
    precision: float = 0.8,
) -> List[Tuple[int, int]]:
    """
    Busca TODAS las ocurrencias de un template en el frame.
    Retorna lista de (x, y) centros encontrados.
    """
    if template is None or frame_gray is None:
        return []

    search = frame_gray
    offset_x, offset_y = 0, 0

    if region is not None:
        x1, y1, x2, y2 = region
        x1, y1 = max(0, x1), max(0, y1)
        x2 = min(frame_gray.shape[1], x2)
        y2 = min(frame_gray.shape[0], y2)
        search = frame_gray[y1:y2, x1:x2]
        offset_x, offset_y = x1, y1

    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        return []

    res = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(res >= precision)

    th, tw = template.shape[:2]
    results = []
    for pt in zip(*locations[::-1]):
        cx = pt[0] + offset_x + tw // 2
        cy = pt[1] + offset_y + th // 2
        # Deduplicar puntos muy cercanos
        is_duplicate = False
        for ex, ey in results:
            if abs(cx - ex) < tw and abs(cy - ey) < th:
                is_duplicate = True
                break
        if not is_duplicate:
            results.append((cx, cy))

    return results


class ScreenCalibrator:
    """
    Detecta automáticamente las regiones de la interfaz de Tibia
    a partir de un frame de OBS.

    Regiones detectadas:
    - battle_region: (x1, y1, x2, y2) de la battle list
    - map_region: (x1, y1, x2, y2) del minimapa
    - game_region: (x1, y1, x2, y2) del game window
    - player_center: (x, y) centro del jugador en el game window
    - sqms: lista de 9 posiciones (x, y) para los SQMs alrededor del jugador
    - sqm_size: (width, height) tamaño de un SQM
    """

    def __init__(self):
        # Regiones detectadas (coordenadas absolutas en el frame)
        self.battle_region: Optional[Tuple[int, int, int, int]] = None
        self.map_region: Optional[Tuple[int, int, int, int]] = None
        self.game_region: Optional[Tuple[int, int, int, int]] = None
        self.player_center: Optional[Tuple[int, int]] = None
        self.sqms: List[Tuple[int, int]] = []
        self.sqm_size: Tuple[int, int] = (0, 0)

        # Estado
        self.calibrated: bool = False
        self.last_error: str = ""

        # Cache de templates
        self._templates: Dict[str, Optional[np.ndarray]] = {}
        self._load_templates()

    def _load_templates(self):
        """Pre-carga todos los templates necesarios."""
        template_files = {
            "battle_list": "TibiaSettings/BattleList.png",
            "map_settings": "MapSettings/MapSettings.png",
            "stop": "TibiaSettings/Stop.png",
            # Game window borders
            "left_opt1": "PlayerSettings/LeftOption1.png",
            "left_opt2": "PlayerSettings/LeftOption2.png",
            "left_opt3": "PlayerSettings/LeftOption3.png",
            "right_opt1": "PlayerSettings/RightOption1.png",
            "right_opt2": "PlayerSettings/RightOption2.png",
            "right_opt3": "PlayerSettings/RightOption3.png",
            "right_opt4": "PlayerSettings/RightOption4.png",
            "end_location": "PlayerSettings/EndLocation.png",
        }
        for key, path in template_files.items():
            self._templates[key] = _load_template(path)

    def calibrate(self, frame: np.ndarray) -> bool:
        """
        Ejecuta la calibración completa desde un frame de OBS (BGR).

        Returns:
            True si la calibración fue exitosa (al menos battle list encontrada).
        """
        if frame is None or frame.size == 0:
            self.last_error = "Frame vacío o None"
            return False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. Detectar Battle List
        bl_found = self._detect_battle_list(gray)

        # 2. Detectar Minimap
        mm_found = self._detect_minimap(gray)

        # 3. Detectar Game Window y calcular SQMs
        gw_found = self._detect_game_window(gray)

        self.calibrated = bl_found  # Mínimo requerido
        if not bl_found:
            self.last_error = "No se encontró la Battle List"
        elif not gw_found:
            self.last_error = "Battle List OK, pero no se detectó Game Window"
        elif not mm_found:
            self.last_error = "Battle List y Game Window OK, Minimap no detectado"

        return self.calibrated

    def _detect_battle_list(self, gray: np.ndarray) -> bool:
        """Detecta la posición de la Battle List."""
        tpl = self._templates.get("battle_list")
        if tpl is None:
            self.last_error = "Template BattleList.png no encontrado"
            return False

        x, y = _locate_image(gray, tpl, precision=0.85)
        if x == 0 and y == 0:
            return False

        # La battle list es 155px de ancho y ~415px de alto debajo del header
        self.battle_region = (x + 8, y, x + 155, y + 415)
        return True

    def _detect_minimap(self, gray: np.ndarray) -> bool:
        """Detecta la posición del minimapa."""
        tpl = self._templates.get("map_settings")
        if tpl is None:
            return False

        x, y = _locate_image(gray, tpl, precision=0.8)
        if x == 0 and y == 0:
            return False

        # El minimapa es 110x110px a la izquierda del icono MapSettings
        map_size = 110
        x1 = x - map_size + 4
        y1 = y + 1
        x2 = x - 1
        y2 = y + map_size - 1

        self.map_region = (x1, y1, x2, y2)
        return True

    def _detect_game_window(self, gray: np.ndarray) -> bool:
        """Detecta el game window y calcula posición del jugador y SQMs."""
        # Borde izquierdo
        left_x, left_y = 0, 0
        for key in ["left_opt1", "left_opt2", "left_opt3"]:
            tpl = self._templates.get(key)
            if tpl is not None:
                left_x, left_y = _locate_image(gray, tpl, precision=0.75)
                if left_x != 0 or left_y != 0:
                    break

        if left_x == 0 and left_y == 0:
            return False

        # Borde derecho
        right_x = 0
        for key in ["right_opt1", "right_opt2", "right_opt3", "right_opt4"]:
            tpl = self._templates.get(key)
            if tpl is not None:
                rx, ry = _locate_image(gray, tpl, precision=0.75)
                if rx != 0 or ry != 0:
                    right_x = rx
                    break

        if right_x == 0:
            return False

        # Borde inferior
        tpl_end = self._templates.get("end_location")
        if tpl_end is None:
            return False

        end_x, end_y = _locate_image(gray, tpl_end, precision=0.7)
        if end_x == 0 and end_y == 0:
            return False

        # Game window bounds
        self.game_region = (left_x, left_y, right_x, end_y)

        # Player center = centro del game window
        player_x = (right_x + left_x) // 2
        player_y = (end_y + left_y) // 2
        self.player_center = (player_x, player_y)

        # Calcular tamaño de SQM (game window es 15x11 SQMs)
        sqm_w = (right_x - left_x) // 15
        sqm_h = (end_y - left_y) // 11
        self.sqm_size = (sqm_w, sqm_h)

        # Calcular 9 SQMs alrededor del jugador
        # Orden: SW, S, SE, W, Center, E, NW, N, NE
        # (igual que TibiaAuto12: pares de coordenadas)
        self.sqms = [
            (player_x - sqm_w, player_y + sqm_h),  # SW
            (player_x,         player_y + sqm_h),  # S
            (player_x + sqm_w, player_y + sqm_h),  # SE
            (player_x - sqm_w, player_y),           # W
            (player_x,         player_y),           # Center (player)
            (player_x + sqm_w, player_y),           # E
            (player_x - sqm_w, player_y - sqm_h),  # NW
            (player_x,         player_y - sqm_h),  # N
            (player_x + sqm_w, player_y - sqm_h),  # NE
        ]

        return True

    def get_battle_roi(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Extrae el ROI de la battle list del frame."""
        if self.battle_region is None or frame is None:
            return None
        x1, y1, x2, y2 = self.battle_region
        return frame[y1:y2, x1:x2]

    def get_map_roi(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Extrae el ROI del minimapa del frame."""
        if self.map_region is None or frame is None:
            return None
        x1, y1, x2, y2 = self.map_region
        return frame[y1:y2, x1:x2]

    def get_game_roi(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Extrae el ROI del game window del frame."""
        if self.game_region is None or frame is None:
            return None
        x1, y1, x2, y2 = self.game_region
        return frame[y1:y2, x1:x2]

    def get_status(self) -> Dict:
        """Retorna el estado de la calibración."""
        return {
            "calibrated": self.calibrated,
            "battle_region": self.battle_region,
            "map_region": self.map_region,
            "game_region": self.game_region,
            "player_center": self.player_center,
            "sqm_count": len(self.sqms),
            "sqm_size": self.sqm_size,
            "last_error": self.last_error,
        }

    def __repr__(self) -> str:
        return (
            f"<ScreenCalibrator calibrated={self.calibrated} "
            f"battle={self.battle_region is not None} "
            f"map={self.map_region is not None} "
            f"game={self.game_region is not None}>"
        )
