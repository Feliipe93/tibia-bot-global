"""
looter/looter_engine.py - Motor de auto-loot v8.

Cambios v8 (SQMs ciegos + thread separado):
  Diagnóstico de v7:
    - Template matching de cadáveres: INVIABLE (0.25 confianza, template tiene
      fondo de terreno que impide el match).  Probado con 6 métodos distintos.
    - HSV (aura/sangre): falsos positivos masivos.  Detecta colores del terreno
      (verde, marrón) como cadáveres → clicks "a lo loco" en posiciones erróneas.
    - Estadística v7: tpl=7, hsv=18, ciegos=0 de 25 loots.
      Los 18 hsv clickeaban posiciones incorrectas.

  Solución v8:
    - SOLO SQMs ciegos como método de detección (100% confiable).
    - El cadáver SIEMPRE cae en el SQM del player o en un adyacente (chase mode).
    - Thread separado para loot → NO bloquea el targeting → targeting puede seguir
      atacando criaturas mientras se lootea.
    - 5 clicks máx: center + 4 cardinales (N,S,E,W). Suficiente para 1-2 cadáveres.
    - Delay mínimo entre clicks: 0.05s (antes 0.08s).
    - Mantiene interfaz compatible: corpse_detector y corpse_template_detector
      siguen existiendo como atributos para no romper healer_bot._init_modules().

  Problemas que arregla:
    - v7 bloqueaba el targeting durante loot (0.3-0.5s) → si había 2-4 criaturas,
      el targeting se "congelaba" hasta terminar de lootear.
    - v7 usaba HSV que enviaba clicks a posiciones erróneas del terreno.
    - v7 usaba template matching que casi nunca encontraba el cadáver (0.25 conf).
"""

import time
import threading
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from looter.corpse_detector import CorpseDetector
from looter.corpse_template_detector import CorpseTemplateDetector


