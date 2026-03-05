"""
targeting/spell_rotator.py - Rotador de hechizos con cooldowns.
Gestiona la rotación de ataques (exori, exori gran, exori mas, etc.)
respetando los cooldowns individuales y de grupo.
"""

import time
from typing import Callable, Dict, List, Optional


class Spell:
    """Representa un hechizo de ataque."""

    def __init__(
        self,
        name: str,
        words: str = "",
        hotkey: str = "",
        cooldown: float = 2.0,
        group_cooldown: float = 1.0,
        mana_cost: int = 0,
        is_aoe: bool = False,
        min_monsters: int = 1,
        max_range: int = 1,
        priority: int = 50,
        enabled: bool = True,
    ):
        self.name = name
        self.words = words          # Comando del hechizo ("exori")
        self.hotkey = hotkey        # Tecla asignada (F1, F2, etc.)
        self.cooldown = cooldown    # Cooldown individual (segundos)
        self.group_cooldown = group_cooldown  # Cooldown de grupo
        self.mana_cost = mana_cost
        self.is_aoe = is_aoe        # ¿Es ataque en área?
        self.min_monsters = min_monsters  # Mínimo de monstruos para usar AOE
        self.max_range = max_range   # Rango máximo en tiles
        self.priority = priority     # Menor = mayor prioridad
        self.enabled = enabled

        # Estado de cooldown
        self.last_cast_time: float = 0.0

    @property
    def is_ready(self) -> bool:
        """¿El hechizo está listo para usar?"""
        if not self.enabled:
            return False
        return time.time() - self.last_cast_time >= self.cooldown

    @property
    def remaining_cooldown(self) -> float:
        """Tiempo restante de cooldown en segundos."""
        elapsed = time.time() - self.last_cast_time
        remaining = self.cooldown - elapsed
        return max(0.0, remaining)

    def cast(self) -> None:
        """Registra que el hechizo fue casteado."""
        self.last_cast_time = time.time()

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "words": self.words,
            "hotkey": self.hotkey,
            "cooldown": self.cooldown,
            "group_cooldown": self.group_cooldown,
            "mana_cost": self.mana_cost,
            "is_aoe": self.is_aoe,
            "min_monsters": self.min_monsters,
            "max_range": self.max_range,
            "priority": self.priority,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(data: Dict) -> "Spell":
        return Spell(
            name=data.get("name", "Unknown"),
            words=data.get("words", ""),
            hotkey=data.get("hotkey", ""),
            cooldown=data.get("cooldown", 2.0),
            group_cooldown=data.get("group_cooldown", 1.0),
            mana_cost=data.get("mana_cost", 0),
            is_aoe=data.get("is_aoe", False),
            min_monsters=data.get("min_monsters", 1),
            max_range=data.get("max_range", 1),
            priority=data.get("priority", 50),
            enabled=data.get("enabled", True),
        )

    def __repr__(self) -> str:
        ready = "✓" if self.is_ready else f"⏳{self.remaining_cooldown:.1f}s"
        return f"<Spell '{self.name}' [{self.hotkey}] {ready}>"


