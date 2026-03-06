"""
mouse_click_sender.py - Envío de clicks del mouse a Tibia via SendMessage.
Soporta click izquierdo, derecho, doble click, y modificadores (Shift/Ctrl).
No requiere que Tibia esté en primer plano.

Basado en TibiaAuto12/core/SendToClient.py:
  - MOUSEMOVE con PostMessage (asíncrono)
  - BUTTONDOWN/UP con SendMessage (síncrono)
  - lParam = MAKELONG(x, y) para coordenadas de cliente
"""

import time
import ctypes
import win32api
import win32con
import win32gui
from typing import Optional, Tuple


class MouseClickSender:
    """Envía clicks del mouse a una ventana de Tibia mediante PostMessage."""

    def __init__(self, hwnd: Optional[int] = None):
        self.hwnd = hwnd
        self.last_click_time: float = 0.0
        self.last_click_pos: Tuple[int, int] = (0, 0)
        self.click_count: int = 0

    def set_target(self, hwnd: int) -> None:
        """Establece la ventana destino."""
        self.hwnd = hwnd

    # ==================================================================
    # Coordenadas
    # ==================================================================
    @staticmethod
    def _make_lparam(x: int, y: int) -> int:
        """
        Empaqueta coordenadas (x, y) en lParam para mensajes de mouse.
        lParam = (y << 16) | (x & 0xFFFF)
        """
        return (y << 16) | (x & 0xFFFF)

    def screen_to_client(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """
        Convierte coordenadas de pantalla a coordenadas de cliente
        relativas a la ventana de Tibia.
        """
        if self.hwnd is None:
            return screen_x, screen_y
        try:
            client_x, client_y = win32gui.ScreenToClient(
                self.hwnd, (screen_x, screen_y)
            )
            return client_x, client_y
        except Exception:
            return screen_x, screen_y

    def client_to_screen(self, client_x: int, client_y: int) -> Tuple[int, int]:
        """Convierte coordenadas de cliente a pantalla."""
        if self.hwnd is None:
            return client_x, client_y
        try:
            screen_x, screen_y = win32gui.ClientToScreen(
                self.hwnd, (client_x, client_y)
            )
            return screen_x, screen_y
        except Exception:
            return client_x, client_y

    def get_client_size(self) -> Tuple[int, int]:
        """Retorna el tamaño del área de cliente de la ventana."""
        if self.hwnd is None:
            return 0, 0
        try:
            rect = win32gui.GetClientRect(self.hwnd)
            return rect[2], rect[3]  # width, height
        except Exception:
            return 0, 0

    # ==================================================================
    # Clicks
    # ==================================================================
    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        double: bool = False,
        shift: bool = False,
        ctrl: bool = False,
        delay: float = 0.05,
    ) -> bool:
        """
        Envía un click en coordenadas de CLIENTE (relativas a la ventana).

        Args:
            x: Coordenada X dentro del área de cliente.
            y: Coordenada Y dentro del área de cliente.
            button: "left" o "right".
            double: True para doble click.
            shift: True para Shift+Click (quick loot en Tibia).
            ctrl: True para Ctrl+Click (uso de items).
            delay: Pausa entre down y up.

        Returns:
            True si se envió correctamente.
        """
        if self.hwnd is None:
            return False

        try:
            lparam = self._make_lparam(x, y)

            # Construir wParam con modificadores
            wparam = 0
            if button == "left":
                wparam |= win32con.MK_LBUTTON
                msg_down = win32con.WM_LBUTTONDOWN
                msg_up = win32con.WM_LBUTTONUP
                msg_dbl = win32con.WM_LBUTTONDBLCLK
            else:
                wparam |= win32con.MK_RBUTTON
                msg_down = win32con.WM_RBUTTONDOWN
                msg_up = win32con.WM_RBUTTONUP
                msg_dbl = win32con.WM_RBUTTONDBLCLK

            if shift:
                wparam |= win32con.MK_SHIFT
            if ctrl:
                wparam |= win32con.MK_CONTROL

            # Mover mouse primero (PostMessage asíncrono como TibiaAuto12)
            win32api.PostMessage(
                self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam
            )
            time.sleep(0.01)

            # Click down — SendMessage síncrono (como TibiaAuto12)
            win32api.SendMessage(self.hwnd, msg_down, wparam, lparam)

            if double:
                time.sleep(delay)
                win32api.SendMessage(self.hwnd, msg_up, 0, lparam)
                time.sleep(0.01)
                win32api.SendMessage(self.hwnd, msg_dbl, wparam, lparam)

            time.sleep(delay)

            # Click up — SendMessage síncrono
            win32api.SendMessage(self.hwnd, msg_up, 0, lparam)

            # Registrar
            self.last_click_time = time.time()
            self.last_click_pos = (x, y)
            self.click_count += 1
            return True

        except Exception:
            return False

    def left_click(self, x: int, y: int, **kwargs) -> bool:
        """Atajo para click izquierdo."""
        return self.click(x, y, button="left", **kwargs)

    def right_click(self, x: int, y: int, **kwargs) -> bool:
        """Atajo para click derecho (abrir cuerpos, usar items)."""
        return self.click(x, y, button="right", **kwargs)

    def shift_click(self, x: int, y: int) -> bool:
        """Shift+Click izquierdo (quick loot en Tibia 12+)."""
        return self.click(x, y, button="left", shift=True)

    def ctrl_click(self, x: int, y: int) -> bool:
        """Ctrl+Click izquierdo (usar item en Tibia)."""
        return self.click(x, y, button="left", ctrl=True)

    def double_click(self, x: int, y: int) -> bool:
        """Doble click izquierdo."""
        return self.click(x, y, button="left", double=True)

    # ==================================================================
    # Movimiento del mouse (sin click)
    # ==================================================================
    def move_to(self, x: int, y: int) -> bool:
        """Mueve el cursor sobre la ventana (sin click)."""
        if self.hwnd is None:
            return False
        try:
            lparam = self._make_lparam(x, y)
            win32api.PostMessage(
                self.hwnd, win32con.WM_MOUSEMOVE, 0, lparam
            )
            return True
        except Exception:
            return False

    def can_click(self, cooldown: float = 0.1) -> bool:
        """Verifica si pasó suficiente tiempo desde el último click."""
        return (time.time() - self.last_click_time) >= cooldown

    def __repr__(self) -> str:
        return (
            f"<MouseClickSender hwnd={self.hwnd} "
            f"clicks={self.click_count}>"
        )
