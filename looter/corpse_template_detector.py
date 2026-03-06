"""
looter/corpse_template_detector.py - Detección de cadáveres por template matching.

Busca sprites de cadáveres (PNGs) en el game window usando OpenCV matchTemplate.
Cada criatura tiene su propio template de cadáver en corpse_loot/.

Flujo:
1. Cargar templates de corpse_loot/ (ej: SwampTroll.png, CaveRat.png)
2. En cada frame, buscar matches en el game window
3. Retornar posiciones de los SQMs donde hay cadáveres
4. El looter clickea en esas posiciones exactas

Los templates se capturan con el botón "Capturar Cadáver" de la GUI:
- El usuario ve el game window, dibuja un rectángulo sobre el cadáver
- La selección se guarda como PNG nombrado por la criatura
- No necesita ser exactamente 32x32, matchTemplate acepta cualquier tamaño
"""

import os
import time
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Directorio de templates de cadáveres
CORPSE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpse_loot")


class CorpseTemplateDetector:
    """
    Detecta cadáveres por template matching en el game window.
    Cada criatura tiene un PNG de su sprite muerto.
    """

    def __init__(self):
        # Templates cargados: {display_name: np.ndarray (BGR)}
        self._templates: Dict[str, np.ndarray] = {}
        self._templates_gray: Dict[str, np.ndarray] = {}

        # Región del game window
        self._game_region: Optional[Tuple[int, int, int, int]] = None
        self._player_center: Tuple[int, int] = (0, 0)
        self._sqm_size: Tuple[int, int] = (0, 0)

        # Configuración
        self.precision: float = 0.70  # Umbral de coincidencia (0-1)
        self.max_corpse_distance: int = 4  # Max SQMs del player
        self.enabled: bool = True

        # Logging
        self._log_fn: Optional[Callable] = None

        # Métricas
        self.total_detections: int = 0
        self._last_detection_time: float = 0.0

    # ==================================================================
    # Configuración
    # ==================================================================
    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_game_region(self, x1: int, y1: int, x2: int, y2: int):
        self._game_region = (x1, y1, x2, y2)

    def set_player_center(self, x: int, y: int):
        self._player_center = (x, y)

    def set_sqm_size(self, w: int, h: int):
        self._sqm_size = (w, h)

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[CorpseTpl] {msg}")

    # ==================================================================
    # Carga de templates
    # ==================================================================
    def load_templates(self, creature_names: Optional[List[str]] = None) -> int:
        """
        Carga templates de cadáveres desde corpse_loot/.

        Args:
            creature_names: Si se especifica, solo carga estos.
                           Si None, carga todos los PNGs disponibles.

        Returns:
            Cantidad de templates cargados.
        """
        self._templates.clear()
        self._templates_gray.clear()

        if not os.path.isdir(CORPSE_DIR):
            os.makedirs(CORPSE_DIR, exist_ok=True)
            self._log(f"Creado directorio: {CORPSE_DIR}")
            return 0

        loaded = 0
        for fname in os.listdir(CORPSE_DIR):
            if not fname.endswith(".png"):
                continue

            raw = fname.replace(".png", "")

            # Convertir nombre de archivo a display name
            # snake_case → Display Name: "swamp_troll" → "Swamp Troll"
            # CamelCase → Display Name: "SwampTroll" → "Swamp Troll"
            display = self._filename_to_display_name(raw)

            # Si filtramos por nombres, verificar
            if creature_names is not None:
                if display not in creature_names and raw not in [n.replace(" ", "") for n in creature_names]:
                    continue

            path = os.path.join(CORPSE_DIR, fname)
            img = cv2.imread(path, cv2.IMREAD_COLOR)
            if img is None:
                self._log(f"⚠ No se pudo cargar: {fname}")
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self._templates[display] = img
            self._templates_gray[display] = gray
            loaded += 1
            self._log(f"Template cargado: {display} ({img.shape[1]}×{img.shape[0]}px)")

        self._log(f"Total templates de cadáveres: {loaded}")
        return loaded

    def _filename_to_display_name(self, raw: str) -> str:
        """Convierte nombre de archivo a display name.
        swamp_troll → Swamp Troll
        SwampTroll → Swamp Troll
        cave_rat → Cave Rat
        """
        # Si tiene underscore, es snake_case
        if "_" in raw:
            return " ".join(word.capitalize() for word in raw.split("_"))

        # CamelCase → insertar espacio antes de mayúsculas
        display = ""
        for i, ch in enumerate(raw):
            if ch.isupper() and i > 0 and raw[i - 1].islower():
                display += " "
            display += ch
        # Capitalizar primera letra
        if display:
            display = display[0].upper() + display[1:]
        return display

    def get_loaded_names(self) -> List[str]:
        return list(self._templates.keys())

    def get_available_templates(self) -> Dict[str, Tuple[int, int]]:
        """Retorna dict {display_name: (width, height)} de templates disponibles."""
        result = {}
        if os.path.isdir(CORPSE_DIR):
            for fname in os.listdir(CORPSE_DIR):
                if fname.endswith(".png"):
                    raw = fname.replace(".png", "")
                    display = self._filename_to_display_name(raw)
                    img = cv2.imread(os.path.join(CORPSE_DIR, fname))
                    if img is not None:
                        result[display] = (img.shape[1], img.shape[0])
        return result

    # ==================================================================
    # Detección
    # ==================================================================
    def detect_corpses(self, frame: np.ndarray) -> List[Tuple[int, int, str]]:
        """
        Busca cadáveres en el game window usando template matching.

        Args:
            frame: Frame completo del OBS (BGR)

        Returns:
            Lista de (x, y, creature_name) donde:
            - x, y son coordenadas del centro del match en el frame completo
            - creature_name es el nombre de la criatura detectada
        """
        if not self.enabled or not self._templates or frame is None:
            return []

        if self._game_region is None:
            return []

        gx1, gy1, gx2, gy2 = self._game_region
        h, w = frame.shape[:2]
        gx1 = max(0, min(gx1, w - 1))
        gy1 = max(0, min(gy1, h - 1))
        gx2 = max(gx1 + 1, min(gx2, w))
        gy2 = max(gy1 + 1, min(gy2, h))

        game_roi = frame[gy1:gy2, gx1:gx2]
        roi_gray = cv2.cvtColor(game_roi, cv2.COLOR_BGR2GRAY)

        detections = []

        for name, tpl_gray in self._templates_gray.items():
            th, tw = tpl_gray.shape[:2]

            # Verificar que el template cabe en la ROI
            if tw > roi_gray.shape[1] or th > roi_gray.shape[0]:
                continue

            # Template matching
            result = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)

            # Encontrar TODOS los matches por encima del umbral
            locations = np.where(result >= self.precision)

            for pt_y, pt_x in zip(*locations):
                # Centro del match en coordenadas del frame completo
                cx = gx1 + pt_x + tw // 2
                cy = gy1 + pt_y + th // 2
                confidence = result[pt_y, pt_x]
                detections.append((cx, cy, name, confidence))

        if not detections:
            return []

        # Eliminar detecciones duplicadas/solapadas (NMS simple)
        detections = self._non_max_suppression(detections)

        # Filtrar por distancia al player
        if self._player_center[0] > 0 and self._sqm_size[0] > 0:
            detections = self._filter_by_distance(detections)

        # Snap a centro de SQM
        results = []
        for cx, cy, name, conf in detections:
            snapped = self._snap_to_sqm(cx, cy)
            results.append((*snapped, name))

        # Deduplicar por posición
        seen = set()
        unique = []
        for x, y, name in results:
            key = (x, y)
            if key not in seen:
                seen.add(key)
                unique.append((x, y, name))

        # Ordenar por distancia al player
        if self._player_center[0] > 0:
            px, py = self._player_center
            unique.sort(key=lambda d: (d[0] - px) ** 2 + (d[1] - py) ** 2)

        if unique:
            self.total_detections += len(unique)
            self._last_detection_time = time.time()
            names_str = ", ".join(f"{n}@({x},{y})" for x, y, n in unique)
            self._log(f"Cadáveres: {len(unique)} → {names_str}")

        return unique

    def detect_corpse_positions(self, frame: np.ndarray) -> List[Tuple[int, int]]:
        """
        Versión simplificada que retorna solo posiciones (x, y).
        Compatible con la interfaz del CorpseDetector HSV.
        """
        detections = self.detect_corpses(frame)
        return [(x, y) for x, y, _ in detections]

    # ==================================================================
    # Helpers
    # ==================================================================
    def _non_max_suppression(
        self, detections: List[Tuple[int, int, str, float]], min_dist: int = 20
    ) -> List[Tuple[int, int, str, float]]:
        """Elimina detecciones solapadas, quedándose con la de mayor confianza."""
        if not detections:
            return []

        # Ordenar por confianza descendente
        sorted_dets = sorted(detections, key=lambda d: d[3], reverse=True)
        kept = []

        for det in sorted_dets:
            is_dup = False
            for existing in kept:
                dx = abs(det[0] - existing[0])
                dy = abs(det[1] - existing[1])
                if dx < min_dist and dy < min_dist:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(det)

        return kept

    def _filter_by_distance(
        self, detections: List[Tuple[int, int, str, float]]
    ) -> List[Tuple[int, int, str, float]]:
        """Filtra detecciones demasiado lejos del player."""
        px, py = self._player_center
        sw, sh = self._sqm_size
        max_px = self.max_corpse_distance * max(sw, sh)

        return [
            d for d in detections
            if abs(d[0] - px) <= max_px and abs(d[1] - py) <= max_px
        ]

    def _snap_to_sqm(self, x: int, y: int) -> Tuple[int, int]:
        """Ajusta una posición al centro del SQM más cercano."""
        px, py = self._player_center
        sw, sh = self._sqm_size

        if sw == 0 or sh == 0:
            return (x, y)

        dx_sqm = round((x - px) / sw)
        dy_sqm = round((y - py) / sh)

        return (px + dx_sqm * sw, py + dy_sqm * sh)

    # ==================================================================
    # Debug
    # ==================================================================
    def get_debug_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Genera frame con las detecciones marcadas."""
        if frame is None:
            return np.zeros((100, 100, 3), dtype=np.uint8)

        debug = frame.copy()
        detections = self.detect_corpses(frame)

        for i, (cx, cy, name) in enumerate(detections):
            # Círculo y label
            cv2.circle(debug, (cx, cy), 18, (0, 255, 255), 2)
            cv2.putText(debug, f"{name}", (cx - 30, cy - 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            # SQM grid
            if self._sqm_size[0] > 0:
                sw, sh = self._sqm_size
                cv2.rectangle(debug, (cx - sw // 2, cy - sh // 2),
                              (cx + sw // 2, cy + sh // 2), (0, 200, 200), 1)

        # Player center
        if self._player_center[0] > 0:
            cv2.drawMarker(debug, self._player_center, (255, 0, 0),
                           cv2.MARKER_CROSS, 20, 2)

        return debug

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "templates_loaded": len(self._templates),
            "template_names": list(self._templates.keys()),
            "precision": self.precision,
            "total_detections": self.total_detections,
            "game_region": self._game_region,
        }
