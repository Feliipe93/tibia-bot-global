"""
looter/looter_engine.py - Motor principal de looteo automático.
Coordina la detección de cadáveres, apertura de cuerpos,
filtrado de items y recogida al backpack.
"""

import time
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from looter.corpse_detector import Corpse, CorpseDetector
from looter.item_filter import ItemFilter
from looter.backpack_manager import BackpackManager


class LootMethod(Enum):
    """Método de looteo."""
    SHIFT_CLICK = "shift_click"     # Shift+Click (quick loot moderno)
    OPEN_BODY = "open_body"          # Abrir cadáver y drag items
    RIGHT_CLICK = "right_click"      # Right-click context menu


class LooterState(Enum):
    """Estado del looter."""
    IDLE = "idle"
    APPROACHING = "approaching"       # Caminando al cadáver
    OPENING_CORPSE = "opening_corpse" # Abriendo el cadáver
    READING_ITEMS = "reading_items"   # Leyendo items del cadáver
    LOOTING = "looting"               # Recogiendo items
    BACKPACK_FULL = "backpack_full"   # Backpack lleno
    PAUSED = "paused"


class LooterEngine:
    """
    Motor de looteo automático.
    Coordina:
    - Detección de cadáveres (CorpseDetector)
    - Filtrado de items (ItemFilter)
    - Gestión de backpacks (BackpackManager)
    - Ejecución de looteo (click/drag)
    """

    def __init__(self):
        self.corpse_detector = CorpseDetector()
        self.item_filter = ItemFilter()
        self.backpack_manager = BackpackManager()

        # Estado
        self.state: LooterState = LooterState.IDLE
        self.current_corpse: Optional[Corpse] = None

        # Configuración
        self.loot_method: LootMethod = LootMethod.SHIFT_CLICK
        self.enabled: bool = True
        self.loot_delay: float = 0.3   # Delay entre acciones de looteo
        self.max_range: int = 2         # Rango máximo para lootear (tiles)

        # Callbacks (inyectados)
        self._on_shift_click: Optional[Callable] = None     # callback(hwnd, x, y)
        self._on_right_click: Optional[Callable] = None     # callback(hwnd, x, y)
        self._on_double_click: Optional[Callable] = None    # callback(hwnd, x, y)
        self._on_drag_item: Optional[Callable] = None       # callback(hwnd, fx, fy, tx, ty)

        self.hwnd: int = 0

        # Timing
        self.last_loot_time: float = 0.0
        self.last_scan_time: float = 0.0
        self.scan_interval: float = 0.5

        # Métricas
        self.items_looted: int = 0
        self.corpses_opened: int = 0
        self.gold_collected: int = 0

    # ==================================================================
    # Configuración / Inyección
    # ==================================================================
    def set_shift_click_callback(self, callback: Callable) -> None:
        self._on_shift_click = callback

    def set_right_click_callback(self, callback: Callable) -> None:
        self._on_right_click = callback

    def set_double_click_callback(self, callback: Callable) -> None:
        self._on_double_click = callback

    def set_drag_callback(self, callback: Callable) -> None:
        self._on_drag_item = callback

    def set_hwnd(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self.backpack_manager.set_hwnd(hwnd)

    def set_game_region(self, x: int, y: int, w: int, h: int) -> None:
        self.corpse_detector.set_game_region(x, y, w, h)

    def set_inventory_region(self, x: int, y: int, w: int, h: int) -> None:
        self.backpack_manager.set_inventory_region(x, y, w, h)

    # ==================================================================
    # Registro de kills (llamado por targeting)
    # ==================================================================
    def register_kill(self, screen_x: int, screen_y: int) -> None:
        """Registra la posición de un monstruo muerto."""
        self.corpse_detector.register_kill(screen_x, screen_y)

    # ==================================================================
    # Lógica principal
    # ==================================================================
    def update(self, frame: np.ndarray) -> None:
        """
        Actualización principal del looter. Llamada cada frame.
        """
        if not self.enabled or self.state == LooterState.PAUSED:
            return

        now = time.time()

        # Escanear backpacks periódicamente
        if now - self.last_scan_time >= self.scan_interval:
            self.backpack_manager.scan_backpacks(frame)
            self.last_scan_time = now

        # ¿Backpacks llenos?
        if self.backpack_manager.are_all_backpacks_full():
            self.state = LooterState.BACKPACK_FULL
            if self.backpack_manager.auto_open_next:
                self.backpack_manager.open_next_backpack()
            return

        # Detectar cadáveres
        corpses = self.corpse_detector.detect(frame)

        # Si no hay cadáveres pendientes, idle
        if not corpses:
            if self.state != LooterState.LOOTING:
                self.state = LooterState.IDLE
            return

        # Obtener siguiente cadáver
        if self.current_corpse is None or self.current_corpse.looted:
            self.current_corpse = self.corpse_detector.get_next_corpse()

        if self.current_corpse is None:
            self.state = LooterState.IDLE
            return

        # Cooldown entre acciones
        if now - self.last_loot_time < self.loot_delay:
            return

        # Ejecutar looteo
        self._execute_loot(self.current_corpse)

    def _execute_loot(self, corpse: Corpse) -> None:
        """Ejecuta el looteo de un cadáver."""
        if self.loot_method == LootMethod.SHIFT_CLICK:
            self._loot_shift_click(corpse)
        elif self.loot_method == LootMethod.OPEN_BODY:
            self._loot_open_body(corpse)
        elif self.loot_method == LootMethod.RIGHT_CLICK:
            self._loot_right_click(corpse)

    def _loot_shift_click(self, corpse: Corpse) -> None:
        """
        Lootea con Shift+Click (quick loot de Tibia).
        El juego automáticamente recoge todo al backpack.
        """
        if not self._on_shift_click or self.hwnd == 0:
            return

        self.state = LooterState.LOOTING
        self._on_shift_click(self.hwnd, corpse.screen_x, corpse.screen_y)

        self.last_loot_time = time.time()
        self.corpses_opened += 1
        self.corpse_detector.mark_looted(corpse)
        self.current_corpse = None

    def _loot_open_body(self, corpse: Corpse) -> None:
        """
        Lootea abriendo el cadáver y arrastrando items.
        Proceso: Right-click → Open → Drag items al backpack.
        """
        if not self._on_right_click or self.hwnd == 0:
            return

        self.state = LooterState.OPENING_CORPSE

        # Abrir cadáver (right-click o double-click)
        if self._on_double_click:
            self._on_double_click(self.hwnd, corpse.screen_x, corpse.screen_y)
        else:
            self._on_right_click(self.hwnd, corpse.screen_x, corpse.screen_y)

        self.last_loot_time = time.time()
        self.corpses_opened += 1
        self.corpse_detector.mark_attempt(corpse)

        # Nota: El drag de items requiere otro ciclo después de que
        # el cadáver se abra (el contenido aparece en un panel)

    def _loot_right_click(self, corpse: Corpse) -> None:
        """Lootea con right-click (menú contextual)."""
        if not self._on_right_click or self.hwnd == 0:
            return

        self.state = LooterState.LOOTING
        self._on_right_click(self.hwnd, corpse.screen_x, corpse.screen_y)

        self.last_loot_time = time.time()
        self.corpse_detector.mark_attempt(corpse)

    # ==================================================================
    # Control
    # ==================================================================
    def start(self) -> None:
        """Inicia el looter."""
        self.enabled = True
        self.state = LooterState.IDLE

    def pause(self) -> None:
        """Pausa el looter."""
        self.state = LooterState.PAUSED

    def resume(self) -> None:
        """Reanuda el looter."""
        if self.state == LooterState.PAUSED:
            self.state = LooterState.IDLE

    def stop(self) -> None:
        """Detiene el looter."""
        self.enabled = False
        self.state = LooterState.IDLE
        self.current_corpse = None

    def reset_stats(self) -> None:
        """Reinicia estadísticas."""
        self.items_looted = 0
        self.corpses_opened = 0
        self.gold_collected = 0
        self.corpse_detector.clear()

    # ==================================================================
    # Info
    # ==================================================================
    def get_status(self) -> Dict:
        return {
            "state": self.state.value,
            "enabled": self.enabled,
            "loot_method": self.loot_method.value,
            "pending_corpses": self.corpse_detector.pending_count,
            "current_corpse": self.current_corpse.to_dict() if self.current_corpse else None,
            "items_looted": self.items_looted,
            "corpses_opened": self.corpses_opened,
            "gold_collected": self.gold_collected,
            "backpack_status": self.backpack_manager.get_status(),
        }

    def __repr__(self) -> str:
        return (
            f"<LooterEngine state={self.state.value} "
            f"pending={self.corpse_detector.pending_count} "
            f"looted={self.items_looted}>"
        )
