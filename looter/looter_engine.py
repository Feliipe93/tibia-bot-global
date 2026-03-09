"""
looter/looter_engine.py - Motor de auto-loot v9.

Cambios v9 (GameScreenDetector + SQMs ciegos como fallback):
  Novedad principal:
    - Integra GameScreenDetector (game_screen_detector.py) para detectar
      VISUALMENTE dónde cayó el cadáver usando frame diff o color HSV.
    - Si la detección visual falla → fallback a SQMs ciegos (igual que v8).
    - La región del game window se calcula proporcionalmente (ref 1366×768)
      y se sobreescribe con el valor exacto del screen_calibrator si está.
    - Se relaja la guarda de calibración: ahora también arranca si el GSD
      ya tiene el tamaño de frame (no depende de sqms ni player_center).

  Flujo de detección por kill:
    1. notify_kill() recibe el frame del momento del kill.
    2. Llama a gsd.update_reference_frame(frame) ANTES de dormir.
    3. El thread de loot llama a gsd.find_corpse_position(last_frame)
       DESPUÉS de dormir 0.10 s (el cadáver ya apareció).
    4. Si devuelve posición → click exacto ahí.
    5. Si devuelve None → SQMs ciegos (center + cardinales).

  Sin cambios en:
    - healer_bot.py  (NO tocado)
    - targeting_engine.py  (NO tocado)
    - Interfaz pública: set_sqms, set_game_region, notify_kill, process_frame.
"""

import time
import threading
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from looter.corpse_detector import CorpseDetector
from looter.corpse_template_detector import CorpseTemplateDetector
from looter.game_screen_detector import GameScreenDetector


