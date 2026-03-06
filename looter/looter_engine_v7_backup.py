"""
looter/looter_engine.py - Motor de auto-loot v7.

Cambios v7 (loot inmediato — fix definitivo):
  - notify_kill() ejecuta loot INMEDIATAMENTE (sin cola, sin depender del dispatcher)
  - NO depende de process_frame para lootear — process_frame solo hace loot periódico
  - Método principal: SQMs ciegos 3×3 alrededor del player (SIEMPRE funciona)
  - HSV/template como bonus SOLO si detectan pocas posiciones (≤ max_loot_clicks)
  - Si HSV devuelve muchas posiciones = falso positivo → usa SQMs ciegos
  - Loot se ejecuta en el mismo hilo del targeting (blocking, simple)
  - Compatible con free account: left-click en el cuerpo en el game screen
  
Problemas que arregla:
  - v6 dependía del dispatcher habilitado para process_frame → si el módulo looter
    estaba deshabilitado en el dispatcher, notify_kill llenaba la cola infinitamente
    pero process_frame nunca la vaciaba.
  - HSV detectaba 17+ posiciones (falsos positivos por verde del suelo) → ahora
    descarta si hay demasiadas detecciones.
"""

import time
import threading
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from looter.corpse_detector import CorpseDetector
from looter.corpse_template_detector import CorpseTemplateDetector


