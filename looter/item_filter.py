"""
looter/item_filter.py - Filtro de items para el looteo.
Gestiona listas de items valiosos, basura, y gold.
Determina qué items recoger y cuáles ignorar.
"""

from typing import Dict, List, Optional, Set


class ItemCategory:
    """Categorías de items."""
    GOLD = "gold"
    VALUABLE = "valuable"
    EQUIPMENT = "equipment"
    STACKABLE = "stackable"
    USABLE = "usable"
    TRASH = "trash"
    UNKNOWN = "unknown"


class ItemEntry:
    """Representa un item en las listas del filtro."""

    def __init__(
        self,
        name: str,
        category: str = ItemCategory.UNKNOWN,
        min_value: int = 0,
        pick_up: bool = True,
        backpack_index: int = 0,
    ):
        self.name = name.lower()
        self.category = category
        self.min_value = min_value      # Valor mínimo en gold para recoger
        self.pick_up = pick_up          # ¿Recoger este item?
        self.backpack_index = backpack_index  # A qué backpack mover

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category,
            "min_value": self.min_value,
            "pick_up": self.pick_up,
            "backpack_index": self.backpack_index,
        }

    @staticmethod
    def from_dict(data: Dict) -> "ItemEntry":
        return ItemEntry(
            name=data.get("name", ""),
            category=data.get("category", ItemCategory.UNKNOWN),
            min_value=data.get("min_value", 0),
            pick_up=data.get("pick_up", True),
            backpack_index=data.get("backpack_index", 0),
        )

    def __repr__(self) -> str:
        action = "✓" if self.pick_up else "✗"
        return f"<Item '{self.name}' {self.category} {action}>"


