"""
targeting/battle_list_reader.py - Lector de la battle list de Tibia v2.
Usa template matching (OpenCV) para detectar nombres de monstruos.
Mejoras v2:
  - is_attacking() ahora retorna True cuando SÍ estamos atacando (corregido)
  - count_monsters_by_name() para kill detection por nombre
  - Deduplicación mejorada de resultados
  - Mejor logging de estado
Basado en TibiaAuto12/engine/CaveBot/Scanners.py.
"""

import os
import time
import cv2
import numpy as np
from typing import Callable, Dict, List, Optional, Set, Tuple
from enum import Enum

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
NAMES_DIR = os.path.join(IMAGES_DIR, "Targets", "Names")
ATTACK_DIR = os.path.join(IMAGES_DIR, "MonstersAttack")


class CreatureType(Enum):
    MONSTER = "monster"
    PLAYER = "player"
    NPC = "npc"
    UNKNOWN = "unknown"


class CreatureEntry:
    """Criatura encontrada en la battle list."""
    def __init__(self, name="", creature_type=CreatureType.UNKNOWN,
                 screen_x=0, screen_y=0, position_index=0):
        self.name = name
        self.creature_type = creature_type
        self.screen_x = screen_x
        self.screen_y = screen_y
        self.position_index = position_index

    def to_dict(self):
        return {"name": self.name, "type": self.creature_type.value,
                "screen_x": self.screen_x, "screen_y": self.screen_y}

    def __repr__(self):
        return f"<Creature '{self.name}' at ({self.screen_x},{self.screen_y})>"