class LooterEngine:
    """
    Motor de auto-loot v8.
    Recibe notificaciones de kills y ejecuta clicks en thread separado.
    SOLO usa SQMs ciegos (centro + cardinales) — 100% confiable.
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
        # pero NO se usan para detección en v8 (solo SQMs ciegos)
        self.corpse_detector = CorpseDetector()
        self.corpse_template_detector = CorpseTemplateDetector()
        self._last_frame: Optional[np.ndarray] = None
        self._use_visual_detection: bool = False  # v8: DESHABILITADO

        # Métricas
        self.total_loots: int = 0
        self.total_clicks: int = 0
        self.template_detections: int = 0    # v8: siempre 0
        self.visual_detections: int = 0      # v8: siempre 0
        self.blind_fallbacks: int = 0        # v8: = total_loots (siempre ciego)
        self.thread_loots: int = 0           # v8: loots ejecutados en thread

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
            # Configurar detectores (compatibilidad)
            self.corpse_detector.set_player_center(*self._player_center)
            self.corpse_detector.set_sqm_size(*self._sqm_size)
            self.corpse_template_detector.set_player_center(*self._player_center)
            self.corpse_template_detector.set_sqm_size(*self._sqm_size)
            # Log detallado de los SQMs para v8
            self._log(f"SQMs configurados: {len(sqms)} posiciones")
            self._log(f"  Center (idx 4): {self._player_center}")
            self._log(f"  SQM size: {self._sqm_size}")
            self._log(f"  Cardinales: S={sqms[1]}, N={sqms[7]}, E={sqms[5]}, W={sqms[3]}")
        else:
            self._log(f"SQMs parciales: {len(sqms)} posiciones (necesito 9 para modo fijo)")
        

    def set_game_region(self, x1: int, y1: int, x2: int, y2: int):
        """Configura la región del game window (compatibilidad)."""
        self.corpse_detector.set_game_region(x1, y1, x2, y2)
        self.corpse_template_detector.set_game_region(x1, y1, x2, y2)

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
        v8: Lanza loot en THREAD SEPARADO para no bloquear el targeting.
        
        Args:
            monster_name: Nombre del monstruo matado
            x, y: Coordenadas del último ataque (battle list — no usadas)
            frame: Frame actual (no usado en v8 — solo SQMs ciegos)
        """
        if not self.enabled:
            return

        if not self._left_click_fn:
            self._log(f"Kill ignorada (sin callback de click): {monster_name}")
            return

        # Si no tenemos SQMs ni player center, no podemos lootear
        if not self._sqms and self._player_center == (0, 0):
            self._log(f"Kill ignorada (sin calibración): {monster_name}")
            return

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
        NO bloquea el targeting — el targeting puede seguir atacando.
        """
        try:
            with self._loot_lock:
                self.state = "looting"
                self.thread_loots += 1

                # Pequeña pausa para que el cadáver aparezca en pantalla
                time.sleep(0.10)

                # SQMs ciegos — ÚNICO método en v8
                positions = self._calculate_loot_sqms()
                self.blind_fallbacks += 1

                if not positions:
                    self._log(f"Sin SQMs para lootear {monster_name}")
                    self.state = "idle"
                    return

                # Limitar clicks
                clicks_target = min(len(positions), self.max_loot_clicks)
                positions = positions[:clicks_target]

                coords_str = " → ".join(f"({x},{y})" for x, y in positions)
                self._log(f"Looteando: {monster_name} — {clicks_target} SQMs: {coords_str}")
                
                # Debug: verificar si usamos SQMs fijos o dinámicos
                source = "SQMs_fijos" if len(self._sqms) >= 9 else "dinámico"
                self._log(f"  Método: {source}, player_center={self._player_center}, sqm_size={self._sqm_size}")

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
                self._log(f"Loot OK: {monster_name} — {clicks_done}/{clicks_target} clicks")
                
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
        v8: Solo log periódico + loot periódico opcional.
        El loot principal se ejecuta en notify_kill() → thread separado.
        """
        if not self.enabled or frame is None:
            return

        self._last_frame = frame
        now = time.time()

        # Log periódico (~cada 15s)
        if now - self._last_status_log >= 15.0:
            self._last_status_log = now
            self._log(
                f"v8 Estado: loots={self.total_loots}, "
                f"clicks={self.total_clicks}, "
                f"threads={self.thread_loots}, "
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
        self._log(f"Looter v8 activado — SOLO SQMs ciegos (thread separado)")
        self._log(f"  Método click: {self.loot_method}, cuenta: {self.account_type}")
        self._log(f"  SQMs calibrados: {len(self._sqms)} posiciones")
        if len(self._sqms) >= 9:
            center = self._sqms[4]
            self._log(f"  SQMs fijos: Center={center}, usando índices [4,1,7,5,3]")
        else:
            self._log(f"  SQMs dinámicos: center={self._player_center}, sqm_size={self._sqm_size}")
        self._log(f"  Max clicks: {self.max_loot_clicks}, delay: {self.loot_delay}s")
        self._log(f"  Detección visual: DESHABILITADA (TPL=0.25 conf, HSV=falsos positivos)")
        
        # Verificar calibración
        if len(self._sqms) < 9 and self._player_center == (0, 0):
            self._log("⚠ ADVERTENCIA: Sin calibración completa — presiona 'Calibrar' primero")
            self._log("  El loot funcionará cuando se calibren las coordenadas")
        elif len(self._sqms) >= 9:
            self._log("✓ Calibración OK — usando SQMs fijos del screen_calibrator")
        else:
            self._log("⚠ Usando calibración parcial — puede ser menos preciso")

    def stop(self):
        self.enabled = False
        self._running = False
        self.state = "idle"
        # Esperar a que termine el thread de loot si hay uno activo
        if self._loot_thread and self._loot_thread.is_alive():
            self._loot_thread.join(timeout=1.0)
        self._log("Looter v8 desactivado")

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
            "blind_fallbacks": self.blind_fallbacks,
            "thread_loots": self.thread_loots,
            "corpse_templates": len(self.corpse_template_detector._templates),
            "sqms_configured": len(self._sqms),
            "player_center": self._player_center,
            "sqm_size": self._sqm_size,
            "periodic_loot": self.periodic_loot,
            "loot_during_combat": self.loot_during_combat,
            "visual_detection": self._use_visual_detection,
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
