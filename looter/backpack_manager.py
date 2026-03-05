"""
looter/backpack_manager.py - Gestor de mochilas (backpacks).
Detecta backpacks abiertos, estado de llenado,
y gestiona la apertura de nuevas mochilas.
"""

import time
import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple


class BackpackSlot:
    """Representa un slot dentro de un backpack."""

    def __init__(
        self,
        index: int = 0,
        screen_x: int = 0,
        screen_y: int = 0,
        is_empty: bool = True,
    ):
        self.index = index
        self.screen_x = screen_x
        self.screen_y = screen_y
        self.is_empty = is_empty

    @property
    def center(self) -> Tuple[int, int]:
        return (self.screen_x, self.screen_y)


class Backpack:
    """Representa un backpack abierto en la UI."""

    def __init__(
        self,
        index: int = 0,
        name: str = "",
        region: Optional[Tuple[int, int, int, int]] = None,
    ):
        self.index = index
        self.name = name
        self.region = region    # (x, y, w, h) en pantalla
        self.slots: List[BackpackSlot] = []
        self.total_slots: int = 20  # Backpack estándar
        self.is_open: bool = True

    @property
    def free_slots(self) -> int:
        return sum(1 for s in self.slots if s.is_empty)

    @property
    def used_slots(self) -> int:
        return sum(1 for s in self.slots if not s.is_empty)

    @property
    def is_full(self) -> bool:
        if not self.slots:
            return False
        return all(not s.is_empty for s in self.slots)

    def get_first_empty_slot(self) -> Optional[BackpackSlot]:
        for s in self.slots:
            if s.is_empty:
                return s
        return None

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "name": self.name,
            "total_slots": self.total_slots,
            "free_slots": self.free_slots,
            "used_slots": self.used_slots,
            "is_full": self.is_full,
            "is_open": self.is_open,
        }


