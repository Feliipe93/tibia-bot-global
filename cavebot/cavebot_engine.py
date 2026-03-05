"""
cavebot/cavebot_engine.py - Motor principal del cavebot.
Gestiona waypoints, navegación, ejecución de acciones especiales
(rope, shovel, ladder) y rutas cíclicas.
"""

import json
import os
import time
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from cavebot.pathfinder import Pathfinder
from utils.geometry import manhattan_distance, direction_to


class WaypointType(Enum):
    """Tipos de waypoint soportados."""
    WALK = "walk"           # Caminar normalmente
    STAND = "stand"         # Esperar X segundos
    ROPE = "rope"           # Usar cuerda
    SHOVEL = "shovel"       # Usar pala
    LADDER = "ladder"       # Subir/bajar escalera
    STAIRS_UP = "stairs_up"
    STAIRS_DOWN = "stairs_down"
    DOOR = "door"           # Abrir puerta
    USE = "use"             # Usar item genérico
    NODE = "node"           # Punto de decisión (sin acción)
    REFILL = "refill"       # Ir a refillear


class CavebotState(Enum):
    """Estado del cavebot."""
    IDLE = "idle"
    WALKING = "walking"
    EXECUTING_ACTION = "executing_action"
    WAITING = "waiting"
    PATHFINDING = "pathfinding"
    STUCK = "stuck"
    PAUSED = "paused"


class Waypoint:
    """Representa un punto de ruta."""

    def __init__(
        self,
        wp_type: WaypointType = WaypointType.WALK,
        x: int = 0,
        y: int = 0,
        z: int = 7,
        label: str = "",
        action_key: str = "",
        wait_seconds: float = 0.0,
        range_tiles: int = 1,
    ):
        self.type = wp_type
        self.x = x
        self.y = y
        self.z = z  # Floor level de Tibia (7 = superficie)
        self.label = label
        self.action_key = action_key
        self.wait_seconds = wait_seconds
        self.range_tiles = range_tiles

    @property
    def coords(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "label": self.label,
            "action_key": self.action_key,
            "wait_seconds": self.wait_seconds,
            "range_tiles": self.range_tiles,
        }

    @staticmethod
    def from_dict(data: Dict) -> "Waypoint":
        return Waypoint(
            wp_type=WaypointType(data.get("type", "walk")),
            x=data.get("x", 0),
            y=data.get("y", 0),
            z=data.get("z", 7),
            label=data.get("label", ""),
            action_key=data.get("action_key", ""),
            wait_seconds=data.get("wait_seconds", 0.0),
            range_tiles=data.get("range_tiles", 1),
        )

    def __repr__(self) -> str:
        return f"<WP {self.type.value} ({self.x},{self.y},{self.z}) '{self.label}'>"


