"""
looter/looter_engine.py - Motor de looteo inteligente.
Solo lootea cuando el targeting confirma una kill.
Usa left-click en el cuerpo del monstruo muerto.
Basado en el comportamiento de Classic Controls + Loot: Left de Tibia.
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


class LooterEngine:
    """
    Motor de looteo automático inteligente.
    - Recibe notificación de kill con posición donde murió el monstruo
    - Usa left-click en el SQM del cuerpo para abrir el loot
    - Tiene cooldown para no spamear clicks
    - Si no sabe dónde murió, lootea el SQM central (player_center)
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"  # idle, waiting, looting

        # SQMs alrededor del jugador (9 posiciones x,y en espacio OBS)
        self.sqms: List[Tuple[int, int]] = []
        self.player_center: Tuple[int, int] = (0, 0)

        # Configuración
        self.loot_method: str = "left_click"  # "left_click" o "right_click"
        self.loot_delay: float = 0.15         # Delay entre clicks
        self.loot_range: int = 2              # Rango en tiles (1=adyacente, 2=pantalla)
        self.loot_cooldown: float = 1.5       # Cooldown entre looteos completos
        self.max_loot_sqms: int = 3           # Max SQMs a lootear por kill

        # Callbacks
        self._right_click_fn: Optional[Callable] = None
        self._left_click_fn: Optional[Callable] = None
        self._log_fn: Optional[Callable] = None

        # Cola de looteo: lista de (x, y, timestamp) donde murieron monstruos
        self._kill_positions: List[Tuple[int, int, float]] = []
        self._pending_loots: int = 0

        # Métricas
        self.loot_actions: int = 0
        self.corpses_looted: int = 0
        self.last_loot_time: float = 0.0

    # ==================================================================
    # Configuración
    # ==================================================================
    def set_right_click_callback(self, fn: Callable):
        self._right_click_fn = fn

    def set_left_click_callback(self, fn: Callable):
        self._left_click_fn = fn

    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_sqms(self, sqms: List[Tuple[int, int]]):
        """Establece los 9 SQMs alrededor del jugador."""
        self.sqms = sqms
        # El SQM del centro (índice 4 de 9) es la posición del jugador
        if len(sqms) >= 5:
            self.player_center = sqms[4]

    def configure(self, config: dict):
        """Aplica configuración desde dict."""
        looter = config if isinstance(config, dict) else {}
        self.loot_method = looter.get("loot_method", "left_click")
        self.loot_delay = looter.get("loot_delay", 0.15)
        self.loot_range = looter.get("loot_range", 2)
        self.loot_cooldown = looter.get("loot_cooldown", 1.5)

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Looter] {msg}")

    # ==================================================================
    # Notificación de kills (desde targeting)
    # ==================================================================
    def notify_kill(self, monster_name: str = "", screen_x: int = 0, screen_y: int = 0):
        """
        Llamado por el TargetingEngine cuando detecta que un monstruo murió.

        Args:
            monster_name: Nombre del monstruo que murió
            screen_x, screen_y: Posición en pantalla donde estaba el monstruo
                                (en el espacio del frame OBS)
        """
        now = time.time()
        self._pending_loots += 1

        if screen_x != 0 and screen_y != 0:
            self._kill_positions.append((screen_x, screen_y, now))
            self._log(f"Kill registrada: {monster_name} en ({screen_x},{screen_y})")
        else:
            self._log(f"Kill registrada: {monster_name} (posición desconocida)")

        # Limpiar posiciones viejas (>30 segundos)
        self._kill_positions = [
            (x, y, t) for x, y, t in self._kill_positions
            if now - t < 30.0
        ]

    # ==================================================================
    # Loop principal (llamado por dispatcher)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """Procesa looteo pendiente."""
        if not self.enabled:
            return
        if self._pending_loots <= 0:
            self.state = "idle"
            return

        now = time.time()

        # Cooldown entre looteos
        if now - self.last_loot_time < self.loot_cooldown:
            self.state = "waiting"
            return

        if not self.sqms:
            self._log("⚠ Sin SQMs configurados — presiona 'Calibrar'")
            return

        # Ejecutar looteo del kill más reciente
        self._take_loot()
        self._pending_loots = max(0, self._pending_loots - 1)

    def _take_loot(self):
        """
        Lootea el cuerpo del monstruo muerto.

        Estrategia:
        1. Si tenemos la posición exacta del kill → click en ese SQM
        2. Si no → click en los SQMs cercanos al player center
        """
        click_fn = self._left_click_fn if self.loot_method == "left_click" else self._right_click_fn
        if click_fn is None:
            self._log("⚠ Sin callback de click configurado")
            return

        self.state = "looting"

        # ¿Tenemos posición del kill?
        if self._kill_positions:
            kx, ky, kt = self._kill_positions.pop(0)
            # Buscar el SQM más cercano a la posición del kill
            closest_sqms = self._get_closest_sqms(kx, ky, self.max_loot_sqms)
            if closest_sqms:
                self._log(f"Looteando {len(closest_sqms)} SQMs cerca de kill ({kx},{ky})")
                for sx, sy in closest_sqms:
                    click_fn(sx, sy)
                    time.sleep(self.loot_delay)
                    self.loot_actions += 1
            else:
                # Fallback: click en posición del kill
                self._log(f"Looteando posición de kill ({kx},{ky})")
                click_fn(kx, ky)
                self.loot_actions += 1
        else:
            # Sin posición conocida: lootear SQMs adyacentes al jugador
            # Excluir SQM central (índice 4 = posición del jugador)
            adjacent_sqms = [
                (sx, sy) for i, (sx, sy) in enumerate(self.sqms)
                if i != 4 and not (sx == 0 and sy == 0)
            ]
            sqms_to_loot = adjacent_sqms[:self.max_loot_sqms]
            if sqms_to_loot:
                self._log(f"Looteando {len(sqms_to_loot)} SQMs alrededor del jugador")
                for sx, sy in sqms_to_loot:
                    if sx == 0 and sy == 0:
                        continue
                    click_fn(sx, sy)
                    time.sleep(self.loot_delay)
                    self.loot_actions += 1

        self.corpses_looted += 1
        self.last_loot_time = time.time()
        self.state = "idle"
        self._log(f"Loot completado (total corpses: {self.corpses_looted})")

    def _get_closest_sqms(
        self, target_x: int, target_y: int, max_count: int
    ) -> List[Tuple[int, int]]:
        """
        Retorna los SQMs más cercanos a la posición target,
        ordenados por distancia.
        Excluye el SQM central (posición del jugador) porque ahí
        no puede haber un cuerpo — el jugador está encima.
        """
        if not self.sqms:
            return []

        sqm_distances = []
        for i, (sx, sy) in enumerate(self.sqms):
            if sx == 0 and sy == 0:
                continue
            # Excluir el SQM del centro (índice 4) = posición del jugador
            if i == 4:
                continue
            dist = ((sx - target_x) ** 2 + (sy - target_y) ** 2) ** 0.5
            sqm_distances.append((dist, sx, sy))

        sqm_distances.sort(key=lambda x: x[0])
        return [(sx, sy) for _, sx, sy in sqm_distances[:max_count]]

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._pending_loots = 0  # Reset al activar
        self._kill_positions.clear()
        self._log("Looter activado")
        self._log(f"Método: {self.loot_method}, Cooldown: {self.loot_cooldown}s")
        if not self.sqms:
            self._log("⚠ Sin SQMs — presiona 'Calibrar' primero")
        else:
            self._log(f"SQMs configurados: {len(self.sqms)}")

    def stop(self):
        self.enabled = False
        self.state = "idle"
        self._pending_loots = 0
        self._kill_positions.clear()
        self._log("Looter desactivado")

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "pending_loots": self._pending_loots,
            "corpses_looted": self.corpses_looted,
            "loot_actions": self.loot_actions,
            "sqms_configured": len(self.sqms),
            "kill_positions_tracked": len(self._kill_positions),
        }
