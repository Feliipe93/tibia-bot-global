"""
looter/game_screen_detector.py - Detección visual de cadáveres en el game screen.

Estrategia (en orden de prioridad):
  1. Frame diff: compara el frame previo a la muerte con el frame actual.
     Una zona nueva oscura/roja en el game window = cadáver.
  2. Fallback proporcional: si no se detectó nada visual, devuelve
     los SQMs calculados proporcionalmente para la resolución del user.

Resolución de referencia: 1366 × 768 (monitor del usuario).
Constantes de proportiones obtenidas del proyecto cavebot_test
(position_detector.py + real_minimap_detector.py).

NO modifica ningún otro módulo — solo es usado por looter_engine.py.
"""

import os
import time
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

# ──────────────────────────────────────────────
# Proporciones del game window para 1366×768
# Fuente: cavebot_test/position_detector.py
# Game area: x 129→1197, y 25→648  (píxeles absolutos a 1366×768)
# ──────────────────────────────────────────────
_REF_W: int = 1366
_REF_H: int = 768

# Fracciones del game window dentro del frame OBS
_GAME_X1_FRAC: float = 129 / _REF_W   # ≈ 0.0944
_GAME_Y1_FRAC: float = 25  / _REF_H   # ≈ 0.0326
_GAME_X2_FRAC: float = 1197 / _REF_W  # ≈ 0.8762
_GAME_Y2_FRAC: float = 648  / _REF_H  # ≈ 0.8438

# Centro del player dentro del game window (proporcional al game window mismo)
# El player está ~centrado: 50% horizontal, ~52% vertical
_PLAYER_REL_X: float = 0.50
_PLAYER_REL_Y: float = 0.52

# Umbral para frame diff (diferencia de píxeles que indica cambio)
_DIFF_THRESHOLD: int = 40

# Tamaño mínimo de región de cambio para considerarse un cadáver (px²)
_MIN_CORPSE_AREA: int = 60

# Directorios de debug
_DEBUG_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "debug", "gsd")


