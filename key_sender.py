"""
key_sender.py - Envío de teclas a la ventana de Tibia via SendMessage.
Usa SendMessage (síncrono) en vez de PostMessage (asíncrono) porque
Tibia ignora PostMessage para teclado (comprobado en TibiaAuto12).
No requiere que Tibia esté en primer plano.
Soporta: F1-F12, 0-9, A-Z, Space, Enter, Escape, Tab, y combinaciones Ctrl+key.
"""

import time
import win32api
import win32con
import win32gui
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
    "SHIFT": win32con.VK_SHIFT,
    "LSHIFT": win32con.VK_LSHIFT,
    "RSHIFT": win32con.VK_RSHIFT,
    "PGUP": win32con.VK_PRIOR,
    "PGDN": win32con.VK_NEXT,
    "CTRL+PGUP": "CTRL+PGUP",  # Special case handled in send_key
    "CTRL+PGDN": "CTRL+PGDN",  # Special case handled in send_key
}


class KeySender:
    """
    Envía teclas a una ventana de Windows mediante SendMessage.
    Basado en TibiaAuto12/core/SendToClient.py — usa SendMessage (síncrono)
    con lParam=0 porque Tibia ignora PostMessage para teclado.
    """

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
        Envía una tecla a la ventana de Tibia usando SendMessage (síncrono).
        Patrón de TibiaAuto12: SendMessage(WM_KEYDOWN, vk, 0) + SendMessage(WM_KEYUP, vk, 0)
        
        Soporta combinaciones Ctrl+key y Shift+key.

        Args:
            key_name: Nombre de la tecla ("F1", "A", "Ctrl+1", "Shift+2", etc.).
            delay: Pausa en segundos entre KeyDown y KeyUp.

        Returns:
            True si se envió correctamente.
        """
        if self.hwnd is None or not win32gui.IsWindow(self.hwnd):
            return False

        # Detectar modificadores
        use_ctrl = False
        use_shift = False
        actual_key = key_name.strip().upper()
        
        if actual_key.startswith("CTRL+"):
            use_ctrl = True
            actual_key = actual_key[5:].strip()
        elif actual_key.startswith("SHIFT+"):
            use_shift = True
            actual_key = actual_key[6:].strip()

        vk = VK_MAP.get(actual_key)
        if vk is None:
            # Special cases for Ctrl+PageUp/PageDown
            if actual_key == "PGUP" and use_ctrl:
                vk = win32con.VK_PRIOR
            elif actual_key == "PGDN" and use_ctrl:
                vk = win32con.VK_NEXT
            else:
                return False

        try:
            # Si Ctrl, usar keybd_event global (patrón TibiaAuto12 PressHotkey)
            if use_ctrl:
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                time.sleep(0.05)

            # Si Shift, usar keybd_event global para Shift
            if use_shift:
                win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
                time.sleep(0.05)

            # SendMessage síncrono con lParam=0 (como TibiaAuto12)
            win32api.SendMessage(self.hwnd, win32con.WM_KEYDOWN, vk, 0)
            time.sleep(delay)
            win32api.SendMessage(self.hwnd, win32con.WM_KEYUP, vk, 0)

            # Soltar modificadores en orden inverso
            if use_shift:
                time.sleep(0.05)
                win32api.keybd_event(
                    win32con.VK_SHIFT, 0,
                    win32con.KEYEVENTF_KEYUP, 0
                )
            
            if use_ctrl:
                time.sleep(0.05)
                win32api.keybd_event(
                    win32con.VK_CONTROL, 0,
                    win32con.KEYEVENTF_KEYUP, 0
                )

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
        title = ""
        try:
            if self.hwnd and win32gui.IsWindow(self.hwnd):
                title = win32gui.GetWindowText(self.hwnd)
        except Exception:
            pass
        return (
            f"<KeySender hwnd={self.hwnd} title='{title}' "
            f"last_key='{self.last_key_sent}' "
            f"sends={self.send_count}>"
        )
