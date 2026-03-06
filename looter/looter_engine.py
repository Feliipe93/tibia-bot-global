"""
looter/looter_engine.py - Motor de looteo v4 (estilo TibiaAuto12).
Cambios respecto a v3:
  - Lootea INMEDIATAMENTE tras cada kill (no espera a matar todo)
  - Click en los 9 SQMs incluyendo centro (brute-force como TibiaAuto12)
  - Delay mínimo entre clicks (0.05s vs 0.20s anterior)
  - Cooldown corto entre looteos (0.3s vs 1.5s anterior)
  - NO pausa el targeting — el loot es rápido (~0.5s para 9 clicks)
  - always_loot=True por defecto
  - Eliminado flag _is_looting que pausaba targeting
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


class LooterEngine:
    """
    Motor de looteo automático — estilo TibiaAuto12.

    Flujo:
    1. Targeting detecta kill (conteo de battle list bajó)
    2. _targeting_with_loot wrapper llama notify_kill()
    3. En el siguiente frame del dispatcher, process_frame() ve pendientes > 0
    4. Click rápido en 9 SQMs (~0.05s entre clicks = ~0.5s total)
    5. Targeting sigue atacando normalmente (NO se pausa)

    El loot es tan rápido que no necesita pausar al targeting.
    TibiaAuto12 tampoco pausa el combate durante el looteo.
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"  # idle, looting, waiting_combat

        # SQMs alrededor del jugador (9 posiciones x,y en espacio OBS)
        self.sqms: List[Tuple[int, int]] = []
        self.player_center: Tuple[int, int] = (0, 0)

        # Configuración de looteo — valores TibiaAuto12-style
        self.loot_method: str = "left_click"  # "left_click" o "right_click"
        self.loot_delay: float = 0.05         # Delay entre clicks (muy corto)
        self.loot_cooldown: float = 0.3       # Cooldown mínimo entre sesiones
        self.max_loot_sqms: int = 9           # 9 = todos (incluido centro)

        # Configuración threshold (opcional)
        self.loot_threshold: int = 0  # 0 = lootear siempre inmediatamente
        self.always_loot: bool = True  # True = ignorar threshold

        # Drop items al piso
        self.drop_enabled: bool = False
        self.drop_items: List[str] = []
        self.drop_delay: float = 0.3

        # Callbacks
        self._right_click_fn: Optional[Callable] = None
        self._left_click_fn: Optional[Callable] = None
        self._log_fn: Optional[Callable] = None

        # Referencia al targeting (para consultar creature count)
        self._targeting_engine = None

        # Cola de kills pendientes de lootear
        self._pending_loots: int = 0
        self._kill_names: List[str] = []

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
        self.loot_delay = looter.get("loot_delay", 0.05)
        self.loot_cooldown = looter.get("loot_cooldown", 0.3)
        self.max_loot_sqms = looter.get("max_loot_sqms", 9)

        # Threshold config
        self.loot_threshold = looter.get("loot_threshold", 0)
        self.always_loot = looter.get("always_loot", True)

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
    # API pública
    # ==================================================================
    @property
    def is_looting(self) -> bool:
        """True si el looter está activamente looteando.
        NOTE: Ya NO se usa para pausar targeting. Se mantiene solo
        por compatibilidad y para queries de estado."""
        return self.state == "looting"

    # ==================================================================
    # Notificación de kills (desde targeting)
    # ==================================================================
    def notify_kill(self, monster_name: str = "", screen_x: int = 0, screen_y: int = 0):
        """
        Llamado cuando el targeting detecta una kill.
        Incrementa el contador de pendientes para lootear en el próximo frame.
        """
        self._pending_loots += 1
        self._kill_names.append(monster_name or "desconocido")
        self._log(f"Kill: {monster_name} — pendientes: {self._pending_loots}")

    # ==================================================================
    # Loop principal (llamado por dispatcher cada frame)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """
        Procesa looteo pendiente.
        Lógica simple como TibiaAuto12: si hay kills pendientes → lootear.
        NO pausa targeting — el loot es rápido (~0.5s).
        """
        if not self.enabled:
            return

        # Sin kills pendientes → nada que hacer
        if self._pending_loots <= 0:
            self.state = "idle"
            return

        now = time.time()

        # --- Threshold opcional: ¿demasiadas criaturas vivas? ---
        if not self.always_loot and self._targeting_engine is not None:
            creature_count = self._targeting_engine.get_creature_count()
            if self.loot_threshold > 0 and creature_count > self.loot_threshold:
                self.state = "waiting_combat"
                if not hasattr(self, '_last_wait_log'):
                    self._last_wait_log = 0.0
                if now - self._last_wait_log >= 3.0:
                    self._last_wait_log = now
                    self._log(
                        f"Esperando combate ({creature_count} > "
                        f"threshold {self.loot_threshold}) — "
                        f"{self._pending_loots} pendientes"
                    )
                    self.skipped_by_combat += 1
                return

        # --- Cooldown mínimo entre looteos ---
        if now - self.last_loot_time < self.loot_cooldown:
            return

        # --- Verificar que tenemos SQMs ---
        if not self.sqms:
            self._log("⚠ Sin SQMs — presiona 'Calibrar'")
            return

        # --- LOOTEAR (rápido, sin pausar targeting) ---
        self._take_loot()

    def _take_loot(self):
        """
        Lootea cuerpos clickeando en los SQMs alrededor del jugador.
        Patrón brute-force idéntico a TibiaAuto12:
        SW → S → SE → W → Centro → E → NW → N → NE

        Incluye el SQM central (jugador) porque el cadáver puede
        quedar debajo del personaje.
        """
        click_fn = self._get_click_fn()
        if click_fn is None:
            self._log("⚠ Sin callback de click configurado")
            return

        self.state = "looting"

        # Nombre del monstruo para el log
        kname = self._kill_names.pop(0) if self._kill_names else "desconocido"

        # Seleccionar SQMs a clickear (9 = todos incluido centro)
        sqms_to_click = self._get_loot_sqms()

        if not sqms_to_click:
            self._log("⚠ Sin SQMs disponibles")
            self.state = "idle"
            return

        self._log(f"Looteando {kname}: {len(sqms_to_click)} SQMs")

        # Click rápido en cada SQM (delay mínimo como TibiaAuto12)
        for sx, sy in sqms_to_click:
            try:
                click_fn(sx, sy)
            except Exception as e:
                self._log(f"⚠ Error click ({sx},{sy}): {e}")
            if self.loot_delay > 0:
                time.sleep(self.loot_delay)
            self.loot_actions += 1

        # Actualizar contadores
        self._pending_loots = max(0, self._pending_loots - 1)
        self.corpses_looted += 1
        self.last_loot_time = time.time()
        self.state = "idle"

    def _get_click_fn(self) -> Optional[Callable]:
        """Retorna la función de click según el método configurado."""
        if self.loot_method == "right_click":
            return self._right_click_fn
        return self._left_click_fn  # default: left_click

    def _get_loot_sqms(self) -> List[Tuple[int, int]]:
        """
        Retorna los SQMs a clickear para lootear.
        max_loot_sqms >= 9: todos los 9 SQMs (incluido centro).
        max_loot_sqms < 9: los primeros N (priorizando adyacentes).
        Orden: SW(0), S(1), SE(2), W(3), Center(4), E(5), NW(6), N(7), NE(8).
        """
        if not self.sqms:
            return []

        valid_sqms = []
        for i, (sx, sy) in enumerate(self.sqms):
            if sx == 0 and sy == 0:
                continue  # SQM no calibrado
            valid_sqms.append((sx, sy))

        return valid_sqms[:self.max_loot_sqms]

    # ==================================================================
    # Drop items no deseados (placeholder)
    # ==================================================================
    def drop_unwanted_items(self):
        """Placeholder para drop de items no deseados."""
        if not self.drop_enabled or not self.drop_items:
            return
        self.state = "dropping"
        self._log(f"Drop items: {self.drop_items} (próxima versión)")
        self.state = "idle"

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._pending_loots = 0
        self._kill_names.clear()
        self._log("Looter activado")
        self._log(f"  Método: {self.loot_method}")
        self._log(f"  SQMs: {self.max_loot_sqms} (9=todos incl. centro)")
        self._log(f"  Delay entre clicks: {self.loot_delay}s")
        self._log(f"  Cooldown entre looteos: {self.loot_cooldown}s")

        if self.always_loot:
            self._log("  Modo: lootear inmediatamente tras cada kill")
        else:
            self._log(f"  Modo: threshold (lootear si criaturas ≤ {self.loot_threshold})")

        if not self.sqms:
            self._log("⚠ Sin SQMs — presiona 'Calibrar' primero")
        else:
            self._log(f"  SQMs calibrados: {len(self.sqms)}")

    def stop(self):
        self.enabled = False
        self.state = "idle"
        self._pending_loots = 0
        self._kill_names.clear()
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
            "loot_method": self.loot_method,
        }