class GameScreenDetector:
    """
    Detecta visualmente dónde cayó el cadáver en el game screen.

    Flujo de uso (desde looter_engine.py):
      1. set_frame_size(w, h)               ← llamar cuando llega el 1er frame
      2. set_game_region_from_calibrator()  ← si screen_calibrator lo detectó
      3. set_player_center(cx, cy)          ← si screen_calibrator lo detectó
      4. update_reference_frame(frame)      ← llamar ANTES de que muera la criatura
                                               (en notify_kill antes del sleep)
      5. find_corpse_position(frame)        ← llamar DESPUÉS del sleep (cadáver ya visible)
         → devuelve (x, y) en coords OBS o None
    """

    def __init__(self):
        # Tamaño del frame OBS (pixeles)
        self._frame_w: int = 0
        self._frame_h: int = 0

        # Región del game window en coords OBS [x1, y1, x2, y2]
        self._game_x1: int = 0
        self._game_y1: int = 0
        self._game_x2: int = 0
        self._game_y2: int = 0
        self._calibrator_region_set: bool = False  # True = usó screen_calibrator

        # Centro del player en coords OBS
        self._player_cx: int = 0
        self._player_cy: int = 0

        # Frame de referencia (antes de la muerte) en escala de grises
        self._ref_frame_gray: Optional[np.ndarray] = None
        self._ref_frame_time: float = 0.0

        # Logging
        self._log_fn: Optional[Callable] = None

        # Debug
        self._debug_save: bool = False  # Activa guardado de imágenes debug
        self._debug_counter: int = 0

    # ──────────────────────────────────────────
    # Configuración
    # ──────────────────────────────────────────

    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_debug(self, enabled: bool):
        """Activa/desactiva el guardado de imágenes de debug."""
        self._debug_save = enabled
        if enabled:
            os.makedirs(_DEBUG_DIR, exist_ok=True)

    def set_frame_size(self, w: int, h: int):
        """
        Informa al detector el tamaño del frame OBS.
        Recalcula la región del game window proporcional si no hay región
        del calibrator.
        """
        if w == self._frame_w and h == self._frame_h:
            return  # Sin cambios

        self._frame_w = w
        self._frame_h = h

        if not self._calibrator_region_set:
            self._recalc_proportional_region()
            self._log(
                f"GSD frame_size={w}×{h} → game_region proporcional "
                f"({self._game_x1},{self._game_y1})-({self._game_x2},{self._game_y2})"
            )

    def set_game_region_from_calibrator(self, x1: int, y1: int, x2: int, y2: int):
        """
        Usa la región exacta detectada por screen_calibrator.
        Tiene prioridad sobre el cálculo proporcional.
        """
        self._game_x1 = x1
        self._game_y1 = y1
        self._game_x2 = x2
        self._game_y2 = y2
        self._calibrator_region_set = True
        self._recalc_player_center_from_region()
        self._log(
            f"GSD region_calibrator=({x1},{y1})-({x2},{y2}) "
            f"player_center=({self._player_cx},{self._player_cy})"
        )

    def set_player_center(self, cx: int, cy: int):
        """Sobreescribe el centro del player (si lo detectó screen_calibrator)."""
        if cx > 0 and cy > 0:
            self._player_cx = cx
            self._player_cy = cy

    def is_ready(self) -> bool:
        """True si el detector tiene suficiente info para funcionar."""
        return self._frame_w > 0 and self._game_x2 > self._game_x1

    # ──────────────────────────────────────────
    # Frame de referencia
    # ──────────────────────────────────────────

    def update_reference_frame(self, frame: np.ndarray):
        """
        Guarda el frame ANTES de la muerte como referencia.
        Llamar desde notify_kill(), antes del sleep.
        """
        if frame is None:
            return
        try:
            roi = self._extract_game_roi(frame)
            if roi is not None and roi.size > 0:
                self._ref_frame_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                self._ref_frame_time = time.time()
        except Exception as e:
            self._log(f"GSD update_ref error: {e}")

    # ──────────────────────────────────────────
    # Detección del cadáver
    # ──────────────────────────────────────────

    def find_corpse_position(
        self,
        current_frame: np.ndarray,
        monster_name: str = ""
    ) -> Optional[Tuple[int, int]]:
        """
        Busca la posición del cadáver en el frame actual.

        Returns:
            (x, y) en coordenadas del frame OBS (para pasarle a _execute_loot_click),
            o None si no pudo detectar.
        """
        if not self.is_ready() or current_frame is None:
            return None

        # Intentar frame diff primero
        pos = self._detect_by_frame_diff(current_frame, monster_name)
        if pos:
            return pos

        # Intentar detección por color de sangre/oscurecimiento
        pos = self._detect_by_corpse_color(current_frame, monster_name)
        if pos:
            return pos

        return None

    # ──────────────────────────────────────────
    # SQMs proporcionales (fallback sin detección)
    # ──────────────────────────────────────────

    def get_proportional_sqms(self, max_sqms: int = 5) -> List[Tuple[int, int]]:
        """
        Calcula los SQMs alrededor del player usando las proporciones
        del game window, sin depender del screen_calibrator.
        Devuelve coords en frame OBS.
        """
        if not self.is_ready():
            return []

        cx = self._player_cx
        cy = self._player_cy

        if cx == 0 or cy == 0:
            return []

        # Tamaño de un SQM = game_width / 15 (el game muestra ~15 SQMs de ancho)
        gw = self._game_x2 - self._game_x1
        gh = self._game_y2 - self._game_y1
        sqm_w = max(1, gw // 15)
        sqm_h = max(1, gh // 11)  # ~11 SQMs de alto

        offsets = [
            (0,      0),      # Center
            (0,      sqm_h),  # S
            (0,     -sqm_h),  # N
            (sqm_w,  0),      # E
            (-sqm_w, 0),      # W
        ]

        sqms = [(cx + dx, cy + dy) for dx, dy in offsets]
        return sqms[:max_sqms]

    # ──────────────────────────────────────────
    # Métodos internos de detección
    # ──────────────────────────────────────────

    def _detect_by_frame_diff(
        self,
        current_frame: np.ndarray,
        monster_name: str = ""
    ) -> Optional[Tuple[int, int]]:
        """
        Detecta cambio en el game screen comparando con el frame de referencia.
        El cadáver aparece como una mancha oscura nueva en el suelo.
        """
        if self._ref_frame_gray is None:
            return None

        # El frame de referencia no debe ser demasiado viejo (max 3s)
        if time.time() - self._ref_frame_time > 3.0:
            return None

        try:
            roi = self._extract_game_roi(current_frame)
            if roi is None or roi.size == 0:
                return None

            cur_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            # Ajustar tamaño si cambiaron las dims (por si acaso)
            ref = self._ref_frame_gray
            if ref.shape != cur_gray.shape:
                ref = cv2.resize(ref, (cur_gray.shape[1], cur_gray.shape[0]))

            # Frame diff
            diff = cv2.absdiff(ref, cur_gray)
            _, mask = cv2.threshold(diff, _DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)

            # Morfología para eliminar ruido pequeño
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.dilate(mask, kernel, iterations=2)

            # Encontrar contornos del cambio
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return None

            # Filtrar contornos por tamaño mínimo y tomar el más cercano al player
            valid = [c for c in contours if cv2.contourArea(c) >= _MIN_CORPSE_AREA]
            if not valid:
                return None

            # Centro del player en coords del ROI
            pcx_roi = self._player_cx - self._game_x1
            pcy_roi = self._player_cy - self._game_y1

            # Tomar el contorno con centroide más cercano al player
            best_pt = self._closest_contour_center(valid, pcx_roi, pcy_roi)
            if best_pt is None:
                return None

            # Convertir de coords ROI → coords frame OBS
            obs_x = best_pt[0] + self._game_x1
            obs_y = best_pt[1] + self._game_y1

            # Guardar debug si está activado
            if self._debug_save:
                self._save_debug_image(roi, mask, best_pt, monster_name, "diff")

            self._log(
                f"GSD diff: cadáver={monster_name} detectado en "
                f"OBS({obs_x},{obs_y}) ROI({best_pt[0]},{best_pt[1]})"
            )
            return (obs_x, obs_y)

        except Exception as e:
            self._log(f"GSD _detect_by_frame_diff error: {e}")
            return None

    def _detect_by_corpse_color(
        self,
        current_frame: np.ndarray,
        monster_name: str = ""
    ) -> Optional[Tuple[int, int]]:
        """
        Detecta cadáveres por color: manchas rojizas/oscuras nuevas
        cerca del player center.
        Esto complementa frame_diff cuando el fondo cambia poco.
        """
        try:
            roi = self._extract_game_roi(current_frame)
            if roi is None or roi.size == 0:
                return None

            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            # Rango de "sangre/cadáver rojo-oscuro" en HSV
            # Tibia usa tonos marrón rojizo oscuro para los cuerpos
            lower1 = np.array([0,   60, 20],  dtype=np.uint8)
            upper1 = np.array([15, 255, 120], dtype=np.uint8)
            lower2 = np.array([165, 60, 20],  dtype=np.uint8)
            upper2 = np.array([180,255, 120], dtype=np.uint8)

            mask1 = cv2.inRange(hsv, lower1, upper1)
            mask2 = cv2.inRange(hsv, lower2, upper2)
            mask = cv2.bitwise_or(mask1, mask2)

            # Dilatar para conectar píxeles cercanos
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.dilate(mask, kernel, iterations=1)

            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return None

            valid = [c for c in contours if cv2.contourArea(c) >= _MIN_CORPSE_AREA * 2]
            if not valid:
                return None

            # Solo considerar contornos dentro de 3 SQMs del player
            gw = self._game_x2 - self._game_x1
            max_dist_px = (gw // 15) * 3  # 3 SQMs de radio

            pcx_roi = self._player_cx - self._game_x1
            pcy_roi = self._player_cy - self._game_y1

            near_valid = self._filter_by_distance(valid, pcx_roi, pcy_roi, max_dist_px)
            if not near_valid:
                return None

            best_pt = self._closest_contour_center(near_valid, pcx_roi, pcy_roi)
            if best_pt is None:
                return None

            obs_x = best_pt[0] + self._game_x1
            obs_y = best_pt[1] + self._game_y1

            if self._debug_save:
                self._save_debug_image(roi, mask, best_pt, monster_name, "hsv")

            self._log(
                f"GSD hsv: cadáver={monster_name} detectado en "
                f"OBS({obs_x},{obs_y}) ROI({best_pt[0]},{best_pt[1]})"
            )
            return (obs_x, obs_y)

        except Exception as e:
            self._log(f"GSD _detect_by_corpse_color error: {e}")
            return None

    # ──────────────────────────────────────────
    # Helpers internos
    # ──────────────────────────────────────────

    def _extract_game_roi(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Extrae el ROI del game window del frame OBS."""
        if frame is None:
            return None
        h, w = frame.shape[:2]
        # Si las dimensiones del frame cambiaron, recalcular
        if w != self._frame_w or h != self._frame_h:
            self.set_frame_size(w, h)
        x1 = max(0, self._game_x1)
        y1 = max(0, self._game_y1)
        x2 = min(w, self._game_x2)
        y2 = min(h, self._game_y2)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    def _recalc_proportional_region(self):
        """Calcula la región del game window usando proporciones fijas."""
        if self._frame_w == 0 or self._frame_h == 0:
            return
        sx = self._frame_w / _REF_W
        sy = self._frame_h / _REF_H
        self._game_x1 = int(129 * sx)
        self._game_y1 = int(25  * sy)
        self._game_x2 = int(1197 * sx)
        self._game_y2 = int(648  * sy)
        self._recalc_player_center_from_region()

    def _recalc_player_center_from_region(self):
        """Calcula el player center desde la región del game window."""
        gw = self._game_x2 - self._game_x1
        gh = self._game_y2 - self._game_y1
        self._player_cx = self._game_x1 + int(gw * _PLAYER_REL_X)
        self._player_cy = self._game_y1 + int(gh * _PLAYER_REL_Y)

    @staticmethod
    def _contour_center(c) -> Tuple[int, int]:
        M = cv2.moments(c)
        if M["m00"] == 0:
            x, y, ww, hh = cv2.boundingRect(c)
            return (x + ww // 2, y + hh // 2)
        return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

    @staticmethod
    def _dist(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) ** 0.5

    def _closest_contour_center(
        self,
        contours,
        ref_x: int,
        ref_y: int
    ) -> Optional[Tuple[int, int]]:
        """Devuelve el centroide del contorno más cercano a (ref_x, ref_y)."""
        best = None
        best_dist = float("inf")
        for c in contours:
            cx, cy = self._contour_center(c)
            d = self._dist((cx, cy), (ref_x, ref_y))
            if d < best_dist:
                best_dist = d
                best = (cx, cy)
        return best

    def _filter_by_distance(
        self,
        contours,
        ref_x: int,
        ref_y: int,
        max_dist: float
    ) -> list:
        """Filtra contornos que están dentro de max_dist del punto de referencia."""
        result = []
        for c in contours:
            cx, cy = self._contour_center(c)
            if self._dist((cx, cy), (ref_x, ref_y)) <= max_dist:
                result.append(c)
        return result

    def _save_debug_image(
        self,
        roi: np.ndarray,
        mask: np.ndarray,
        best_pt: Tuple[int, int],
        monster_name: str,
        method: str
    ):
        """Guarda imágenes de debug para inspección manual."""
        try:
            os.makedirs(_DEBUG_DIR, exist_ok=True)
            self._debug_counter += 1
            ts = int(time.time())
            safe_name = monster_name.replace(" ", "_")[:20]

            # Imagen ROI con el punto detectado marcado
            debug_img = roi.copy()
            cv2.circle(debug_img, best_pt, 8, (0, 255, 0), 2)
            cv2.circle(debug_img, best_pt, 2, (0, 255, 0), -1)

            # Marcar player center
            pcx_roi = self._player_cx - self._game_x1
            pcy_roi = self._player_cy - self._game_y1
            cv2.circle(debug_img, (pcx_roi, pcy_roi), 6, (255, 0, 0), 2)

            fname_img = f"{ts}_{self._debug_counter:04d}_{safe_name}_{method}_roi.png"
            fname_mask = f"{ts}_{self._debug_counter:04d}_{safe_name}_{method}_mask.png"
            cv2.imwrite(os.path.join(_DEBUG_DIR, fname_img), debug_img)
            cv2.imwrite(os.path.join(_DEBUG_DIR, fname_mask), mask)
        except Exception as e:
            self._log(f"GSD debug save error: {e}")

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[GSD] {msg}")
