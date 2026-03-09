"""
looter/corpse_sprite_detector.py - Detección de cadáveres por template matching.

Busca sprites de cadáveres (fotos del cuerpo muerto 32x32) en el game screen
usando template matching de OpenCV.  Es el método más confiable para
localizar cadáveres porque:
  1. NO depende de inferencia de posición (que siempre da player_center)
  2. NO depende de frame diff (que falla por animaciones/movimiento)
  3. Busca el CUERPO MUERTO real en la pantalla

Flujo:
  1. El usuario captura una foto del cadáver desde la GUI (32x32)
  2. Se guarda en images/Looter/Corpses/{NombreCriatura}.png
  3. Al matar, este detector busca ESE sprite en el game screen
  4. Retorna las coordenadas exactas para clickear

Soporta múltiples sprites por criatura (variantes de cadáver).
"""

import os
import time
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Directorio de sprites de cadáveres
CORPSE_SPRITES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "images", "Looter", "Corpses"
)


class CorpseSpriteDetector:
    """
    Detecta cadáveres en el game screen usando template matching
    de sprites capturados por el usuario.
    """

    def __init__(self):
        # Templates: {nombre_lower: [lista de templates numpy gray]}
        # Soporta múltiples variantes por criatura
        self._templates: Dict[str, List[np.ndarray]] = {}

        # Región del game screen en coords OBS
        self._game_region: Optional[Tuple[int, int, int, int]] = None

        # Centro del player en coords OBS
        self._player_center: Tuple[int, int] = (0, 0)

        # Tamaño de SQM en píxeles
        self._sqm_size: Tuple[int, int] = (0, 0)

        # Configuración de template matching
        self._precision: float = 0.55          # Umbral de confianza
        self._search_radius_sqms: int = 4      # Radio de búsqueda (SQMs)
        self._min_match_distance: int = 10     # Distancia mínima entre matches (px)

        # Logging
        self._log_fn: Optional[Callable] = None

        # Métricas
        self.detections: int = 0
        self.searches: int = 0
        self.templates_loaded: int = 0

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

    def set_precision(self, precision: float):
        """Ajusta el umbral de confianza (0.0-1.0). Menor = más permisivo."""
        self._precision = max(0.1, min(1.0, precision))

    # ══════════════════════════════════════════
    # Carga de templates
    # ══════════════════════════════════════════

    def load_templates(self, monster_names: Optional[List[str]] = None) -> int:
        """
        Carga templates de cadáveres desde images/Looter/Corpses/.

        Estructura de archivos:
          - Rotworm.png          → template principal
          - Rotworm_2.png        → variante 2
          - Rotworm_3.png        → variante 3

        Args:
            monster_names: Si se especifica, solo carga esos monstruos.
                          Si None, carga TODOS los disponibles.
        Returns:
            Número total de templates cargados.
        """
        os.makedirs(CORPSE_SPRITES_DIR, exist_ok=True)
        self._templates.clear()
        loaded = 0

        if not os.path.isdir(CORPSE_SPRITES_DIR):
            return 0

        for fname in sorted(os.listdir(CORPSE_SPRITES_DIR)):
            if not fname.lower().endswith(".png"):
                continue

            # Extraer nombre: "Rotworm.png" → "rotworm", "Rotworm_2.png" → "rotworm"
            base = fname.replace(".png", "").replace(".PNG", "")
            # Separar variantes: "Rotworm_2" → "Rotworm"
            parts = base.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                display_name = parts[0]
            else:
                display_name = base

            name_lower = display_name.lower()

            # Filtrar por nombres si se especificaron
            if monster_names:
                if not any(m.lower() == name_lower for m in monster_names):
                    continue

            path = os.path.join(CORPSE_SPRITES_DIR, fname)
            tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if tpl is None:
                continue

            if name_lower not in self._templates:
                self._templates[name_lower] = []
            self._templates[name_lower].append(tpl)
            loaded += 1

        self.templates_loaded = loaded
        if loaded > 0:
            names = list(self._templates.keys())
            self._log(
                f"[CorpseDetect] {loaded} sprites de cadáveres cargados: "
                f"{names}"
            )
        return loaded

    def get_loaded_names(self) -> List[str]:
        """Retorna nombres de criaturas con sprites de cadáver cargados."""
        return list(self._templates.keys())

    def has_template(self, monster_name: str) -> bool:
        """Verifica si hay template de cadáver para un monstruo."""
        return monster_name.lower() in self._templates

    # ══════════════════════════════════════════
    # Detección principal
    # ══════════════════════════════════════════

    def find_corpses(
        self,
        frame: np.ndarray,
        monster_name: str,
        max_results: int = 5,
    ) -> List[Tuple[int, int, float]]:
        """
        Busca cadáveres del monstruo en el game screen.

        Args:
            frame: Frame OBS completo (BGR).
            monster_name: Nombre del monstruo (case-insensitive).
            max_results: Máximo de cadáveres a encontrar.

        Returns:
            Lista de (x, y, confidence) en coords OBS, ordenados por
            distancia al player (más cercano primero).
        """
        self.searches += 1
        name_lower = monster_name.lower()

        templates = self._templates.get(name_lower, [])
        if not templates:
            # Intentar sin espacios: "Cave Rat" → "caverat"
            name_nospace = name_lower.replace(" ", "")
            templates = self._templates.get(name_nospace, [])
            if not templates:
                return []

        if frame is None or frame.size == 0:
            return []

        # Extraer ROI del game screen (zona de búsqueda)
        roi, offset_x, offset_y = self._extract_search_roi(frame)
        if roi is None or roi.size == 0:
            return []

        # Convertir a gris
        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Buscar con TODOS los templates (variantes) del monstruo
        all_matches: List[Tuple[int, int, float]] = []

        for tpl in templates:
            th, tw = tpl.shape[:2]

            # Verificar que el template cabe en el ROI
            if roi_gray.shape[0] < th or roi_gray.shape[1] < tw:
                continue

            # Template matching
            res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)

            # Encontrar TODOS los matches por encima del umbral
            locations = np.where(res >= self._precision)

            for pt in zip(*locations[::-1]):
                x_obs = pt[0] + tw // 2 + offset_x
                y_obs = pt[1] + th // 2 + offset_y
                # Obtener confianza exacta de este punto
                conf = float(res[pt[1], pt[0]])

                # Verificar que no sea duplicado (otro match muy cercano)
                is_dup = False
                for mx, my, mc in all_matches:
                    if (abs(x_obs - mx) < self._min_match_distance and
                            abs(y_obs - my) < self._min_match_distance):
                        # Mantener el de mayor confianza
                        if conf > mc:
                            all_matches.remove((mx, my, mc))
                        else:
                            is_dup = True
                        break

                if not is_dup:
                    all_matches.append((x_obs, y_obs, conf))

        if not all_matches:
            return []

        # Ordenar por distancia al player (más cercano primero)
        px, py = self._player_center
        if px > 0 and py > 0:
            all_matches.sort(
                key=lambda m: (m[0] - px) ** 2 + (m[1] - py) ** 2
            )
        else:
            # Si no hay player center, ordenar por confianza
            all_matches.sort(key=lambda m: m[2], reverse=True)

        # Limitar resultados
        results = all_matches[:max_results]

        self.detections += len(results)
        for rx, ry, rc in results:
            self._log(
                f"[CorpseDetect] Cadáver de {monster_name} en "
                f"OBS({rx},{ry}) conf={rc:.3f}"
            )

        return results

    def find_any_corpse(
        self,
        frame: np.ndarray,
        max_results: int = 5,
    ) -> List[Tuple[int, int, float, str]]:
        """
        Busca cadáveres de CUALQUIER monstruo con template cargado.

        Returns:
            Lista de (x, y, confidence, monster_name) en coords OBS.
        """
        all_results: List[Tuple[int, int, float, str]] = []

        for name in self._templates:
            matches = self.find_corpses(frame, name, max_results=3)
            for x, y, conf in matches:
                all_results.append((x, y, conf, name))

        # Ordenar por distancia al player
        px, py = self._player_center
        if px > 0 and py > 0:
            all_results.sort(
                key=lambda m: (m[0] - px) ** 2 + (m[1] - py) ** 2
            )

        return all_results[:max_results]

    # ══════════════════════════════════════════
    # ROI extraction
    # ══════════════════════════════════════════

    def _extract_search_roi(
        self,
        frame: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], int, int]:
        """
        Extrae la región de búsqueda del game screen.
        Si hay game_region calibrado, usa eso.
        Si hay player_center + sqm_size, limita el radio de búsqueda.
        """
        h, w = frame.shape[:2]

        if self._game_region:
            gx1, gy1, gx2, gy2 = self._game_region
            gx1 = max(0, gx1)
            gy1 = max(0, gy1)
            gx2 = min(w, gx2)
            gy2 = min(h, gy2)

            # Si tenemos player center y sqm_size, limitar radio
            px, py = self._player_center
            sw, sh = self._sqm_size
            if px > 0 and sw > 0:
                radius = self._search_radius_sqms
                sx1 = max(gx1, px - radius * sw)
                sy1 = max(gy1, py - radius * sh)
                sx2 = min(gx2, px + radius * sw)
                sy2 = min(gy2, py + radius * sh)
                return frame[sy1:sy2, sx1:sx2], sx1, sy1

            return frame[gy1:gy2, gx1:gx2], gx1, gy1

        # Sin game region — usar frame completo (menos eficiente)
        return frame, 0, 0

    # ══════════════════════════════════════════
    # Captura de sprites (para GUI)
    # ══════════════════════════════════════════

    @staticmethod
    def capture_sprite_from_frame(
        frame: np.ndarray,
        x: int,
        y: int,
        size: int = 32,
    ) -> Optional[np.ndarray]:
        """
        Captura un sprite de cadáver centrado en (x, y) del frame.

        Args:
            frame: Frame OBS completo (BGR).
            x, y: Centro del sprite en coords del frame.
            size: Tamaño del recorte (32x32 por defecto).

        Returns:
            Imagen recortada (BGR) o None.
        """
        if frame is None:
            return None
        fh, fw = frame.shape[:2]
        half = size // 2
        x1 = max(0, x - half)
        y1 = max(0, y - half)
        x2 = min(fw, x + half)
        y2 = min(fh, y + half)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2].copy()

    @staticmethod
    def save_corpse_sprite(
        sprite: np.ndarray,
        creature_name: str,
        variant: int = 0,
    ) -> str:
        """
        Guarda un sprite de cadáver en images/Looter/Corpses/.

        Args:
            sprite: Imagen del sprite (BGR).
            creature_name: Nombre de la criatura.
            variant: Número de variante (0 = principal, 1+ = alternativa).

        Returns:
            Ruta del archivo guardado.
        """
        os.makedirs(CORPSE_SPRITES_DIR, exist_ok=True)
        clean_name = creature_name.replace(" ", "")
        if variant > 0:
            filename = f"{clean_name}_{variant + 1}.png"
        else:
            filename = f"{clean_name}.png"
        path = os.path.join(CORPSE_SPRITES_DIR, filename)
        cv2.imwrite(path, sprite)
        return path

    @staticmethod
    def get_next_variant_number(creature_name: str) -> int:
        """Retorna el próximo número de variante disponible."""
        clean_name = creature_name.replace(" ", "").lower()
        if not os.path.isdir(CORPSE_SPRITES_DIR):
            return 0
        existing = 0
        for fname in os.listdir(CORPSE_SPRITES_DIR):
            base = fname.lower().replace(".png", "")
            if base == clean_name or base.startswith(clean_name + "_"):
                existing += 1
        return existing

    # ══════════════════════════════════════════
    # Estado
    # ══════════════════════════════════════════

    def get_status(self) -> Dict:
        return {
            "templates_loaded": self.templates_loaded,
            "creature_names": list(self._templates.keys()),
            "detections": self.detections,
            "searches": self.searches,
            "precision": self._precision,
            "game_region": self._game_region,
            "player_center": self._player_center,
        }

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(msg)
