"""
healer_bot.py - Lógica principal del bot de auto-curación.
Ejecuta el loop de captura → detección → curación en un hilo secundario.
El hilo principal queda libre para la GUI (tkinter).

Usa OBS WebSocket para capturar frames directamente de la memoria de OBS,
sin necesidad de que el proyector sea visible en pantalla.
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
from debug_visual import DebugVisual


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

        # Estado
        self.running: bool = False      # True = hilo activo
        self.active: bool = False       # True = curando activamente
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

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
            # Si hay un título guardado, buscar coincidencia
            if saved_title:
                for t in tibias:
                    if saved_title.lower() in t["title"].lower():
                        self.tibia_hwnd = t["hwnd"]
                        self.tibia_title = t["title"]
                        self.key_sender.set_target(t["hwnd"])
                        tibia_found = True
                        break

            # Si no se encontró la guardada, usar la primera
            if not tibia_found:
                t = tibias[0]
                self.tibia_hwnd = t["hwnd"]
                self.tibia_title = t["title"]
                self.key_sender.set_target(t["hwnd"])
                tibia_found = True

            if tibia_found:
                self.log.ok(f"Tibia encontrado: {self.tibia_title}")
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
        self.config.set("tibia_window_title", title)
        self.log.ok(f"Tibia seleccionado: {title}")
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
                    error = self.capture.last_error
                    self.log.warning(f"Captura fallida: {error}")
                    time.sleep(0.5)
                    continue

                if self.capture.is_black_screen():
                    brightness = self.capture.last_brightness
                    self.log.warning(
                        f"Pantalla negra detectada (brillo={brightness:.1f}) "
                        "— ¿Fuente OBS inactiva?"
                    )
                    self.hp_percent = None
                    self.mp_percent = None
                    self._notify_status()
                    time.sleep(1.0)
                    continue

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
                        self.log.heal(
                            f"HP={hp * 100:.0f}% < {threshold * 100:.0f}% "
                            f"→ {key} ({desc})"
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
        """Ejecuta calibración automática de barras."""
        img = self.take_test_capture()
        if img is None:
            self.log.error("No se pudo calibrar — captura fallida")
            return {}
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
        return result

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
