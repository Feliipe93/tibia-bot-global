"""
looter/looter_engine.py - Motor de looteo inteligente v2.
Lootea después de kills, con lógica kill-first-then-loot:
  - Si hay muchas criaturas vivas → espera a que targeting termine
  - Si quedan pocas o ninguna → lootea los cuerpos
  - Drop de items no deseados al piso
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


class LooterEngine:
    """
    Motor de looteo automático inteligente.

    Lógica "kill first, then loot":
    - Consulta al targeting cuántas criaturas hay en pantalla
    - Si criaturas > loot_threshold → NO lootea, deja que targeting trabaje
    - Si criaturas <= loot_threshold → lootea cuerpos pendientes
    - Configurable: right_click o left_click según Tibia config
    - Drop de items no deseados al piso
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"  # idle, waiting_kills, waiting_cooldown, looting, dropping

        # SQMs alrededor del jugador (9 posiciones x,y en espacio OBS)
        self.sqms: List[Tuple[int, int]] = []
        self.player_center: Tuple[int, int] = (0, 0)

        # Configuración de looteo
        self.loot_method: str = "left_click"  # "left_click" o "right_click"
        self.loot_delay: float = 0.18         # Delay entre clicks en SQMs
        self.loot_cooldown: float = 1.5       # Cooldown entre sesiones de looteo
        self.max_loot_sqms: int = 3           # Max SQMs a clickear por kill

        # Configuración kill-first-then-loot
        self.loot_threshold: int = 2  # Solo lootear si criaturas <= este valor
        self.always_loot: bool = False  # Si True, ignora threshold y lootea siempre

        # Drop items al piso
        self.drop_enabled: bool = False
        self.drop_items: List[str] = []  # Lista de items a tirar
        self.drop_delay: float = 0.3

        # Callbacks
        self._right_click_fn: Optional[Callable] = None
        self._left_click_fn: Optional[Callable] = None
        self._log_fn: Optional[Callable] = None

        # Referencia al targeting (para consultar creature count)
        self._targeting_engine = None

        # Cola de looteo: lista de (x, y, timestamp, monster_name)
        self._kill_positions: List[Tuple[int, int, float, str]] = []
        self._pending_loots: int = 0

        # Métricas
        self.loot_actions: int = 0
        self.corpses_looted: int = 0
        self.skipped_by_combat: int = 0
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

    def set_targeting_engine(self, engine):
        """Referencia al TargetingEngine para consultar creature count."""
        self._targeting_engine = engine

    def set_sqms(self, sqms: List[Tuple[int, int]]):
        """Establece los 9 SQMs alrededor del jugador."""
        self.sqms = sqms
        if len(sqms) >= 5:
            self.player_center = sqms[4]

    def configure(self, config: dict):
        """Aplica configuración desde dict."""
        looter = config if isinstance(config, dict) else {}
        self.loot_method = looter.get("loot_method", "left_click")
        self.loot_delay = looter.get("loot_delay", 0.18)
        self.loot_cooldown = looter.get("loot_cooldown", 1.5)
        self.max_loot_sqms = looter.get("max_loot_sqms", 3)

        # Kill-first config
        self.loot_threshold = looter.get("loot_threshold", 2)
        self.always_loot = looter.get("always_loot", False)

        # Drop config
        self.drop_enabled = looter.get("drop_enabled", False)
        drop_str = looter.get("drop_items", "")
        if isinstance(drop_str, str):
            self.drop_items = [s.strip() for s in drop_str.split(",") if s.strip()]
        elif isinstance(drop_str, list):
            self.drop_items = drop_str

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Looter] {msg}")

    # ==================================================================
    # Notificación de kills (desde targeting)
    # ==================================================================
    def notify_kill(self, monster_name: str = "", screen_x: int = 0, screen_y: int = 0):
        """
        Llamado cuando el targeting detecta una kill.
        screen_x/screen_y = posición del player center (donde cayó el cuerpo).
        """
        now = time.time()
        self._pending_loots += 1
        self._kill_positions.append((screen_x, screen_y, now, monster_name))
        self._log(f"Kill: {monster_name} — pendientes: {self._pending_loots}")

        # Limpiar posiciones viejas (>45 segundos)
        self._kill_positions = [
            (x, y, t, n) for x, y, t, n in self._kill_positions
            if now - t < 45.0
        ]

    # ==================================================================
    # Loop principal (llamado por dispatcher)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """Procesa looteo pendiente con lógica kill-first-then-loot."""
        if not self.enabled:
            return

        # Sin kills pendientes → nada que hacer
        if self._pending_loots <= 0:
            self.state = "idle"
            return

        now = time.time()

        # --- Kill-first: ¿hay muchas criaturas vivas? ---
        if not self.always_loot and self._targeting_engine is not None:
            creature_count = self._targeting_engine.get_creature_count()
            in_combat = self._targeting_engine.is_in_combat()

            if creature_count > self.loot_threshold:
                # Muchas criaturas → priorizar combate
                self.state = "waiting_kills"
                # Log cada 3 segundos para no spamear
                if not hasattr(self, '_last_wait_log'):
                    self._last_wait_log = 0.0
                if now - self._last_wait_log >= 3.0:
                    self._last_wait_log = now
                    self._log(
                        f"Esperando combate ({creature_count} criaturas > "
                        f"threshold {self.loot_threshold}) — "
                        f"{self._pending_loots} loot pendientes"
                    )
                    self.skipped_by_combat += 1
                return

            # Pocas criaturas pero aún en combate activo → esperar un poco
            if in_combat and creature_count > 0:
                self.state = "waiting_kills"
                return

        # --- Cooldown entre sesiones de looteo ---
        if now - self.last_loot_time < self.loot_cooldown:
            self.state = "waiting_cooldown"
            return

        if not self.sqms:
            self._log("⚠ Sin SQMs configurados — presiona 'Calibrar'")
            return

        # --- Ejecutar looteo ---
        self._take_loot()
        self._pending_loots = max(0, self._pending_loots - 1)

    def _take_loot(self):
        """
        Lootea cuerpos. Usa el método configurado (left/right click).
        Clickea en SQMs cercanos a donde murió el monstruo.
        """
        click_fn = self._get_click_fn()
        if click_fn is None:
            self._log("⚠ Sin callback de click configurado")
            return

        self.state = "looting"

        # ¿Tenemos posición del kill?
        if self._kill_positions:
            kx, ky, kt, kname = self._kill_positions.pop(0)
            closest_sqms = self._get_closest_sqms(kx, ky, self.max_loot_sqms)
            if closest_sqms:
                self._log(f"Looteando {kname}: {len(closest_sqms)} SQMs")
                for sx, sy in closest_sqms:
                    click_fn(sx, sy)
                    time.sleep(self.loot_delay)
                    self.loot_actions += 1
            else:
                self._log(f"Looteando {kname}: click en ({kx},{ky})")
                click_fn(kx, ky)
                self.loot_actions += 1
        else:
            # Sin posición conocida: SQMs adyacentes
            adjacent = self._get_adjacent_sqms(self.max_loot_sqms)
            if adjacent:
                self._log(f"Looteando {len(adjacent)} SQMs adyacentes")
                for sx, sy in adjacent:
                    click_fn(sx, sy)
                    time.sleep(self.loot_delay)
                    self.loot_actions += 1

        self.corpses_looted += 1
        self.last_loot_time = time.time()
        self.state = "idle"

    def _get_click_fn(self) -> Optional[Callable]:
        """Retorna la función de click según el método configurado."""
        if self.loot_method == "right_click":
            return self._right_click_fn
        return self._left_click_fn  # default: left_click

    def _get_closest_sqms(
        self, target_x: int, target_y: int, max_count: int
    ) -> List[Tuple[int, int]]:
        """
        Retorna los SQMs más cercanos a la posición target.
        Excluye el SQM central (posición del jugador).
        """
        if not self.sqms:
            return []

        sqm_distances = []
        for i, (sx, sy) in enumerate(self.sqms):
            if sx == 0 and sy == 0:
                continue
            if i == 4:  # SQM central = jugador
                continue
            dist = ((sx - target_x) ** 2 + (sy - target_y) ** 2) ** 0.5
            sqm_distances.append((dist, sx, sy))

        sqm_distances.sort(key=lambda x: x[0])
        return [(sx, sy) for _, sx, sy in sqm_distances[:max_count]]

    def _get_adjacent_sqms(self, max_count: int) -> List[Tuple[int, int]]:
        """Retorna SQMs adyacentes al jugador (excluyendo centro)."""
        if not self.sqms:
            return []
        return [
            (sx, sy) for i, (sx, sy) in enumerate(self.sqms)
            if i != 4 and not (sx == 0 and sy == 0)
        ][:max_count]

    # ==================================================================
    # Drop items no deseados al piso
    # ==================================================================
    def drop_unwanted_items(self):
        """
        Tira items no deseados al piso.
        En Tibia con Classic Controls: Ctrl+click en el item del inventario
        lo tira al piso (o arrastrarlo al game area).

        Por ahora esta función es placeholder — necesita detección de items
        en el inventario via template matching para funcionar completamente.
        """
        if not self.drop_enabled or not self.drop_items:
            return

        self.state = "dropping"
        self._log(f"Drop items configurado: {self.drop_items}")
        self._log("⚠ Drop automático requiere detección de inventario (próxima versión)")
        self.state = "idle"

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._pending_loots = 0
        self._kill_positions.clear()
        self._log("Looter activado")
        self._log(f"Método: {self.loot_method}")
        self._log(f"Cooldown: {self.loot_cooldown}s")

        if self.always_loot:
            self._log("Modo: lootear siempre (sin esperar combate)")
        else:
            self._log(f"Modo: kill-first (lootear cuando criaturas ≤ {self.loot_threshold})")

        if self.drop_enabled:
            self._log(f"Drop items: {self.drop_items}")

        if not self.sqms:
            self._log("⚠ Sin SQMs — presiona 'Calibrar' primero")
        else:
            self._log(f"SQMs: {len(self.sqms)} configurados")

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
            "skipped_by_combat": self.skipped_by_combat,
            "sqms_configured": len(self.sqms),
            "kill_positions_tracked": len(self._kill_positions),
            "loot_method": self.loot_method,
        }