class ItemFilter:
    """
    Filtro de items para el looter.
    Decide qué items recoger y a qué backpack enviarlos.
    """

    def __init__(self):
        # Items que SIEMPRE se recogen
        self._pickup_list: Dict[str, ItemEntry] = {}

        # Items que NUNCA se recogen
        self._ignore_list: Set[str] = set()

        # Configuración general
        self.pick_gold: bool = True
        self.pick_platinum: bool = True
        self.pick_crystal: bool = True
        self.min_gold_value: int = 0
        self.pick_unknown_items: bool = False  # ¿Recoger items no catalogados?
        self.pick_equipment: bool = True        # ¿Recoger equipo?
        self.pick_stackables: bool = True       # ¿Recoger apilables?

        # Cargar items comunes por defecto
        self._init_default_items()

    def _init_default_items(self) -> None:
        """Carga items comunes de Tibia."""
        # Gold siempre
        self.add_pickup("gold coin", ItemCategory.GOLD)
        self.add_pickup("platinum coin", ItemCategory.GOLD)
        self.add_pickup("crystal coin", ItemCategory.GOLD)

        # Items valiosos comunes
        valuable_items = [
            "small diamond", "small sapphire", "small ruby",
            "small emerald", "small amethyst",
            "gold ingot", "platinum amulet",
            "blue gem", "green gem", "yellow gem", "violet gem",
            "giant sword", "magic plate armor",
            "sudden death rune", "great mana potion",
            "ultimate health potion", "ultimate mana potion",
            "supreme health potion",
        ]
        for item in valuable_items:
            self.add_pickup(item, ItemCategory.VALUABLE)

        # Items basura comunes
        trash_items = [
            "torch", "leather armor", "leather helmet",
            "leather legs", "leather boots",
            "sabre", "dagger", "short sword",
            "bone", "meat", "fish",
            "empty vial",
        ]
        for item in trash_items:
            self.add_ignore(item)

    # ==================================================================
    # Gestión de listas
    # ==================================================================
    def add_pickup(
        self,
        name: str,
        category: str = ItemCategory.UNKNOWN,
        min_value: int = 0,
        backpack_index: int = 0,
    ) -> None:
        """Agrega un item a la lista de pickup."""
        key = name.lower().strip()
        self._pickup_list[key] = ItemEntry(
            name=key,
            category=category,
            min_value=min_value,
            pick_up=True,
            backpack_index=backpack_index,
        )
        # Remover de ignore si estaba
        self._ignore_list.discard(key)

    def add_ignore(self, name: str) -> None:
        """Agrega un item a la lista de ignorados."""
        key = name.lower().strip()
        self._ignore_list.add(key)
        # Remover de pickup si estaba
        self._pickup_list.pop(key, None)

    def remove_pickup(self, name: str) -> None:
        """Remueve un item de la lista de pickup."""
        self._pickup_list.pop(name.lower().strip(), None)

    def remove_ignore(self, name: str) -> None:
        """Remueve un item de la lista de ignorados."""
        self._ignore_list.discard(name.lower().strip())

    # ==================================================================
    # Decisiones
    # ==================================================================
    def should_pickup(self, item_name: str) -> bool:
        """
        Decide si un item debe ser recogido.

        Args:
            item_name: Nombre del item.

        Returns:
            True si debe ser recogido.
        """
        key = item_name.lower().strip()

        # ¿Está en la lista de ignorados?
        if key in self._ignore_list:
            return False

        # ¿Está en la lista de pickup?
        if key in self._pickup_list:
            return self._pickup_list[key].pick_up

        # Gold coins
        if "gold coin" in key and self.pick_gold:
            return True
        if "platinum coin" in key and self.pick_platinum:
            return True
        if "crystal coin" in key and self.pick_crystal:
            return True

        # Item desconocido
        return self.pick_unknown_items

    def get_backpack_for_item(self, item_name: str) -> int:
        """
        Retorna el índice de backpack donde mover el item.

        Returns:
            Índice de backpack (0 = principal).
        """
        key = item_name.lower().strip()
        entry = self._pickup_list.get(key)
        if entry:
            return entry.backpack_index
        return 0  # Backpack principal por defecto

    def get_item_entry(self, item_name: str) -> Optional[ItemEntry]:
        """Busca un item en la lista de pickup."""
        return self._pickup_list.get(item_name.lower().strip())

    # ==================================================================
    # Info
    # ==================================================================
    @property
    def pickup_count(self) -> int:
        return len(self._pickup_list)

    @property
    def ignore_count(self) -> int:
        return len(self._ignore_list)

    def get_pickup_list(self) -> List[ItemEntry]:
        """Retorna la lista de items a recoger."""
        return sorted(self._pickup_list.values(), key=lambda i: i.name)

    def get_ignore_list(self) -> List[str]:
        """Retorna la lista de items ignorados."""
        return sorted(self._ignore_list)

    # ==================================================================
    # Serialización
    # ==================================================================
    def to_dict(self) -> Dict:
        return {
            "pick_gold": self.pick_gold,
            "pick_platinum": self.pick_platinum,
            "pick_crystal": self.pick_crystal,
            "min_gold_value": self.min_gold_value,
            "pick_unknown_items": self.pick_unknown_items,
            "pick_equipment": self.pick_equipment,
            "pick_stackables": self.pick_stackables,
            "pickup_list": [e.to_dict() for e in self._pickup_list.values()],
            "ignore_list": list(self._ignore_list),
        }

    def load_from_dict(self, data: Dict) -> None:
        """Carga configuración desde diccionario."""
        self.pick_gold = data.get("pick_gold", True)
        self.pick_platinum = data.get("pick_platinum", True)
        self.pick_crystal = data.get("pick_crystal", True)
        self.min_gold_value = data.get("min_gold_value", 0)
        self.pick_unknown_items = data.get("pick_unknown_items", False)
        self.pick_equipment = data.get("pick_equipment", True)
        self.pick_stackables = data.get("pick_stackables", True)

        # Cargar pickup list
        self._pickup_list.clear()
        for item_data in data.get("pickup_list", []):
            entry = ItemEntry.from_dict(item_data)
            self._pickup_list[entry.name] = entry

        # Cargar ignore list
        self._ignore_list = set(data.get("ignore_list", []))

    def clear_all(self) -> None:
        """Limpia todas las listas."""
        self._pickup_list.clear()
        self._ignore_list.clear()

    def __repr__(self) -> str:
        return f"<ItemFilter pickup={self.pickup_count} ignore={self.ignore_count}>"
