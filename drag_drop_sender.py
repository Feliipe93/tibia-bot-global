"""
drag_drop_sender.py - Simula arrastrar y soltar items en Tibia via PostMessage.
Usa WM_LBUTTONDOWN → WM_MOUSEMOVE (pasos intermedios) → WM_LBUTTONUP
para mover items desde cuerpos al backpack.
"""

import time
import win32api
import win32con
from typing import Optional, Tuple


class DragDropSender:
    """Simula operaciones de drag & drop sobre la ventana de Tibia."""

    def __init__(self, hwnd: Optional[int] = None):
        self.hwnd = hwnd
        self.drag_count: int = 0
        self.last_drag_time: float = 0.0

    def set_target(self, hwnd: int) -> None:
        """Establece la ventana destino."""
        self.hwnd = hwnd

    @staticmethod
    def _make_lparam(x: int, y: int) -> int:
        """Empaqueta (x, y) en lParam."""
        return (y << 16) | (x & 0xFFFF)

    def drag(
        self,
        from_x: int,
        from_y: int,
        to_x: int,
        to_y: int,
        steps: int = 8,
        step_delay: float = 0.015,
        hold_delay: float = 0.1,
    ) -> bool:
        """
        Arrastra un item desde (from_x, from_y) hasta (to_x, to_y).

        Simula:
        1. Mover cursor al origen
        2. LBUTTONDOWN en origen (agarrar item)
        3. MOUSEMOVE en pasos intermedios (mover item)
        4. LBUTTONUP en destino (soltar item)

        Args:
            from_x, from_y: Coordenadas de cliente del item a arrastrar.
            to_x, to_y: Coordenadas de cliente del destino (backpack slot).
            steps: Cantidad de pasos intermedios para simular trayectoria.
            step_delay: Pausa entre cada paso de movimiento.
            hold_delay: Pausa después de agarrar el item.

        Returns:
            True si se completó la operación.
        """
        if self.hwnd is None:
            return False

        try:
            # 1. Mover cursor al origen
            lp_from = self._make_lparam(from_x, from_y)
            win32api.PostMessage(
                self.hwnd, win32con.WM_MOUSEMOVE, 0, lp_from
            )
            time.sleep(0.02)

            # 2. Click down en origen (agarrar)
            win32api.PostMessage(
                self.hwnd,
                win32con.WM_LBUTTONDOWN,
                win32con.MK_LBUTTON,
                lp_from,
            )
            time.sleep(hold_delay)

            # 3. Mover en pasos intermedios
            for i in range(1, steps + 1):
                t = i / steps
                ix = int(from_x + (to_x - from_x) * t)
                iy = int(from_y + (to_y - from_y) * t)
                lp_mid = self._make_lparam(ix, iy)
                win32api.PostMessage(
                    self.hwnd,
                    win32con.WM_MOUSEMOVE,
                    win32con.MK_LBUTTON,
                    lp_mid,
                )
                time.sleep(step_delay)

            # 4. Soltar en destino
            lp_to = self._make_lparam(to_x, to_y)
            win32api.PostMessage(
                self.hwnd, win32con.WM_LBUTTONUP, 0, lp_to
            )

            self.drag_count += 1
            self.last_drag_time = time.time()
            return True

        except Exception:
            return False

    def drag_item_to_backpack(
        self,
        item_x: int,
        item_y: int,
        bp_x: int,
        bp_y: int,
    ) -> bool:
        """Atajo para arrastrar un item a un slot del backpack."""
        return self.drag(item_x, item_y, bp_x, bp_y, steps=10, hold_delay=0.12)

    def can_drag(self, cooldown: float = 0.2) -> bool:
        """Verifica si pasó suficiente tiempo desde el último drag."""
        return (time.time() - self.last_drag_time) >= cooldown

    def __repr__(self) -> str:
        return f"<DragDropSender hwnd={self.hwnd} drags={self.drag_count}>"
