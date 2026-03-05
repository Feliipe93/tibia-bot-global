"""
looter/looter_engine.py - Motor de looteo FUNCIONAL.
Cuando un monstruo muere (conteo en battle list disminuye),
hace right-click en los 9 SQMs alrededor del jugador.
Basado en TibiaAuto12/engine/CaveBot/CaveBotController.py → TakeLoot().
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


class LooterEngine:
    """
    Motor de looteo automático.
    Recibe notificación de kill del TargetingEngine y hace right-click
    en los 9 SQMs alrededor del jugador para recoger loot.
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"

        # SQMs alrededor del jugador (9 posiciones x,y)
        self.sqms: List[Tuple[int, int]] = []

        # Configuración
        self.loot_button: str = "right"  # "right" o "left"
        self.loot_delay: float = 0.05    # Delay entre clicks de SQM
        self.eat_food: bool = False
        self.food_key: str = ""

        # Callbacks
        self._right_click_fn: Optional[Callable] = None  # right_click(x, y)
        self._left_click_fn: Optional[Callable] = None    # left_click(x, y)
        self._log_fn: Optional[Callable] = None

        # Métricas
        self.loot_actions: int = 0
        self.corpses_looted: int = 0
        self.last_loot_time: float = 0.0

        # Kill tracking
        self._pending_loots: int = 0

    # ==================================================================
    # Configuración
    # ==================================================================
    def set_right_click_callback(self, fn: Callable):
        """fn(x, y) - right click en coordenadas de cliente."""
        self._right_click_fn = fn

    def set_left_click_callback(self, fn: Callable):
        """fn(x, y) - left click en coordenadas de cliente."""
        self._left_click_fn = fn

    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_sqms(self, sqms: List[Tuple[int, int]]):
        """Establece los 9 SQMs alrededor del jugador."""
        self.sqms = sqms

    def configure(self, config: dict):
        """Aplica configuración desde dict."""
        looter = config if isinstance(config, dict) else {}
        self.loot_button = looter.get("loot_button", "right")
        self.loot_delay = looter.get("loot_delay", 0.05)
        self.eat_food = looter.get("eat_food", False)
        self.food_key = looter.get("food_key", "")

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Looter] {msg}")

    # ==================================================================
    # Notificación de kills
    # ==================================================================
    def notify_kill(self):
        """Llamado por el TargetingEngine cuando detecta que un monstruo murió."""
        self._pending_loots += 1

    # ==================================================================
    # Loop principal (llamado por dispatcher)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """Procesa looteo pendiente. Frame se ignora (usamos SQMs precalculados)."""
        if not self.enabled:
            return
        if self._pending_loots <= 0:
            return
        if not self.sqms:
            self._log("Sin SQMs configurados - necesita calibración")
            return

        # Ejecutar looteo
        self._take_loot()
        self._pending_loots -= 1

    def _take_loot(self):
        """
        Hace click en los 9 SQMs alrededor del jugador.
        Igual que TibiaAuto12: for i, j in zip(range(0, 18, 2), range(1, 19, 2))
        """
        click_fn = self._right_click_fn if self.loot_button == "right" else self._left_click_fn
        if click_fn is None:
            self._log("Sin callback de click configurado")
            return

        self.state = "looting"
        self._log(f"Looteando {len(self.sqms)} SQMs...")

        for i, (x, y) in enumerate(self.sqms):
            if x == 0 and y == 0:
                continue
            click_fn(x, y)
            if self.loot_delay > 0:
                time.sleep(self.loot_delay)
            self.loot_actions += 1

        self.corpses_looted += 1
        self.last_loot_time = time.time()
        self.state = "idle"
        self._log(f"Loot completado (total: {self.corpses_looted})")

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._log("Looter activado")

    def stop(self):
        self.enabled = False
        self.state = "idle"
        self._pending_loots = 0
        self._log("Looter desactivado")

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "pending_loots": self._pending_loots,
            "corpses_looted": self.corpses_looted,
            "loot_actions": self.loot_actions,
            "sqms_configured": len(self.sqms),
        }
