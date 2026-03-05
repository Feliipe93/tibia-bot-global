"""
cavebot/waypoint_editor.py - Editor y gestor de waypoints.
Gestiona la estructura de datos de waypoints, permite
agregar/editar/eliminar waypoints, y guardar/cargar rutas.
"""

import json
import os
from typing import Callable, Dict, List, Optional, Tuple

from cavebot.cavebot_engine import Waypoint, WaypointType


class WaypointRoute:
    """
    Representa una ruta completa de waypoints.
    Maneja persistencia, validación y metadatos.
    """

    def __init__(self, name: str = "Nueva Ruta"):
        self.name: str = name
        self.waypoints: List[Waypoint] = []
        self.cyclic: bool = True
        self.description: str = ""
        self.filepath: Optional[str] = None

        # Callback cuando la ruta cambia
        self._on_change: Optional[Callable] = None

    # ==================================================================
    # CRUD de waypoints
    # ==================================================================
    def add(
        self,
        wp_type: WaypointType,
        x: int,
        y: int,
        z: int = 7,
        label: str = "",
        action_key: str = "",
        wait_seconds: float = 0.0,
        range_tiles: int = 1,
    ) -> Waypoint:
        """Crea y agrega un nuevo waypoint."""
        wp = Waypoint(
            wp_type=wp_type,
            x=x,
            y=y,
            z=z,
            label=label or f"WP-{len(self.waypoints) + 1}",
            action_key=action_key,
            wait_seconds=wait_seconds,
            range_tiles=range_tiles,
        )
        self.waypoints.append(wp)
        self._notify_change()
        return wp

    def add_walk(self, x: int, y: int, z: int = 7, label: str = "") -> Waypoint:
        """Atajo para agregar un waypoint de caminar."""
        return self.add(WaypointType.WALK, x, y, z, label)

    def add_stand(self, x: int, y: int, z: int = 7, seconds: float = 3.0, label: str = "") -> Waypoint:
        """Atajo para agregar un waypoint de espera."""
        return self.add(WaypointType.STAND, x, y, z, label, wait_seconds=seconds)

    def add_rope(self, x: int, y: int, z: int = 7, key: str = "", label: str = "") -> Waypoint:
        """Atajo para agregar un waypoint de cuerda."""
        return self.add(WaypointType.ROPE, x, y, z, label, action_key=key)

    def add_shovel(self, x: int, y: int, z: int = 7, key: str = "", label: str = "") -> Waypoint:
        """Atajo para agregar un waypoint de pala."""
        return self.add(WaypointType.SHOVEL, x, y, z, label, action_key=key)

    def add_ladder(self, x: int, y: int, z: int = 7, label: str = "") -> Waypoint:
        """Atajo para agregar un waypoint de escalera."""
        return self.add(WaypointType.LADDER, x, y, z, label)

    def insert(self, index: int, waypoint: Waypoint) -> None:
        """Inserta un waypoint en posición específica."""
        self.waypoints.insert(index, waypoint)
        self._notify_change()

    def remove(self, index: int) -> Optional[Waypoint]:
        """Elimina un waypoint por índice."""
        if 0 <= index < len(self.waypoints):
            wp = self.waypoints.pop(index)
            self._notify_change()
            return wp
        return None

    def move_up(self, index: int) -> bool:
        """Mueve un waypoint una posición arriba."""
        if 1 <= index < len(self.waypoints):
            self.waypoints[index], self.waypoints[index - 1] = (
                self.waypoints[index - 1],
                self.waypoints[index],
            )
            self._notify_change()
            return True
        return False

    def move_down(self, index: int) -> bool:
        """Mueve un waypoint una posición abajo."""
        if 0 <= index < len(self.waypoints) - 1:
            self.waypoints[index], self.waypoints[index + 1] = (
                self.waypoints[index + 1],
                self.waypoints[index],
            )
            self._notify_change()
            return True
        return False

    def update(self, index: int, **kwargs) -> bool:
        """Actualiza campos de un waypoint existente."""
        if 0 <= index < len(self.waypoints):
            wp = self.waypoints[index]
            for key, value in kwargs.items():
                if key == "type" and isinstance(value, str):
                    wp.type = WaypointType(value)
                elif key == "type" and isinstance(value, WaypointType):
                    wp.type = value
                elif hasattr(wp, key):
                    setattr(wp, key, value)
            self._notify_change()
            return True
        return False

    def clear(self) -> None:
        """Elimina todos los waypoints."""
        self.waypoints.clear()
        self._notify_change()

    def get(self, index: int) -> Optional[Waypoint]:
        """Retorna waypoint por índice."""
        if 0 <= index < len(self.waypoints):
            return self.waypoints[index]
        return None

    @property
    def count(self) -> int:
        return len(self.waypoints)

    # ==================================================================
    # Validación
    # ==================================================================
    def validate(self) -> List[str]:
        """Valida la ruta y retorna lista de advertencias."""
        warnings = []
        if not self.waypoints:
            warnings.append("La ruta está vacía")
            return warnings

        for i, wp in enumerate(self.waypoints):
            if wp.type in (WaypointType.ROPE, WaypointType.SHOVEL, WaypointType.USE):
                if not wp.action_key:
                    warnings.append(f"WP #{i+1} ({wp.type.value}): Sin tecla de acción asignada")

            if wp.type == WaypointType.STAND and wp.wait_seconds <= 0:
                warnings.append(f"WP #{i+1} (stand): Tiempo de espera debe ser > 0")

        # Verificar waypoints duplicados consecutivos
        for i in range(1, len(self.waypoints)):
            prev = self.waypoints[i - 1]
            curr = self.waypoints[i]
            if prev.x == curr.x and prev.y == curr.y and prev.z == curr.z:
                if prev.type == curr.type == WaypointType.WALK:
                    warnings.append(
                        f"WP #{i} y #{i+1}: Waypoints de caminar duplicados en ({curr.x},{curr.y})"
                    )

        return warnings

    # ==================================================================
    # Persistencia JSON
    # ==================================================================
    def to_dict(self) -> Dict:
        """Serializa la ruta completa a diccionario."""
        return {
            "name": self.name,
            "description": self.description,
            "cyclic": self.cyclic,
            "waypoint_count": len(self.waypoints),
            "waypoints": [wp.to_dict() for wp in self.waypoints],
        }

    @staticmethod
    def from_dict(data: Dict) -> "WaypointRoute":
        """Crea una ruta desde un diccionario."""
        route = WaypointRoute(name=data.get("name", "Ruta cargada"))
        route.description = data.get("description", "")
        route.cyclic = data.get("cyclic", True)
        route.waypoints = [
            Waypoint.from_dict(wp) for wp in data.get("waypoints", [])
        ]
        return route

    def save(self, filepath: Optional[str] = None) -> bool:
        """Guarda la ruta en un archivo JSON."""
        path = filepath or self.filepath
        if not path:
            return False
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            self.filepath = path
            return True
        except Exception:
            return False

    @staticmethod
    def load(filepath: str) -> Optional["WaypointRoute"]:
        """Carga una ruta desde un archivo JSON."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            route = WaypointRoute.from_dict(data)
            route.filepath = filepath
            return route
        except Exception:
            return None

    # ==================================================================
    # Utilidades
    # ==================================================================
    def get_summary(self) -> str:
        """Resumen de la ruta."""
        type_counts: Dict[str, int] = {}
        for wp in self.waypoints:
            t = wp.type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        parts = [f"{self.name}: {self.count} waypoints"]
        for t, c in type_counts.items():
            parts.append(f"  {t}: {c}")
        if self.cyclic:
            parts.append("  [Cíclica]")
        return "\n".join(parts)

    def duplicate(self) -> "WaypointRoute":
        """Crea una copia de la ruta."""
        return WaypointRoute.from_dict(self.to_dict())

    def set_on_change(self, callback: Callable) -> None:
        """Establece callback para cuando la ruta cambia."""
        self._on_change = callback

    def _notify_change(self) -> None:
        """Notifica cambios a observers."""
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"<WaypointRoute '{self.name}' {self.count} wps {'cyclic' if self.cyclic else 'linear'}>"

    def __len__(self) -> int:
        return len(self.waypoints)

    def __iter__(self):
        return iter(self.waypoints)

    def __getitem__(self, index: int) -> Waypoint:
        return self.waypoints[index]
