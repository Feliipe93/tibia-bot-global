"""
targeting/creature_tracker.py - Rastreo visual de criaturas en el game screen.

Rastrea la posición del monstruo que estamos atacando en el game screen.
Cuando el target muere, la ÚLTIMA POSICIÓN conocida se pasa al looter
para clickear exactamente donde cayó el cadáver.

Métodos de rastreo (en orden de prioridad):
  1. Template matching: Si hay un sprite PNG del monstruo, lo busca
     en el game screen (32x32 o tamaño custom).
  2. Battle list cross-reference: Usa el nombre del target + posición
     relativa en la battle list para inferir posición en el game screen.
     En Tibia, las criaturas aparecen en la battle list ordenadas por
     distancia (más arriba = más cercano). Con chase mode, la criatura
     más cercana suele estar en el SQM adyacente al player.

Flujo de uso:
  1. TargetingEngine llama a track(frame, target_name) cada frame
  2. CreatureTracker actualiza last_known_position
  3. Al detectar kill → TargetingEngine pasa last_known_position al looter
  4. Looter clickea en esa posición exacta → looteo preciso

Captura de sprites:
  - El usuario puede capturar el sprite de una criatura desde la GUI
  - Se guarda en images/Targets/Sprites/{NombreCriatura}.png
  - El tracker lo usa automáticamente para template matching
"""

import os
import time
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np


# Directorio de sprites de criaturas para template matching
SPRITES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "images", "Targets", "Sprites"
)

# Tamaño estándar de un sprite de criatura en Tibia (32x32 píxeles base)
DEFAULT_SPRITE_SIZE = 32


