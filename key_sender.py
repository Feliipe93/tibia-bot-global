"""
key_sender.py - Envío de teclas a la ventana de Tibia via PostMessage.
No requiere que Tibia esté en primer plano.
Soporta: F1-F12, 0-9, A-Z, Space, Enter, Escape, Tab, y combinaciones Ctrl+key.
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
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35,
    "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39, "0": 0x30,
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45,
    "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A,
    "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F,
    "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
    "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59,
    "Z": 0x5A,
    "SPACE": win32con.VK_SPACE,
    "ENTER": win32con.VK_RETURN,
    "ESCAPE": win32con.VK_ESCAPE,
    "ESC": win32con.VK_ESCAPE,
    "TAB": win32con.VK_TAB,
    "BACKSPACE": win32con.VK_BACK,
    "DELETE": win32con.VK_DELETE,
    "UP": win32con.VK_UP,
    "DOWN": win32con.VK_DOWN,
    "LEFT": win32con.VK_LEFT,
    "RIGHT": win32con.VK_RIGHT,
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

        Soporta combinaciones con Ctrl: "Ctrl+A", "Ctrl+1", etc.

        Args:
            key_name: Nombre de la tecla ("F1", "A", "Ctrl+1", etc.).
            delay: Pausa en segundos entre KeyDown y KeyUp.

        Returns:
            True si se envió correctamente.
        """
        if self.hwnd is None:
            return False

        # Detectar modificador Ctrl+
        use_ctrl = False
        actual_key = key_name.strip().upper()
        if actual_key.startswith("CTRL+"):
            use_ctrl = True
            actual_key = actual_key[5:].strip()

        vk = VK_MAP.get(actual_key)
        if vk is None:
            return False

        try:
            scan_code = win32api.MapVirtualKey(vk, 0)
            lparam_down = (scan_code << 16) | 1
            lparam_up = (scan_code << 16) | 0xC0000001

            # Si Ctrl, enviar Ctrl down primero
            if use_ctrl:
                ctrl_scan = win32api.MapVirtualKey(win32con.VK_CONTROL, 0)
                ctrl_lparam_down = (ctrl_scan << 16) | 1
                ctrl_lparam_up = (ctrl_scan << 16) | 0xC0000001
                win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, win32con.VK_CONTROL, ctrl_lparam_down)
                time.sleep(0.02)

            win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
            time.sleep(delay)
            win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, vk, lparam_up)

            # Si Ctrl, soltar Ctrl después
            if use_ctrl:
                time.sleep(0.02)
                win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, win32con.VK_CONTROL, ctrl_lparam_up)

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
