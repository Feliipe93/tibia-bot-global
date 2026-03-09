"""
looter/looter_engine.py - Motor de auto-loot v11.

Cambios v11 (Corpse Sprite Detection):
  Novedad principal:
    - Detección de cadáveres por TEMPLATE MATCHING de sprites capturados.
    - El usuario captura fotos 32x32 de los cadáveres desde la GUI.
    - Al matar, el bot busca ESE sprite en el game screen y clickea exacto.

  Prioridad de looteo:
    1. Corpse Sprite Detection (template matching del cadáver) → clicks exactos
    2. SQMs ciegos (center + 4 cardinales) → fallback que siempre funciona

  Mejoras vs v10:
    - Espera 0.30s después del kill para que el cadáver aparezca (era 0.10s)
    - Usa frame FRESCO (post-kill) para buscar el cadáver
    - Busca MÚLTIPLES cadáveres del mismo tipo (no solo 1)
    - Cada cadáver encontrado = 1 click preciso en su posición
    - Fallback SIEMPRE incluye 5 clicks (center + 4 cardinales)

  Sin cambios en interfaz pública: set_sqms, set_game_region, process_frame.
"""

import time
import threading
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from looter.corpse_detector import CorpseDetector
from looter.corpse_template_detector import CorpseTemplateDetector
from looter.game_screen_detector import GameScreenDetector
from looter.corpse_sprite_detector import CorpseSpriteDetector


