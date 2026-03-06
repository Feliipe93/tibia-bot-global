"""
cavebot/cavebot_engine.py - Motor de navegación por waypoints v2.
Reescritura completa basada en:
  - TibiaAuto12 CaveBotController (walk-for-refresh, stuck recovery)
  - TibiaPilotNG walkToWaypoint + orchestrator (múltiples tipos de wp)

Mejoras v2:
  - Walk-for-refresh recovery cuando el bot se queda stuck
  - Integración con targeting (pausa navegación si hay monstruos)
  - Múltiples tipos de waypoint (walk, rope, shovel, ladder, stand, etc.)
  - Detección de llegada mejorada con tolerancia configurable
  - Coordenadas X/Y/Z para waypoints
  - Soporte click + arrow keys para moverse
"""

import json
import os
import time
import random
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
MAP_MARKS_DIR = os.path.join(IMAGES_DIR, "MapSettings")


class WaypointType(Enum):
    WALK = "WALK"
    ROPE = "ROPE"
    SHOVEL = "SHOVEL"
    LADDER = "LADDER"
    DOOR = "DOOR"
    STAIRS = "STAIRS"
    STAND = "STAND"
    SINGLE_MOVE = "SINGLE_MOVE"
    PICK = "PICK"
    MACHETE = "MACHETE"
    SEWER = "SEWER"
    RIGHT_CLICK_USE = "RIGHT_CLICK_USE"
    NPC_TALK = "NPC_TALK"
    DEPOSIT_GOLD = "DEPOSIT_GOLD"
    DEPOSIT_ITEMS = "DEPOSIT_ITEMS"
    TRAVEL = "TRAVEL"
    BUY_BACKPACK = "BUY_BACKPACK"
    DROP_FLASKS = "DROP_FLASKS"
    REFILL_CHECKER = "REFILL_CHECKER"
    REFILL = "REFILL"
    LABEL = "LABEL"


class Waypoint:
    """Un punto de navegación en la ruta del cavebot."""

    def __init__(self, mark: str = "CheckMark", wp_type: str = "WALK",
                 x: int = 0, y: int = 0, z: int = 7,
                 label: str = "", options: str = ""):
        self.mark = mark
        self.wp_type = wp_type
        self.x = x
        self.y = y
        self.z = z
        self.label = label
        self.options = options
        self.status = "pending"  # pending, active, completed, skipped

    def to_dict(self) -> dict:
        return {
            "mark": self.mark,
            "wp_type": self.wp_type,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "label": self.label,
            "options": self.options,
        }

    @staticmethod
    def from_dict(d: dict) -> "Waypoint":
        return Waypoint(
            mark=d.get("mark", "CheckMark"),
            wp_type=d.get("wp_type", "WALK"),
            x=d.get("x", 0),
            y=d.get("y", 0),
            z=d.get("z", 7),
            label=d.get("label", ""),
            options=d.get("options", ""),
        )

    def __repr__(self):
        return f"<WP #{self.wp_type} mark={self.mark} ({self.x},{self.y},{self.z}) '{self.label}'>"


