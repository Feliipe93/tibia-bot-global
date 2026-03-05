"""
key_sender.py - Envío de teclas a la ventana de Tibia via PostMessage.
No requiere que Tibia esté en primer plano.
"""

import time
import win32api
import win32con
from typing import Optional

# Mapa de teclas a Virtual Key Codes de Windows
VK_MAP = {
    "F1": win32con.VK_F1,
    "F2": win32con.VK_F2,
    "F3": win32con.VK_F3,
    "F4": win32con.VK_F4,
    "F5": win32con.VK_F5,
    "F6": win32con.VK_F6,
    "F7": win32con.VK_F7,
    "F8": win32con.VK_F8,
    "F9": win32con.VK_F9,
    "F10": win32con.VK_F10,
    "F11": win32con.VK_F11,
    "F12": win32con.VK_F12,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
    "9": 0x39,
    "0": 0x30,
}


class KeySender:
    """Envía teclas a una ventana de Windows mediante PostMessage."""

    def __init__(self, hwnd: Optional[int] = None):
        self.hwnd = hwnd
        self.last_send_time: float = 0.0
        self.last_key_sent: str = ""
        self.send_count: int = 0

    def set_target(self, hwnd: int) -> None:
        """Establece la ventana destino."""
        self.hwnd = hwnd

    def send_key(self, key_name: str, delay: float = 0.05) -> bool:
        """
        Envía una tecla a la ventana de Tibia usando PostMessage.
        No requiere que la ventana esté en foco/primer plano.

        Args:
            key_name: Nombre de la tecla ("F1", "F2", ..., "F12", "1"-"9").
            delay: Pausa en segundos entre KeyDown y KeyUp.

        Returns:
            True si se envió correctamente.
        """
        if self.hwnd is None:
            return False

        vk = VK_MAP.get(key_name.upper())
        if vk is None:
            return False

        try:
            scan_code = win32api.MapVirtualKey(vk, 0)
            lparam_down = (scan_code << 16) | 1
            lparam_up = (scan_code << 16) | 0xC0000001

            win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
            time.sleep(delay)
            win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, vk, lparam_up)

            self.last_send_time = time.time()
            self.last_key_sent = key_name.upper()
            self.send_count += 1
            return True

        except Exception:
            return False

    def can_send(self, cooldown: float) -> bool:
        """Verifica si ha pasado suficiente tiempo desde el último envío."""
        return (time.time() - self.last_send_time) >= cooldown

    @staticmethod
    def get_available_keys():
        """Retorna la lista de teclas disponibles para asignar."""
        return list(VK_MAP.keys())

    def __repr__(self) -> str:
        return (
            f"<KeySender hwnd={self.hwnd} "
            f"last_key='{self.last_key_sent}' "
            f"sends={self.send_count}>"
        )
