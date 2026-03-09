"""
simple_walking.py - Grabador y reproductor simple de caminata por flechas direccionales.
Graba pulsaciones de flechas (Up/Down/Left/Right) y las reproduce en bucle
enviando las teclas al cliente de Tibia via SendMessage (sin foco).

Usa polling con keyboard.is_pressed() para máxima compatibilidad
(evita conflictos con keyboard.hook/add_hotkey del GUI principal).
"""

import json
import time
import threading
from dataclasses import dataclass, asdict
from typing import Callable, List, Optional

import keyboard


# Mapa dirección → nombre de tecla para KeySender
DIRECTION_MAP = {
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
}

DIRECTION_ARROWS = {
    "up": "↑ Norte",
    "down": "↓ Sur",
    "left": "← Oeste",
    "right": "→ Este",
}

# Teclas que se monitorean para polling
_POLL_KEYS = ["up", "down", "left", "right"]


@dataclass
class WalkStep:
    """Un paso grabado: dirección + delay respecto al paso anterior."""
    direction: str          # "up", "down", "left", "right"
    delay: float = 0.0     # segundos desde el paso anterior
    index: int = 0          # número de waypoint


class SimpleWalkRecorder:
    """
    Graba y reproduce secuencias de flechas direccionales.
    - Graba: detecta flechas con polling (keyboard.is_pressed) y almacena la secuencia.
    - Reproduce: envía las teclas al cliente de Tibia en bucle infinito.
    """

    def __init__(self):
        # --- Grabación ---
        self.is_recording: bool = False
        self.steps: List[WalkStep] = []
        self._record_start: float = 0.0
        self._last_step_time: float = 0.0
        self._pressed: set = set()
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_stop = threading.Event()

        # --- Reproducción ---
        self.is_playing: bool = False
        self._play_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.current_index: int = 0
        self.cycle_count: int = 0

        # --- Callbacks ---
        self._send_key: Optional[Callable[[str], bool]] = None
        self._on_step_recorded: Optional[Callable[['WalkStep'], None]] = None
        self._on_playback_step: Optional[Callable[[int, int], None]] = None
        self._on_cycle_complete: Optional[Callable[[int], None]] = None
        self._log: Optional[Callable[[str], None]] = None

    # ==================================================================
    # Configuración de callbacks
    # ==================================================================
    def set_send_key_callback(self, fn: Callable[[str], bool]):
        self._send_key = fn

    def set_on_step_recorded(self, fn: Callable[['WalkStep'], None]):
        self._on_step_recorded = fn

    def set_on_playback_step(self, fn: Callable[[int, int], None]):
        self._on_playback_step = fn

    def set_on_cycle_complete(self, fn: Callable[[int], None]):
        self._on_cycle_complete = fn

    def set_log_callback(self, fn: Callable[[str], None]):
        self._log = fn

    def _emit_log(self, msg: str):
        if self._log:
            self._log(msg)

    # ==================================================================
    # Grabación (polling)
    # ==================================================================
    def start_recording(self):
        if self.is_recording:
            return
        self.steps.clear()
        self.is_recording = True
        self._record_start = time.time()
        self._last_step_time = self._record_start
        self._pressed.clear()
        self._poll_stop.clear()

        self._poll_thread = threading.Thread(target=self._poll_worker, daemon=True)
        self._poll_thread.start()
        self._emit_log("🔴 Grabación iniciada — presiona flechas ↑↓←→ para grabar pasos")

    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self._poll_stop.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=1.0)
        self._poll_thread = None
        self._emit_log(f"⏹️ Grabación detenida — {len(self.steps)} pasos grabados")

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _poll_worker(self):
        """Hilo que monitorea flechas por polling cada 40ms."""
        while self.is_recording and not self._poll_stop.is_set():
            for key in _POLL_KEYS:
                try:
                    if keyboard.is_pressed(key):
                        if key not in self._pressed:
                            self._pressed.add(key)
                            self._record_step(key)
                    else:
                        self._pressed.discard(key)
                except Exception:
                    pass
            self._poll_stop.wait(timeout=0.04)  # 40ms = ~25 checks/sec

    def _record_step(self, key: str):
        now = time.time()
        delay = now - self._last_step_time
        step = WalkStep(
            direction=key,
            delay=delay,
            index=len(self.steps),
        )
        self.steps.append(step)
        self._last_step_time = now
        self._emit_log(
            f"  #{step.index + 1} {DIRECTION_ARROWS.get(key, key)}  (delay {delay:.2f}s)"
        )
        if self._on_step_recorded:
            self._on_step_recorded(step)

    # ==================================================================
    # Reproducción
    # ==================================================================
    def start_playback(self):
        if self.is_playing:
            return
        if not self.steps:
            self._emit_log("⚠️ No hay pasos grabados para reproducir")
            return
        if not self._send_key:
            self._emit_log("⚠️ No hay callback de envío de teclas configurado")
            return

        self.is_playing = True
        self.current_index = 0
        self.cycle_count = 0
        self._stop_event.clear()
        self._play_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self._play_thread.start()
        self._emit_log(f"▶️ Reproducción iniciada — {len(self.steps)} pasos en bucle")

    def stop_playback(self):
        if not self.is_playing:
            return
        self.is_playing = False
        self._stop_event.set()
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=2.0)
        self._emit_log(
            f"⏹️ Reproducción detenida — {self.cycle_count} ciclos completados"
        )

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def _playback_worker(self):
        while self.is_playing and not self._stop_event.is_set():
            for i, step in enumerate(self.steps):
                if self._stop_event.is_set():
                    break

                self.current_index = i

                # Esperar el delay original entre pasos
                if step.delay > 0 and i > 0:
                    if self._stop_event.wait(timeout=step.delay):
                        break

                # Enviar tecla al Tibia
                key_name = DIRECTION_MAP.get(step.direction, "")
                if key_name and self._send_key:
                    ok = self._send_key(key_name)
                    if not ok:
                        self._emit_log(f"  ⚠️ Fallo al enviar tecla {key_name}")

                # Notificar a la GUI
                if self._on_playback_step:
                    self._on_playback_step(i, self.cycle_count)

            else:
                # Ciclo completado normalmente
                self.cycle_count += 1
                self._emit_log(f"🔄 Ciclo #{self.cycle_count} completado")
                if self._on_cycle_complete:
                    self._on_cycle_complete(self.cycle_count)
                if self._stop_event.wait(timeout=0.3):
                    break
                continue

            break

        self.is_playing = False

    # ==================================================================
    # Persistencia
    # ==================================================================
    def save(self, filepath: str) -> bool:
        try:
            data = {
                "version": "1.0",
                "steps": [asdict(s) for s in self.steps],
                "total_steps": len(self.steps),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._emit_log(f"💾 Ruta guardada: {filepath}")
            return True
        except Exception as e:
            self._emit_log(f"❌ Error guardando: {e}")
            return False

    def load(self, filepath: str) -> bool:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.steps.clear()
            for sd in data.get("steps", []):
                step = WalkStep(
                    direction=sd["direction"],
                    delay=sd.get("delay", 0.0),
                    index=sd.get("index", 0),
                )
                self.steps.append(step)
            self._emit_log(f"📂 Ruta cargada: {filepath} — {len(self.steps)} pasos")
            return True
        except Exception as e:
            self._emit_log(f"❌ Error cargando: {e}")
            return False

    def clear(self):
        self.steps.clear()
        self._emit_log("🗑️ Pasos borrados")

    # ==================================================================
    # Estado
    # ==================================================================
    def get_status(self) -> dict:
        return {
            "is_recording": self.is_recording,
            "is_playing": self.is_playing,
            "total_steps": len(self.steps),
            "current_index": self.current_index,
            "cycle_count": self.cycle_count,
        }