class CavebotEngine:
    """
    Motor de navegación del cavebot.
    Administra la lista de waypoints, el estado de navegación,
    y la interacción con el pathfinder.
    """

    def __init__(self):
        self.waypoints: List[Waypoint] = []
        self.current_index: int = 0
        self.state: CavebotState = CavebotState.IDLE
        self.cyclic: bool = True

        self.pathfinder = Pathfinder()

        # Posición actual del jugador (actualizada por el minimapa)
        self.player_pos: Optional[Tuple[int, int]] = None
        self.player_floor: int = 7

        # Ruta calculada actual
        self.current_path: List[Tuple[int, int]] = []
        self.path_step: int = 0

        # Timing
        self.last_move_time: float = 0.0
        self.last_action_time: float = 0.0
        self.wait_until: float = 0.0
        self.stuck_counter: int = 0
        self.stuck_threshold: int = 5

        # Callbacks para acciones
        self._on_walk: Optional[Callable] = None
        self._on_use_key: Optional[Callable] = None
        self._on_click_tile: Optional[Callable] = None

        # Métricas
        self.total_steps: int = 0
        self.waypoints_completed: int = 0

    # ==================================================================
    # Gestión de waypoints
    # ==================================================================
    def add_waypoint(self, waypoint: Waypoint) -> None:
        """Agrega un waypoint al final de la lista."""
        self.waypoints.append(waypoint)

    def insert_waypoint(self, index: int, waypoint: Waypoint) -> None:
        """Inserta un waypoint en una posición específica."""
        self.waypoints.insert(index, waypoint)

    def remove_waypoint(self, index: int) -> None:
        """Elimina un waypoint por índice."""
        if 0 <= index < len(self.waypoints):
            self.waypoints.pop(index)
            if self.current_index >= len(self.waypoints):
                self.current_index = 0

    def move_waypoint(self, from_idx: int, to_idx: int) -> None:
        """Mueve un waypoint de posición."""
        if 0 <= from_idx < len(self.waypoints) and 0 <= to_idx < len(self.waypoints):
            wp = self.waypoints.pop(from_idx)
            self.waypoints.insert(to_idx, wp)

    def clear_waypoints(self) -> None:
        """Elimina todos los waypoints."""
        self.waypoints.clear()
        self.current_index = 0
        self.state = CavebotState.IDLE

    @property
    def current_waypoint(self) -> Optional[Waypoint]:
        """Waypoint actual al que se dirige."""
        if 0 <= self.current_index < len(self.waypoints):
            return self.waypoints[self.current_index]
        return None

    # ==================================================================
    # Guardar / Cargar rutas
    # ==================================================================
    def save_route(self, filepath: str) -> bool:
        """Guarda la ruta actual en un archivo JSON."""
        try:
            data = {
                "name": os.path.splitext(os.path.basename(filepath))[0],
                "cyclic": self.cyclic,
                "waypoints": [wp.to_dict() for wp in self.waypoints],
            }
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_route(self, filepath: str) -> bool:
        """Carga una ruta desde un archivo JSON."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.waypoints = [Waypoint.from_dict(wp) for wp in data.get("waypoints", [])]
            self.cyclic = data.get("cyclic", True)
            self.current_index = 0
            self.state = CavebotState.IDLE
            return True
        except Exception:
            return False

    # ==================================================================
    # Callbacks
    # ==================================================================
    def set_walk_callback(self, callback: Callable) -> None:
        """Callback para caminar: callback(direction: str)"""
        self._on_walk = callback

    def set_use_key_callback(self, callback: Callable) -> None:
        """Callback para usar tecla: callback(key_name: str)"""
        self._on_use_key = callback

    def set_click_tile_callback(self, callback: Callable) -> None:
        """Callback para click en tile: callback(tile_x: int, tile_y: int)"""
        self._on_click_tile = callback

    # ==================================================================
    # Lógica principal
    # ==================================================================
    def update(self, frame: np.ndarray, player_pos: Optional[Tuple[int, int]] = None) -> None:
        """
        Actualización principal del cavebot. Llamada cada frame.

        Args:
            frame: Frame actual de OBS (para análisis de minimapa).
            player_pos: Posición actual del jugador (si ya se detectó).
        """
        if self.state == CavebotState.PAUSED:
            return

        if not self.waypoints:
            self.state = CavebotState.IDLE
            return

        if player_pos is not None:
            self.player_pos = player_pos

        if self.player_pos is None:
            return

        # Estado: esperando
        if self.state == CavebotState.WAITING:
            if time.time() >= self.wait_until:
                self.state = CavebotState.WALKING
                self._advance_waypoint()
            return

        target_wp = self.current_waypoint
        if target_wp is None:
            self.state = CavebotState.IDLE
            return

        # ¿Ya llegamos al waypoint actual?
        dist = manhattan_distance(self.player_pos, target_wp.coords)
        if dist <= target_wp.range_tiles:
            self._execute_waypoint_action(target_wp)
            return

        # Necesitamos caminar
        self.state = CavebotState.WALKING
        self._walk_towards(target_wp)

    def _walk_towards(self, waypoint: Waypoint) -> None:
        """Camina hacia el waypoint actual."""
        if self.player_pos is None:
            return

        # Cooldown entre pasos
        if time.time() - self.last_move_time < 0.3:
            return

        direction = direction_to(self.player_pos, waypoint.coords)
        if direction is None:
            return

        if self._on_walk:
            self._on_walk(direction)
            self.last_move_time = time.time()
            self.total_steps += 1

    def _execute_waypoint_action(self, waypoint: Waypoint) -> None:
        """Ejecuta la acción del waypoint actual."""
        if waypoint.type == WaypointType.WALK or waypoint.type == WaypointType.NODE:
            # Sin acción especial, avanzar
            self._advance_waypoint()

        elif waypoint.type == WaypointType.STAND:
            self.state = CavebotState.WAITING
            self.wait_until = time.time() + waypoint.wait_seconds

        elif waypoint.type in (
            WaypointType.ROPE,
            WaypointType.SHOVEL,
            WaypointType.USE,
            WaypointType.DOOR,
        ):
            self.state = CavebotState.EXECUTING_ACTION
            if self._on_use_key and waypoint.action_key:
                self._on_use_key(waypoint.action_key)
            self.last_action_time = time.time()
            self._advance_waypoint()

        elif waypoint.type in (
            WaypointType.LADDER,
            WaypointType.STAIRS_UP,
            WaypointType.STAIRS_DOWN,
        ):
            # Click en el tile de la escalera
            if self._on_click_tile:
                self._on_click_tile(waypoint.x, waypoint.y)
            self._advance_waypoint()

        elif waypoint.type == WaypointType.REFILL:
            # Pausar módulos de combate, solo healer activo
            self.state = CavebotState.WAITING
            self.wait_until = time.time() + waypoint.wait_seconds

        else:
            self._advance_waypoint()

    def _advance_waypoint(self) -> None:
        """Avanza al siguiente waypoint."""
        self.waypoints_completed += 1
        self.current_index += 1
        self.stuck_counter = 0
        self.current_path = []
        self.path_step = 0

        if self.current_index >= len(self.waypoints):
            if self.cyclic:
                self.current_index = 0
            else:
                self.state = CavebotState.IDLE
                return

        self.state = CavebotState.WALKING

    # ==================================================================
    # Control
    # ==================================================================
    def start(self) -> None:
        """Inicia la navegación desde el waypoint actual."""
        if self.waypoints:
            self.state = CavebotState.WALKING
            self.stuck_counter = 0

    def pause(self) -> None:
        """Pausa la navegación."""
        self.state = CavebotState.PAUSED

    def resume(self) -> None:
        """Reanuda la navegación."""
        if self.state == CavebotState.PAUSED:
            self.state = CavebotState.WALKING

    def reset(self) -> None:
        """Reinicia al primer waypoint."""
        self.current_index = 0
        self.state = CavebotState.IDLE
        self.stuck_counter = 0
        self.current_path = []

    # ==================================================================
    # Info
    # ==================================================================
    def get_status(self) -> Dict:
        """Retorna estado actual del cavebot."""
        wp = self.current_waypoint
        return {
            "state": self.state.value,
            "current_index": self.current_index,
            "total_waypoints": len(self.waypoints),
            "current_wp": wp.to_dict() if wp else None,
            "player_pos": self.player_pos,
            "total_steps": self.total_steps,
            "waypoints_completed": self.waypoints_completed,
            "cyclic": self.cyclic,
        }

    def __repr__(self) -> str:
        return (
            f"<CavebotEngine state={self.state.value} "
            f"wp={self.current_index}/{len(self.waypoints)} "
            f"steps={self.total_steps}>"
        )