class BackpackManager:
    """
    Gestiona los backpacks del inventario.
    Detecta backpacks abiertos, slots vacíos/ocupados,
    y coordina la apertura de nuevas mochilas.
    """

    # Tamaño de un slot de inventario en Tibia (pixels)
    SLOT_SIZE = 32
    SLOTS_PER_ROW = 4
    HEADER_HEIGHT = 20   # Altura del header del backpack

    # Colores para detección
    SLOT_EMPTY_COLOR_HSV = {
        "lower": np.array([0, 0, 30]),
        "upper": np.array([180, 40, 80]),
    }

    def __init__(self):
        # Lista de backpacks detectados
        self.backpacks: List[Backpack] = []

        # Región del panel de inventario
        self.inventory_region: Optional[Tuple[int, int, int, int]] = None

        # Configuración
        self.max_backpacks: int = 4
        self.auto_open_next: bool = True

        # Callbacks
        self._on_open_backpack = None   # callback(hwnd, x, y) - double click
        self._on_drag_item = None       # callback(hwnd, from_x, from_y, to_x, to_y)

        self.hwnd: int = 0

    def set_inventory_region(self, x: int, y: int, w: int, h: int) -> None:
        """Configura la región del panel de inventario."""
        self.inventory_region = (x, y, w, h)

    def set_open_callback(self, callback) -> None:
        """callback(hwnd, x, y) para abrir backpack (double click)."""
        self._on_open_backpack = callback

    def set_drag_callback(self, callback) -> None:
        """callback(hwnd, from_x, from_y, to_x, to_y) para drag&drop."""
        self._on_drag_item = callback

    def set_hwnd(self, hwnd: int) -> None:
        self.hwnd = hwnd

    # ==================================================================
    # Detección de backpacks
    # ==================================================================
    def scan_backpacks(self, frame: np.ndarray) -> List[Backpack]:
        """
        Escanea el frame para detectar backpacks abiertos
        y sus slots.
        """
        if self.inventory_region is None or frame is None:
            return self.backpacks

        ix, iy, iw, ih = self.inventory_region
        roi = frame[iy:iy + ih, ix:ix + iw]
        if roi.size == 0:
            return self.backpacks

        # Detectar headers de backpacks (barras con título)
        backpack_headers = self._detect_backpack_headers(roi)

        self.backpacks.clear()
        for i, (hx, hy, hw, hh) in enumerate(backpack_headers):
            if i >= self.max_backpacks:
                break

            bp = Backpack(index=i, region=(ix + hx, iy + hy, hw, 0))

            # Detectar slots debajo del header
            slots_y = hy + hh
            slots = self._detect_slots(roi, hx, slots_y, hw)
            bp.slots = slots
            bp.total_slots = max(len(slots), 20)

            # Actualizar altura de la región
            if slots:
                last_slot = max(slots, key=lambda s: s.screen_y)
                bp_height = (last_slot.screen_y - iy - hy) + self.SLOT_SIZE
                bp.region = (ix + hx, iy + hy, hw, bp_height)

            self.backpacks.append(bp)

        return self.backpacks

    def _detect_backpack_headers(
        self, roi: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detecta headers de backpacks en el panel de inventario.
        Los headers son barras horizontales oscuras con texto.
        """
        headers = []
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Buscar líneas horizontales oscuras (headers de backpack)
        # Los headers de Tibia son barras oscuras de ~20px de alto
        for y in range(0, h - self.HEADER_HEIGHT, 5):
            row = gray[y:y + self.HEADER_HEIGHT, :]
            mean_val = np.mean(row)
            # Headers son oscuros (40-80 de luminosidad)
            if 30 < mean_val < 90:
                # Verificar que es un rectángulo continuo
                dark_mask = row < 100
                dark_ratio = np.count_nonzero(dark_mask) / max(dark_mask.size, 1)
                if dark_ratio > 0.6:
                    # Verificar que no está muy cerca de otro header
                    too_close = False
                    for _, hy, _, _ in headers:
                        if abs(y - hy) < 40:
                            too_close = True
                            break
                    if not too_close:
                        headers.append((0, y, w, self.HEADER_HEIGHT))

        return headers

    def _detect_slots(
        self, roi: np.ndarray, start_x: int, start_y: int, width: int
    ) -> List[BackpackSlot]:
        """Detecta slots dentro de un backpack."""
        slots = []
        h, w = roi.shape[:2]
        ss = self.SLOT_SIZE
        cols = self.SLOTS_PER_ROW
        rows = 5  # Backpack estándar tiene 5 filas × 4 columnas

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        for row in range(rows):
            for col in range(cols):
                sx = start_x + col * ss
                sy = start_y + row * ss

                if sy + ss > h or sx + ss > w:
                    continue

                slot_region = hsv[sy:sy + ss, sx:sx + ss]
                if slot_region.size == 0:
                    continue

                # Determinar si el slot está vacío
                is_empty = self._is_slot_empty(slot_region)

                slot = BackpackSlot(
                    index=row * cols + col,
                    screen_x=sx + ss // 2,
                    screen_y=sy + ss // 2,
                    is_empty=is_empty,
                )
                slots.append(slot)

        return slots

    def _is_slot_empty(self, slot_hsv: np.ndarray) -> bool:
        """Determina si un slot de backpack está vacío."""
        # Un slot vacío es predominantemente gris oscuro uniforme
        mask = cv2.inRange(
            slot_hsv,
            self.SLOT_EMPTY_COLOR_HSV["lower"],
            self.SLOT_EMPTY_COLOR_HSV["upper"],
        )
        ratio = np.count_nonzero(mask) / max(mask.size, 1)
        return ratio > 0.7

    # ==================================================================
    # Gestión de slots
    # ==================================================================
    def get_main_backpack(self) -> Optional[Backpack]:
        """Retorna el backpack principal (índice 0)."""
        if self.backpacks:
            return self.backpacks[0]
        return None

    def get_backpack(self, index: int) -> Optional[Backpack]:
        """Retorna un backpack por índice."""
        for bp in self.backpacks:
            if bp.index == index:
                return bp
        return None

    def find_empty_slot(self, backpack_index: int = 0) -> Optional[BackpackSlot]:
        """Busca un slot vacío en el backpack especificado."""
        bp = self.get_backpack(backpack_index)
        if bp:
            return bp.get_first_empty_slot()
        return None

    def find_any_empty_slot(self) -> Optional[Tuple[int, BackpackSlot]]:
        """Busca un slot vacío en cualquier backpack abierto."""
        for bp in self.backpacks:
            slot = bp.get_first_empty_slot()
            if slot:
                return (bp.index, slot)
        return None

    def is_any_backpack_full(self) -> bool:
        """¿Algún backpack está lleno?"""
        return any(bp.is_full for bp in self.backpacks)

    def are_all_backpacks_full(self) -> bool:
        """¿Todos los backpacks están llenos?"""
        if not self.backpacks:
            return False
        return all(bp.is_full for bp in self.backpacks)

    def get_total_free_slots(self) -> int:
        """Cuenta total de slots vacíos en todos los backpacks."""
        return sum(bp.free_slots for bp in self.backpacks)

    # ==================================================================
    # Acciones
    # ==================================================================
    def open_next_backpack(self) -> bool:
        """
        Intenta abrir el siguiente backpack dentro del actual.
        Busca un slot con un backpack y hace double click.
        """
        if not self._on_open_backpack or self.hwnd == 0:
            return False

        # El último slot del backpack actual debería ser otro backpack
        main = self.get_main_backpack()
        if not main or not main.slots:
            return False

        # El último slot no vacío podría ser un backpack
        non_empty = [s for s in main.slots if not s.is_empty]
        if not non_empty:
            return False

        last_slot = non_empty[-1]
        self._on_open_backpack(self.hwnd, last_slot.screen_x, last_slot.screen_y)
        return True

    # ==================================================================
    # Info
    # ==================================================================
    def get_status(self) -> Dict:
        return {
            "backpack_count": len(self.backpacks),
            "total_free_slots": self.get_total_free_slots(),
            "all_full": self.are_all_backpacks_full(),
            "backpacks": [bp.to_dict() for bp in self.backpacks],
        }

    def __repr__(self) -> str:
        free = self.get_total_free_slots()
        return f"<BackpackManager bps={len(self.backpacks)} free={free}>"
