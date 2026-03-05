"""
cavebot/walk_simulator.py - Simulador de caminata.
Ejecuta la caminata del personaje usando clicks en pantalla
y teclas de dirección mediante PostMessage.
"""

import time
from typing import Optional, Tuple

import numpy as np

from utils.geometry import (
    CENTER_TILE_X,
    CENTER_TILE_Y,
    TILE_SIZE_GAME,
    game_tile_to_screen,
)


class WalkSimulator:
    """
    Simula la caminata del personaje en Tibia.
    Soporta dos modos:
    1. Click en game window (click en tile destino)
    2. Teclas de dirección (arrow keys)
    """

    # Mapeo de direcciones a teclas de flecha (VK codes)
    DIRECTION_KEYS = {
        "up": "UP",
        "down": "DOWN",
        "left": "LEFT",
        "right": "RIGHT",
        # Diagonales con Ctrl (Tibia usa Ctrl+Arrow para diag)
        "up_left": "NUMPAD7",
        "up_right": "NUMPAD9",
        "down_left": "NUMPAD1",
        "down_right": "NUMPAD3",
    }

    def __init__(self):
        # Referencias a los módulos de acción (inyectados)
        self._action_dispatcher = None
        self._mouse_sender = None
        self._key_sender = None

        # Handle de la ventana de Tibia
        self.hwnd: int = 0

        # Modo de caminata: "click" o "arrow"
        self.walk_mode: str = "click"

        # Región del game window
        self.game_region: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)

        # Timing
        self.step_delay: float = 0.25  # Delay entre pasos
        self.last_step_time: float = 0.0

        # Estado
        self.is_walking: bool = False
        self.steps_taken: int = 0

    def set_action_dispatcher(self, dispatcher) -> None:
        """Inyecta el action dispatcher."""
        self._action_dispatcher = dispatcher

    def set_mouse_sender(self, sender) -> None:
        """Inyecta el mouse click sender."""
        self._mouse_sender = sender

    def set_key_sender(self, sender) -> None:
        """Inyecta el key sender."""
        self._key_sender = sender

    def set_hwnd(self, hwnd: int) -> None:
        """Establece el handle de la ventana de Tibia."""
        self.hwnd = hwnd

    def set_game_region(self, x: int, y: int, w: int, h: int) -> None:
        """Configura la región del game window."""
        self.game_region = (x, y, w, h)

    # ==================================================================
    # Caminata por click
    # ==================================================================
    def walk_click(self, tile_offset_x: int, tile_offset_y: int) -> bool:
        """
        Camina haciendo click en un tile relativo al jugador.
        El jugador siempre está en el centro del game window.

        Args:
            tile_offset_x: Offset X en tiles desde el jugador (-7 a +7).
            tile_offset_y: Offset Y en tiles desde el jugador (-5 a +5).

        Returns:
            True si se envió el click correctamente.
        """
        if not self._can_walk():
            return False

        if self.game_region is None:
            return False

        gx, gy, gw, gh = self.game_region

        # Calcular tile destino relativo al centro
        screen_x, screen_y = game_tile_to_screen(
            CENTER_TILE_X + tile_offset_x,
            CENTER_TILE_Y + tile_offset_y,
            gx, gy, gw, gh,
        )

        return self._send_click(screen_x, screen_y)

    def walk_to_adjacent(self, direction: str) -> bool:
        """
        Camina un tile en la dirección dada.

        Args:
            direction: "up", "down", "left", "right",
                      "up_left", "up_right", "down_left", "down_right"

        Returns:
            True si se ejecutó la acción.
        """
        if not self._can_walk():
            return False

        if self.walk_mode == "arrow":
            return self._walk_arrow(direction)
        else:
            return self._walk_click_direction(direction)

    def _walk_arrow(self, direction: str) -> bool:
        """Camina usando teclas de dirección."""
        key = self.DIRECTION_KEYS.get(direction)
        if not key:
            return False

        if self._key_sender and self.hwnd:
            self._key_sender.send_key(self.hwnd, key)
            self._register_step()
            return True

        return False

    def _walk_click_direction(self, direction: str) -> bool:
        """Camina haciendo click en el tile adyacente."""
        offsets = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
            "up_left": (-1, -1),
            "up_right": (1, -1),
            "down_left": (-1, 1),
            "down_right": (1, 1),
        }

        offset = offsets.get(direction)
        if not offset:
            return False

        return self.walk_click(offset[0], offset[1])

    # ==================================================================
    # Click en tile absoluto (game window)
    # ==================================================================
    def click_tile(self, game_tile_x: int, game_tile_y: int) -> bool:
        """
        Hace click en un tile del game window (coordenadas de tile 0-14, 0-10).
        """
        if self.game_region is None:
            return False

        gx, gy, gw, gh = self.game_region
        screen_x, screen_y = game_tile_to_screen(
            game_tile_x, game_tile_y, gx, gy, gw, gh,
        )

        return self._send_click(screen_x, screen_y)

    # ==================================================================
    # Click en escalera / cuerda / pala
    # ==================================================================
    def use_on_tile(self, tile_offset_x: int, tile_offset_y: int, hotkey: str = "") -> bool:
        """
        Usa un item (crosshair mode) en un tile relativo al jugador.
        Si hotkey se proporciona, primero presiona la tecla (crosshair)
        y luego clickea el tile.
        """
        if self.game_region is None:
            return False

        # Presionar hotkey primero (ej: F8 para cuerda)
        if hotkey and self._key_sender and self.hwnd:
            self._key_sender.send_key(self.hwnd, hotkey)
            time.sleep(0.15)

        gx, gy, gw, gh = self.game_region
        screen_x, screen_y = game_tile_to_screen(
            CENTER_TILE_X + tile_offset_x,
            CENTER_TILE_Y + tile_offset_y,
            gx, gy, gw, gh,
        )

        return self._send_click(screen_x, screen_y)

    # ==================================================================
    # Utilidades internas
    # ==================================================================
    def _send_click(self, screen_x: int, screen_y: int) -> bool:
        """Envía un click izquierdo en las coordenadas dadas."""
        if self._action_dispatcher:
            self._action_dispatcher.walk_click(self.hwnd, screen_x, screen_y)
            self._register_step()
            return True
        elif self._mouse_sender:
            self._mouse_sender.left_click(self.hwnd, screen_x, screen_y)
            self._register_step()
            return True
        return False

    def _can_walk(self) -> bool:
        """Verifica si podemos dar otro paso (cooldown)."""
        now = time.time()
        if now - self.last_step_time < self.step_delay:
            return False
        if self.hwnd == 0:
            return False
        return True

    def _register_step(self) -> None:
        """Registra que se dio un paso."""
        self.last_step_time = time.time()
        self.steps_taken += 1
        self.is_walking = True

    def reset_stats(self) -> None:
        """Reinicia estadísticas."""
        self.steps_taken = 0
        self.is_walking = False

    def __repr__(self) -> str:
        return (
            f"<WalkSimulator mode={self.walk_mode} "
            f"steps={self.steps_taken} "
            f"hwnd={self.hwnd}>"
        )
