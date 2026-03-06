"""
looter/looter_engine.py - Motor de auto-loot v4.
Mejoras v4:
  - Detección visual de cuerpos (aura de muerte + blood splashes)
  - Clickea SOLO en los SQMs donde hay cuerpos reales (no 9 SQMs ciegos)
  - Fallback inteligente: si no detecta cuerpos → usa SQMs alrededor del player
  - 3 modos de click: left_click, right_click, shift_right_click
  - Solo 1 intento rápido por kill, cooldown corto
  - Free account mode
Basado en detección visual del efecto de muerte que todos los cuerpos comparten.
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from looter.corpse_detector import CorpseDetector


class LooterEngine:
    """
    Motor de auto-loot v3.
    Recibe notificaciones de kills del TargetingEngine y ejecuta secuencia de clicks
    sobre los SQMs alrededor de donde murió el monstruo.
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"     # idle, looting, waiting
        self._running: bool = False

        # Callbacks inyectados
        self._left_click_fn: Optional[Callable] = None
        self._right_click_fn: Optional[Callable] = None
        self._shift_right_click_fn: Optional[Callable] = None
        self._log_fn: Optional[Callable] = None
        self._targeting_engine = None

        # Posiciones de los 9 SQMs fijos (inyectados por screen_calibrator)
        # Orden: SW(0), S(1), SE(2), W(3), Center(4), E(5), NW(6), N(7), NE(8)
        self._sqms: List[Tuple[int, int]] = []

        # Player center y SQM size (para calcular SQMs dinámicos)
        self._player_center: Tuple[int, int] = (0, 0)
        self._sqm_size: Tuple[int, int] = (0, 0)

        # Cola de kills pendientes de lootear
        self._kill_queue: List[Dict] = []

        # Configuración
        self.loot_method: str = "left_click"
        self.free_account: bool = False
        self.loot_delay: float = 0.15        # Delay entre clicks (rápido)
        self.max_corpse_age: float = 10.0    # Segundos máx para lootear
        self.max_loot_attempts: int = 1      # Solo 1 intento rápido
        self.loot_cooldown: float = 0.5      # Cooldown corto entre secuencias
        self.periodic_loot: bool = False
        self.periodic_interval: float = 8.0
        self.max_loot_sqms: int = 9          # Cuántos SQMs clickear (1-9)
        self.max_range: int = 2
        self.loot_during_combat: bool = True
        self.auto_open_next_bp: bool = True

        # Timing interno
        self._last_loot_time: float = 0.0
        self._last_periodic_loot: float = 0.0
        self._loot_start_time: float = 0.0
        self._current_sqm_idx: int = 0
        self._last_click_time: float = 0.0

        # SQMs dinámicos para el loot actual (calculados por kill)
        self._loot_sqms: List[Tuple[int, int]] = []

        # Detector visual de cuerpos (aura de muerte + blood splashes)
        self.corpse_detector = CorpseDetector()
        self._last_frame: Optional[np.ndarray] = None  # Frame actual para detección
        self._use_visual_detection: bool = True  # Usar detección visual (True) o SQMs ciegos (False)

        # Métricas
        self.total_loots: int = 0
        self.total_clicks: int = 0
        self.visual_detections: int = 0  # Veces que usó detección visual
        self.blind_fallbacks: int = 0    # Veces que usó fallback ciego

        # Status logging
        self._last_status_log: float = 0.0

    # ==================================================================
    # Configuración y callbacks
    # ==================================================================
    def set_left_click_callback(self, fn: Callable):
        self._left_click_fn = fn

    def set_right_click_callback(self, fn: Callable):
        self._right_click_fn = fn

    def set_shift_right_click_callback(self, fn: Callable):
        self._shift_right_click_fn = fn

    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_targeting_engine(self, engine):
        self._targeting_engine = engine

    def set_sqms(self, sqms: List[Tuple[int, int]]):
        """Configura las 9 posiciones de SQMs fijos del game window."""
        self._sqms = list(sqms)
        # Extraer player center y sqm_size de las posiciones
        if len(sqms) >= 9:
            self._player_center = sqms[4]  # Center
            # sqm_size = distancia entre Center y E (horizontal)
            sw = (sqms[5][0] - sqms[4][0], sqms[1][1] - sqms[4][1])
            self._sqm_size = (abs(sw[0]), abs(sw[1]))
            # Propagar al corpse detector
            self.corpse_detector.set_player_center(*self._player_center)
            self.corpse_detector.set_sqm_size(*self._sqm_size)
        self._log(f"SQMs configurados: {len(sqms)} posiciones, center={self._player_center}, sqm_size={self._sqm_size}")

    def set_game_region(self, x1: int, y1: int, x2: int, y2: int):
        """Configura la región del game window para detección visual."""
        self.corpse_detector.set_game_region(x1, y1, x2, y2)
        self._log(f"Game region para detección de cuerpos: ({x1},{y1})-({x2},{y2})")

    def set_player_center(self, x: int, y: int):
        """Establece el centro del jugador manualmente."""
        self._player_center = (x, y)

    def set_sqm_size(self, w: int, h: int):
        """Establece el tamaño de un SQM manualmente."""
        self._sqm_size = (w, h)

    def configure(self, config: dict):
        """Aplica configuración desde el dict de config."""
        cfg = config if isinstance(config, dict) else {}
        self.loot_method = cfg.get("loot_method", "left_click")
        self.free_account = cfg.get("free_account", False)
        self.loot_delay = cfg.get("loot_delay", 0.15)
        self.max_corpse_age = cfg.get("max_corpse_age", 10.0)
        self.max_loot_attempts = cfg.get("max_loot_attempts", 1)
        self.loot_cooldown = cfg.get("loot_cooldown", 0.5)
        self.periodic_loot = cfg.get("periodic_loot", False)
        self.periodic_interval = cfg.get("periodic_interval", 8.0)
        self.max_loot_sqms = cfg.get("max_loot_sqms", 9)
        self.max_range = cfg.get("max_range", 2)
        self.loot_during_combat = cfg.get("loot_during_combat", True)
        self.auto_open_next_bp = cfg.get("auto_open_next_bp", True)

        # Mapear método viejo a nuevo
        method_map = {"shift_click": "shift_right_click", "open_body": "right_click"}
        if self.loot_method in method_map:
            self.loot_method = method_map[self.loot_method]

        if self.free_account:
            self.loot_method = "left_click"
            self._log("Free account: forzando left_click (todo a BP principal)")

        self._log(f"Configurado: método={self.loot_method}, delay={self.loot_delay}s, sqms={self.max_loot_sqms}")

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Looter] {msg}")

    # ==================================================================
    # Cálculo de SQMs dinámicos
    # ==================================================================
    def _calculate_loot_sqms_around_player(self) -> List[Tuple[int, int]]:
        """
        Calcula los SQMs a lootear alrededor del player center.
        El cuerpo siempre cae en uno de los 9 SQMs del player.
        Orden: Center primero (más probable), luego espiral.
        """
        cx, cy = self._player_center
        sw, sh = self._sqm_size

        if cx == 0 or sw == 0:
            # Fallback a SQMs fijos
            return list(self._sqms)

        # Orden espiral desde el centro: Center, S, N, E, W, SE, SW, NE, NW
        offsets = [
            (0, 0),      # Center (más probable — el jugador está sobre el cuerpo)
            (0, sh),     # S
            (0, -sh),    # N
            (sw, 0),     # E
            (-sw, 0),    # W
            (sw, sh),    # SE
            (-sw, sh),   # SW
            (sw, -sh),   # NE
            (-sw, -sh),  # NW
        ]

        sqms = [(cx + dx, cy + dy) for dx, dy in offsets]
        return sqms[:self.max_loot_sqms]

    # ==================================================================
    # Kill notification (llamado por TargetingEngine)
    # ==================================================================
    def notify_kill(self, monster_name: str, x: int = 0, y: int = 0):
        """
        Recibe notificación de kill del TargetingEngine.
        x, y son coordenadas de la battle list (no del game window).
        """
        self._kill_queue.append({
            "monster": monster_name,
            "time": time.time(),
            "attempts": 0,
        })
        self._log(f"Kill recibida: {monster_name} — cola: {len(self._kill_queue)}")

    # ==================================================================
    # Loop principal
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        if not self.enabled or frame is None:
            return

        # Guardar frame para detección visual de cuerpos
        self._last_frame = frame
        now = time.time()

        # Log periódico (~cada 10s)
        if now - self._last_status_log >= 10.0:
            self._last_status_log = now
            self._log(
                f"Estado: cola={len(self._kill_queue)}, "
                f"loot_total={self.total_loots}, visual={self.visual_detections}, "
                f"ciegos={self.blind_fallbacks}, método={self.loot_method}"
            )

        # Verificar combate
        if not self.loot_during_combat and self._targeting_engine:
            if self._targeting_engine.is_in_combat():
                return

        # Limpiar kills viejas
        self._cleanup_old_kills(now)

        # ¿En medio de una secuencia de loot?
        if self.state == "looting":
            self._continue_loot_sequence(now)
            return

        # Cooldown entre secuencias
        if now - self._last_loot_time < self.loot_cooldown:
            return

        # Iniciar loot desde cola
        if self._kill_queue:
            self._start_loot_sequence(now)
            return

        # Timer periódico
        if self.periodic_loot and now - self._last_periodic_loot >= self.periodic_interval:
            self._start_periodic_loot(now)

    def _cleanup_old_kills(self, now: float):
        before = len(self._kill_queue)
        self._kill_queue = [k for k in self._kill_queue if now - k["time"] < self.max_corpse_age]
        removed = before - len(self._kill_queue)
        if removed > 0:
            self._log(f"Kills expiradas: {removed}")

    # ==================================================================
    # Secuencia de loot
    # ==================================================================
    def _start_loot_sequence(self, now: float):
        if not self._sqms and not self._player_center[0]:
            self._log("⚠ No hay SQMs configurados — presiona 'Calibrar'")
            return

        kill = self._kill_queue[0]
        kill["attempts"] += 1

        if kill["attempts"] > self.max_loot_attempts:
            removed = self._kill_queue.pop(0)
            self._log(f"Kill de {removed['monster']} descartada (max intentos)")
            return

        # ===== DETECCIÓN VISUAL DE CUERPOS =====
        # Intentar detectar cuerpos en el game window por su aura/sangre
        detected_corpses = []
        if self._use_visual_detection and self._last_frame is not None:
            detected_corpses = self.corpse_detector.detect_corpses(self._last_frame)

        if detected_corpses:
            # ¡Detectamos cuerpos! Clickear SOLO en esas posiciones
            self._loot_sqms = detected_corpses
            self.visual_detections += 1
            self._log(
                f"Looteando: {kill['monster']} — "
                f"{len(detected_corpses)} cuerpos DETECTADOS visualmente"
            )
        else:
            # Fallback: SQMs ciegos alrededor del player
            self._loot_sqms = self._calculate_loot_sqms_around_player()
            self.blind_fallbacks += 1
            self._log(
                f"Looteando: {kill['monster']} — "
                f"{len(self._loot_sqms)} SQMs ciegos (no se detectaron cuerpos)"
            )

        self.state = "looting"
        self._current_sqm_idx = 0
        self._loot_start_time = now
        self._last_click_time = 0.0

    def _start_periodic_loot(self, now: float):
        if not self._sqms and not self._player_center[0]:
            return
        self._loot_sqms = self._calculate_loot_sqms_around_player()
        self.state = "looting"
        self._current_sqm_idx = 0
        self._loot_start_time = now
        self._last_click_time = 0.0
        self._last_periodic_loot = now
        self._log("Loot periódico activado")

    def _continue_loot_sequence(self, now: float):
        # Timeout
        if now - self._loot_start_time > self.max_corpse_age:
            self._finish_loot_sequence("timeout")
            return

        # Delay entre clicks
        if now - self._last_click_time < self.loot_delay:
            return

        # ¿Terminamos todos los SQMs?
        if self._current_sqm_idx >= len(self._loot_sqms):
            self._finish_loot_sequence("completed")
            return

        # Obtener posición del SQM
        sx, sy = self._loot_sqms[self._current_sqm_idx]

        # Ejecutar click
        click_ok = self._execute_loot_click(sx, sy)

        if click_ok:
            self.total_clicks += 1
            self._last_click_time = now
            # Solo log primer y último click
            if self._current_sqm_idx == 0:
                self._log(f"Loot click #{self._current_sqm_idx+1}/{len(self._loot_sqms)} en ({sx},{sy})")

        self._current_sqm_idx += 1

    def _execute_loot_click(self, x: int, y: int) -> bool:
        if self.loot_method == "left_click":
            if self._left_click_fn:
                self._left_click_fn(x, y)
                return True
        elif self.loot_method == "right_click":
            if self._right_click_fn:
                self._right_click_fn(x, y)
                return True
        elif self.loot_method == "shift_right_click":
            if self._shift_right_click_fn:
                self._shift_right_click_fn(x, y)
                return True
            elif self._right_click_fn:
                self._right_click_fn(x, y)
                return True
        return False

    def _finish_loot_sequence(self, reason: str):
        self.state = "idle"
        self._last_loot_time = time.time()
        self.total_loots += 1

        if self._kill_queue and reason == "completed":
            removed = self._kill_queue.pop(0)
            self._log(f"Loot completado: {removed['monster']} ({len(self._loot_sqms)} clicks)")
        elif reason == "timeout":
            if self._kill_queue:
                removed = self._kill_queue.pop(0)
                self._log(f"Loot timeout: {removed['monster']}")
            else:
                self._log("Loot periódico completado")
        else:
            self._log(f"Loot terminado: {reason}")

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._running = True
        self.state = "idle"
        self._kill_queue.clear()
        self._current_sqm_idx = 0
        detect_mode = "VISUAL (aura+sangre)" if self._use_visual_detection else "SQMs ciegos"
        self._log(f"Looter v4 activado — método: {self.loot_method}, detección: {detect_mode}")
        self._log(f"  SQMs: {len(self._sqms)}, center: {self._player_center}, sqm_size: {self._sqm_size}")
        self._log(f"  Max SQMs fallback: {self.max_loot_sqms}, delay: {self.loot_delay}s")
        if not self._sqms and not self._player_center[0]:
            self._log("⚠ Sin SQMs — presiona 'Calibrar' primero")

    def stop(self):
        self.enabled = False
        self._running = False
        self.state = "idle"
        self._kill_queue.clear()
        self._log("Looter desactivado")

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "loot_method": self.loot_method,
            "free_account": self.free_account,
            "kill_queue": len(self._kill_queue),
            "total_loots": self.total_loots,
            "total_clicks": self.total_clicks,
            "visual_detections": self.visual_detections,
            "blind_fallbacks": self.blind_fallbacks,
            "sqms_configured": len(self._sqms),
            "player_center": self._player_center,
            "sqm_size": self._sqm_size,
            "periodic_loot": self.periodic_loot,
            "loot_during_combat": self.loot_during_combat,
            "visual_detection": self._use_visual_detection,
        }
