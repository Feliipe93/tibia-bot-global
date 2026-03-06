"""
config.py - Gestión de configuración del bot con persistencia JSON.
Carga/guarda automáticamente desde config.json.
"""

import json
import os
import copy
from typing import Any, Dict, List, Optional

CONFIG_FILE = "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "tibia_window_title": "",
    "obs_projector_title": "",
    "obs_websocket": {
        "host": "localhost",
        "port": 4455,
        "password": "",
        "source_name": "",
    },
    "heal_levels": [
        {"threshold": 0.70, "key": "F1", "description": "Exura"},
        {"threshold": 0.50, "key": "F2", "description": "Exura Gran"},
        {"threshold": 0.30, "key": "F6", "description": "Exura Vita"},
    ],
    "mana_heal": {
        "enabled": False,
        "threshold": 0.30,
        "key": "F3",
        "description": "Mana potion",
    },
    "cooldown_seconds": 1.2,
    "check_interval_seconds": 0.25,
    "hotkey_toggle": "F9",
    "hotkey_exit": "F10",
    "debug_save_images": True,
    "debug_every_n_cycles": 40,
    "log_level": "INFO",
    "bar_detection": {
        "expected_full_width_ratio": 0.43,
        "scan_height_ratio": 0.10,
    },
    # ===== v2.0 Cavebot =====
    "cavebot": {
        "enabled": False,
        "cyclic": True,
        "walk_mode": "click",           # "click" o "arrow"
        "step_delay": 0.25,
        "stuck_threshold": 5,
        "current_route": "",            # Ruta .json cargada
        "minimap_region": {"x": 0, "y": 0, "w": 106, "h": 109},
        "game_region": {"x": 0, "y": 0, "w": 480, "h": 352},
    },
    # ===== v2.1 Targeting =====
    "targeting": {
        "enabled": False,
        "auto_attack": True,
        "chase_monsters": True,
        "attack_mode": "offensive",     # offensive, balanced, defensive
        "target_priority": "closest",   # closest, lowest_hp, highest_hp, dangerous
        "attack_delay": 0.3,
        "re_attack_delay": 0.6,
        "max_chase_distance": 5,
        "use_aoe": True,
        "aoe_min_monsters": 3,
        "dangerous_monsters": [],
        "ignore_monsters": [],
        "attack_list": [],              # Lista de monstruos a atacar
        "ignore_list": [],              # Lista de monstruos a ignorar
        "priority_list": [],            # Lista de monstruos prioritarios
        "creature_profiles": {},        # Per-creature config: {name: {chase_mode, attack_mode, ...}}
        "chase_key": "",               # Hotkey to toggle chase mode in Tibia
        "stand_key": "",               # Hotkey to toggle stand mode in Tibia
        "battle_list_region": {"x": 0, "y": 0, "w": 160, "h": 220},
        "spell_rotation": {
            "enabled": True,
            "global_cooldown": 1.0,
            "spells": [],
        },
    },
    # ===== v2.2 Looter =====
    "looter": {
        "enabled": False,
        "loot_method": "left_click",   # left_click, right_click, shift_right_click
        "free_account": False,          # Free account mode: loot to main BP only
        "loot_delay": 0.15,
        "loot_cooldown": 0.5,
        "max_range": 2,
        "max_corpse_age": 10.0,
        "max_loot_attempts": 1,
        "max_loot_sqms": 9,
        "periodic_loot": False,
        "periodic_interval": 8.0,
        "loot_during_combat": True,
        "auto_open_next_bp": True,
        "inventory_region": {"x": 0, "y": 0, "w": 160, "h": 400},
        "item_filter": {
            "pick_gold": True,
            "pick_platinum": True,
            "pick_crystal": True,
            "pick_unknown_items": False,
            "pick_equipment": True,
            "pick_stackables": True,
            "pick_valuables": True,
            "pick_creature_products": False,
            "min_item_value": 0,
            "pickup_list": [],
            "ignore_list": [],
        },
        "backpack_routing": {
            "default_backpack": 0,
            "category_routes": {
                "gold": 0,
                "valuable": 1,
                "equipment": 1,
                "potion": 2,
                "rune": 2,
                "food": 3,
                "creature_product": 3,
            },
            "item_routes": {},
        },
    },
    # ===== NPC Interacción =====
    "npc": {
        "step_delay": 0.8,
        "say_delay": 1.0,
        "trade_delay": 0.5,
        "walk_to_npc_timeout": 10.0,
        "dialogue_timeout": 30.0,
    },
    # ===== Hotkeys globales =====
    "hotkeys": {
        "rope": "",
        "shovel": "",
        "food": "",
        "mana_potion": "",
        "health_potion": "",
        "pick": "",
        "machete": "",
        "light": "",
    },
}


