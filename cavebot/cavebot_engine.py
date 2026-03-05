"""
cavebot/cavebot_engine.py - Motor de navegación por minimapa FUNCIONAL.
Usa template matching para encontrar marcas en el minimapa y
hace click para navegar hacia ellas.
Basado en TibiaAuto12/engine/CaveBot/CaveBotController.py.
"""

import os
import json
import time
import cv2
import numpy as np
from typing import Callable, Dict, List, Optional, Tuple

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
MAP_DIR = os.path.join(IMAGES_DIR, "MapSettings")


class Waypoint:
    """Un punto de ruta en el script del cavebot."""
    def __init__(self, mark: str, wp_type: str = "walk", status: bool = False):
        self.mark = mark         # Nombre de la marca en el minimapa (ej: "CheckMark")
        self.wp_type = wp_type   # "walk", "rope", "shovel", "stand"
        self.status = status     # True = waypoint actual

    def to_dict(self):
        return {"mark": self.mark, "type": self.wp_type, "status": self.status}

    @staticmethod
    def from_dict(d):
        return Waypoint(d.get("mark", ""), d.get("type", "walk"), d.get("status", False))


class CavebotEngine:
    """
    Motor de cavebot basado en navegación por minimapa.
    Lee una ruta (lista de waypoints) y navega haciendo click
    en las marcas del minimapa.
    """

    def __init__(self):
        # Estado
        self.enabled: bool = False
        self.state: str = "idle"
        self.current_wp_index: int = 0

        # Ruta
        self.waypoints: List[Waypoint] = []
        self.route_name: str = ""
        self.cyclic: bool = True

        # Regiones
        self.map_region: Optional[Tuple[int, int, int, int]] = None

        # Templates de marcas del minimapa
        self._mark_templates: Dict[str, np.ndarray] = {}

        # Configuración
        self.walk_mode: str = "click"   # "click" o "arrow"
        self.stand_time: float = 0.3
        self.arrival_zone: int = 48     # Píxeles desde el borde para considerar "llegó"
        self.mark_precision: float = 0.70

        # Callbacks
        self._click_fn: Optional[Callable] = None    # click(x, y)
        self._key_fn: Optional[Callable] = None       # send_key(key_name)
        self._log_fn: Optional[Callable] = None

        # Timing
        self.last_nav_time: float = 0.0
        self.nav_interval: float = 1.0   # Segundos entre acciones de navegación
        self.steps: int = 0

        # Cargar templates de marcas
        self._load_mark_templates()

    def _load_mark_templates(self):
        """Carga todas las imágenes de marcas del minimapa."""
        if not os.path.isdir(MAP_DIR):
            return
        for fname in os.listdir(MAP_DIR):
            if fname.endswith(".png") and fname != "MapSettings.png" and fname != "position.png":
                key = fname.replace(".png", "")
                tpl = cv2.imread(os.path.join(MAP_DIR, fname), cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._mark_templates[key] = tpl

    # ==================================================================
    # Configuración
    # ==================================================================
    def set_click_callback(self, fn: Callable):
        self._click_fn = fn

    def set_key_callback(self, fn: Callable):
        self._key_fn = fn

    def set_log_callback(self, fn: Callable):
        self._log_fn = fn

    def set_map_region(self, x1, y1, x2, y2):
        self.map_region = (x1, y1, x2, y2)

    def configure(self, config: dict):
        cavebot = config if isinstance(config, dict) else {}
        self.walk_mode = cavebot.get("walk_mode", "click")
        self.cyclic = cavebot.get("cyclic", True)
        self.stand_time = cavebot.get("stand_time", 0.3)
        self.nav_interval = cavebot.get("nav_interval", 1.0)

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Cavebot] {msg}")

    # ==================================================================
    # Manejo de rutas
    # ==================================================================
    def load_route(self, path: str) -> bool:
        """Carga una ruta desde un archivo JSON."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.waypoints = [Waypoint.from_dict(d) for d in data]
            self.route_name = os.path.basename(path)
            self.current_wp_index = 0
            if self.waypoints:
                self.waypoints[0].status = True
            self._log(f"Ruta cargada: {self.route_name} ({len(self.waypoints)} waypoints)")
            return True
        except Exception as e:
            self._log(f"Error cargando ruta: {e}")
            return False

    def save_route(self, path: str) -> bool:
        """Guarda la ruta actual en un archivo JSON."""
        try:
            data = [wp.to_dict() for wp in self.waypoints]
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
            self._log(f"Ruta guardada: {path}")
            return True
        except Exception as e:
            self._log(f"Error guardando ruta: {e}")
            return False

    def add_waypoint(self, mark: str, wp_type: str = "walk"):
        """Agrega un waypoint al final de la ruta."""
        wp = Waypoint(mark, wp_type)
        self.waypoints.append(wp)
        self._log(f"Waypoint agregado: {mark} ({wp_type})")

    def remove_last_waypoint(self):
        if self.waypoints:
            removed = self.waypoints.pop()
            self._log(f"Waypoint eliminado: {removed.mark}")

    def clear_route(self):
        self.waypoints.clear()
        self.current_wp_index = 0
        self._log("Ruta limpiada")

    def get_available_marks(self) -> List[str]:
        """Retorna los nombres de marcas disponibles."""
        return list(self._mark_templates.keys())

    # ==================================================================
    # Navegación (llamado por dispatcher)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """Procesamiento principal del cavebot."""
        if not self.enabled or frame is None:
            return
        if not self.waypoints:
            return
        if self.map_region is None:
            self._log("Sin región de minimapa - necesita calibración")
            return

        now = time.time()
        if now - self.last_nav_time < self.nav_interval:
            return

        self.last_nav_time = now
        self.state = "navigating"

        # Obtener waypoint actual
        if self.current_wp_index >= len(self.waypoints):
            if self.cyclic:
                self.current_wp_index = 0
            else:
                self.state = "finished"
                self._log("Ruta completada")
                return

        wp = self.waypoints[self.current_wp_index]

        # Verificar si ya llegamos al waypoint
        if self._check_arrival(frame, wp.mark):
            self._log(f"Llegamos a WP #{self.current_wp_index}: {wp.mark}")
            self._handle_waypoint_type(wp)
            self._advance_waypoint()
            return

        # Si no hemos llegado, navegar hacia la marca
        self._navigate_to_mark(frame, wp.mark)

    def _find_mark_in_map(self, frame: np.ndarray, mark_name: str) -> Tuple[int, int]:
        """
        Busca una marca en el minimapa. Retorna (x, y) absoluto en el frame.
        """
        template = self._mark_templates.get(mark_name)
        if template is None or self.map_region is None:
            return 0, 0

        x1, y1, x2, y2 = self.map_region
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

        if max_val >= self.mark_precision:
            th, tw = template.shape[:2]
            abs_x = x1 + max_loc[0] + tw // 2
            abs_y = y1 + max_loc[1] + th // 2
            return abs_x, abs_y

        return 0, 0

    def _check_arrival(self, frame: np.ndarray, mark_name: str) -> bool:
        """
        Verifica si la marca está en la zona central del minimapa (±arrival_zone px).
        Si está en el centro, significa que el jugador llegó al waypoint.
        """
        template = self._mark_templates.get(mark_name)
        if template is None or self.map_region is None:
            return False

        x1, y1, x2, y2 = self.map_region
        # Zona central del minimapa
        cx1 = x1 + self.arrival_zone
        cy1 = y1 + self.arrival_zone
        cx2 = x2 - self.arrival_zone
        cy2 = y2 - self.arrival_zone

        h, w = frame.shape[:2]
        cx1, cy1 = max(0, cx1), max(0, cy1)
        cx2, cy2 = min(w, cx2), min(h, cy2)

        roi = frame[cy1:cy2, cx1:cx2]
        if roi.size == 0:
            return False

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if roi_gray.shape[0] < template.shape[0] or roi_gray.shape[1] < template.shape[1]:
            return False

        res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)

        return max_val >= self.mark_precision

    def _navigate_to_mark(self, frame: np.ndarray, mark_name: str):
        """Click en la marca del minimapa para caminar hacia ella."""
        x, y = self._find_mark_in_map(frame, mark_name)
        if x != 0 and y != 0:
            if self._click_fn:
                self._click_fn(x, y)
                self.steps += 1
        else:
            self._log(f"Marca '{mark_name}' no encontrada en minimapa")

    def _handle_waypoint_type(self, wp: Waypoint):
        """Ejecuta la acción del tipo de waypoint."""
        if wp.wp_type == "rope" and self._key_fn:
            self._key_fn("rope")
            time.sleep(0.3)
        elif wp.wp_type == "shovel" and self._key_fn:
            self._key_fn("shovel")
            time.sleep(0.3)
        elif wp.wp_type == "stand":
            time.sleep(self.stand_time)

    def _advance_waypoint(self):
        """Avanza al siguiente waypoint."""
        if self.current_wp_index < len(self.waypoints):
            self.waypoints[self.current_wp_index].status = False
        self.current_wp_index += 1
        if self.current_wp_index >= len(self.waypoints):
            if self.cyclic:
                self.current_wp_index = 0
        if self.current_wp_index < len(self.waypoints):
            self.waypoints[self.current_wp_index].status = True

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self.state = "navigating"
        self._log("Cavebot activado")
        if not self.waypoints:
            self._log("⚠ Sin waypoints cargados — usa 'Cargar Ruta' para seleccionar un archivo de ruta")
        else:
            self._log(f"Ruta: {self.route_name} ({len(self.waypoints)} waypoints)")
        if self.map_region is None:
            self._log("⚠ Sin región de minimapa — presiona 'Calibrar' primero")
        marks = len(self._mark_templates)
        self._log(f"Templates de marcas: {marks} cargados")

    def stop(self):
        self.enabled = False
        self.state = "idle"
        self._log("Cavebot desactivado")

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "route": self.route_name,
            "current_wp": self.current_wp_index,
            "total_wps": len(self.waypoints),
            "steps": self.steps,
            "marks_loaded": len(self._mark_templates),
        }