class CreatureTracker:
    """
    Rastrea la posición visual de criaturas en el game screen.

    Usa template matching de sprites + inferencia por posición en battle list
    para saber DÓNDE está el monstruo que estamos atacando en el game screen.
    """

    def __init__(self):
        # Templates de sprites de criaturas {nombre_lower: numpy_gray}
        self._sprite_templates: Dict[str, np.ndarray] = {}

        # Región del game window en coords OBS [x1, y1, x2, y2]
        self._game_region: Optional[Tuple[int, int, int, int]] = None

        # Centro del player en coords OBS
        self._player_center: Tuple[int, int] = (0, 0)

        # Tamaño de un SQM en píxeles
        self._sqm_size: Tuple[int, int] = (0, 0)

        # ── Estado de tracking ──
        # Última posición conocida del target en coords OBS
        self.last_known_position: Optional[Tuple[int, int]] = None

        # Nombre del target actual
        self._tracking_target: str = ""

        # Confianza de la última detección (0.0 - 1.0)
        self._last_confidence: float = 0.0

        # Método usado en la última detección
        self._last_method: str = "none"

        # Timestamp de la última detección exitosa
        self._last_detect_time: float = 0.0

        # Historial de posiciones recientes (para suavizado)
        self._position_history: List[Tuple[int, int]] = []
        self._max_history: int = 5

        # Precisión mínima para template matching de sprites
        self._sprite_precision: float = 0.65

        # Radio máximo de búsqueda alrededor del player (en SQMs)
        self._search_radius_sqms: int = 3

        # Logging
        self._log_fn: Optional[Callable] = None

        # Métricas
        self.sprite_detections: int = 0
        self.inferred_detections: int = 0
        self.total_tracks: int = 0

    # ══════════════════════════════════════════
    # Configuración
    # ══════════════════════════════════════════

    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_game_region(self, x1: int, y1: int, x2: int, y2: int):
        self._game_region = (x1, y1, x2, y2)

    def set_player_center(self, cx: int, cy: int):
        self._player_center = (cx, cy)

    def set_sqm_size(self, w: int, h: int):
        self._sqm_size = (w, h)

    def load_sprite_templates(self, monster_names: Optional[List[str]] = None) -> int:
        """
        Carga templates de sprites de criaturas desde images/Targets/Sprites/.
        Si monster_names se especifica, solo carga esos. Si no, carga todos.

        Returns:
            Número de templates cargados.
        """
        os.makedirs(SPRITES_DIR, exist_ok=True)
        loaded = 0

        if monster_names:
            for name in monster_names:
                filename = name.replace(" ", "")
                path = os.path.join(SPRITES_DIR, f"{filename}.png")
                if os.path.exists(path):
                    tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if tpl is not None:
                        self._sprite_templates[name.lower()] = tpl
                        loaded += 1
                        self._log(
                            f"[Tracker] Sprite cargado: {name} "
                            f"({tpl.shape[1]}x{tpl.shape[0]}px)"
                        )
        else:
            if os.path.isdir(SPRITES_DIR):
                for fname in os.listdir(SPRITES_DIR):
                    if fname.endswith(".png"):
                        raw = fname.replace(".png", "")
                        # CamelCase → "Display Name"
                        display = ""
                        for i, ch in enumerate(raw):
                            if ch.isupper() and i > 0 and raw[i - 1].islower():
                                display += " "
                            display += ch
                        tpl = cv2.imread(
                            os.path.join(SPRITES_DIR, fname),
                            cv2.IMREAD_GRAYSCALE,
                        )
                        if tpl is not None:
                            self._sprite_templates[display.lower()] = tpl
                            loaded += 1

        if loaded > 0:
            self._log(f"[Tracker] {loaded} sprites de criaturas cargados")
        return loaded

    def get_loaded_sprites(self) -> List[str]:
        """Retorna lista de nombres de criaturas con sprites cargados."""
        return list(self._sprite_templates.keys())

    # ══════════════════════════════════════════
    # Tracking principal
    # ══════════════════════════════════════════

    def track(
        self,
        frame: np.ndarray,
        target_name: str,
        battle_list_index: int = 0,
    ) -> Optional[Tuple[int, int]]:
        """
        Rastrea la posición del target en el game screen.

        Args:
            frame: Frame OBS actual (numpy BGR).
            target_name: Nombre del monstruo que estamos atacando.
            battle_list_index: Posición del target en la battle list
                               (0 = más cercano, más arriba).

        Returns:
            (x, y) en coords OBS del centro del monstruo, o None si no detectó.
        """
        if frame is None or not target_name:
            return None
        if self._game_region is None or self._player_center == (0, 0):
            return None

        self.total_tracks += 1

        # Si cambiamos de target, resetear historial
        name_lower = target_name.lower()
        if name_lower != self._tracking_target:
            self._tracking_target = name_lower
            self._position_history.clear()
            self.last_known_position = None

        # Intento 1: Template matching del sprite en game screen
        pos = self._detect_by_sprite(frame, name_lower)
        if pos:
            self._update_position(pos, "sprite")
            return pos

        # Intento 2: Inferencia por posición en battle list + chase mode
        pos = self._infer_from_battle_list(battle_list_index)
        if pos:
            self._update_position(pos, "inferred")
            return pos

        # Si no detectó nada pero tenemos historial reciente, usar el último
        if (self.last_known_position and
                time.time() - self._last_detect_time < 2.0):
            return self.last_known_position

        return None

    def get_death_position(self) -> Optional[Tuple[int, int]]:
        """
        Retorna la última posición conocida del target para looteo.
        Llamar cuando se detecta un kill.

        Returns:
            (x, y) en coords OBS donde murió la criatura, o None.
        """
        if self.last_known_position is None:
            return None

        # Si la última detección fue hace más de 3 segundos, no es confiable
        if time.time() - self._last_detect_time > 3.0:
            self._log(
                f"[Tracker] Posición de muerte descartada — "
                f"última detección hace {time.time() - self._last_detect_time:.1f}s"
            )
            return None

        pos = self.last_known_position
        self._log(
            f"[Tracker] Posición de muerte: OBS{pos} "
            f"(método={self._last_method}, conf={self._last_confidence:.2f})"
        )
        return pos

    def reset(self):
        """Resetea el estado de tracking (cuando se suelta el target)."""
        self._tracking_target = ""
        self._position_history.clear()
        self.last_known_position = None
        self._last_confidence = 0.0
        self._last_method = "none"

    # ══════════════════════════════════════════
    # Detección por sprite (template matching)
    # ══════════════════════════════════════════

    def _detect_by_sprite(
        self,
        frame: np.ndarray,
        target_name_lower: str,
    ) -> Optional[Tuple[int, int]]:
        """
        Busca el sprite del monstruo en el game screen usando template matching.
        Solo busca en un área reducida alrededor del player (para eficiencia).
        """
        template = self._sprite_templates.get(target_name_lower)
        if template is None:
            return None

        try:
            # Extraer ROI del game screen alrededor del player
            roi, offset_x, offset_y = self._extract_search_roi(frame)
            if roi is None or roi.size == 0:
                return None

            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            # Verificar que el template cabe en la ROI
            th, tw = template.shape[:2]
            if roi_gray.shape[0] < th or roi_gray.shape[1] < tw:
                return None

            # Template matching
            res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= self._sprite_precision:
                # Centro del match
                cx = max_loc[0] + tw // 2 + offset_x
                cy = max_loc[1] + th // 2 + offset_y
                self._last_confidence = max_val
                self.sprite_detections += 1
                return (cx, cy)

        except Exception as e:
            self._log(f"[Tracker] Error en sprite detection: {e}")

        return None

    # ══════════════════════════════════════════
    # Inferencia por battle list
    # ══════════════════════════════════════════

    def _infer_from_battle_list(
        self,
        battle_list_index: int,
    ) -> Optional[Tuple[int, int]]:
        """
        Infiere la posición del monstruo en el game screen basado en:
        - Su posición en la battle list (index 0 = más cercano)
        - En chase mode, la criatura más cercana está adyacente al player

        En Tibia con chase mode activo:
        - El monstruo que atacamos suele estar en un SQM adyacente
        - La batalla se da cuerpo a cuerpo
        - Al morir, el cadáver queda en ESE SQM (o debajo del player)

        Para battle_list_index 0 (primera criatura = más cercana):
        → Retornamos el player center (la criatura está encima o adyacente)
        → En chase mode el cadáver cae debajo del player o 1 SQM al rededor
        """
        px, py = self._player_center
        sw, sh = self._sqm_size

        if px == 0 or sw == 0:
            return None

        if battle_list_index == 0:
            # La criatura más cercana en chase mode está adyacente al player
            # Mejor estimación: el player center (cadáver cae aquí o 1 SQM)
            self._last_confidence = 0.50
            self.inferred_detections += 1
            return (px, py)

        # Para criaturas más lejanas, no podemos inferir bien
        # (necesitaríamos el sprite para tracking preciso)
        return None

    # ══════════════════════════════════════════
    # Helpers internos
    # ══════════════════════════════════════════

    def _extract_search_roi(
        self,
        frame: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], int, int]:
        """
        Extrae un ROI del game screen centrado en el player,
        con radio de búsqueda limitado para eficiencia.

        Returns:
            (roi, offset_x, offset_y) o (None, 0, 0)
        """
        if self._game_region is None:
            return None, 0, 0

        gx1, gy1, gx2, gy2 = self._game_region
        px, py = self._player_center
        sw, sh = self._sqm_size

        if sw == 0 or sh == 0:
            # Usar toda la game region como fallback
            h, w = frame.shape[:2]
            x1 = max(0, gx1)
            y1 = max(0, gy1)
            x2 = min(w, gx2)
            y2 = min(h, gy2)
            return frame[y1:y2, x1:x2], x1, y1

        # Área de búsqueda: N SQMs alrededor del player
        radius = self._search_radius_sqms
        search_x1 = max(gx1, px - radius * sw)
        search_y1 = max(gy1, py - radius * sh)
        search_x2 = min(gx2, px + radius * sw)
        search_y2 = min(gy2, py + radius * sh)

        h, w = frame.shape[:2]
        search_x1 = max(0, min(search_x1, w - 1))
        search_y1 = max(0, min(search_y1, h - 1))
        search_x2 = max(search_x1 + 1, min(search_x2, w))
        search_y2 = max(search_y1 + 1, min(search_y2, h))

        roi = frame[search_y1:search_y2, search_x1:search_x2]
        return roi, search_x1, search_y1

    def _update_position(self, pos: Tuple[int, int], method: str):
        """Actualiza la posición conocida y el historial."""
        self.last_known_position = pos
        self._last_method = method
        self._last_detect_time = time.time()

        self._position_history.append(pos)
        if len(self._position_history) > self._max_history:
            self._position_history.pop(0)

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(msg)

    # ══════════════════════════════════════════
    # Captura de sprites (para GUI)
    # ══════════════════════════════════════════

    @staticmethod
    def capture_sprite_from_frame(
        frame: np.ndarray,
        x: int,
        y: int,
        size: int = DEFAULT_SPRITE_SIZE,
    ) -> Optional[np.ndarray]:
        """
        Captura un sprite de tamaño size×size centrado en (x, y).
        Usado desde la GUI para que el usuario capture sprites de criaturas.

        Args:
            frame: Frame OBS completo (numpy BGR).
            x, y: Centro del sprite en coords del frame.
            size: Tamaño del sprite (default 32x32).

        Returns:
            Imagen recortada (numpy BGR) o None.
        """
        if frame is None:
            return None
        h, w = frame.shape[:2]
        half = size // 2
        x1 = max(0, x - half)
        y1 = max(0, y - half)
        x2 = min(w, x + half)
        y2 = min(h, y + half)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2].copy()

    @staticmethod
    def save_sprite_template(
        sprite: np.ndarray,
        creature_name: str,
    ) -> str:
        """
        Guarda un sprite como template en images/Targets/Sprites/.

        Args:
            sprite: Imagen del sprite (numpy BGR).
            creature_name: Nombre de la criatura.

        Returns:
            Ruta del archivo guardado.
        """
        os.makedirs(SPRITES_DIR, exist_ok=True)
        filename = creature_name.replace(" ", "") + ".png"
        path = os.path.join(SPRITES_DIR, filename)
        cv2.imwrite(path, sprite)
        return path

    # ══════════════════════════════════════════
    # Estado / Debug
    # ══════════════════════════════════════════

    def get_status(self) -> Dict:
        return {
            "tracking_target": self._tracking_target,
            "last_position": self.last_known_position,
            "last_method": self._last_method,
            "last_confidence": self._last_confidence,
            "sprites_loaded": len(self._sprite_templates),
            "sprite_names": list(self._sprite_templates.keys()),
            "sprite_detections": self.sprite_detections,
            "inferred_detections": self.inferred_detections,
            "total_tracks": self.total_tracks,
        }