class LooterEngine:
    """
    Motor de auto-loot v7.
    Recibe notificaciones de kills y ejecuta clicks INMEDIATAMENTE.
    No depende del dispatcher para lootear.
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"     # idle, looting
        self._running: bool = False

        # Callbacks inyectados
        self._left_click_fn: Optional[Callable] = None
        self._right_click_fn: Optional[Callable] = None
        self._shift_right_click_fn: Optional[Callable] = None
        self._log_fn: Optional[Callable] = None
        self._targeting_engine = None

        # Posiciones de los 9 SQMs fijos (inyectados por screen_calibrator)
        self._sqms: List[Tuple[int, int]] = []

        # Player center y SQM size (para calcular SQMs dinámicos)
        self._player_center: Tuple[int, int] = (0, 0)
        self._sqm_size: Tuple[int, int] = (0, 0)

        # Configuración
        self.loot_method: str = "left_click"
        self.account_type: str = "premium"
        self.loot_delay: float = 0.08
        self.max_corpse_age: float = 10.0
        self.loot_cooldown: float = 0.3
        self.periodic_loot: bool = False
        self.periodic_interval: float = 8.0
        self.max_loot_sqms: int = 9
        self.max_loot_clicks: int = 3
        self.max_range: int = 2
        self.loot_during_combat: bool = True
        self.auto_open_next_bp: bool = True
        self.always_loot: bool = True

        # Timing interno
        self._last_loot_time: float = 0.0
        self._last_periodic_loot: float = 0.0
        self._loot_lock = threading.Lock()

        # Cola de kills — v7 la usa solo como fallback si el loot inmediato falla
        self._kill_queue: List[Dict] = []

        # Detector visual de cuerpos (aura de muerte + blood splashes)
        self.corpse_detector = CorpseDetector()
        self._last_frame: Optional[np.ndarray] = None
        self._use_visual_detection: bool = True

        # Detector por template matching de sprites de cadáveres
        self.corpse_template_detector = CorpseTemplateDetector()

        # Métricas
        self.total_loots: int = 0
        self.total_clicks: int = 0
        self.template_detections: int = 0
        self.visual_detections: int = 0
        self.blind_fallbacks: int = 0

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
        if len(sqms) >= 9:
            self._player_center = sqms[4]  # Center
            sw = (sqms[5][0] - sqms[4][0], sqms[1][1] - sqms[4][1])
            self._sqm_size = (abs(sw[0]), abs(sw[1]))
            self.corpse_detector.set_player_center(*self._player_center)
            self.corpse_detector.set_sqm_size(*self._sqm_size)
            self.corpse_template_detector.set_player_center(*self._player_center)
            self.corpse_template_detector.set_sqm_size(*self._sqm_size)
        self._log(f"SQMs configurados: {len(sqms)} posiciones, center={self._player_center}, sqm_size={self._sqm_size}")

    def set_game_region(self, x1: int, y1: int, x2: int, y2: int):
        """Configura la región del game window para detección visual."""
        self.corpse_detector.set_game_region(x1, y1, x2, y2)
        self.corpse_template_detector.set_game_region(x1, y1, x2, y2)
        self._log(f"Game region para detección de cuerpos: ({x1},{y1})-({x2},{y2})")

    def set_player_center(self, x: int, y: int):
        self._player_center = (x, y)

    def set_sqm_size(self, w: int, h: int):
        self._sqm_size = (w, h)

    def configure(self, config: dict):
        """Aplica configuración desde el dict de config."""
        cfg = config if isinstance(config, dict) else {}
        self.loot_method = cfg.get("loot_method", "left_click")
        if "account_type" in cfg:
            self.account_type = cfg.get("account_type", "premium")
        elif cfg.get("free_account", False):
            self.account_type = "free"
        else:
            self.account_type = "premium"
        self.loot_delay = cfg.get("loot_delay", 0.08)
        self.max_corpse_age = cfg.get("max_corpse_age", 10.0)
        self.loot_cooldown = cfg.get("loot_cooldown", 0.3)
        self.periodic_loot = cfg.get("periodic_loot", False)
        self.periodic_interval = cfg.get("periodic_interval", 8.0)
        self.max_loot_sqms = cfg.get("max_loot_sqms", 9)
        self.max_loot_clicks = cfg.get("max_loot_clicks", 3)
        self.max_range = cfg.get("max_range", 2)
        self.loot_during_combat = cfg.get("loot_during_combat", True)
        self.auto_open_next_bp = cfg.get("auto_open_next_bp", True)
        self.always_loot = cfg.get("always_loot", True)

        method_map = {"shift_click": "shift_right_click", "open_body": "right_click"}
        if self.loot_method in method_map:
            self.loot_method = method_map[self.loot_method]

        if self.account_type == "premium":
            self._log(f"Cuenta PREMIUM — el cliente organiza el loot automáticamente")
        else:
            self._log(f"Cuenta FREE — loot va a BP principal")
        self._log(f"Configurado: método={self.loot_method}, delay={self.loot_delay}s, "
                  f"max_clicks={self.max_loot_clicks}, cuenta={self.account_type}")

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Looter] {msg}")

    # ==================================================================
    # Cálculo de SQMs ciegos alrededor del player
    # ==================================================================
    def _calculate_loot_sqms_around_player(self) -> List[Tuple[int, int]]:
        """
        Calcula los SQMs a lootear alrededor del player center.
        Orden: Center primero, luego los 8 adyacentes.
        MÉTODO PRINCIPAL — siempre funciona, no depende de detección visual.
        
        En Tibia, cuando matas una criatura estando en chase mode,
        el cuerpo cae en tu SQM o en un SQM adyacente (1 tile de distancia).
        Clickear los 3 SQMs más probables es suficiente.
        """
        cx, cy = self._player_center
        sw, sh = self._sqm_size

        if cx == 0 or sw == 0:
            return list(self._sqms) if self._sqms else []

        # Orden optimizado: center, luego los 4 cardinales, luego diagonales
        offsets = [
            (0, 0),      # Center (cuerpo puede caer aquí)
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
    # Detección de cadáveres (visual con fallback ciego)
    # ==================================================================
    def _detect_corpse_positions(self, frame: Optional[np.ndarray]) -> Tuple[List[Tuple[int, int]], str]:
        """
        Detecta posiciones de cadáveres.
        
        Estrategia v7:
        1. Template matching → si encuentra 1-3 posiciones → usar esas (más preciso)
        2. HSV (aura/sangre) → SOLO si encuentra ≤ max_loot_clicks posiciones
           (si hay más = falso positivo por verde/café del terreno)
        3. SQMs ciegos 3×3 → SIEMPRE como fallback (nunca falla)
        """
        max_visual = self.max_loot_clicks  # Máx posiciones confiables

        if frame is None:
            self.blind_fallbacks += 1
            return self._calculate_loot_sqms_around_player(), "blind"

        # Nivel 1: Templates de cadáveres (más preciso)
        if self.corpse_template_detector.enabled and len(self.corpse_template_detector._templates) > 0:
            tpl_results = self.corpse_template_detector.detect_corpse_positions(frame)
            if tpl_results and len(tpl_results) <= max_visual:
                self.template_detections += 1
                return tpl_results, "template"

        # Nivel 2: HSV (aura + sangre) — solo si pocas detecciones
        if self._use_visual_detection:
            hsv_results = self.corpse_detector.detect_corpses(frame)
            if hsv_results and len(hsv_results) <= max_visual:
                self.visual_detections += 1
                return hsv_results, "hsv"
            # >max_visual posiciones = falso positivo → ignorar

        # Nivel 3: SQMs ciegos (siempre funciona)
        self.blind_fallbacks += 1
        return self._calculate_loot_sqms_around_player(), "blind"

    # ==================================================================
    # Kill notification — LOOT INMEDIATO (llamado por TargetingEngine)
    # ==================================================================
    def notify_kill(self, monster_name: str, x: int = 0, y: int = 0,
                    frame: Optional[np.ndarray] = None):
        """
        Recibe notificación de kill del TargetingEngine.
        EJECUTA LOOT INMEDIATAMENTE — no usa cola ni depende del dispatcher.
        
        Args:
            monster_name: Nombre del monstruo matado
            x, y: Coordenadas del último ataque (battle list coords — no usadas para loot)
            frame: Frame actual del OBS para detección visual de cadáveres
        """
        if not self.enabled:
            self._log(f"Kill ignorada (looter deshabilitado): {monster_name}")
            return

        if not self._left_click_fn:
            self._log(f"Kill ignorada (sin callback de click): {monster_name}")
            return

        # Si no tenemos SQMs ni player center, no podemos lootear
        if not self._sqms and self._player_center == (0, 0):
            self._log(f"Kill ignorada (sin calibración): {monster_name}")
            return

        self._log(f"Kill recibida: {monster_name} — looteando INMEDIATO")

        # Ejecutar loot directamente (blocking en el hilo del targeting)
        with self._loot_lock:
            self._loot_immediate(monster_name, frame)

    # ==================================================================
    # Ejecución inmediata de loot
    # ==================================================================
    def _loot_immediate(self, monster_name: str, frame: Optional[np.ndarray]):
        """
        Ejecuta la secuencia COMPLETA de loot para un kill.
        Hace clicks directamente con time.sleep entre ellos.
        BLOQUEA hasta terminar (se ejecuta en el hilo del targeting).
        """
        self.state = "looting"

        # Detectar posiciones de cadáveres
        positions, method = self._detect_corpse_positions(frame)

        if not positions:
            self._log(f"Sin posiciones para lootear {monster_name}")
            self.state = "idle"
            return

        # Limitar al máximo de clicks por kill
        if len(positions) > self.max_loot_clicks:
            positions = positions[:self.max_loot_clicks]

        method_label = {
            "template": f"TEMPLATE ({len(positions)} pos)",
            "hsv": f"HSV ({len(positions)} pos)",
            "blind": f"SQMs ciegos ({len(positions)} pos)",
        }.get(method, method)

        self._log(f"Looteando: {monster_name} — {method_label}")

        # Ejecutar clicks directamente con delay (blocking)
        clicks_done = 0
        for i, (sx, sy) in enumerate(positions):
            if not self.enabled:
                break
            ok = self._execute_loot_click(sx, sy)
            if ok:
                clicks_done += 1
                self.total_clicks += 1
            # Delay entre clicks (excepto el último)
            if i < len(positions) - 1:
                time.sleep(self.loot_delay)

        self.total_loots += 1
        self._last_loot_time = time.time()
        self.state = "idle"
        self._log(f"Loot completado: {monster_name} — {clicks_done} clicks ({method})")

    def _execute_loot_click(self, x: int, y: int) -> bool:
        """Ejecuta UN click de loot en la posición dada."""
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

    # ==================================================================
    # Loop principal (llamado por dispatcher — solo periódico + status)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """
        Llamado por el dispatcher cada frame.
        En v7 este método SOLO hace:
        - Log periódico de estado
        - Loot periódico (recoger items sueltos sin kill)
        
        El loot principal se ejecuta en notify_kill() directamente.
        """
        if not self.enabled or frame is None:
            return

        self._last_frame = frame
        now = time.time()

        # Log periódico (~cada 10s)
        if now - self._last_status_log >= 10.0:
            self._last_status_log = now
            self._log(
                f"Estado: loot_total={self.total_loots}, "
                f"tpl={self.template_detections}, "
                f"hsv={self.visual_detections}, "
                f"ciegos={self.blind_fallbacks}, "
                f"método={self.loot_method}"
            )

        # Ya estamos looteando → no interferir
        if self.state == "looting":
            return

        # Loot periódico (recoger items sueltos sin kill)
        if self.periodic_loot and now - self._last_periodic_loot >= self.periodic_interval:
            self._last_periodic_loot = now
            with self._loot_lock:
                self._loot_immediate("Periódico", frame)

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._running = True
        self.state = "idle"
        tpl_count = self.corpse_template_detector.load_templates()
        detect_mode = f"TPL({tpl_count})+HSV+Blind" if self._use_visual_detection else "SQMs ciegos"
        self._log(f"Looter v7 activado — método: {self.loot_method}, detección: {detect_mode}")
        self._log(f"  SQMs: {len(self._sqms)}, center: {self._player_center}, sqm_size: {self._sqm_size}")
        self._log(f"  Max clicks: {self.max_loot_clicks}, delay: {self.loot_delay}s, cooldown: {self.loot_cooldown}s")
        if not self._sqms and not self._player_center[0]:
            self._log("⚠ Sin SQMs — presiona 'Calibrar' primero")

    def stop(self):
        self.enabled = False
        self._running = False
        self.state = "idle"
        self._log("Looter desactivado")

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "loot_method": self.loot_method,
            "account_type": self.account_type,
            "kill_queue": 0,  # v7 no usa cola
            "total_loots": self.total_loots,
            "total_clicks": self.total_clicks,
            "template_detections": self.template_detections,
            "visual_detections": self.visual_detections,
            "blind_fallbacks": self.blind_fallbacks,
            "corpse_templates": len(self.corpse_template_detector._templates),
            "sqms_configured": len(self._sqms),
            "player_center": self._player_center,
            "sqm_size": self._sqm_size,
            "periodic_loot": self.periodic_loot,
            "loot_during_combat": self.loot_during_combat,
            "visual_detection": self._use_visual_detection,
        }
