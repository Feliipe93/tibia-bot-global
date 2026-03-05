"""
targeting/battle_list_reader.py - Lector de la battle list de Tibia.
Lee los nombres y estados de los monstruos/jugadores de la battle list
usando análisis de píxeles y OCR.
"""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple
from enum import Enum


class CreatureType(Enum):
    """Tipo de criatura en la battle list."""
    MONSTER = "monster"
    PLAYER = "player"
    NPC = "npc"
    UNKNOWN = "unknown"


class CreatureEntry:
    """Representa una entrada en la battle list."""

    def __init__(
        self,
        name: str = "",
        creature_type: CreatureType = CreatureType.UNKNOWN,
        hp_percent: int = 100,
        is_attacking: bool = False,
        is_following: bool = False,
        position_index: int = 0,
        skull: str = "",
    ):
        self.name = name
        self.creature_type = creature_type
        self.hp_percent = hp_percent
        self.is_attacking = is_attacking
        self.is_following = is_following
        self.position_index = position_index
        self.skull = skull

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.creature_type.value,
            "hp_percent": self.hp_percent,
            "is_attacking": self.is_attacking,
            "is_following": self.is_following,
            "position_index": self.position_index,
            "skull": self.skull,
        }

    def __repr__(self) -> str:
        atk = " [ATK]" if self.is_attacking else ""
        return f"<Creature '{self.name}' HP={self.hp_percent}%{atk}>"


