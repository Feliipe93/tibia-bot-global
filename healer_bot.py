"""
healer_bot.py - Lógica principal del bot de auto-curación.
Ejecuta el loop de captura → detección → curación en un hilo secundario.
El hilo principal queda libre para la GUI (tkinter).

Usa OBS WebSocket para capturar frames directamente de la memoria de OBS,
sin necesidad de que el proyector sea visible en pantalla.

v2.0+: Integra dispatcher para cavebot, targeting y looter.
v3.0:  Todos los módulos funcionan con template matching real (OpenCV).
"""

import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from config import Config
from logger import BotLogger
from window_finder import (
    find_tibia_windows,
    is_window_valid,
)
from screen_capture import ScreenCapture
from bar_detector import BarDetector
from key_sender import KeySender
from mouse_click_sender import MouseClickSender
from debug_visual import DebugVisual
from dispatcher import BotDispatcher
from screen_calibrator import ScreenCalibrator
from targeting.targeting_engine import TargetingEngine
from looter.looter_engine import LooterEngine
from cavebot.cavebot_engine import CavebotEngine


class HealerBot:
    """
    Bot de auto-curación para Tibia.

    Flujo:
        1. Captura screenshot de OBS via WebSocket (GetSourceScreenshot)
        2. Analiza barras de HP/Mana con OpenCV HSV
        3. Si HP/Mana está por debajo de un umbral → envía tecla a Tibia via PostMessage
    """

    def __init__(self, config: Config, logger: BotLogger):
        self.config = config
        self.log = logger

        # Componentes
        self.capture = ScreenCapture()
        self.detector = BarDetector(
            expected_full_width_ratio=config.bar_detection.get(
                "expected_full_width_ratio", 0.43
            ),
            scan_height_ratio=config.bar_detection.get("scan_height_ratio", 0.10),
        )
        self.key_sender = KeySender()
        self.debug_visual = DebugVisual(
            enabled=config.get("debug_save_images", True)
        )

        # Dispatcher v2 (cavebot, targeting, looter)
        self.dispatcher = BotDispatcher(self.config, self.log, self.capture)

        # --- Módulos v3 (template matching real) ---
        self.mouse_sender = MouseClickSender()
        self.calibrator = ScreenCalibrator()
        self.targeting_engine = TargetingEngine()
        self.looter_engine = LooterEngine()
        self.cavebot_engine = CavebotEngine()
        self._calibrated = False

        # Wire calibrator log callback for diagnostics
        self.calibrator.set_log_callback(lambda msg: self.log.info(msg))

        # Coordenadas: factores de escala OBS frame → Tibia client
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0
        self._obs_frame_size: Tuple[int, int] = (0, 0)  # (w, h)

        # Estado
        self.running: bool = False      # True = hilo activo
        self.active: bool = False       # True = curando activamente
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self._click_lock = threading.Lock()  # Mutex para serializar clicks (targeting vs looter)

        # Ventanas
        self.tibia_hwnd: Optional[int] = None
        self.tibia_title: str = ""

        # OBS WebSocket
        self.obs_connected: bool = False
        self.obs_version: str = ""

        # Métricas
        self.hp_percent: Optional[float] = None
        self.mp_percent: Optional[float] = None
        self.hp_color: str = "N/A"
        self.captures_per_sec: float = 0.0
        self.cycle_count: int = 0
        self.heal_count: int = 0
        self.last_heal_time: float = 0.0
        self.last_heal_key: str = ""
        self.errors: List[str] = []
        self.last_frame: Optional[np.ndarray] = None  # Último frame capturado (para GUI preview)

        # Callbacks para actualizar la GUI (se establecen desde gui.py)
        self._on_status_update: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    # ==================================================================
    # Propiedades de estado
    # ==================================================================
    @property
    def status_text(self) -> str:
        if not self.running:
            return "DETENIDO"
        return "ACTIVO" if self.active else "EN ESPERA"

    @property
    def tibia_connected(self) -> bool:
        return self.tibia_hwnd is not None and is_window_valid(self.tibia_hwnd)

    @property
    def projector_connected(self) -> bool:
        """Ahora verifica conexión OBS WebSocket en vez de proyector."""
        return self.capture.is_connected and bool(self.capture.source_name)

    # ==================================================================
    # Callbacks
    # ==================================================================
    def set_status_callback(self, callback: Callable) -> None:
        self._on_status_update = callback

    def set_error_callback(self, callback: Callable) -> None:
        self._on_error = callback

    def _notify_status(self) -> None:
        if self._on_status_update:
            try:
                self._on_status_update()
            except Exception:
                pass

    # ==================================================================
    # Inicialización de módulos v3
    # ==================================================================
    def _scaled_left_click(self, x: int, y: int) -> bool:
        """Click izquierdo con coordenadas escaladas de OBS frame → Tibia client."""
        with self._click_lock:
            cx = int(x * self._scale_x)
            cy = int(y * self._scale_y)
            result = self.mouse_sender.left_click(cx, cy)
            if not result:
                self.log.warning(
                    f"Click izquierdo FALLÓ — OBS({x},{y}) → client({cx},{cy}) "
                    f"[scale x={self._scale_x:.3f} y={self._scale_y:.3f}] "
                    f"hwnd={self.mouse_sender.hwnd}, "
                    f"valid={is_window_valid(self.mouse_sender.hwnd) if self.mouse_sender.hwnd else False}"
                )
            else:
                self.log.debug(
                    f"Click OK — OBS({x},{y}) → client({cx},{cy}) hwnd={self.mouse_sender.hwnd}"
                )
            return result

    def _scaled_right_click(self, x: int, y: int) -> bool:
        """Click derecho con coordenadas escaladas de OBS frame → Tibia client."""
        with self._click_lock:
            cx = int(x * self._scale_x)
            cy = int(y * self._scale_y)
            return self.mouse_sender.right_click(cx, cy)

    def _scaled_shift_right_click(self, x: int, y: int) -> bool:
        """Shift+Click derecho con coordenadas escaladas (loot rápido)."""
        with self._click_lock:
            cx = int(x * self._scale_x)
            cy = int(y * self._scale_y)
            return self.mouse_sender.click(cx, cy, button="right", shift=True)

    def _update_scale_factors(self, frame: np.ndarray):
        """Calcula factores de escala OBS frame → Tibia client coordinates."""
        if frame is None:
            return
        frame_h, frame_w = frame.shape[:2]
        self._obs_frame_size = (frame_w, frame_h)

        client_w, client_h = self.mouse_sender.get_client_size()
        if client_w > 0 and client_h > 0 and frame_w > 0 and frame_h > 0:
            self._scale_x = client_w / frame_w
            self._scale_y = client_h / frame_h
            self.log.info(
                f"Escala OBS({frame_w}x{frame_h}) → Tibia({client_w}x{client_h}): "
                f"x={self._scale_x:.3f} y={self._scale_y:.3f}"
            )
        else:
            self._scale_x = 1.0
            self._scale_y = 1.0

    def _init_modules(self):
        """
        Wires all module callbacks and registers dispatcher handlers.
        Called once when tibia_hwnd is available and mouse_sender has a target.
        v3.1: targeting v2 notifica kills al looter directamente (sin wrapper).
        """
        # --- Targeting ---
        self.targeting_engine.set_click_callback(self._scaled_left_click)
        self.targeting_engine.set_key_callback(self.key_sender.send_key)
        self.targeting_engine.set_log_callback(
            lambda msg: self.log.info(msg)
        )
        self.targeting_engine.set_calibrator(self.calibrator)
        self.targeting_engine.configure(self.config.targeting)

        # --- Looter ---
        self.looter_engine.set_right_click_callback(self._scaled_right_click)
        self.looter_engine.set_left_click_callback(self._scaled_left_click)
        self.looter_engine.set_shift_right_click_callback(self._scaled_shift_right_click)
        self.looter_engine.set_log_callback(
            lambda msg: self.log.info(msg)
        )
        self.looter_engine.corpse_detector.set_log_callback(
            lambda msg: self.log.info(msg)
        )
        self.looter_engine.corpse_template_detector.set_log_callback(
            lambda msg: self.log.info(msg)
        )
        self.looter_engine.set_targeting_engine(self.targeting_engine)
        self.looter_engine.configure(self.config.looter)

        # --- Cavebot ---
        self.cavebot_engine.set_click_callback(self._scaled_left_click)
        self.cavebot_engine.set_key_callback(self.key_sender.send_key)
        self.cavebot_engine.set_log_callback(
            lambda msg: self.log.info(msg)
        )
        self.cavebot_engine.set_targeting_engine(self.targeting_engine)
        self.cavebot_engine.set_hotkeys(self.config.hotkeys)
        self.cavebot_engine.configure(self.config.cavebot)

        # --- Conexiones cruzadas ---
        # Targeting v2 notifica kills directamente al looter (sin wrapper)
        self.targeting_engine.set_looter_engine(self.looter_engine)

        # --- Registrar handlers en dispatcher ---
        # Orden: targeting → cavebot → looter (targeting primero para detectar kills)
        self.dispatcher.register_handler("targeting", self.targeting_engine.process_frame)
        self.dispatcher.register_handler("cavebot", self.cavebot_engine.process_frame)
        self.dispatcher.register_handler("looter", self.looter_engine.process_frame)

        self.log.ok("Módulos v3.1 inicializados (targeting v2, looter v2, cavebot v2)")

    def _run_calibration_on_frame(self, frame: np.ndarray) -> bool:
        """
        Calibra regiones del juego usando el frame actual.
        Configura todas las regiones para targeting, looter y cavebot.
        v3.1: Log reducido — solo muestra error las primeras N veces.
        """
        success = self.calibrator.calibrate(frame)
        if not success:
            # Solo loguear warning las primeras 3 veces y luego cada 20
            fail_n = self.calibrator._fail_count
            if fail_n <= 3 or fail_n % 20 == 0:
                confs = self.calibrator.last_confidences
                conf_str = ", ".join(f"{k}={v:.2f}" for k, v in confs.items()) if confs else "sin datos"
                self.log.warning(
                    f"Calibración fallida #{fail_n} — {self.calibrator.last_error} | {conf_str}"
                )
            return False

        # Pasar regiones a los módulos
        br = self.calibrator.battle_region
        if br:
            self.targeting_engine.set_battle_region(*br)
            self.log.info(f"Battle region: {br}")

        mr = self.calibrator.map_region
        if mr:
            self.cavebot_engine.set_map_region(*mr)
            self.log.info(f"Map region: {mr}")

        sqms = self.calibrator.sqms
        if sqms:
            self.looter_engine.set_sqms(sqms)
            self.log.info(f"SQMs configurados: {len(sqms)} posiciones")

        # Pasar game region al looter para detección visual de cuerpos
        gr = self.calibrator.game_region
        if gr:
            self.looter_engine.set_game_region(*gr)
            self.log.info(f"Game region para detección de cuerpos: {gr}")

        pc = self.calibrator.player_center
        if pc:
            self.log.info(f"Player center: {pc}")

        # v10: Actualizar calibración del creature tracker en targeting
        self.targeting_engine.update_tracker_calibration()

        # Actualizar factores de escala OBS → Tibia client
        self._update_scale_factors(frame)

        self._calibrated = True
        self.log.ok("Calibración completada exitosamente")
        return True

    # ==================================================================
    # Conexión OBS WebSocket
    # ==================================================================
    def connect_obs(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> bool:
        """
        Conecta a OBS vía WebSocket.
        Si no se pasan parámetros, usa los de config.
        """
        h = host or self.config.obs_host
        p = port or self.config.obs_port
        pw = password if password is not None else self.config.obs_password
        src = source_name or self.config.obs_source_name

        self.log.info(f"Conectando a OBS WebSocket {h}:{p}...")

        success = self.capture.connect(
            host=h, port=p, password=pw, source_name=src
        )

        if success:
            self.obs_connected = True
            self.obs_version = self.capture.get_obs_version()
            self.log.ok(f"Conectado a OBS: {self.obs_version}")

            # Guardar config
            self.config.obs_websocket = {
                "host": h,
                "port": p,
                "password": pw,
                "source_name": src,
            }
            self.config.save()
        else:
            self.obs_connected = False
            self.obs_version = ""
            error = self.capture.last_error
            self.log.error(f"Error al conectar a OBS: {error}")

        self._notify_status()
        return success

    def disconnect_obs(self) -> None:
        """Desconecta de OBS WebSocket."""
        self.capture.disconnect()
        self.obs_connected = False
        self.obs_version = ""
        self.log.info("Desconectado de OBS WebSocket")
        self._notify_status()

    def set_obs_source(self, source_name: str) -> None:
        """Cambia la fuente de OBS a capturar."""
        self.capture.source_name = source_name
        self.config.obs_source_name = source_name
        self.config.save()
        self.log.ok(f"Fuente OBS seleccionada: {source_name}")
        self._notify_status()

    def get_obs_sources(self) -> list:
        """Obtiene las fuentes disponibles en OBS."""
        return self.capture.get_obs_sources()

    def get_obs_scenes(self) -> list:
        """Obtiene las escenas disponibles en OBS."""
        return self.capture.get_obs_scenes()

    # ==================================================================
    # Detección de ventanas (solo Tibia ahora)
    # ==================================================================
    def detect_windows(self) -> Tuple[bool, bool]:
        """
        Busca la ventana de Tibia.
        Retorna (tibia_found, obs_connected).
        """
        tibia_found = False

        # Buscar Tibia
        tibias = find_tibia_windows()
        saved_title = self.config.get("tibia_window_title", "")

        if tibias:
            # Separar: ventanas del juego real vs otras (navegadores, etc.)
            game_windows = [t for t in tibias if t.get("is_game", False)]

            # PRIORIDAD 1: Si hay ventanas del juego real, usar la primera
            # (ya están ordenadas por is_game primero en window_finder)
            if game_windows:
                # Si hay título guardado, buscar entre las game windows
                if saved_title:
                    for t in game_windows:
                        if saved_title.lower() in t["title"].lower():
                            self.tibia_hwnd = t["hwnd"]
                            self.tibia_title = t["title"]
                            self.key_sender.set_target(t["hwnd"])
                            self.mouse_sender.set_target(t["hwnd"])
                            tibia_found = True
                            break
                # Si no coincidió, usar la primera game window
                if not tibia_found:
                    t = game_windows[0]
                    self.tibia_hwnd = t["hwnd"]
                    self.tibia_title = t["title"]
                    self.key_sender.set_target(t["hwnd"])
                    self.mouse_sender.set_target(t["hwnd"])
                    tibia_found = True

            # PRIORIDAD 2: Si no hay game windows, buscar por título guardado
            if not tibia_found and saved_title:
                for t in tibias:
                    if saved_title.lower() in t["title"].lower():
                        self.tibia_hwnd = t["hwnd"]
                        self.tibia_title = t["title"]
                        self.key_sender.set_target(t["hwnd"])
                        self.mouse_sender.set_target(t["hwnd"])
                        tibia_found = True
                        self.log.warning(
                            f"⚠ Usando ventana no-game: {t['title']} "
                            f"(no se encontraron ventanas del cliente Tibia)"
                        )
                        break

            # PRIORIDAD 3: Fallback a la primera ventana con 'tibia'
            if not tibia_found:
                t = tibias[0]
                self.tibia_hwnd = t["hwnd"]
                self.tibia_title = t["title"]
                self.key_sender.set_target(t["hwnd"])
                self.mouse_sender.set_target(t["hwnd"])
                tibia_found = True

            if tibia_found:
                self.log.ok(f"Tibia encontrado: {self.tibia_title}")
                self.log.info(
                    f"  HWND={self.tibia_hwnd} | "
                    f"Ventanas Tibia encontradas: {len(tibias)}"
                )
                for i, t in enumerate(tibias):
                    self.log.info(
                        f"  [{i}] hwnd={t['hwnd']} title='{t['title']}' "
                        f"({t['width']}x{t['height']})"
                    )
                self._init_modules()
        else:
            self.tibia_hwnd = None
            self.tibia_title = ""
            self.log.warning("Ventana de Tibia no encontrada")

        self._notify_status()
        return tibia_found, self.projector_connected

    def set_tibia_window(self, hwnd: int, title: str) -> None:
        """Establece manualmente la ventana de Tibia."""
        self.tibia_hwnd = hwnd
        self.tibia_title = title
        self.key_sender.set_target(hwnd)
        self.mouse_sender.set_target(hwnd)
        self.config.set("tibia_window_title", title)
        self.log.ok(f"Tibia seleccionado: {title}")
        self._init_modules()
        self._notify_status()

    # ==================================================================
    # Control del bot
    # ==================================================================
    def start(self) -> bool:
        """Inicia el hilo del bot."""
        if self.running:
            return False
        self.running = True
        self.thread = threading.Thread(target=self._main_loop, daemon=True)
        self.thread.start()
        self.log.ok("Bot iniciado")
        self._notify_status()
        return True

    def stop(self) -> None:
        """Detiene el hilo del bot."""
        self.running = False
        self.active = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        self.thread = None
        self.log.ok("Bot detenido")
        self._notify_status()

    def toggle_active(self) -> bool:
        """Activa/desactiva la curación automática. Retorna el nuevo estado."""
        self.active = not self.active
        state = "ACTIVADO" if self.active else "DESACTIVADO"
        self.log.info(f"Auto-healer {state}")
        self._notify_status()
        return self.active

    # ==================================================================
    # Loop principal (corre en hilo secundario)
    # ==================================================================
    def _main_loop(self) -> None:
        """Loop principal de captura → detección → curación."""
        self.log.info("Loop principal iniciado")
        fps_counter = 0
        fps_timer = time.time()
        _capture_fail_count = 0       # contador de fallos consecutivos
        _black_screen_fail_count = 0  # contador de pantallas negras consecutivas

        while self.running:
            try:
                loop_start = time.time()

                # --- 1. Verificar conexión OBS ---
                if not self.projector_connected:
                    self.hp_percent = None
                    self.mp_percent = None
                    self.hp_color = "N/A"
                    self._notify_status()
                    time.sleep(1.0)
                    continue

                # --- 2. Capturar frame de OBS ---
                img = self.capture.capture_source()

                if img is None:
                    _capture_fail_count += 1
                    # Solo loguear cada 10 fallos para no saturar la GUI
                    if _capture_fail_count <= 3 or _capture_fail_count % 10 == 0:
                        error = self.capture.last_error
                        self.log.warning(
                            f"Captura fallida ({_capture_fail_count}x): {error}"
                        )
                    # Backoff: empieza en 0.5s, sube hasta 3s
                    backoff = min(0.5 + (_capture_fail_count * 0.3), 3.0)
                    time.sleep(backoff)
                    continue

                # Captura OK → resetear contador de fallos
                _capture_fail_count = 0

                if self.capture.is_black_screen():
                    _black_screen_fail_count += 1
                    if _black_screen_fail_count <= 3 or _black_screen_fail_count % 10 == 0:
                        brightness = self.capture.last_brightness
                        self.log.warning(
                            f"Pantalla negra ({_black_screen_fail_count}x, "
                            f"brillo={brightness:.1f}) — ¿Fuente OBS inactiva?"
                        )
                    self.hp_percent = None
                    self.mp_percent = None
                    self._notify_status()
                    backoff = min(1.0 + (_black_screen_fail_count * 0.5), 5.0)
                    time.sleep(backoff)
                    continue

                # Pantalla OK → resetear contador
                _black_screen_fail_count = 0

                # --- 2b. Guardar frame para GUI preview ---
                self.last_frame = img

                # --- 3. Detectar HP y Mana ---
                hp, mp = self.detector.detect(img)
                with self.lock:
                    self.hp_percent = hp
                    self.mp_percent = mp
                    self.hp_color = self.detector.get_hp_color_name(hp)

                # Log periódico
                self.cycle_count += 1
                if self.cycle_count % 20 == 0:
                    hp_str = f"{hp * 100:.0f}%" if hp is not None else "N/A"
                    mp_str = f"{mp * 100:.0f}%" if mp is not None else "N/A"
                    self.log.info(
                        f"HP={hp_str} ({self.hp_color}) | MP={mp_str} | "
                        f"Estado={'ACTIVO' if self.active else 'EN ESPERA'}"
                    )

                # --- 4. Debug visual periódico ---
                debug_every = self.config.get("debug_every_n_cycles", 40)
                if (
                    self.config.get("debug_save_images", False)
                    and self.cycle_count % debug_every == 0
                ):
                    self.debug_visual.generate_debug_image(
                        img,
                        hp,
                        mp,
                        self.detector.last_mask_hp,
                        self.detector.last_mask_mp,
                        self.detector.last_scan_height,
                    )
                    self.log.debug(
                        f"Debug image guardada (ciclo #{self.cycle_count})"
                    )

                # --- 5. Curación automática ---
                if self.active and self.tibia_connected:
                    self._process_healing(hp, mp)

                # --- 5b. Auto-calibración en primer frame ---
                # La calibración se ejecuta independientemente de si el
                # healer está ACTIVO, para que targeting/cavebot/looter
                # puedan funcionar con sus propios toggles.
                if self.tibia_connected and not self._calibrated:
                    try:
                        self._run_calibration_on_frame(img)
                    except Exception as e:
                        self.log.debug(f"Calibración pendiente: {e}")

                # Re-calibrar regiones periódicamente (cada 120 ciclos ≈ 60s)
                # para adaptarse a cambios de paneles en Tibia
                if self.tibia_connected and self._calibrated and self.cycle_count % 120 == 0:
                    try:
                        self._run_calibration_on_frame(img)
                    except Exception:
                        pass

                # --- 5c. Dispatcher v3 (targeting / cavebot / looter) ---
                # Los módulos tienen sus propios toggles individuales en la GUI.
                # No requieren que el healer esté ACTIVO (F9).
                # El dispatcher tiene timeout por módulo para evitar congelamiento.
                if self.tibia_connected and self._calibrated:
                    try:
                        self.dispatcher.dispatch_frame(img)
                    except Exception as e:
                        self.log.debug(f"Dispatcher error: {e}")

                # --- 6. FPS ---
                fps_counter += 1
                elapsed = time.time() - fps_timer
                if elapsed >= 1.0:
                    self.captures_per_sec = fps_counter / elapsed
                    fps_counter = 0
                    fps_timer = time.time()

                self._notify_status()

                # --- 7. Esperar intervalo ---
                loop_elapsed = time.time() - loop_start
                sleep_time = max(
                    0.01, self.config.check_interval - loop_elapsed
                )
                time.sleep(sleep_time)

            except Exception as e:
                self.log.error(f"Error en loop principal: {e}")
                self.errors.append(str(e))
                time.sleep(1.0)

        self.log.info("Loop principal finalizado")

    def _process_healing(
        self, hp: Optional[float], mp: Optional[float]
    ) -> None:
        """Evalúa si debe curar y envía la tecla correspondiente."""
        now = time.time()

        # Verificar cooldown
        if (now - self.last_heal_time) < self.config.cooldown:
            return

        # HP healing: evaluar niveles de mayor a menor prioridad
        # Los niveles están ordenados de mayor threshold a menor
        if hp is not None:
            heal_levels = sorted(
                self.config.heal_levels,
                key=lambda x: x.get("threshold", 0),
            )
            for level in heal_levels:
                threshold = level.get("threshold", 0)
                key = level.get("key", "")
                desc = level.get("description", key)

                if hp < threshold and key:
                    success = self.key_sender.send_key(key)
                    if success:
                        self.last_heal_time = now
                        self.last_heal_key = key
                        self.heal_count += 1
                        # Log detallado con hwnd para diagnóstico
                        self.log.heal(
                            f"HP={hp * 100:.0f}% < {threshold * 100:.0f}% "
                            f"→ {key} ({desc}) [hwnd={self.key_sender.hwnd}]"
                        )
                    else:
                        self.log.error(
                            f"Error enviando tecla {key} a Tibia"
                        )
                    return  # Solo una curación por ciclo

        # Mana healing
        mana_cfg = self.config.mana_heal
        if (
            mana_cfg.get("enabled", False)
            and mp is not None
            and mp < mana_cfg.get("threshold", 0.30)
        ):
            key = mana_cfg.get("key", "F3")
            if (now - self.last_heal_time) >= self.config.cooldown:
                success = self.key_sender.send_key(key)
                if success:
                    self.last_heal_time = now
                    self.last_heal_key = key
                    self.heal_count += 1
                    self.log.heal(
                        f"MP={mp * 100:.0f}% < {mana_cfg['threshold'] * 100:.0f}% "
                        f"→ {key} ({mana_cfg.get('description', 'Mana')})"
                    )

    # ==================================================================
    # Utilidades
    # ==================================================================
    def take_test_capture(self) -> Optional[np.ndarray]:
        """Toma una captura de prueba y retorna la imagen."""
        if not self.projector_connected:
            self.log.warning("No hay conexión OBS para captura de prueba")
            return None
        img = self.capture.capture_source()
        if img is not None:
            self.log.ok(
                f"Captura de prueba: {img.shape[1]}x{img.shape[0]} px, "
                f"brillo={self.capture.last_brightness:.1f}"
            )
        else:
            self.log.warning(f"Captura fallida: {self.capture.last_error}")
        return img

    def run_calibration(self) -> Dict:
        """Ejecuta calibración automática de barras + regiones del juego."""
        img = self.take_test_capture()
        if img is None:
            self.log.error("No se pudo calibrar — captura fallida")
            return {}

        # Calibración de barras (original)
        result = self.detector.auto_calibrate(img)
        if result.get("hp_row") is not None:
            self.log.ok(
                f"Calibración exitosa: HP en fila {result['hp_row']}, "
                f"MP en fila {result.get('mp_row', 'N/A')}, "
                f"ancho máx={result['bar_max_width']}px"
            )
        else:
            self.log.warning(
                "Calibración: no se encontraron barras. "
                "¿El proyector está mostrando Tibia?"
            )

        # Calibración de regiones del juego (v3)
        try:
            self._run_calibration_on_frame(img)
        except Exception as e:
            self.log.warning(f"Calibración de regiones falló: {e}")

        return result

    def force_recalibrate(self) -> bool:
        """Fuerza recalibración de regiones del juego."""
        self._calibrated = False
        img = self.take_test_capture()
        if img is None:
            return False
        return self._run_calibration_on_frame(img)

    def generate_analysis_image(self) -> Optional[np.ndarray]:
        """Genera una imagen de análisis de barras."""
        img = self.take_test_capture()
        if img is None:
            return None
        hp, mp = self.detector.detect(img)
        debug_img = self.debug_visual.generate_debug_image(
            img,
            hp,
            mp,
            self.detector.last_mask_hp,
            self.detector.last_mask_mp,
            self.detector.last_scan_height,
            save=True,
        )
        return debug_img

    def cleanup(self) -> None:
        """Limpieza al cerrar la aplicación."""
        self.stop()
        self.capture.close()
        self.debug_visual.cleanup_old_files()
        self.config.save()
