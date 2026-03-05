"""
game_data/loader.py - Cargador de bases de datos del juego.
Carga monsters.json, items.json y npcs.json, y provee acceso
rápido a la información del juego.
"""

import json
import os
from typing import Any, Dict, List, Optional, Set


class GameData:
    """
    Cargador centralizado de datos del juego.
    Carga una vez y cachea para acceso rápido.
    """

    _instance: Optional["GameData"] = None

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__))
        self.data_dir = data_dir

        self._monsters: Dict[str, Dict] = {}
        self._items: Dict[str, Dict] = {}
        self._npcs: Dict[str, Any] = {}
        self._monster_names: Set[str] = set()
        self._item_names: Set[str] = set()
        self._travel_cities: List[str] = []
        self._potions: Dict[str, Dict] = {}
        self._city_data: Dict[str, Dict] = {}

        self._loaded = False

    @classmethod
    def instance(cls) -> "GameData":
        """Singleton para acceso global."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_all()
        return cls._instance

    # ==================================================================
    # Carga
    # ==================================================================
    def load_all(self) -> bool:
        """Carga todos los archivos JSON de datos del juego."""
        ok = True
        ok = self._load_monsters() and ok
        ok = self._load_items() and ok
        ok = self._load_npcs() and ok
        self._loaded = True
        return ok

    def _load_json(self, filename: str) -> Optional[Dict]:
        """Carga un archivo JSON desde data_dir."""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _load_monsters(self) -> bool:
        """Carga monsters.json."""
        data = self._load_json("monsters.json")
        if data and "monsters" in data:
            self._monsters = data["monsters"]
            self._monster_names = set(
                name.lower() for name in self._monsters.keys()
            )
            return True
        return False

    def _load_items(self) -> bool:
        """Carga items.json."""
        data = self._load_json("items.json")
        if data and "items" in data:
            self._items = data["items"]
            self._item_names = set(
                name.lower() for name in self._items.keys()
            )
            return True
        return False

    def _load_npcs(self) -> bool:
        """Carga npcs.json."""
        data = self._load_json("npcs.json")
        if data:
            self._npcs = data
            self._travel_cities = data.get("travel_keywords", [])
            self._potions = data.get("potions", {})
            self._city_data = data.get("cities", {})
            return True
        return False

    # ==================================================================
    # Monstruos
    # ==================================================================
    def is_monster(self, name: str) -> bool:
        """Verifica si un nombre corresponde a un monstruo conocido."""
        return name.lower() in self._monster_names

    def get_monster(self, name: str) -> Optional[Dict]:
        """Retorna datos de un monstruo por nombre (case-insensitive)."""
        for k, v in self._monsters.items():
            if k.lower() == name.lower():
                return v
        return None

    def get_monster_danger(self, name: str) -> int:
        """Retorna el nivel de peligro de un monstruo (1-10, 0 si desconocido)."""
        m = self.get_monster(name)
        return m.get("danger_level", 0) if m else 0

    def get_monster_loot(self, name: str) -> List[str]:
        """Retorna la lista de loot esperado de un monstruo."""
        m = self.get_monster(name)
        return m.get("loot", []) if m else []

    def get_all_monster_names(self) -> List[str]:
        """Retorna todos los nombres de monstruos conocidos."""
        return sorted(self._monsters.keys())

    # ==================================================================
    # Items
    # ==================================================================
    def is_known_item(self, name: str) -> bool:
        """Verifica si un item es conocido."""
        return name.lower() in self._item_names

    def get_item(self, name: str) -> Optional[Dict]:
        """Retorna datos de un item por nombre (case-insensitive)."""
        for k, v in self._items.items():
            if k.lower() == name.lower():
                return v
        return None

    def get_item_value(self, name: str) -> int:
        """Retorna el valor estimado de un item en gold."""
        item = self.get_item(name)
        return item.get("value", 0) if item else 0

    def get_item_category(self, name: str) -> str:
        """Retorna la categoría de un item."""
        item = self.get_item(name)
        return item.get("category", "unknown") if item else "unknown"

    def is_trash(self, name: str) -> bool:
        """¿Es un item basura?"""
        return self.get_item_category(name) == "trash"

    def is_valuable(self, name: str) -> bool:
        """¿Es un item valioso? (valuable, equipment, creature_product con valor > 500)"""
        item = self.get_item(name)
        if not item:
            return False
        cat = item.get("category", "")
        val = item.get("value", 0)
        return cat in ("valuable", "equipment", "creature_product") and val >= 500

    def get_items_by_category(self, category: str) -> List[str]:
        """Retorna nombres de items de una categoría específica."""
        return sorted(
            k for k, v in self._items.items()
            if v.get("category") == category
        )

    # ==================================================================
    # NPCs / Ciudades
    # ==================================================================
    def get_npc_dialogue(self, npc_type: str) -> Optional[Dict]:
        """Retorna la secuencia de diálogo de un tipo de NPC."""
        npc_types = self._npcs.get("npc_types", {})
        return npc_types.get(npc_type)

    def get_travel_cities(self) -> List[str]:
        """Retorna la lista de ciudades válidas para travel."""
        return list(self._travel_cities)

    def get_city_data(self, city: str) -> Optional[Dict]:
        """Retorna datos de una ciudad (NPC locations, depot, etc)."""
        return self._city_data.get(city)

    def get_city_depot(self, city: str) -> Optional[List[int]]:
        """Retorna la ubicación del depot de una ciudad."""
        cd = self._city_data.get(city)
        if cd and "depot" in cd:
            return cd["depot"].get("location")
        return None

    def get_city_names(self) -> List[str]:
        """Retorna todos los nombres de ciudades."""
        return sorted(self._city_data.keys())

    # ==================================================================
    # Pociones
    # ==================================================================
    def get_health_potions(self) -> Dict[str, Dict]:
        """Retorna todas las pociones de salud disponibles."""
        return self._potions.get("health", {})

    def get_mana_potions(self) -> Dict[str, Dict]:
        """Retorna todas las pociones de mana disponibles."""
        return self._potions.get("mana", {})

    def get_spirit_potions(self) -> Dict[str, Dict]:
        """Retorna todas las pociones de espíritu disponibles."""
        return self._potions.get("spirit", {})

    def get_all_potion_names(self) -> List[str]:
        """Retorna nombres de todas las pociones."""
        names = []
        for category in self._potions.values():
            names.extend(category.keys())
        return sorted(names)

    # ==================================================================
    # Info
    # ==================================================================
    @property
    def loaded(self) -> bool:
        return self._loaded

    def __repr__(self) -> str:
        return (
            f"<GameData monsters={len(self._monsters)} "
            f"items={len(self._items)} "
            f"cities={len(self._city_data)}>"
        )