class BattleListReader:
    """
    Lee la battle list de Tibia desde un frame de OBS.
    Detecta criaturas por análisis de píxeles:
    - HP bars (verde a rojo)
    - Texto blanco (nombres de criaturas)
    - Iconos de ataque/seguimiento
    """

    # Colores de referencia para la battle list (BGR)
    COLORS = {
        # HP bar colores
        "hp_full": (0, 200, 0),       # Verde = 100%
        "hp_high": (0, 220, 220),     # Amarillo = ~75%
        "hp_medium": (0, 165, 255),   # Naranja = ~50%
        "hp_low": (0, 0, 255),        # Rojo = ~25%
        # Fondo de la battle list
        "bg_dark": (30, 30, 30),
        "bg_selected": (80, 60, 40),  # Azul oscuro seleccionado
        # Texto
        "text_white": (255, 255, 255),
        "text_monster": (200, 200, 200),
        "text_player": (200, 200, 255),
    }

    # Dimensiones típicas de una entrada en la battle list
    ENTRY_HEIGHT = 22       # Altura de cada entrada en px
    HP_BAR_HEIGHT = 3       # Altura de la barra de HP
    HP_BAR_OFFSET_Y = 17   # Offset Y de la barra de HP desde inicio de entrada
    NAME_OFFSET_Y = 2       # Offset Y del nombre
    ICON_WIDTH = 12          # Ancho del icono (skull, etc)

    def __init__(self):
        # Región de la battle list dentro del frame (x, y, w, h)
        self.battle_list_region: Optional[Tuple[int, int, int, int]] = None

        # Cache de criaturas detectadas
        self._creatures: List[CreatureEntry] = []

        # Configuración
        self.max_entries: int = 10
        self.min_hp_bar_width: int = 20

        # OCR helper (inyectado opcionalmente)
        self._ocr = None

    def set_region(self, x: int, y: int, w: int, h: int) -> None:
        """Configura la región de la battle list."""
        self.battle_list_region = (x, y, w, h)

    def set_ocr(self, ocr_helper) -> None:
        """Inyecta el helper de OCR para lectura de nombres."""
        self._ocr = ocr_helper

    def read(self, frame: np.ndarray) -> List[CreatureEntry]:
        """
        Lee la battle list completa del frame actual.

        Args:
            frame: Frame BGR de OBS.

        Returns:
            Lista de CreatureEntry detectadas.
        """
        if self.battle_list_region is None or frame is None:
            return []

        x, y, w, h = self.battle_list_region
        roi = frame[y:y + h, x:x + w]
        if roi.size == 0:
            return []

        creatures = []

        # Buscar barras de HP horizontales
        hp_bars = self._detect_hp_bars(roi)

        for i, (bar_x, bar_y, bar_w, hp_pct) in enumerate(hp_bars):
            if i >= self.max_entries:
                break

            entry = CreatureEntry(
                position_index=i,
                hp_percent=hp_pct,
            )

            # Intentar leer nombre con OCR
            name_y = max(0, bar_y - self.HP_BAR_OFFSET_Y + self.NAME_OFFSET_Y)
            name_h = self.HP_BAR_OFFSET_Y - self.NAME_OFFSET_Y
            name_roi = roi[name_y:name_y + name_h, bar_x:bar_x + bar_w]

            if self._ocr and name_roi.size > 0:
                text = self._ocr.read_text(name_roi)
                if text:
                    entry.name = text.strip()

            # Detectar si está siendo atacado (borde rojo alrededor)
            entry.is_attacking = self._detect_attacking_indicator(roi, bar_y)

            # Clasificar tipo de criatura por color del nombre
            entry.creature_type = self._classify_creature(roi, bar_x, name_y, bar_w, name_h)

            creatures.append(entry)

        self._creatures = creatures
        return creatures

    def _detect_hp_bars(self, roi: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detecta barras de HP en la battle list.

        Returns:
            Lista de (x, y, width, hp_percent).
        """
        bars = []
        h, w = roi.shape[:2]

        # Crear máscara de colores de HP (verde, amarillo, naranja, rojo)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Rango amplio para barras de HP (de rojo a verde pasando por amarillo)
        # Verde: H=40-80
        mask_green = cv2.inRange(hsv, np.array([35, 100, 100]), np.array([85, 255, 255]))
        # Amarillo: H=20-35
        mask_yellow = cv2.inRange(hsv, np.array([15, 100, 100]), np.array([35, 255, 255]))
        # Rojo: H=0-15 y H=170-180
        mask_red1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([15, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([170, 100, 100]), np.array([180, 255, 255]))

        hp_mask = mask_green | mask_yellow | mask_red1 | mask_red2

        # Buscar contornos horizontales (barras)
        contours, _ = cv2.findContours(hp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)

            # Filtrar: barras de HP son delgadas y horizontales
            if bw < self.min_hp_bar_width or bh > 8 or bh < 2:
                continue

            # Calcular HP % basado en ratio de color
            bar_region = hp_mask[by:by + bh, bx:bx + bw]
            filled_ratio = np.count_nonzero(bar_region) / max(bar_region.size, 1)

            # Estimar HP basado en colores presentes
            hp_pct = self._estimate_hp_from_bar(roi[by:by + bh, bx:bx + bw])

            bars.append((bx, by, bw, hp_pct))

        # Ordenar por Y (de arriba a abajo)
        bars.sort(key=lambda b: b[1])
        return bars

    def _estimate_hp_from_bar(self, bar_roi: np.ndarray) -> int:
        """Estima el % de HP basado en el color predominante de la barra."""
        if bar_roi.size == 0:
            return 0

        hsv = cv2.cvtColor(bar_roi, cv2.COLOR_BGR2HSV)
        h_mean = np.mean(hsv[:, :, 0])

        # Mapear hue a HP%:
        # Verde (H~60) = 100%, Amarillo (H~30) = 60%, Rojo (H~0/180) = ~10%
        if h_mean > 50:
            return 100
        elif h_mean > 35:
            return 75
        elif h_mean > 20:
            return 50
        elif h_mean > 10:
            return 25
        else:
            return 10

    def _detect_attacking_indicator(self, roi: np.ndarray, entry_y: int) -> bool:
        """Detecta si hay indicador de ataque (borde rojo / icono de espada)."""
        # Buscar píxeles rojos intensos en el área de la entrada
        entry_start = max(0, entry_y - self.ENTRY_HEIGHT)
        entry_region = roi[entry_start:entry_y + self.HP_BAR_HEIGHT, :5]

        if entry_region.size == 0:
            return False

        # Buscar rojo brillante (icono de espadas cruzadas)
        hsv = cv2.cvtColor(entry_region, cv2.COLOR_BGR2HSV)
        mask_red = cv2.inRange(hsv, np.array([0, 150, 150]), np.array([10, 255, 255]))
        return np.count_nonzero(mask_red) > 5

    def _classify_creature(
        self, roi: np.ndarray, x: int, y: int, w: int, h: int
    ) -> CreatureType:
        """Clasifica el tipo de criatura basado en el color del texto del nombre."""
        if h <= 0 or w <= 0:
            return CreatureType.UNKNOWN

        name_region = roi[y:y + h, x:x + w]
        if name_region.size == 0:
            return CreatureType.UNKNOWN

        # Analizar color promedio del texto
        # Máscaras para texto blanco/gris
        gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY)
        text_mask = gray > 150

        if np.count_nonzero(text_mask) == 0:
            return CreatureType.UNKNOWN

        # Extraer canal azul del texto
        blue_channel = name_region[:, :, 0]
        red_channel = name_region[:, :, 2]

        text_blue = np.mean(blue_channel[text_mask]) if np.any(text_mask) else 0
        text_red = np.mean(red_channel[text_mask]) if np.any(text_mask) else 0

        # Jugadores suelen tener nombres más azulados
        if text_blue > text_red + 30:
            return CreatureType.PLAYER
        else:
            return CreatureType.MONSTER

    # ==================================================================
    # Acceso a datos
    # ==================================================================
    @property
    def creatures(self) -> List[CreatureEntry]:
        return self._creatures

    @property
    def creature_count(self) -> int:
        return len(self._creatures)

    def get_attacking_target(self) -> Optional[CreatureEntry]:
        """Retorna la criatura que estamos atacando actualmente."""
        for c in self._creatures:
            if c.is_attacking:
                return c
        return None

    def get_monsters(self) -> List[CreatureEntry]:
        """Retorna solo monstruos."""
        return [c for c in self._creatures if c.creature_type == CreatureType.MONSTER]

    def get_players(self) -> List[CreatureEntry]:
        """Retorna solo jugadores."""
        return [c for c in self._creatures if c.creature_type == CreatureType.PLAYER]

    def get_lowest_hp_monster(self) -> Optional[CreatureEntry]:
        """Retorna el monstruo con menor HP."""
        monsters = self.get_monsters()
        if not monsters:
            return None
        return min(monsters, key=lambda c: c.hp_percent)

    def has_monsters(self) -> bool:
        """¿Hay monstruos en la battle list?"""
        return any(c.creature_type == CreatureType.MONSTER for c in self._creatures)

    def has_players(self) -> bool:
        """¿Hay jugadores en la battle list?"""
        return any(c.creature_type == CreatureType.PLAYER for c in self._creatures)