class LooterEngine:
    """
    Motor de auto-loot v9.
    Recibe notificaciones de kills y ejecuta clicks en thread separado.
    v9: Intenta detección visual (frame diff / HSV) antes de SQMs ciegos.
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
        self.loot_delay: float = 0.05       # v8: más rápido (era 0.08)
        self.max_corpse_age: float = 10.0
        self.loot_cooldown: float = 0.3
        self.periodic_loot: bool = False
        self.periodic_interval: float = 8.0
        self.max_loot_sqms: int = 5          # v8: 5 (center + 4 cardinales)
        self.max_loot_clicks: int = 5        # v8: 5 clicks max por kill
        self.max_range: int = 1              # v8: 1 SQM (chase mode = adyacente)
        self.loot_during_combat: bool = True
        self.auto_open_next_bp: bool = True
        self.always_loot: bool = True

        # Timing interno
        self._last_loot_time: float = 0.0
        self._last_periodic_loot: float = 0.0
        self._loot_lock = threading.Lock()

        # Thread de loot separado (no bloquea targeting)
        self._loot_thread: Optional[threading.Thread] = None

        # Detectores visuales — mantenidos para compatibilidad con healer_bot
        # corpse_detector y corpse_template_detector: interfaz de compatibilidad
        self.corpse_detector = CorpseDetector()
        self.corpse_template_detector = CorpseTemplateDetector()
        self._last_frame: Optional[np.ndarray] = None
        self._use_visual_detection: bool = False  # v8 legacy flag

        # v9: GameScreenDetector — detección visual de cadáveres
        self.game_screen_detector = GameScreenDetector()
        self._use_game_screen_detection: bool = True  # v9: HABILITADO

        # Métricas
        self.total_loots: int = 0
        self.total_clicks: int = 0
        self.template_detections: int = 0    # legacy
        self.visual_detections: int = 0      # legacy
        self.gsd_detections: int = 0         # v9: detecciones exitosas de GSD
        self.blind_fallbacks: int = 0        # veces que se usaron SQMs ciegos
        self.thread_loots: int = 0           # loots ejecutados en thread

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
        # Propagar el log al GSD también
        self.game_screen_detector.set_log_callback(fn)

    def set_targeting_engine(self, engine):
        self._targeting_engine = engine

    def set_sqms(self, sqms: List[Tuple[int, int]]):
        """Configura las 9 posiciones de SQMs fijos del game window."""
        self._sqms = list(sqms)
        if len(sqms) >= 9:
            self._player_center = sqms[4]  # Center
            sw = (sqms[5][0] - sqms[4][0], sqms[1][1] - sqms[4][1])
            self._sqm_size = (abs(sw[0]), abs(sw[1]))
            # Configurar detectores (compatibilidad)
            self.corpse_detector.set_player_center(*self._player_center)
            self.corpse_detector.set_sqm_size(*self._sqm_size)
            self.corpse_template_detector.set_player_center(*self._player_center)
            self.corpse_template_detector.set_sqm_size(*self._sqm_size)
            # v9: propagar player center al GSD
            self.game_screen_detector.set_player_center(*self._player_center)
            # Log detallado de los SQMs para v9
            self._log(f"SQMs configurados: {len(sqms)} posiciones")
            self._log(f"  Center (idx 4): {self._player_center}")
            self._log(f"  SQM size: {self._sqm_size}")
            self._log(f"  Cardinales: S={sqms[1]}, N={sqms[7]}, E={sqms[5]}, W={sqms[3]}")
        else:
            self._log(f"SQMs parciales: {len(sqms)} posiciones (necesito 9 para modo fijo)")
        

    def set_game_region(self, x1: int, y1: int, x2: int, y2: int):
        """Configura la región del game window."""
        self.corpse_detector.set_game_region(x1, y1, x2, y2)
        self.corpse_template_detector.set_game_region(x1, y1, x2, y2)
        # v9: propagar al GSD para que use la región exacta del calibrator
        self.game_screen_detector.set_game_region_from_calibrator(x1, y1, x2, y2)

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
        self.loot_delay = cfg.get("loot_delay", 0.05)
        self.max_corpse_age = cfg.get("max_corpse_age", 10.0)
        self.loot_cooldown = cfg.get("loot_cooldown", 0.3)
        self.periodic_loot = cfg.get("periodic_loot", False)
        self.periodic_interval = cfg.get("periodic_interval", 8.0)
        self.max_loot_sqms = cfg.get("max_loot_sqms", 5)
        self.max_loot_clicks = cfg.get("max_loot_clicks", 5)
        self.max_range = cfg.get("max_range", 1)
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
    def _calculate_loot_sqms(self) -> List[Tuple[int, int]]:
        """
        Calcula los SQMs a lootear alrededor del player center.
        
        v8: MÉTODO ÚNICO Y PRINCIPAL — siempre funciona.
        
        En Tibia con chase mode, al matar una criatura el cuerpo cae en:
        - Tu propio SQM (si te paraste encima al matarla)
        - Un SQM adyacente cardinal (N/S/E/W) o diagonal
        
        IMPORTANTE: Las coordenadas están en escala de frame OBS.
        healer_bot._scaled_left_click() se encarga del escalado final.
        
        Orden: Center → S → N → E → W (los más probables en chase mode).
        Solo 5 clicks para cubrir el 95% de los casos.
        """
        # Usar SQMs fijos del calibrator si están disponibles (más preciso)
        if len(self._sqms) >= 9:
            # Los SQMs están en orden: SW, S, SE, W, Center, E, NW, N, NE
            # Reordenar para v8: Center primero, luego cardinales
            center = self._sqms[4]      # Index 4 = Center
            s = self._sqms[1]           # Index 1 = S
            n = self._sqms[7]           # Index 7 = N  
            e = self._sqms[5]           # Index 5 = E
            w = self._sqms[3]           # Index 3 = W
            
            # Orden optimizado v8
            sqms = [center, s, n, e, w]
            return sqms[:self.max_loot_sqms]
        
        # Fallback: calcular dinámicamente si no hay SQMs fijos
        cx, cy = self._player_center
        sw, sh = self._sqm_size

        if cx == 0 or sw == 0:
            return []

        # Orden optimizado para chase mode:
        # Center primero (más probable), luego cardinales
        offsets = [
            (0, 0),      # Center — cuerpo cae aquí si te paraste encima
            (0, sh),     # S  — muy común en chase mode
            (0, -sh),    # N
            (sw, 0),     # E
            (-sw, 0),    # W
        ]

        sqms = [(cx + dx, cy + dy) for dx, dy in offsets]
        return sqms[:self.max_loot_sqms]

    # ==================================================================
    # Kill notification — LOOT EN THREAD SEPARADO
    # ==================================================================
    def notify_kill(self, monster_name: str, x: int = 0, y: int = 0,
                    frame: Optional[np.ndarray] = None):
        """
        Recibe notificación de kill del TargetingEngine.
        v9: Guarda frame de referencia para GSD, luego lanza thread.

        Args:
            monster_name: Nombre del monstruo matado
            x, y: Coordenadas del último ataque (battle list — no usadas)
            frame: Frame OBS en el momento del kill (para detección visual)
        """
        if not self.enabled:
            return

        if not self._left_click_fn:
            self._log(f"Kill ignorada (sin callback de click): {monster_name}")
            return

        # v9: también permitir si GSD ya tiene tamaño de frame
        gsd_ready = self.game_screen_detector.is_ready()
        has_sqms = bool(self._sqms)
        has_center = self._player_center != (0, 0)

        if not has_sqms and not has_center and not gsd_ready:
            self._log(f"Kill ignorada (sin calibración): {monster_name}")
            return

        # v9: guardar frame de referencia ANTES de lanzar el thread
        # El thread dormirá 0.10s → en ese tiempo el cadáver aparece
        ref_frame = frame if frame is not None else self._last_frame
        if ref_frame is not None and self._use_game_screen_detection:
            self.game_screen_detector.update_reference_frame(ref_frame)

        # Si ya hay un loot en curso, esperar a que termine (no apilar)
        if self._loot_thread and self._loot_thread.is_alive():
            self._log(f"Kill de {monster_name} — esperando loot anterior...")
            self._loot_thread.join(timeout=2.0)

        # Lanzar loot en thread separado
        self._loot_thread = threading.Thread(
            target=self._loot_in_thread,
            args=(monster_name,),
            daemon=True,
            name=f"loot-{monster_name}"
        )
        self._loot_thread.start()
        self._log(f"Kill: {monster_name} — loot lanzado en thread")

    # ==================================================================
    # Ejecución de loot en thread separado
    # ==================================================================
    def _loot_in_thread(self, monster_name: str):
        """
        Ejecuta la secuencia COMPLETA de loot en un thread daemon.
        v9: Intenta detección visual (GSD) → fallback a SQMs ciegos.
        """
        try:
            with self._loot_lock:
                self.state = "looting"
                self.thread_loots += 1

                # Pequeña pausa para que el cadáver aparezca en pantalla
                time.sleep(0.10)

                # ── v9: intentar detección visual del cadáver ──────────────
                positions: List[Tuple[int, int]] = []
                gsd_used = False

                if self._use_game_screen_detection and self._last_frame is not None:
                    gsd_pos = self.game_screen_detector.find_corpse_position(
                        self._last_frame, monster_name
                    )
                    if gsd_pos is not None:
                        # GSD detectó el cadáver — click exacto ahí
                        positions = [gsd_pos]
                        gsd_used = True
                        self.gsd_detections += 1
                        self._log(
                            f"GSD detectó cadáver en OBS{gsd_pos} → click exacto"
                        )

                # ── Fallback: SQMs ciegos ──────────────────────────────────
                if not positions:
                    positions = self._calculate_loot_sqms()
                    self.blind_fallbacks += 1
                    source = "SQMs_fijos" if len(self._sqms) >= 9 else "dinámico"

                    # Último recurso: SQMs proporcionales del GSD
                    if not positions and self.game_screen_detector.is_ready():
                        positions = self.game_screen_detector.get_proportional_sqms(
                            self.max_loot_sqms
                        )
                        source = "GSD_proporcional"

                    if not positions:
                        self._log(f"Sin SQMs para lootear {monster_name}")
                        self.state = "idle"
                        return

                    self._log(
                        f"GSD sin detección → fallback {source}, "
                        f"player_center={self._player_center}"
                    )

                # Limitar clicks
                clicks_target = min(len(positions), self.max_loot_clicks)
                positions = positions[:clicks_target]

                coords_str = " → ".join(f"({x},{y})" for x, y in positions)
                metodo = "GSD_visual" if gsd_used else "ciegos"
                self._log(
                    f"Looteando: {monster_name} — {metodo} "
                    f"{clicks_target} clicks: {coords_str}"
                )

                # Ejecutar clicks
                clicks_done = 0
                for i, (sx, sy) in enumerate(positions):
                    if not self.enabled:
                        break
                    ok = self._execute_loot_click(sx, sy)
                    if ok:
                        clicks_done += 1
                        self.total_clicks += 1
                    # Delay entre clicks (excepto el último)
                    if i < clicks_target - 1:
                        time.sleep(self.loot_delay)

                self.total_loots += 1
                self._last_loot_time = time.time()
                self.state = "idle"
                self._log(
                    f"Loot OK: {monster_name} — {clicks_done}/{clicks_target} clicks"
                )

        except Exception as e:
            self._log(f"ERROR en loot thread para {monster_name}: {e}")
            self.state = "idle"

    def _execute_loot_click(self, x: int, y: int) -> bool:
        """
        Ejecuta UN click de loot en la posición dada.
        Las coordenadas están en frame OBS, healer_bot se encarga del escalado.
        """
        if self.loot_method == "left_click":
            if self._left_click_fn:
                try:
                    self._left_click_fn(x, y)
                    return True
                except Exception as e:
                    self._log(f"Error en left_click({x},{y}): {e}")
                    return False
        elif self.loot_method == "right_click":
            if self._right_click_fn:
                try:
                    self._right_click_fn(x, y)
                    return True
                except Exception as e:
                    self._log(f"Error en right_click({x},{y}): {e}")
                    return False
        elif self.loot_method == "shift_right_click":
            if self._shift_right_click_fn:
                try:
                    self._shift_right_click_fn(x, y)
                    return True
                except Exception as e:
                    self._log(f"Error en shift_right_click({x},{y}): {e}")
                    return False
            elif self._right_click_fn:
                try:
                    self._right_click_fn(x, y)
                    return True
                except Exception as e:
                    self._log(f"Error en right_click fallback({x},{y}): {e}")
                    return False
        
        self._log(f"Sin callback para método {self.loot_method}")
        return False

    # ==================================================================
    # Loop principal (llamado por dispatcher — solo status + periódico)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """
        Llamado por el dispatcher cada frame.
        v9: Inicializa GSD con tamaño de frame + log periódico + loot periódico.
        """
        if not self.enabled or frame is None:
            return

        self._last_frame = frame
        now = time.time()

        # v9: Inicializar GSD con tamaño de frame (solo la primera vez o si cambia)
        fh, fw = frame.shape[:2]
        if self.game_screen_detector._frame_w != fw or \
                self.game_screen_detector._frame_h != fh:
            self.game_screen_detector.set_frame_size(fw, fh)

        # Log periódico (~cada 15s)
        if now - self._last_status_log >= 15.0:
            self._last_status_log = now
            self._log(
                f"v9 Estado: loots={self.total_loots}, "
                f"clicks={self.total_clicks}, "
                f"gsd={self.gsd_detections}, "
                f"ciegos={self.blind_fallbacks}, "
                f"método={self.loot_method}"
            )

        # Ya estamos looteando → no interferir
        if self.state == "looting":
            return

        # Loot periódico (recoger items sueltos sin kill)
        if self.periodic_loot and now - self._last_periodic_loot >= self.periodic_interval:
            self._last_periodic_loot = now
            # Periódico también en thread para no bloquear
            t = threading.Thread(
                target=self._loot_in_thread,
                args=("Periódico",),
                daemon=True,
                name="loot-periodic"
            )
            t.start()

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._running = True
        self.state = "idle"
        # Cargar templates para compatibilidad (no se usan para detección)
        self.corpse_template_detector.load_templates()
        self._log(f"Looter v9 activado — GSD visual + SQMs ciegos (fallback)")
        self._log(f"  Método click: {self.loot_method}, cuenta: {self.account_type}")
        self._log(f"  SQMs calibrados: {len(self._sqms)} posiciones")
        self._log(f"  GSD listo: {self.game_screen_detector.is_ready()}")
        if len(self._sqms) >= 9:
            center = self._sqms[4]
            self._log(f"  SQMs fijos: Center={center}, usando índices [4,1,7,5,3]")
        else:
            self._log(f"  SQMs dinámicos: center={self._player_center}, sqm_size={self._sqm_size}")
        self._log(f"  Max clicks: {self.max_loot_clicks}, delay: {self.loot_delay}s")
        self._log(f"  Detección GSD: {'HABILITADA' if self._use_game_screen_detection else 'DESHABILITADA'}")

        # Verificar calibración
        gsd_ok = self.game_screen_detector.is_ready()
        if len(self._sqms) < 9 and self._player_center == (0, 0) and not gsd_ok:
            self._log("⚠ ADVERTENCIA: Sin calibración completa — presiona 'Calibrar' primero")
            self._log("  El loot funcionará cuando se calibren las coordenadas")
        elif len(self._sqms) >= 9:
            self._log("✓ Calibración OK — usando SQMs fijos del screen_calibrator")
        elif gsd_ok:
            self._log("✓ GSD OK — usando proporciones de game window")

    def stop(self):
        self.enabled = False
        self._running = False
        self.state = "idle"
        # Esperar a que termine el thread de loot si hay uno activo
        if self._loot_thread and self._loot_thread.is_alive():
            self._loot_thread.join(timeout=1.0)
        self._log("Looter v9 desactivado")

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "loot_method": self.loot_method,
            "account_type": self.account_type,
            "kill_queue": 0,
            "total_loots": self.total_loots,
            "total_clicks": self.total_clicks,
            "template_detections": self.template_detections,
            "visual_detections": self.visual_detections,
            "gsd_detections": self.gsd_detections,
            "blind_fallbacks": self.blind_fallbacks,
            "thread_loots": self.thread_loots,
            "corpse_templates": len(self.corpse_template_detector._templates),
            "sqms_configured": len(self._sqms),
            "player_center": self._player_center,
            "sqm_size": self._sqm_size,
            "periodic_loot": self.periodic_loot,
            "loot_during_combat": self.loot_during_combat,
            "visual_detection": self._use_visual_detection,
            "gsd_ready": self.game_screen_detector.is_ready(),
            "gsd_enabled": self._use_game_screen_detection,
        }

    def debug_coordinates(self) -> Dict:
        """Retorna información detallada de coordenadas para debugging."""
        loot_sqms = self._calculate_loot_sqms()
        return {
            "sqms_available": len(self._sqms),
            "sqms_fixed": self._sqms if len(self._sqms) >= 9 else [],
            "player_center": self._player_center,
            "sqm_size": self._sqm_size,
            "calculated_loot_sqms": loot_sqms,
            "max_loot_sqms": self.max_loot_sqms,
            "using_fixed_sqms": len(self._sqms) >= 9,
        }

    def test_loot_clicks(self, monster_name: str = "TEST") -> bool:
        """
        Prueba manual de clicks de loot para verificar coordenadas.
        Útil para debugging — ejecuta 1 secuencia de loot sin kill real.
        """
        if not self.enabled:
            self._log("Test ignorado — looter deshabilitado")
            return False
        
        if not self._left_click_fn:
            self._log("Test ignorado — sin callback de click")
            return False
        
        # Calcular posiciones
        positions = self._calculate_loot_sqms()
        if not positions:
            self._log("Test ignorado — sin SQMs calculados")
            return False
        
        # Ejecutar test en thread separado (igual que loot real)
        self._log(f"🧪 TEST LOOT iniciado — {len(positions)} SQMs")
        thread = threading.Thread(
            target=self._loot_in_thread,
            args=(f"TEST-{monster_name}",),
            daemon=True,
            name="test-loot"
        )
        thread.start()
        return True