class Config:
    """Gestiona la configuración del bot con persistencia en JSON."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or CONFIG_FILE
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def load(self) -> bool:
        """Carga config.json. Retorna True si se cargó correctamente."""
        if not os.path.exists(self.path):
            self.save()  # crea archivo con valores por defecto
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Merge: mantener defaults para claves faltantes
            self._deep_merge(self.data, loaded)
            return True
        except (json.JSONDecodeError, IOError) as exc:
            print(f"[Config] Error al cargar {self.path}: {exc}")
            return False

    def save(self) -> bool:
        """Guarda la configuración actual en config.json."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            return True
        except IOError as exc:
            print(f"[Config] Error al guardar {self.path}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Acceso a datos
    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    # -- Heal levels ---------------------------------------------------
    @property
    def heal_levels(self) -> List[Dict]:
        return self.data.get("heal_levels", [])

    @heal_levels.setter
    def heal_levels(self, levels: List[Dict]) -> None:
        self.data["heal_levels"] = levels

    def add_heal_level(self, threshold: float, key: str, description: str = "") -> None:
        self.data["heal_levels"].append({
            "threshold": threshold,
            "key": key,
            "description": description,
        })
        # Ordenar de mayor a menor threshold
        self.data["heal_levels"].sort(key=lambda x: x["threshold"], reverse=True)

    def remove_heal_level(self, index: int) -> None:
        if 0 <= index < len(self.data["heal_levels"]):
            self.data["heal_levels"].pop(index)

    # -- Mana heal -----------------------------------------------------
    @property
    def mana_heal(self) -> Dict:
        return self.data.get("mana_heal", DEFAULT_CONFIG["mana_heal"])

    @mana_heal.setter
    def mana_heal(self, value: Dict) -> None:
        self.data["mana_heal"] = value

    # -- Propiedades de acceso rápido ----------------------------------
    @property
    def cooldown(self) -> float:
        return self.data.get("cooldown_seconds", 1.2)

    @cooldown.setter
    def cooldown(self, val: float) -> None:
        self.data["cooldown_seconds"] = max(0.1, val)

    @property
    def check_interval(self) -> float:
        return self.data.get("check_interval_seconds", 0.25)

    @check_interval.setter
    def check_interval(self, val: float) -> None:
        self.data["check_interval_seconds"] = max(0.05, val)

    @property
    def hotkey_toggle(self) -> str:
        return self.data.get("hotkey_toggle", "F9")

    @hotkey_toggle.setter
    def hotkey_toggle(self, val: str) -> None:
        self.data["hotkey_toggle"] = val

    @property
    def hotkey_exit(self) -> str:
        return self.data.get("hotkey_exit", "F10")

    @hotkey_exit.setter
    def hotkey_exit(self, val: str) -> None:
        self.data["hotkey_exit"] = val

    @property
    def log_level(self) -> str:
        return self.data.get("log_level", "INFO")

    @log_level.setter
    def log_level(self, val: str) -> None:
        self.data["log_level"] = val.upper()

    @property
    def bar_detection(self) -> Dict:
        return self.data.get("bar_detection", DEFAULT_CONFIG["bar_detection"])

    # -- OBS WebSocket -------------------------------------------------
    @property
    def obs_websocket(self) -> Dict:
        return self.data.get("obs_websocket", DEFAULT_CONFIG["obs_websocket"])

    @obs_websocket.setter
    def obs_websocket(self, value: Dict) -> None:
        self.data["obs_websocket"] = value

    @property
    def obs_host(self) -> str:
        return self.obs_websocket.get("host", "localhost")

    @property
    def obs_port(self) -> int:
        return self.obs_websocket.get("port", 4455)

    @property
    def obs_password(self) -> str:
        return self.obs_websocket.get("password", "")

    @property
    def obs_source_name(self) -> str:
        return self.obs_websocket.get("source_name", "")

    @obs_source_name.setter
    def obs_source_name(self, val: str) -> None:
        ws = self.obs_websocket
        ws["source_name"] = val
        self.data["obs_websocket"] = ws

    # -- Cavebot (v2.0) -----------------------------------------------
    @property
    def cavebot(self) -> Dict:
        return self.data.get("cavebot", DEFAULT_CONFIG["cavebot"])

    @cavebot.setter
    def cavebot(self, value: Dict) -> None:
        self.data["cavebot"] = value

    @property
    def cavebot_enabled(self) -> bool:
        return self.cavebot.get("enabled", False)

    @cavebot_enabled.setter
    def cavebot_enabled(self, val: bool) -> None:
        self.data.setdefault("cavebot", {})["enabled"] = val

    # -- Targeting (v2.1) ----------------------------------------------
    @property
    def targeting(self) -> Dict:
        return self.data.get("targeting", DEFAULT_CONFIG["targeting"])

    @targeting.setter
    def targeting(self, value: Dict) -> None:
        self.data["targeting"] = value

    @property
    def targeting_enabled(self) -> bool:
        return self.targeting.get("enabled", False)

    @targeting_enabled.setter
    def targeting_enabled(self, val: bool) -> None:
        self.data.setdefault("targeting", {})["enabled"] = val

    # -- Looter (v2.2) -------------------------------------------------
    @property
    def looter(self) -> Dict:
        return self.data.get("looter", DEFAULT_CONFIG["looter"])

    @looter.setter
    def looter(self, value: Dict) -> None:
        self.data["looter"] = value

    @property
    def looter_enabled(self) -> bool:
        return self.looter.get("enabled", False)

    @looter_enabled.setter
    def looter_enabled(self, val: bool) -> None:
        self.data.setdefault("looter", {})["enabled"] = val

    # -- Hotkeys -------------------------------------------------------
    @property
    def hotkeys(self) -> Dict:
        return self.data.get("hotkeys", DEFAULT_CONFIG.get("hotkeys", {}))

    @hotkeys.setter
    def hotkeys(self, value: Dict) -> None:
        self.data["hotkeys"] = value

    # -- NPC config ----------------------------------------------------
    @property
    def npc(self) -> Dict:
        return self.data.get("npc", DEFAULT_CONFIG.get("npc", {}))

    @npc.setter
    def npc(self, value: Dict) -> None:
        self.data["npc"] = value

    # -- Backpack routing (looter) ------------------------------------
    @property
    def backpack_routing(self) -> Dict:
        return self.looter.get("backpack_routing", DEFAULT_CONFIG["looter"]["backpack_routing"])

    @backpack_routing.setter
    def backpack_routing(self, value: Dict) -> None:
        self.data.setdefault("looter", {})["backpack_routing"] = value

    # -- Targeting lists -----------------------------------------------
    @property
    def attack_list(self) -> List[str]:
        return self.targeting.get("attack_list", [])

    @attack_list.setter
    def attack_list(self, value: List[str]) -> None:
        self.data.setdefault("targeting", {})["attack_list"] = value

    @property
    def ignore_list(self) -> List[str]:
        return self.targeting.get("ignore_list", [])

    @ignore_list.setter
    def ignore_list(self, value: List[str]) -> None:
        self.data.setdefault("targeting", {})["ignore_list"] = value

    @property
    def priority_list(self) -> List[str]:
        return self.targeting.get("priority_list", [])

    @priority_list.setter
    def priority_list(self, value: List[str]) -> None:
        self.data.setdefault("targeting", {})["priority_list"] = value

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        """Fusiona *override* dentro de *base* recursivamente."""
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                Config._deep_merge(base[k], v)
            else:
                base[k] = v

    def reset_to_defaults(self) -> None:
        """Restablece toda la configuración a los valores por defecto."""
        self.data = copy.deepcopy(DEFAULT_CONFIG)
        self.save()

    def __repr__(self) -> str:
        return f"<Config path='{self.path}' keys={list(self.data.keys())}>"