class BattleListReader:
    """
    Lector basado en template matching.
    Busca PNGs de nombres de monstruos en la región de la battle list.
    v3.1: is_attacking() con fallback por tiempo + logging de confianza.
    """

    def __init__(self):
        self.battle_region: Optional[Tuple[int, int, int, int]] = None
        self._name_templates: Dict[str, np.ndarray] = {}
        self._attack_templates: Dict[str, np.ndarray] = {}
        self.attack_list: Set[str] = set()
        self.ignore_list: Set[str] = set()
        self.priority_list: Set[str] = set()
        self._creatures: List[CreatureEntry] = []
        self._monster_count: int = 0
        self._is_attacking: bool = False
        self.name_precision: float = 0.35  # Umbral optimizado para detectar nombres con variaciones
        self.attack_precision: float = 0.65  # Bajado para detectar bordes de ataque más fácilmente

        # --- Fallback temporal para is_attacking ---
        # Si hicimos click en un target hace < N segundos Y ese target
        # sigue en la battle list → asumir que estamos atacando
        self._last_attack_click_time: float = 0.0
        self._last_attack_click_name: str = ""
        self._attack_click_timeout: float = 30.0  # Cubrir todo el combate hasta que muera

        # Logging
        self._log_fn: Optional[Callable] = None
        self._attack_log_counter: int = 0  # Solo loguear cada N calls

        self._load_attack_templates()

    def set_log_callback(self, fn):
        """fn(msg) para diagnóstico."""
        self._log_fn = fn

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(msg)

    def notify_attack_click(self, target_name: str):
        """Llamado por TargetingEngine cuando hace click en un target."""
        self._last_attack_click_time = time.time()
        self._last_attack_click_name = target_name.lower()

    def _load_attack_templates(self):
        """Carga templates de bordes de ataque (rojo/rosa para detectar si estamos atacando)."""
        if not os.path.isdir(ATTACK_DIR):
            return
        for fname in os.listdir(ATTACK_DIR):
            if fname.endswith(".png") and fname != "VerifyAttacking.png":
                key = fname.replace(".png", "")
                tpl = cv2.imread(os.path.join(ATTACK_DIR, fname), cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._attack_templates[key] = tpl

    def load_monster_templates(self, monster_names: List[str]) -> int:
        """Carga templates PNG para los monstruos especificados."""
        loaded = 0
        for name in monster_names:
            filename = name.replace(" ", "")
            path = os.path.join(NAMES_DIR, f"{filename}.png")
            if os.path.exists(path):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._name_templates[name] = tpl
                    loaded += 1
        return loaded

    def load_all_available_templates(self) -> int:
        """Carga todos los templates PNG disponibles en el directorio."""
        if not os.path.isdir(NAMES_DIR):
            return 0
        loaded = 0
        for fname in os.listdir(NAMES_DIR):
            if fname.endswith(".png"):
                raw = fname.replace(".png", "")
                display = ""
                for i, ch in enumerate(raw):
                    if ch.isupper() and i > 0 and raw[i-1].islower():
                        display += " "
                    display += ch
                tpl = cv2.imread(os.path.join(NAMES_DIR, fname), cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._name_templates[display] = tpl
                    loaded += 1
        return loaded

    def get_loaded_monster_names(self) -> List[str]:
        return list(self._name_templates.keys())

    def set_region(self, x1, y1, x2, y2):
        self.battle_region = (x1, y1, x2, y2)

    # ==================================================================
    # Lectura de battle list
    # ==================================================================
    def read(self, frame: np.ndarray) -> List[CreatureEntry]:
        """Lee la battle list. Retorna criaturas encontradas ordenadas por Y."""
        if self.battle_region is None or frame is None or not self._name_templates:
            return []

        x1, y1, x2, y2 = self.battle_region
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return []

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        creatures = []
        idx = 0

        # Filtrar templates según attack_list
        templates = {}
        if self.attack_list:
            for name in self.attack_list:
                if name in self._name_templates:
                    templates[name] = self._name_templates[name]
        else:
            templates = self._name_templates

        for monster_name, template in templates.items():
            if monster_name.lower() in {n.lower() for n in self.ignore_list}:
                continue
            if roi_gray.shape[0] < template.shape[0] or roi_gray.shape[1] < template.shape[1]:
                continue

            res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(res >= self.name_precision)
            th, tw = template.shape[:2]

            for pt in zip(*locations[::-1]):
                cx, cy = pt[0] + tw // 2, pt[1] + th // 2
                # Deduplicar: no agregar si ya hay una criatura muy cerca
                is_dup = False
                for e in creatures:
                    if abs((e.screen_x - x1) - cx) < tw and abs((e.screen_y - y1) - cy) < th:
                        is_dup = True
                        break
                if is_dup:
                    continue

                creatures.append(CreatureEntry(
                    name=monster_name, creature_type=CreatureType.MONSTER,
                    screen_x=x1 + cx, screen_y=y1 + cy, position_index=idx,
                ))
                idx += 1

        # Ordenar por Y (más arriba = más cercano en Tibia)
        creatures.sort(key=lambda c: c.screen_y)
        self._creatures = creatures
        self._monster_count = len(creatures)
        return creatures

    def count_monsters_by_name(self, frame: np.ndarray) -> Dict[str, int]:
        """
        Cuenta criaturas POR NOMBRE en la battle list.
        Retorna dict {nombre: cantidad} para kill detection precisa.
        """
        creatures = self.read(frame)
        counts: Dict[str, int] = {}
        for c in creatures:
            name = c.name.lower()
            counts[name] = counts.get(name, 0) + 1
        return counts

    def count_monster(self, frame: np.ndarray, monster_name: str) -> int:
        """Cuenta instancias de un monstruo específico en la battle list."""
        if self.battle_region is None or frame is None:
            return 0
        template = self._name_templates.get(monster_name)
        if template is None:
            return 0

        x1, y1, x2, y2 = self.battle_region
        h, w = frame.shape[:2]
        roi = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if roi.size == 0:
            return 0

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if roi_gray.shape[0] < template.shape[0] or roi_gray.shape[1] < template.shape[1]:
            return 0

        res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
        locs = np.where(res >= self.name_precision)
        th, tw = template.shape[:2]
        pts = []
        for pt in zip(*locs[::-1]):
            if not any(abs(pt[0] - ex) < tw and abs(pt[1] - ey) < th for ex, ey in pts):
                pts.append(pt)
        return len(pts)

    # ==================================================================
    # Detección de estado de ataque
    # ==================================================================
    def is_attacking(self, frame: np.ndarray) -> bool:
        """
        CORREGIDO v3.1: Retorna True si YA estamos atacando algo.
        Retorna False si NO estamos atacando (necesitamos hacer click).

        Detecta el borde rojo/rosa alrededor de la criatura atacada en battle list.
        FALLBACK: Si hicimos click en un target hace < 3s Y ese target sigue en la
        battle list, asumimos que estamos atacando (para evitar re-click spam).
        """
        if self.battle_region is None or frame is None:
            return False

        # --- Intento 1: Template matching de bordes de ataque ---
        template_attacking = self._check_attack_borders(frame)

        if template_attacking:
            self._is_attacking = True
            return True

        # --- Intento 2: Fallback temporal ---
        # Si hicimos click en un target recientemente Y ese target sigue en la battle list
        now = time.time()
        time_since_click = now - self._last_attack_click_time
        if (time_since_click < self._attack_click_timeout
                and self._last_attack_click_name):
            # Verificar que el target sigue en la battle list
            target_still_there = any(
                c.name.lower() == self._last_attack_click_name
                for c in self._creatures
            )
            if target_still_there:
                self._is_attacking = True
                # Log solo cada ~20 calls para no spamear
                self._attack_log_counter += 1
                if self._attack_log_counter % 20 == 1:
                    self._log(
                        f"[BattleReader] is_attacking=True (fallback temporal: "
                        f"'{self._last_attack_click_name}' clickeado hace {time_since_click:.1f}s)"
                    )
                return True

        self._is_attacking = False
        return False

    def _check_attack_borders(self, frame: np.ndarray) -> bool:
        """
        Verifica si hay bordes de ataque (rojo/rosa) en la battle list.
        Retorna True si se detecta un set completo de 4 bordes.
        """
        if not self._attack_templates:
            return False

        x1, y1, x2, y2 = self.battle_region
        h, w = frame.shape[:2]
        roi = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if roi.size == 0:
            return False

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        found = {}
        best_conf = 0.0

        # Umbral más alto para templates pequeños (2-4px) para evitar falsos positivos
        # Los bordes de 2-4px dan match fácilmente con cualquier borde de UI
        SMALL_THRESHOLD = 0.92  # Muy estricto para templates micro (<8px)
        NORMAL_THRESHOLD = self.attack_precision

        for key, tpl in self._attack_templates.items():
            if roi_gray.shape[0] < tpl.shape[0] or roi_gray.shape[1] < tpl.shape[1]:
                continue
            res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            # Templates muy pequeños (bordes de 2-4px) requieren threshold más alto
            min_dim = min(tpl.shape[0], tpl.shape[1])
            threshold = SMALL_THRESHOLD if min_dim < 8 else NORMAL_THRESHOLD
            found[key] = max_val >= threshold
            best_conf = max(best_conf, max_val)

        # Requiere los 4 bordes de un mismo set para confirmar ataque (antes era 2/4)
        # Esto evita falsos positivos por bordes de la UI del cliente
        border_sets = [
            ("LeftRed", "TopRed", "RightRed", "BottomRed"),
            ("LeftBlackRed", "TopBlackRed", "RightBlackRed", "BottomBlackRed"),
            ("LeftPink", "TopPink", "RightPink", "BottomPink"),
            ("LeftBlackPink", "TopBlackPink", "RightBlackPink", "BottomBlackPink"),
        ]
        for borders in border_sets:
            matches = sum(1 for b in borders if found.get(b, False))
            if matches >= 4:  # TODOS los 4 bordes del set deben coincidir
                return True

        # Log diagnóstico cada ~50 calls
        self._attack_log_counter += 1
        if self._attack_log_counter % 50 == 1 and self._attack_templates:
            matched = [k for k, v in found.items() if v]
            self._log(
                f"[BattleReader] Bordes de ataque: best_conf={best_conf:.3f}, "
                f"matched={matched or 'ninguno'} (threshold_small={SMALL_THRESHOLD}, threshold_normal={NORMAL_THRESHOLD})"
            )

        return False
    def find_target(self, frame: np.ndarray, monster_name: str) -> Tuple[int, int]:
        """Busca un monstruo y retorna posición absoluta para click. (0,0) si no hay."""
        if self.battle_region is None or frame is None:
            return 0, 0
        template = self._name_templates.get(monster_name)
        if template is None:
            return 0, 0

        x1, y1, x2, y2 = self.battle_region
        h, w = frame.shape[:2]
        roi = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if roi.size == 0:
            return 0, 0

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if roi_gray.shape[0] < template.shape[0] or roi_gray.shape[1] < template.shape[1]:
            return 0, 0

        res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= self.name_precision:
            th, tw = template.shape[:2]
            return x1 + max_loc[0] + tw // 2 - 10, y1 + max_loc[1] + th // 2
        return 0, 0

    # ==================================================================
    # Propiedades y helpers
    # ==================================================================
    @property
    def creatures(self):
        return self._creatures

    @property
    def creature_count(self):
        return self._monster_count

    @property
    def currently_attacking(self):
        return self._is_attacking

    def has_monsters(self):
        return self._monster_count > 0

    def get_attackable_monsters(self):
        if self.attack_list:
            return [c for c in self._creatures if c.name.lower() in {n.lower() for n in self.attack_list}]
        return [c for c in self._creatures if c.name.lower() not in {n.lower() for n in self.ignore_list}]

    def get_priority_targets(self):
        return [c for c in self._creatures if c.name.lower() in {n.lower() for n in self.priority_list}]