class LooterEngine:
    """
    Motor de auto-loot v11.
    Recibe notificaciones de kills y ejecuta clicks en thread separado.
    v11: Busca cadáveres por sprite template matching, fallback a SQMs ciegos.
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
        self.loot_delay: float = 0.15       # delay entre clicks (Tibia necesita ≥150ms)
        self.max_corpse_age: float = 10.0
        self.loot_cooldown: float = 0.3
        self.periodic_loot: bool = False
        self.periodic_interval: float = 8.0
        self.max_loot_sqms: int = 5          # center + 4 cardinales
        self.max_loot_clicks: int = 5        # clicks max por kill
        self.max_range: int = 1              # 1 SQM (chase mode = adyacente)
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
        self.corpse_detector = CorpseDetector()
        self.corpse_template_detector = CorpseTemplateDetector()
        self._last_frame: Optional[np.ndarray] = None
        self._use_visual_detection: bool = False  # legacy flag

        # v9: GameScreenDetector — mantenido por compatibilidad
        self.game_screen_detector = GameScreenDetector()
        self._use_game_screen_detection: bool = False  # v11: DESHABILITADO

        # v11: Corpse Sprite Detector — MÉTODO PRINCIPAL
        self.corpse_sprite_detector = CorpseSpriteDetector()
        self._use_sprite_detection: bool = True  # v11: HABILITADO
        self.sprite_loot_clicks: int = 0  # clicks exitosos con sprite detection

        # v10 legacy: death_position (mantenido por compatibilidad de interfaz)
        self._death_position: Optional[Tuple[int, int]] = None
        self._use_death_position: bool = False  # v11: DESHABILITADO
        self.death_position_loots: int = 0

        # Métricas
        self.total_loots: int = 0
        self.total_clicks: int = 0
        self.template_detections: int = 0    # legacy
        self.visual_detections: int = 0      # legacy
        self.gsd_detections: int = 0         # legacy
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
        # Propagar el log al GSD y al sprite detector
        self.game_screen_detector.set_log_callback(fn)
        self.corpse_sprite_detector.set_log_callback(fn)

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
            # v11: propagar al sprite detector
            self.corpse_sprite_detector.set_player_center(*self._player_center)
            self.corpse_sprite_detector.set_sqm_size(*self._sqm_size)
            # Log detallado de los SQMs para v11
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
        # v11: propagar al sprite detector
        self.corpse_sprite_detector.set_game_region(x1, y1, x2, y2)

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
        self.loot_delay = max(cfg.get("loot_delay", 0.15), 0.15)  # mínimo 150ms
        self.max_corpse_age = cfg.get("max_corpse_age", 10.0)
        self.loot_cooldown = cfg.get("loot_cooldown", 0.3)
        self.periodic_loot = cfg.get("periodic_loot", False)
        self.periodic_interval = cfg.get("periodic_interval", 8.0)
        raw_sqms = cfg.get("max_loot_sqms", 5)
        self.max_loot_sqms = max(int(raw_sqms), 5)  # mínimo 5 (center + 4 cardinales)
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
                    frame: Optional[np.ndarray] = None,
                    death_position: Optional[Tuple[int, int]] = None):
        """
        Recibe notificación de kill del TargetingEngine.
        v11: Lanza thread que espera al cadáver y busca por sprite.

        Args:
            monster_name: Nombre del monstruo matado
            x, y: Coordenadas del último ataque (battle list)
            frame: Frame OBS en el momento del kill (referencia)
            death_position: Legacy v10 (no se usa en v11)
        """
        if not self.enabled:
            return

        if not self._left_click_fn:
            self._log(f"Kill ignorada (sin callback de click): {monster_name}")
            return

        has_sqms = bool(self._sqms)
        has_center = self._player_center != (0, 0)

        if not has_sqms and not has_center:
            self._log(f"Kill ignorada (sin calibración): {monster_name}")
            return

        # Si ya hay un loot en curso, NO bloquear — simplemente loguear y lanzar
        # El _loot_lock dentro de _loot_in_thread se encarga de serializar
        if self._loot_thread and self._loot_thread.is_alive():
            self._log(f"Kill de {monster_name} — loot anterior en curso, encolando")

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
        v11: Prioridad: sprite detection → SQMs ciegos.

        IMPORTANTE: Espera 0.30s ANTES de buscar el cadáver para que
        el sprite del cadáver aparezca en pantalla después de la muerte.
        Luego usa el frame MÁS RECIENTE (self._last_frame) que el
        dispatcher actualiza cada frame en process_frame().
        """
        try:
            with self._loot_lock:
                self.state = "looting"
                self.thread_loots += 1

                # ═══ ESPERA para que aparezca el cadáver ═══
                # En Tibia, el cadáver aparece ~0.2-0.3s después de morir
                time.sleep(0.30)

                # ═══ PRIORIDAD 1: Sprite Detection del cadáver ═══
                positions: List[Tuple[int, int]] = []
                source_method = "unknown"

                if (self._use_sprite_detection and
                        self.corpse_sprite_detector.has_template(monster_name) and
                        self._last_frame is not None):
                    # Usar el frame MÁS RECIENTE (actualizado por process_frame)
                    fresh_frame = self._last_frame
                    matches = self.corpse_sprite_detector.find_corpses(
                        fresh_frame, monster_name, max_results=5
                    )
                    if matches:
                        positions = [(x, y) for x, y, conf in matches]
                        source_method = "sprite_detection"
                        self.sprite_loot_clicks += len(positions)
                        best_conf = matches[0][2]
                        self._log(
                            f"🎯 Sprite: {len(matches)} cadáver(es) de "
                            f"{monster_name} encontrado(s), "
                            f"mejor conf={best_conf:.3f}"
                        )
                    else:
                        self._log(
                            f"Sprite: No se encontró cadáver de {monster_name} "
                            f"(template exists, 0 matches)"
                        )

                # ═══ PRIORIDAD 2 (FALLBACK): SQMs ciegos ═══
                if not positions:
                    positions = self._calculate_loot_sqms()
                    self.blind_fallbacks += 1
                    source_method = "SQMs_ciegos"

                    if not positions:
                        self._log(f"Sin SQMs para lootear {monster_name}")
                        self.state = "idle"
                        return

                    self._log(
                        f"Fallback SQMs ciegos: {len(positions)} posiciones, "
                        f"center={self._player_center}"
                    )

                # ═══ EJECUTAR CLICKS ═══
                clicks_target = min(len(positions), self.max_loot_clicks)
                positions = positions[:clicks_target]

                coords_str = " → ".join(f"({x},{y})" for x, y in positions)
                self._log(
                    f"Looteando: {monster_name} — {source_method} "
                    f"{clicks_target} clicks: {coords_str}"
                )

                # Espera pre-loot: dar tiempo a que el targeting deje de clickear
                time.sleep(0.10)

                clicks_done = 0
                for i, (sx, sy) in enumerate(positions):
                    if not self.enabled:
                        break
                    ok = self._execute_loot_click(sx, sy)
                    if ok:
                        clicks_done += 1
                        self.total_clicks += 1
                    # Delay entre clicks (Tibia necesita ≥150ms para registrar)
                    if i < clicks_target - 1:
                        time.sleep(self.loot_delay)

                self.total_loots += 1
                self._last_loot_time = time.time()
                self.state = "idle"
                self._log(
                    f"Loot OK: {monster_name} — {clicks_done}/{clicks_target} clicks "
                    f"({source_method})"
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
                f"v11 Estado: loots={self.total_loots}, "
                f"clicks={self.total_clicks}, "
                f"sprite={self.sprite_loot_clicks}, "
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
        # v11: Cargar sprites de cadáveres
        sprite_count = self.corpse_sprite_detector.load_templates()
        sprite_names = self.corpse_sprite_detector.get_loaded_names()

        self._log(f"Looter v11 activado — Sprite Detection + SQMs ciegos (fallback)")
        self._log(f"  Método click: {self.loot_method}, cuenta: {self.account_type}")
        self._log(f"  SQMs calibrados: {len(self._sqms)} posiciones")
        if sprite_count > 0:
            self._log(f"  🎯 Sprites de cadáveres: {sprite_count} ({sprite_names})")
        else:
            self._log(f"  ⚠ Sin sprites de cadáveres — usando SQMs ciegos")
            self._log(f"    💡 Captura sprites en la pestaña Looter para loot preciso")
        self._log(f"  Prioridad: Sprite Detection → SQMs ciegos")
        if len(self._sqms) >= 9:
            center = self._sqms[4]
            self._log(f"  SQMs fijos: Center={center}, usando índices [4,1,7,5,3]")
        else:
            self._log(f"  SQMs dinámicos: center={self._player_center}, sqm_size={self._sqm_size}")
        self._log(f"  Max clicks: {self.max_loot_clicks}, delay: {self.loot_delay}s")

        # Verificar calibración
        if len(self._sqms) < 9 and self._player_center == (0, 0):
            self._log("⚠ ADVERTENCIA: Sin calibración — presiona 'Calibrar' primero")
        elif len(self._sqms) >= 9:
            self._log("✓ Calibración OK — SQMs fijos del screen_calibrator")

    def stop(self):
        self.enabled = False
        self._running = False
        self.state = "idle"
        # Esperar a que termine el thread de loot si hay uno activo
        if self._loot_thread and self._loot_thread.is_alive():
            self._loot_thread.join(timeout=1.0)
        self._log("Looter v11 desactivado")

    def get_status(self) -> Dict:
        sprite_status = self.corpse_sprite_detector.get_status()
        return {
            "enabled": self.enabled,
            "state": self.state,
            "loot_method": self.loot_method,
            "account_type": self.account_type,
            "kill_queue": 0,
            "total_loots": self.total_loots,
            "total_clicks": self.total_clicks,
            "sprite_loot_clicks": self.sprite_loot_clicks,
            "template_detections": self.template_detections,
            "visual_detections": self.visual_detections,
            "gsd_detections": self.gsd_detections,
            "death_position_loots": self.death_position_loots,
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
            "sprite_detection_enabled": self._use_sprite_detection,
            "sprite_detector": sprite_status,
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
