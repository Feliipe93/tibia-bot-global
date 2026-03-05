"""
targeting/battle_list_reader.py - Lector de la battle list de Tibia.
Usa template matching (OpenCV) para detectar nombres de monstruos.
Basado en TibiaAuto12/engine/CaveBot/Scanners.py.
"""

import os
import cv2
import numpy as np
from typing import Dict, List, Optional, Set, Tuple
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
        self.name_precision: float = 0.80
        self.attack_precision: float = 0.80
        self._load_attack_templates()

    def _load_attack_templates(self):
        if not os.path.isdir(ATTACK_DIR):
            return
        for fname in os.listdir(ATTACK_DIR):
            if fname.endswith(".png") and fname != "VerifyAttacking.png":
                key = fname.replace(".png", "")
                tpl = cv2.imread(os.path.join(ATTACK_DIR, fname), cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._attack_templates[key] = tpl

    def load_monster_templates(self, monster_names: List[str]) -> int:
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

    def read(self, frame: np.ndarray) -> List[CreatureEntry]:
        """Lee la battle list. Retorna criaturas encontradas."""
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

        creatures.sort(key=lambda c: c.screen_y)
        self._creatures = creatures
        self._monster_count = len(creatures)
        return creatures

    def count_monster(self, frame: np.ndarray, monster_name: str) -> int:
        """Cuenta instancias de un monstruo en la battle list."""
        if self.battle_region is None or frame is None:
            return 0
        template = self._name_templates.get(monster_name)
        if template is None:
            return 0

        x1, y1, x2, y2 = self.battle_region
        h, w = frame.shape[:2]
        roi = frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]
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
            if not any(abs(pt[0]-ex)<tw and abs(pt[1]-ey)<th for ex,ey in pts):
                pts.append(pt)
        return len(pts)

    def is_attacking(self, frame: np.ndarray) -> bool:
        """
        True = NO estamos atacando (necesitamos hacer click).
        False = YA estamos atacando (hay selección activa).
        """
        if self.battle_region is None or frame is None or not self._attack_templates:
            return True

        x1, y1, x2, y2 = self.battle_region
        h, w = frame.shape[:2]
        roi = frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]
        if roi.size == 0:
            return True

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        found = {}
        for key, tpl in self._attack_templates.items():
            if roi_gray.shape[0] < tpl.shape[0] or roi_gray.shape[1] < tpl.shape[1]:
                continue
            res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            found[key] = max_val >= self.attack_precision

        border_sets = [
            ("LeftRed", "TopRed", "RightRed", "BottomRed"),
            ("LeftBlackRed", "TopBlackRed", "RightBlackRed", "BottomBlackRed"),
            ("LeftPink", "TopPink", "RightPink", "BottomPink"),
            ("LeftBlackPink", "TopBlackPink", "RightBlackPink", "BottomBlackPink"),
        ]
        for borders in border_sets:
            if all(found.get(b, False) for b in borders):
                self._is_attacking = True
                return False

        self._is_attacking = False
        return True

    def find_target(self, frame: np.ndarray, monster_name: str) -> Tuple[int, int]:
        """Busca un monstruo y retorna posición absoluta para click. (0,0) si no hay."""
        if self.battle_region is None or frame is None:
            return 0, 0
        template = self._name_templates.get(monster_name)
        if template is None:
            return 0, 0

        x1, y1, x2, y2 = self.battle_region
        h, w = frame.shape[:2]
        roi = frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]
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
