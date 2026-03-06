"""
looter/corpse_detector.py - Detector de cuerpos de criaturas muertas v1.

Detecta la posición de cuerpos en el game window usando dos métodos:
1. Efecto de muerte (aura brillante amarillo/blanco) — visible por ~2-3 segundos
2. Blood splashes (manchas de sangre roja/verde) — visibles por más tiempo

El detector escanea SOLO el game window (no la UI) y retorna las posiciones
de los SQMs donde hay cuerpos para lootear.

Basado en la observación de que TODOS los cuerpos de criaturas tienen
el mismo efecto visual de muerte, independientemente del tipo de criatura.
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np


class CorpseDetector:
    """
    Detecta cuerpos de criaturas muertas en el game window.
    Usa detección de color (HSV) para encontrar:
    - Aura de muerte (destello brillante amarillo/blanco)
    - Blood splashes (manchas rojas/verdes en el suelo)
    
    Retorna posiciones de SQMs donde hay cuerpos para que el looter
    clickee directamente ahí en vez de los 9 SQMs ciegos.
    """

    def __init__(self):
        # Estado
        self.enabled: bool = True
        self._log_fn: Optional[Callable] = None

        # Game window region (set by calibrator)
        self._game_region: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)
        self._player_center: Tuple[int, int] = (0, 0)
        self._sqm_size: Tuple[int, int] = (0, 0)  # (width, height) de un SQM

        # Detección configuración
        self.min_aura_area: int = 40         # Área mínima de cluster para ser aura
        self.max_aura_area: int = 2500       # Área máxima (evitar falsos positivos grandes)
        self.min_splash_area: int = 30       # Área mínima para blood splash
        self.max_splash_area: int = 1500     # Área máxima para blood splash
        self.max_corpse_distance: int = 4    # Max SQMs de distancia del player (solo lootear cerca)

        # Colores del aura de muerte (HSV ranges)
        # El aura es un destello brillante: alto valor (V), baja saturación (S)
        # Blanco brillante: S < 80, V > 200
        # Amarillo brillante: H=15-40, S=30-150, V > 150
        self.aura_white_lower = np.array([0, 0, 210])
        self.aura_white_upper = np.array([180, 80, 255])
        self.aura_yellow_lower = np.array([15, 30, 160])
        self.aura_yellow_upper = np.array([40, 180, 255])

        # Colores de blood splashes (HSV ranges)
        # Sangre roja: H=0-10 o 170-180, S>80, V>60
        # Sangre verde (criaturas verdes): H=35-80, S>60, V>50
        self.blood_red_lower1 = np.array([0, 80, 60])
        self.blood_red_upper1 = np.array([10, 255, 255])
        self.blood_red_lower2 = np.array([170, 80, 60])
        self.blood_red_upper2 = np.array([180, 255, 255])
        self.blood_green_lower = np.array([35, 60, 50])
        self.blood_green_upper = np.array([80, 255, 200])

        # Cache de detecciones recientes (para no re-detectar el mismo cuerpo)
        self._recent_detections: List[Dict] = []
        self._detection_ttl: float = 8.0  # Segundos que recordamos una detección

        # Métricas
        self.total_detections: int = 0
        self._last_log_time: float = 0.0

    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_game_region(self, x1: int, y1: int, x2: int, y2: int):
        """Configura la región del game window."""
        self._game_region = (x1, y1, x2, y2)

    def set_player_center(self, x: int, y: int):
        self._player_center = (x, y)

    def set_sqm_size(self, w: int, h: int):
        self._sqm_size = (w, h)

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[CorpseDetect] {msg}")

    # ==================================================================
    # Detección principal
    # ==================================================================
    def detect_corpses(self, frame: np.ndarray) -> List[Tuple[int, int]]:
        """
        Detecta posiciones de cuerpos de criaturas en el game window.
        
        Args:
            frame: Frame completo del OBS (BGR)
            
        Returns:
            Lista de (x, y) posiciones centrales de los cuerpos encontrados,
            en coordenadas del frame completo.
            Ordenados por distancia al player (más cercano primero).
        """
        if frame is None or self._game_region is None:
            return []

        gx1, gy1, gx2, gy2 = self._game_region

        # Validar que la región es válida
        h, w = frame.shape[:2]
        gx1 = max(0, gx1)
        gy1 = max(0, gy1)
        gx2 = min(w, gx2)
        gy2 = min(h, gy2)

        if gx2 <= gx1 or gy2 <= gy1:
            return []

        # Extraer ROI del game window
        game_roi = frame[gy1:gy2, gx1:gx2]
        game_hsv = cv2.cvtColor(game_roi, cv2.COLOR_BGR2HSV)

        # Detectar auras de muerte
        aura_positions = self._detect_death_auras(game_hsv, gx1, gy1)

        # Detectar blood splashes
        splash_positions = self._detect_blood_splashes(game_hsv, gx1, gy1)

        # Combinar detecciones (eliminar duplicados cercanos)
        all_positions = self._merge_detections(aura_positions + splash_positions)

        # Filtrar por distancia al player
        if self._player_center[0] > 0 and self._sqm_size[0] > 0:
            all_positions = self._filter_by_distance(all_positions)

        # Snap a centro de SQM más cercano
        if self._sqm_size[0] > 0 and self._player_center[0] > 0:
            all_positions = [self._snap_to_sqm(pos) for pos in all_positions]
            # Deduplicar después de snap
            all_positions = self._deduplicate_positions(all_positions)

        # Ordenar por distancia al player
        if self._player_center[0] > 0:
            px, py = self._player_center
            all_positions.sort(key=lambda p: (p[0]-px)**2 + (p[1]-py)**2)

        # Actualizar cache
        now = time.time()
        for pos in all_positions:
            self._recent_detections.append({
                "pos": pos,
                "time": now,
            })
        # Limpiar cache viejo
        self._recent_detections = [
            d for d in self._recent_detections
            if now - d["time"] < self._detection_ttl
        ]

        if all_positions:
            self.total_detections += len(all_positions)
            self._log(f"Cuerpos detectados: {len(all_positions)} posiciones")

        return all_positions

    # ==================================================================
    # Detección de aura de muerte
    # ==================================================================
    def _detect_death_auras(
        self, hsv_roi: np.ndarray, offset_x: int, offset_y: int
    ) -> List[Tuple[int, int]]:
        """
        Detecta el efecto de muerte (aura brillante) en el game window.
        El aura es un destello blanco-amarillo que aparece ~2-3s sobre el cuerpo.
        """
        # Máscara para brillo blanco extremo (centro del aura)
        mask_white = cv2.inRange(hsv_roi, self.aura_white_lower, self.aura_white_upper)

        # Máscara para amarillo brillante (bordes del aura)
        mask_yellow = cv2.inRange(hsv_roi, self.aura_yellow_lower, self.aura_yellow_upper)

        # Combinar
        aura_mask = cv2.bitwise_or(mask_white, mask_yellow)

        # Morph para unir clusters cercanos y eliminar ruido
        kernel_small = np.ones((3, 3), np.uint8)
        kernel_med = np.ones((5, 5), np.uint8)
        aura_mask = cv2.morphologyEx(aura_mask, cv2.MORPH_OPEN, kernel_small)  # Eliminar ruido
        aura_mask = cv2.dilate(aura_mask, kernel_med, iterations=1)  # Unir cercanos

        # Encontrar contornos
        contours, _ = cv2.findContours(aura_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        positions = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.min_aura_area <= area <= self.max_aura_area:
                x, y, w, h = cv2.boundingRect(cnt)
                # El centro del contorno es la posición del cuerpo
                cx = offset_x + x + w // 2
                cy = offset_y + y + h // 2
                positions.append((cx, cy))

        return positions

    # ==================================================================
    # Detección de blood splashes
    # ==================================================================
    def _detect_blood_splashes(
        self, hsv_roi: np.ndarray, offset_x: int, offset_y: int
    ) -> List[Tuple[int, int]]:
        """
        Detecta manchas de sangre (rojas/verdes) en el suelo del game window.
        Las manchas son más persistentes que el aura (~10-30 segundos).
        """
        # Sangre roja (dos rangos de hue para cubrir el wrap-around)
        mask_red1 = cv2.inRange(hsv_roi, self.blood_red_lower1, self.blood_red_upper1)
        mask_red2 = cv2.inRange(hsv_roi, self.blood_red_lower2, self.blood_red_upper2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        # Sangre verde
        mask_green = cv2.inRange(hsv_roi, self.blood_green_lower, self.blood_green_upper)

        # Combinar
        splash_mask = cv2.bitwise_or(mask_red, mask_green)

        # Morph para limpiar
        kernel = np.ones((3, 3), np.uint8)
        splash_mask = cv2.morphologyEx(splash_mask, cv2.MORPH_OPEN, kernel)
        splash_mask = cv2.dilate(splash_mask, kernel, iterations=1)

        # Encontrar contornos
        contours, _ = cv2.findContours(splash_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        positions = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.min_splash_area <= area <= self.max_splash_area:
                x, y, w, h = cv2.boundingRect(cnt)
                cx = offset_x + x + w // 2
                cy = offset_y + y + h // 2
                positions.append((cx, cy))

        return positions

    # ==================================================================
    # Helpers
    # ==================================================================
    def _merge_detections(self, positions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Elimina detecciones duplicadas que están muy cerca entre sí."""
        if not positions:
            return []

        sqm_w = max(self._sqm_size[0], 20)  # Min 20px para comparación
        merged = []
        for pos in positions:
            is_dup = False
            for existing in merged:
                dx = abs(pos[0] - existing[0])
                dy = abs(pos[1] - existing[1])
                if dx < sqm_w * 0.7 and dy < sqm_w * 0.7:
                    is_dup = True
                    break
            if not is_dup:
                merged.append(pos)
        return merged

    def _filter_by_distance(self, positions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Filtra posiciones que están demasiado lejos del player."""
        if self._sqm_size[0] == 0:
            return positions

        px, py = self._player_center
        sw, sh = self._sqm_size
        max_dist_px = self.max_corpse_distance * max(sw, sh)

        return [
            pos for pos in positions
            if abs(pos[0] - px) <= max_dist_px and abs(pos[1] - py) <= max_dist_px
        ]

    def _snap_to_sqm(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Ajusta una posición detectada al centro del SQM más cercano.
        Esto es importante porque necesitamos clickear en el CENTRO del SQM,
        no en cualquier punto del aura.
        """
        px, py = self._player_center
        sw, sh = self._sqm_size

        if sw == 0 or sh == 0:
            return pos

        # Calcular offset respecto al player center en unidades de SQM
        dx_sqm = round((pos[0] - px) / sw)
        dy_sqm = round((pos[1] - py) / sh)

        # Convertir de vuelta a pixeles (centro del SQM)
        snapped_x = px + dx_sqm * sw
        snapped_y = py + dy_sqm * sh

        return (snapped_x, snapped_y)

    def _deduplicate_positions(self, positions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Elimina posiciones duplicadas exactas después de snap."""
        seen = set()
        unique = []
        for pos in positions:
            if pos not in seen:
                seen.add(pos)
                unique.append(pos)
        return unique

    # ==================================================================
    # Debug
    # ==================================================================
    def get_debug_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Genera un frame de debug con las detecciones visualizadas.
        Útil para la preview en la GUI.
        """
        if frame is None or self._game_region is None:
            return frame if frame is not None else np.zeros((100, 100, 3), dtype=np.uint8)

        debug = frame.copy()
        positions = self.detect_corpses(frame)

        for i, (cx, cy) in enumerate(positions):
            # Dibujar círculo en la posición del cuerpo
            cv2.circle(debug, (cx, cy), 15, (0, 255, 0), 2)
            cv2.putText(debug, f"#{i+1}", (cx-8, cy-18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Dibujar SQM grid
            if self._sqm_size[0] > 0:
                sw, sh = self._sqm_size
                x1 = cx - sw // 2
                y1 = cy - sh // 2
                cv2.rectangle(debug, (x1, y1), (x1 + sw, y1 + sh), (0, 200, 0), 1)

        # Dibujar player center
        if self._player_center[0] > 0:
            px, py = self._player_center
            cv2.drawMarker(debug, (px, py), (255, 0, 0), cv2.MARKER_CROSS, 20, 2)

        return debug

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "game_region": self._game_region,
            "player_center": self._player_center,
            "sqm_size": self._sqm_size,
            "total_detections": self.total_detections,
            "recent_detections": len(self._recent_detections),
        }