class SpellRotator:
    """
    Gestiona la rotación de hechizos de ataque.
    Selecciona el mejor hechizo disponible según la situación:
    - Número de monstruos (AOE vs single target)
    - Cooldowns
    - Mana disponible
    - Prioridad configurada
    """

    def __init__(self):
        self.spells: List[Spell] = []

        # Cooldown global (entre cualquier hechizo)
        self.global_cooldown: float = 1.0
        self.last_global_cast: float = 0.0

        # Callback para enviar tecla
        self._send_key: Optional[Callable] = None

        # Estado
        self.total_casts: int = 0
        self.enabled: bool = True

    # ==================================================================
    # Gestión de hechizos
    # ==================================================================
    def add_spell(self, spell: Spell) -> None:
        """Agrega un hechizo a la rotación."""
        self.spells.append(spell)
        # Ordenar por prioridad
        self.spells.sort(key=lambda s: s.priority)

    def remove_spell(self, name: str) -> bool:
        """Elimina un hechizo por nombre."""
        for i, s in enumerate(self.spells):
            if s.name == name:
                self.spells.pop(i)
                return True
        return False

    def clear_spells(self) -> None:
        """Elimina todos los hechizos."""
        self.spells.clear()

    def get_spell(self, name: str) -> Optional[Spell]:
        """Busca un hechizo por nombre."""
        for s in self.spells:
            if s.name == name:
                return s
        return None

    def set_send_key_callback(self, callback: Callable) -> None:
        """
        Callback para enviar tecla.
        callback(hwnd: int, key_name: str)
        """
        self._send_key = callback

    # ==================================================================
    # Selección de hechizo
    # ==================================================================
    def get_best_spell(
        self,
        monster_count: int = 1,
        current_mana: int = 999999,
        target_distance: float = 1.0,
    ) -> Optional[Spell]:
        """
        Selecciona el mejor hechizo disponible para la situación.

        Args:
            monster_count: Número de monstruos en rango.
            current_mana: Mana actual del jugador.
            target_distance: Distancia al objetivo principal en tiles.

        Returns:
            El mejor hechizo disponible, o None.
        """
        if not self.enabled:
            return None

        # Verificar cooldown global
        if time.time() - self.last_global_cast < self.global_cooldown:
            return None

        candidates = []

        for spell in self.spells:
            if not spell.is_ready:
                continue
            if not spell.enabled:
                continue
            if spell.mana_cost > current_mana:
                continue
            if target_distance > spell.max_range:
                continue

            # Para AOE, necesitamos suficientes monstruos
            if spell.is_aoe and monster_count < spell.min_monsters:
                continue

            # Calcular score
            score = self._calculate_spell_score(spell, monster_count, target_distance)
            candidates.append((spell, score))

        if not candidates:
            return None

        # Retornar el de mejor score
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _calculate_spell_score(
        self, spell: Spell, monster_count: int, distance: float
    ) -> float:
        """Calcula un score para un hechizo (mayor = mejor)."""
        score = 100.0 - spell.priority  # Menor prioridad = mayor score

        # Bonus por AOE cuando hay muchos monstruos
        if spell.is_aoe and monster_count >= spell.min_monsters:
            score += monster_count * 15

        # Bonus por menor cooldown (se puede castear más seguido)
        if spell.cooldown < 3.0:
            score += 5

        return score

    # ==================================================================
    # Ejecución
    # ==================================================================
    def cast_best(
        self,
        hwnd: int,
        monster_count: int = 1,
        current_mana: int = 999999,
        target_distance: float = 1.0,
    ) -> Optional[Spell]:
        """
        Castea el mejor hechizo disponible.

        Returns:
            El hechizo casteado, o None si no se pudo castear.
        """
        spell = self.get_best_spell(monster_count, current_mana, target_distance)
        if spell is None:
            return None

        if self._send_key and spell.hotkey:
            self._send_key(hwnd, spell.hotkey)
            spell.cast()
            self.last_global_cast = time.time()
            self.total_casts += 1
            return spell

        return None

    def reset_cooldowns(self) -> None:
        """Resetea todos los cooldowns."""
        for spell in self.spells:
            spell.last_cast_time = 0.0
        self.last_global_cast = 0.0

    # ==================================================================
    # Presets
    # ==================================================================
    def load_knight_rotation(self) -> None:
        """Carga rotación típica de Knight."""
        self.clear_spells()
        self.add_spell(Spell(
            name="Exori Gran", words="exori gran", hotkey="F1",
            cooldown=4.0, mana_cost=340, is_aoe=False, priority=10,
        ))
        self.add_spell(Spell(
            name="Exori", words="exori", hotkey="F2",
            cooldown=2.0, mana_cost=160, is_aoe=False, priority=20,
        ))
        self.add_spell(Spell(
            name="Exori Mas", words="exori mas", hotkey="F3",
            cooldown=4.0, mana_cost=200, is_aoe=True, min_monsters=3, priority=5,
        ))
        self.add_spell(Spell(
            name="Exori Min", words="exori min", hotkey="F4",
            cooldown=2.0, mana_cost=200, is_aoe=False, max_range=3, priority=30,
        ))

    def load_sorcerer_rotation(self) -> None:
        """Carga rotación típica de Sorcerer."""
        self.clear_spells()
        self.add_spell(Spell(
            name="Exori Vis", words="exori vis", hotkey="F1",
            cooldown=2.0, mana_cost=20, is_aoe=False, priority=20,
        ))
        self.add_spell(Spell(
            name="Exori Gran Vis", words="exori gran vis", hotkey="F2",
            cooldown=4.0, mana_cost=60, is_aoe=False, priority=10,
        ))
        self.add_spell(Spell(
            name="Exevo Vis Hur", words="exevo vis hur", hotkey="F3",
            cooldown=4.0, mana_cost=100, is_aoe=True, min_monsters=3, priority=5,
        ))

    def load_paladin_rotation(self) -> None:
        """Carga rotación típica de Paladin."""
        self.clear_spells()
        self.add_spell(Spell(
            name="Exori San", words="exori san", hotkey="F1",
            cooldown=2.0, mana_cost=20, is_aoe=False, max_range=4, priority=20,
        ))
        self.add_spell(Spell(
            name="Exori Gran Con", words="exori gran con", hotkey="F2",
            cooldown=2.0, mana_cost=20, is_aoe=False, max_range=5, priority=15,
        ))
        self.add_spell(Spell(
            name="Exevo Mas San", words="exevo mas san", hotkey="F3",
            cooldown=4.0, mana_cost=150, is_aoe=True, min_monsters=3, priority=5,
        ))

    def load_druid_rotation(self) -> None:
        """Carga rotación típica de Druid."""
        self.clear_spells()
        self.add_spell(Spell(
            name="Exori Tera", words="exori tera", hotkey="F1",
            cooldown=2.0, mana_cost=20, is_aoe=False, priority=20,
        ))
        self.add_spell(Spell(
            name="Exori Gran Tera", words="exori gran tera", hotkey="F2",
            cooldown=4.0, mana_cost=60, is_aoe=False, priority=10,
        ))
        self.add_spell(Spell(
            name="Exevo Tera Hur", words="exevo tera hur", hotkey="F3",
            cooldown=4.0, mana_cost=100, is_aoe=True, min_monsters=3, priority=5,
        ))

    # ==================================================================
    # Serialización
    # ==================================================================
    def to_dict(self) -> Dict:
        return {
            "global_cooldown": self.global_cooldown,
            "enabled": self.enabled,
            "spells": [s.to_dict() for s in self.spells],
        }

    def load_from_dict(self, data: Dict) -> None:
        """Carga configuración desde diccionario."""
        self.global_cooldown = data.get("global_cooldown", 1.0)
        self.enabled = data.get("enabled", True)
        self.spells = [Spell.from_dict(s) for s in data.get("spells", [])]
        self.spells.sort(key=lambda s: s.priority)

    # ==================================================================
    # Info
    # ==================================================================
    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "total_casts": self.total_casts,
            "spell_count": len(self.spells),
            "spells": [
                {
                    "name": s.name,
                    "hotkey": s.hotkey,
                    "ready": s.is_ready,
                    "cooldown_remaining": round(s.remaining_cooldown, 1),
                    "enabled": s.enabled,
                }
                for s in self.spells
            ],
        }

    def __repr__(self) -> str:
        ready = sum(1 for s in self.spells if s.is_ready)
        return f"<SpellRotator {ready}/{len(self.spells)} ready, casts={self.total_casts}>"
