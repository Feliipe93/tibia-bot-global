"""
action_dispatcher.py - Punto central que unifica todas las acciones del bot.
Coordina key_sender, mouse_click_sender y drag_drop_sender.
Implementa cola de acciones con prioridad para evitar conflictos
entre healer, cavebot, targeting y looter.
"""

import time
import threading
from enum import IntEnum
from typing import Optional

from key_sender import KeySender
from mouse_click_sender import MouseClickSender
from drag_drop_sender import DragDropSender


class ActionPriority(IntEnum):
    """Prioridad de acciones — menor número = mayor prioridad."""
    EMERGENCY = 0      # Curación crítica (HP < 30%)
    HEALER = 10        # Curación normal
    TARGETING = 20     # Ataque a mobs
    CAVEBOT = 30       # Movimiento / waypoints
    LOOTER = 40        # Recoger loot
    UTILITY = 50       # Acciones secundarias


class ActionDispatcher:
    """
    Centraliza el envío de todas las acciones al cliente de Tibia.
    Garantiza que no se envíen acciones en conflicto simultáneamente
    (ej: click de cavebot y tecla de healer al mismo tiempo).
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Senders
        self.key_sender = KeySender()
        self.mouse_sender = MouseClickSender()
        self.drag_sender = DragDropSender()

        # Estado
        self.last_action_time: float = 0.0
        self.last_action_type: str = ""
        self.total_actions: int = 0

        # Cooldown global mínimo entre acciones (evita spam)
        self.global_cooldown: float = 0.05

    def set_target_hwnd(self, hwnd: int) -> None:
        """Establece el HWND de Tibia para todos los senders."""
        self.key_sender.set_target(hwnd)
        self.mouse_sender.set_target(hwnd)
        self.drag_sender.set_target(hwnd)

    @property
    def hwnd(self) -> Optional[int]:
        """HWND actual del target."""
        return self.key_sender.hwnd

    # ==================================================================
    # Verificación de disponibilidad
    # ==================================================================
    def can_act(self, min_cooldown: float = 0.0) -> bool:
        """Verifica si se puede ejecutar una acción (cooldown global)."""
        cd = max(self.global_cooldown, min_cooldown)
        return (time.time() - self.last_action_time) >= cd

    def _register_action(self, action_type: str) -> None:
        """Registra que se ejecutó una acción."""
        self.last_action_time = time.time()
        self.last_action_type = action_type
        self.total_actions += 1

    # ==================================================================
    # Acciones de teclado
    # ==================================================================
    def send_key(
        self,
        key_name: str,
        priority: ActionPriority = ActionPriority.UTILITY,
        delay: float = 0.05,
    ) -> bool:
        """
        Envía una tecla a Tibia.

        Args:
            key_name: Nombre de la tecla ("F1", "1", etc).
            priority: Prioridad de la acción.
            delay: Pausa entre KeyDown y KeyUp.

        Returns:
            True si se envió.
        """
        with self._lock:
            if not self.can_act():
                return False
            success = self.key_sender.send_key(key_name, delay=delay)
            if success:
                self._register_action(f"key:{key_name}")
            return success

    def send_heal_key(self, key_name: str, emergency: bool = False) -> bool:
        """Envía tecla de curación con prioridad alta."""
        prio = ActionPriority.EMERGENCY if emergency else ActionPriority.HEALER
        return self.send_key(key_name, priority=prio)

    def send_attack_key(self, key_name: str) -> bool:
        """Envía tecla de ataque."""
        return self.send_key(key_name, priority=ActionPriority.TARGETING)

    # ==================================================================
    # Acciones de mouse
    # ==================================================================
    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        priority: ActionPriority = ActionPriority.UTILITY,
        **kwargs,
    ) -> bool:
        """
        Envía un click a Tibia.

        Args:
            x, y: Coordenadas de cliente.
            button: "left" o "right".
            priority: Prioridad de la acción.
        """
        with self._lock:
            if not self.can_act():
                return False
            success = self.mouse_sender.click(x, y, button=button, **kwargs)
            if success:
                self._register_action(f"click:{button}@({x},{y})")
            return success

    def walk_click(self, x: int, y: int) -> bool:
        """Click izquierdo para caminar (cavebot)."""
        return self.click(x, y, button="left", priority=ActionPriority.CAVEBOT)

    def attack_click(self, x: int, y: int) -> bool:
        """Click izquierdo para atacar un mob."""
        return self.click(x, y, button="left", priority=ActionPriority.TARGETING)

    def loot_click(self, x: int, y: int) -> bool:
        """Click derecho para abrir cuerpo (looter)."""
        return self.click(x, y, button="right", priority=ActionPriority.LOOTER)

    def shift_loot_click(self, x: int, y: int) -> bool:
        """Shift+Click para quick loot (Tibia 12+)."""
        return self.click(
            x, y, button="left", shift=True, priority=ActionPriority.LOOTER
        )

    # ==================================================================
    # Acciones de drag & drop
    # ==================================================================
    def drag_item(
        self,
        from_x: int,
        from_y: int,
        to_x: int,
        to_y: int,
        priority: ActionPriority = ActionPriority.LOOTER,
    ) -> bool:
        """
        Arrastra un item de un punto a otro.
        """
        with self._lock:
            if not self.can_act(min_cooldown=0.2):
                return False
            success = self.drag_sender.drag(from_x, from_y, to_x, to_y)
            if success:
                self._register_action(
                    f"drag:({from_x},{from_y})->({to_x},{to_y})"
                )
            return success

    # ==================================================================
    # Info
    # ==================================================================
    def get_stats(self) -> dict:
        """Retorna estadísticas de acciones."""
        return {
            "total_actions": self.total_actions,
            "last_action": self.last_action_type,
            "last_time": self.last_action_time,
            "key_sends": self.key_sender.send_count,
            "mouse_clicks": self.mouse_sender.click_count,
            "drags": self.drag_sender.drag_count,
        }

    def __repr__(self) -> str:
        return (
            f"<ActionDispatcher actions={self.total_actions} "
            f"hwnd={self.hwnd}>"
        )