class CavebotEngine:
    """
    Motor de cavebot v2.
    Navega por waypoints usando template matching en el minimapa.
    Soporta múltiples tipos de waypoints y recuperación de stuck.
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"  # idle, walking, executing, stuck, paused
        self._running: bool = False

        # Waypoints
        self.waypoints: List[Waypoint] = []
        self.current_wp_index: int = 0
        self.route_name: str = ""

        # Regiones (inyectadas por calibrador)
        self._map_region: Optional[Tuple[int, int, int, int]] = None

        # Templates de marcas del minimapa
        self._mark_templates: Dict[str, np.ndarray] = {}
        self._load_mark_templates()

        # Callbacks inyectados
        self._click_fn: Optional[Callable] = None
        self._key_fn: Optional[Callable] = None
        self._log_fn: Optional[Callable] = None
        self._right_click_fn: Optional[Callable] = None

        # Referencia a targeting engine (para pausar cuando hay monstruos)
        self._targeting_engine = None

        # Configuración
        self.walk_mode: str = "click"          # "click" o "arrow"
        self.cyclic: bool = True
        self.step_delay: float = 0.25          # Delay entre pasos
        self.stuck_threshold: int = 5          # Frames sin moverse → stuck
        self.arrival_tolerance: int = 8        # Píxeles de tolerancia para llegar
        self.pause_on_monsters: bool = True    # Pausar si hay monstruos
        self.refresh_walk_enabled: bool = True # Walk-for-refresh cuando stuck

        # Timing
        self._last_step_time: float = 0.0
        self._last_walk_time: float = 0.0
        self._step_count: int = 0

        # Detección de stuck
        self._prev_map_hash: Optional[int] = None
        self._same_hash_frames: int = 0
        self._stuck_recovery_attempts: int = 0
        self._max_stuck_recovery: int = 4

        # Detección de posición en minimapa
        self._last_mark_pos: Tuple[int, int] = (0, 0)
        self._map_center: Tuple[int, int] = (0, 0)
        self._mark_precision: float = 0.80

        # Status logging
        self._last_status_log: float = 0.0

        # Hotkeys de herramientas
        self._hotkeys: Dict[str, str] = {}

    # ==================================================================
    # Templates
    # ==================================================================
    def _load_mark_templates(self):
        """Carga todas las marcas del minimapa (CheckMark, Cross, Star, etc.)."""
        if not os.path.isdir(MAP_MARKS_DIR):
            return
        for fname in os.listdir(MAP_MARKS_DIR):
            if fname.endswith(".png") and fname != "MapSettings.png" and fname != "position.png":
                key = fname.replace(".png", "")
                tpl = cv2.imread(os.path.join(MAP_MARKS_DIR, fname), cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._mark_templates[key] = tpl

    def get_available_marks(self) -> List[str]:
        """Retorna las marcas disponibles para waypoints."""
        return sorted(self._mark_templates.keys())

    # ==================================================================
    # Configuración
    # ==================================================================
    def set_click_callback(self, fn: Callable):
        """fn(x, y) - click izquierdo."""
        self._click_fn = fn

    def set_right_click_callback(self, fn: Callable):
        """fn(x, y) - click derecho (para USE items)."""
        self._right_click_fn = fn

    def set_key_callback(self, fn: Callable):
        """fn(key_name) - enviar tecla."""
        self._key_fn = fn

    def set_log_callback(self, fn: Callable):
        """fn(msg) - log del módulo."""
        self._log_fn = fn

    def set_targeting_engine(self, engine):
        """Referencia al TargetingEngine para verificar si hay monstruos."""
        self._targeting_engine = engine

    def set_map_region(self, x1, y1, x2, y2):
        """Configura la región del minimapa en el frame."""
        self._map_region = (x1, y1, x2, y2)
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        self._map_center = (cx, cy)

    def set_hotkeys(self, hotkeys: dict):
        """Configura las hotkeys de herramientas (rope, shovel, etc.)."""
        self._hotkeys = hotkeys

    def configure(self, config: dict):
        """Aplica configuración desde el dict de config."""
        cfg = config if isinstance(config, dict) else {}
        self.walk_mode = cfg.get("walk_mode", "click")
        self.cyclic = cfg.get("cyclic", True)
        self.step_delay = cfg.get("step_delay", 0.25)
        self.stuck_threshold = cfg.get("stuck_threshold", 5)
        self.pause_on_monsters = cfg.get("pause_on_monsters", True)
        self.refresh_walk_enabled = cfg.get("refresh_walk_enabled", True)

        route_file = cfg.get("current_route", "")
        if route_file and os.path.exists(route_file):
            self.load_route(route_file)

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Cavebot] {msg}")

    # ==================================================================
    # Gestión de rutas
    # ==================================================================
    def load_route(self, filepath: str) -> bool:
        """Carga una ruta desde archivo JSON."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            wps = data.get("waypoints", data if isinstance(data, list) else [])
            self.waypoints = [Waypoint.from_dict(w) for w in wps]
            self.route_name = os.path.basename(filepath)
            self.current_wp_index = 0
            self._reset_all_wp_status()
            self._log(f"Ruta cargada: {self.route_name} ({len(self.waypoints)} waypoints)")
            return True
        except Exception as e:
            self._log(f"Error cargando ruta: {e}")
            return False

    def save_route(self, filepath: str) -> bool:
        """Guarda la ruta actual en archivo JSON."""
        try:
            data = {
                "name": self.route_name or "unnamed",
                "waypoints": [w.to_dict() for w in self.waypoints],
            }
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.route_name = os.path.basename(filepath)
            self._log(f"Ruta guardada: {filepath}")
            return True
        except Exception as e:
            self._log(f"Error guardando ruta: {e}")
            return False

    def add_waypoint(self, mark: str = "CheckMark", wp_type: str = "WALK",
                     x: int = 0, y: int = 0, z: int = 7,
                     label: str = "", options: str = ""):
        """Agrega un waypoint al final de la ruta."""
        wp = Waypoint(mark=mark, wp_type=wp_type, x=x, y=y, z=z,
                      label=label, options=options)
        self.waypoints.append(wp)
        idx = len(self.waypoints) - 1
        self._log(f"WP #{idx} agregado: {wp.wp_type} ({wp.mark}) [{wp.x},{wp.y},{wp.z}] {wp.label}")

    def remove_last_waypoint(self) -> bool:
        """Elimina el último waypoint."""
        if self.waypoints:
            removed = self.waypoints.pop()
            self._log(f"WP removido: {removed}")
            if self.current_wp_index >= len(self.waypoints):
                self.current_wp_index = max(0, len(self.waypoints) - 1)
            return True
        return False

    def clear_route(self):
        """Limpia toda la ruta."""
        self.waypoints.clear()
        self.current_wp_index = 0
        self.route_name = ""
        self._log("Ruta limpiada")

    def _reset_all_wp_status(self):
        for wp in self.waypoints:
            wp.status = "pending"

    # ==================================================================
    # Loop principal
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """
        Procesamiento por frame:
        1. Verificar si hay monstruos (pausar si pause_on_monsters)
        2. Obtener waypoint actual
        3. Buscar marca en minimapa
        4. Navegar hacia la marca (click o arrow)
        5. Detectar llegada y avanzar al siguiente wp
        6. Detectar stuck y recuperar
        """
        if not self.enabled or frame is None:
            return
        if not self.waypoints:
            return

        now = time.time()

        # Log periódico (~cada 5s)
        if now - self._last_status_log >= 5.0:
            self._last_status_log = now
            wp = self._current_waypoint()
            self._log(
                f"Estado: {self.state} | WP: {self.current_wp_index + 1}/{len(self.waypoints)} "
                f"| {wp.wp_type if wp else '?'} | Pasos: {self._step_count}"
            )

        # ========== Pausar si hay monstruos ==========
        if self.pause_on_monsters and self._targeting_engine:
            if self._targeting_engine.is_in_combat():
                if self.state != "paused":
                    self._log("Pausado — en combate")
                    self.state = "paused"
                return
            elif self.state == "paused":
                self._log("Resumido — combate terminado")
                self.state = "walking"

        # ========== Respetar step delay ==========
        if now - self._last_step_time < self.step_delay:
            return
        self._last_step_time = now

        # ========== Obtener waypoint actual ==========
        wp = self._current_waypoint()
        if wp is None:
            return

        # ========== Ejecutar según tipo de waypoint ==========
        if wp.wp_type == "WALK":
            self._process_walk_waypoint(frame, wp)
        elif wp.wp_type == "STAND":
            self._process_stand_waypoint(wp)
        elif wp.wp_type in ("ROPE", "SHOVEL", "PICK", "MACHETE"):
            self._process_tool_waypoint(wp)
        elif wp.wp_type in ("LADDER", "STAIRS", "DOOR", "SEWER"):
            self._process_interaction_waypoint(frame, wp)
        elif wp.wp_type == "SINGLE_MOVE":
            self._process_single_move(wp)
        elif wp.wp_type == "LABEL":
            self._process_label_waypoint(wp)
        else:
            # Tipos avanzados: NPC_TALK, DEPOSIT_GOLD, etc. → skip por ahora
            self._log(f"WP tipo '{wp.wp_type}' no implementado — saltando")
            self._advance_waypoint()

    def _current_waypoint(self) -> Optional[Waypoint]:
        """Retorna el waypoint actual o None."""
        if 0 <= self.current_wp_index < len(self.waypoints):
            return self.waypoints[self.current_wp_index]
        return None

    # ==================================================================
    # Procesadores por tipo de waypoint
    # ==================================================================
    def _process_walk_waypoint(self, frame: np.ndarray, wp: Waypoint):
        """
        WALK: Navegar hacia la marca en el minimapa.
        1. Buscar marca en minimapa
        2. Si cerca del centro → llegamos → avanzar
        3. Si lejos → click en la marca para caminar
        4. Si no encontramos marca → stuck recovery
        """
        if self._map_region is None:
            self._log("⚠ Sin map region — presiona 'Calibrar'")
            return

        # Detectar stuck via hash del minimapa
        self._check_stuck(frame)

        if self.state == "stuck":
            self._handle_stuck_recovery()
            return

        self.state = "walking"

        # Buscar marca del wp en minimapa
        mark_x, mark_y = self._find_mark_in_minimap(frame, wp.mark)

        if mark_x == 0 and mark_y == 0:
            # No encontramos la marca → puede ser que ya pasamos o que estamos lejos
            self._same_hash_frames += 1
            if self._same_hash_frames >= self.stuck_threshold * 2:
                self._log(f"Marca '{wp.mark}' no encontrada tras {self._same_hash_frames} frames — avanzando")
                self._advance_waypoint()
            return

        # Calcular distancia al centro del minimapa
        cx, cy = self._map_center
        dist = ((mark_x - cx) ** 2 + (mark_y - cy) ** 2) ** 0.5

        if dist <= self.arrival_tolerance:
            # ¡Llegamos al waypoint!
            self._log(f"✓ Llegamos a WP #{self.current_wp_index + 1} ({wp.mark}) dist={dist:.1f}px")
            self._same_hash_frames = 0
            self._stuck_recovery_attempts = 0
            self._advance_waypoint()
        else:
            # Caminar hacia la marca
            self._walk_to(mark_x, mark_y)

    def _process_stand_waypoint(self, wp: Waypoint):
        """STAND: Esperar un tiempo y luego avanzar."""
        wait_time = float(wp.options) if wp.options else 2.0
        self._log(f"STAND — esperando {wait_time}s")
        time.sleep(wait_time)
        self._advance_waypoint()

    def _process_tool_waypoint(self, wp: Waypoint):
        """ROPE/SHOVEL/PICK/MACHETE: Usar herramienta con hotkey."""
        tool_key = wp.wp_type.lower()  # "rope", "shovel", etc.
        hotkey = self._hotkeys.get(tool_key, "")
        if not hotkey:
            self._log(f"⚠ Sin hotkey para {wp.wp_type} — configura en la pestaña Cavebot")
            self._advance_waypoint()
            return

        if self._key_fn:
            self._log(f"Usando {wp.wp_type} (tecla: {hotkey})")
            self._key_fn(hotkey)
            time.sleep(0.3)
            # Después de usar tool, click en el centro (posición del jugador)
            if self._click_fn and self._map_center != (0, 0):
                # Click en el centro del game window (donde está el jugador)
                # Los tools necesitan click en el SQM debajo del jugador
                pass
        self._advance_waypoint()

    def _process_interaction_waypoint(self, frame: np.ndarray, wp: Waypoint):
        """LADDER/STAIRS/DOOR/SEWER: Click en posición para interactuar."""
        # Para estos tipos, buscamos la marca y hacemos click
        if self._map_region is None:
            self._advance_waypoint()
            return

        mark_x, mark_y = self._find_mark_in_minimap(frame, wp.mark)
        if mark_x != 0 and mark_y != 0:
            dist = ((mark_x - self._map_center[0]) ** 2 + (mark_y - self._map_center[1]) ** 2) ** 0.5
            if dist <= self.arrival_tolerance * 1.5:
                self._log(f"Interactuando: {wp.wp_type}")
                # Click en el centro del personaje (la interacción es automática al llegar)
                self._advance_waypoint()
            else:
                self._walk_to(mark_x, mark_y)
        else:
            self._advance_waypoint()

    def _process_single_move(self, wp: Waypoint):
        """SINGLE_MOVE: Un solo paso en dirección indicada."""
        direction = wp.options.lower() if wp.options else "down"
        key_map = {
            "up": "Up", "down": "Down", "left": "Left", "right": "Right",
            "north": "Up", "south": "Down", "west": "Left", "east": "Right",
        }
        key = key_map.get(direction, "Down")
        if self._key_fn:
            self._log(f"Single move: {direction}")
            self._key_fn(key)
            time.sleep(0.3)
        self._advance_waypoint()

    def _process_label_waypoint(self, wp: Waypoint):
        """LABEL: Punto de referencia, no hace nada."""
        self._log(f"Label: {wp.label or wp.options}")
        self._advance_waypoint()

    # ==================================================================
    # Navegación
    # ==================================================================
    def _walk_to(self, target_x: int, target_y: int):
        """Camina hacia una posición en el minimapa."""
        if self.walk_mode == "click":
            self._walk_by_click(target_x, target_y)
        else:
            self._walk_by_arrow(target_x, target_y)

    def _walk_by_click(self, target_x: int, target_y: int):
        """Click en el minimapa para caminar."""
        if self._click_fn is None:
            return
        self._click_fn(target_x, target_y)
        self._step_count += 1
        self._last_walk_time = time.time()

    def _walk_by_arrow(self, target_x: int, target_y: int):
        """Arrow keys para caminar hacia el target."""
        if self._key_fn is None:
            return

        cx, cy = self._map_center
        dx = target_x - cx
        dy = target_y - cy

        # Elegir la dirección dominante
        if abs(dx) > abs(dy):
            key = "Right" if dx > 0 else "Left"
        else:
            key = "Down" if dy > 0 else "Up"

        self._key_fn(key)
        self._step_count += 1
        self._last_walk_time = time.time()

    def _advance_waypoint(self):
        """Avanza al siguiente waypoint."""
        if not self.waypoints:
            return

        # Marcar actual como completado
        wp = self._current_waypoint()
        if wp:
            wp.status = "completed"

        self.current_wp_index += 1

        if self.current_wp_index >= len(self.waypoints):
            if self.cyclic:
                self.current_wp_index = 0
                self._reset_all_wp_status()
                self._log("Ruta completada — reiniciando (cíclica)")
            else:
                self.current_wp_index = len(self.waypoints) - 1
                self._log("Ruta completada — fin")
                self.state = "idle"
                return

        next_wp = self._current_waypoint()
        if next_wp:
            next_wp.status = "active"
            self._log(f"→ WP #{self.current_wp_index + 1}: {next_wp.wp_type} ({next_wp.mark}) {next_wp.label}")

        self._same_hash_frames = 0
        self._stuck_recovery_attempts = 0

    # ==================================================================
    # Template matching en minimapa
    # ==================================================================
    def _find_mark_in_minimap(self, frame: np.ndarray, mark_name: str) -> Tuple[int, int]:
        """
        Busca una marca (CheckMark, Cross, etc.) en el minimapa.
        Retorna (x, y) coordenadas absolutas en el frame, o (0, 0).
        """
        template = self._mark_templates.get(mark_name)
        if template is None:
            return 0, 0
        if self._map_region is None:
            return 0, 0

        x1, y1, x2, y2 = self._map_region
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return 0, 0

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if roi_gray.shape[0] < template.shape[0] or roi_gray.shape[1] < template.shape[1]:
            return 0, 0

        res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= self._mark_precision:
            th, tw = template.shape[:2]
            abs_x = x1 + max_loc[0] + tw // 2
            abs_y = y1 + max_loc[1] + th // 2
            self._last_mark_pos = (abs_x, abs_y)
            return abs_x, abs_y

        return 0, 0

    # ==================================================================
    # Detección y recuperación de stuck
    # ==================================================================
    def _check_stuck(self, frame: np.ndarray):
        """
        Detecta si el personaje está stuck comparando el hash del minimapa.
        Si el minimapa no cambia en N frames → stuck.
        """
        if self._map_region is None:
            return

        x1, y1, x2, y2 = self._map_region
        h, w = frame.shape[:2]
        roi = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if roi.size == 0:
            return

        # Hash simple del minimapa (resize pequeño + hash)
        small = cv2.resize(roi, (16, 16))
        current_hash = hash(small.tobytes())

        if self._prev_map_hash is not None and current_hash == self._prev_map_hash:
            self._same_hash_frames += 1
            if self._same_hash_frames >= self.stuck_threshold:
                if self.state != "stuck":
                    self._log(f"⚠ Stuck detectado ({self._same_hash_frames} frames sin moverse)")
                    self.state = "stuck"
        else:
            if self.state == "stuck":
                self._log("Movimiento detectado — recuperado de stuck")
                self.state = "walking"
            self._same_hash_frames = 0
            self._stuck_recovery_attempts = 0

        self._prev_map_hash = current_hash

    def _handle_stuck_recovery(self):
        """
        Walk-for-refresh: camina en dirección aleatoria para destrancarse.
        Basado en TibiaAuto12 CaveBotController.
        """
        if not self.refresh_walk_enabled:
            return

        if self._stuck_recovery_attempts >= self._max_stuck_recovery:
            self._log(f"Max recovery attempts ({self._max_stuck_recovery}) — saltando waypoint")
            self._advance_waypoint()
            self.state = "walking"
            self._same_hash_frames = 0
            self._stuck_recovery_attempts = 0
            return

        self._stuck_recovery_attempts += 1
        self._log(
            f"Recovery intento {self._stuck_recovery_attempts}/{self._max_stuck_recovery}"
        )

        # Caminar en dirección aleatoria
        directions = ["Up", "Down", "Left", "Right"]
        direction = random.choice(directions)

        if self._key_fn:
            self._key_fn(direction)
            time.sleep(0.4)

        # Reset stuck counter para dar oportunidad
        self._same_hash_frames = 0
        self._prev_map_hash = None

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        """Activa el cavebot."""
        self.enabled = True
        self._running = True
        self.state = "idle" if not self.waypoints else "walking"
        self._same_hash_frames = 0
        self._stuck_recovery_attempts = 0
        self._prev_map_hash = None
        self._step_count = 0

        # Marcar primer wp como activo
        if self.waypoints:
            self.waypoints[0].status = "active"

        marks = len(self._mark_templates)
        self._log(f"Cavebot v2 activado — {len(self.waypoints)} waypoints, {marks} marcas")
        self._log(f"  Modo: {self.walk_mode}, Cíclico: {self.cyclic}")
        self._log(f"  Step delay: {self.step_delay}s, Stuck threshold: {self.stuck_threshold}")
        if self._map_region is None:
            self._log("⚠ Sin map region — presiona 'Calibrar' primero")
        if not self.waypoints:
            self._log("⚠ Sin waypoints — carga una ruta o agrega waypoints")

    def stop(self):
        """Desactiva el cavebot."""
        self.enabled = False
        self._running = False
        self.state = "idle"
        self._same_hash_frames = 0
        self._stuck_recovery_attempts = 0
        self._log("Cavebot desactivado")

    def get_status(self) -> Dict:
        """Retorna estado actual del cavebot."""
        wp = self._current_waypoint()
        return {
            "enabled": self.enabled,
            "state": self.state,
            "current_wp": self.current_wp_index + 1,
            "total_wps": len(self.waypoints),
            "current_wp_type": wp.wp_type if wp else "",
            "current_wp_mark": wp.mark if wp else "",
            "route_name": self.route_name,
            "step_count": self._step_count,
            "stuck_frames": self._same_hash_frames,
            "stuck_recovery": self._stuck_recovery_attempts,
            "walk_mode": self.walk_mode,
            "cyclic": self.cyclic,
        }
