"""
targeting/targeting_engine.py - Motor principal de targeting/ataque.
Coordina la detección de monstruos, selección de objetivo,
ataque y rotación de hechizos.
"""

import time
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from targeting.battle_list_reader import BattleListReader, CreatureEntry, CreatureType
from targeting.target_detector import ScreenTarget, TargetDetector
from targeting.spell_rotator import SpellRotator


class AttackMode(Enum):
    """Modo de ataque."""
    OFFENSIVE = "offensive"   # Ataque completo
    BALANCED = "balanced"     # Ataque + defensa
    DEFENSIVE = "defensive"   # Solo si atacan


class TargetPriority(Enum):
    """Prioridad de selección de objetivo."""
    CLOSEST = "closest"       # El más cercano
    LOWEST_HP = "lowest_hp"   # El de menor HP
    HIGHEST_HP = "highest_hp" # El de mayor HP
    DANGEROUS = "dangerous"   # El más peligroso (por nombre)


class TargetingState(Enum):
    """Estado del motor de targeting."""
    IDLE = "idle"
    SEARCHING = "searching"
    ATTACKING = "attacking"
    CASTING = "casting"
    CHASING = "chasing"
    PAUSED = "paused"


class TargetingEngine:
    """
    Motor de targeting/ataque del bot.
    Coordina:
    - Lectura de la battle list
    - Detección de monstruos en pantalla
    - Selección de objetivo por prioridad
    - Ataque con click y hechizos
    - Rotación de hechizos AOE/single target
    """

    def __init__(self):
        self.battle_list_reader = BattleListReader()
        self.target_detector = TargetDetector()
        self.spell_rotator = SpellRotator()

        # Estado
        self.state: TargetingState = TargetingState.IDLE
        self.current_target: Optional[CreatureEntry] = None
        self.screen_target: Optional[ScreenTarget] = None

        # Configuración
        self.attack_mode: AttackMode = AttackMode.OFFENSIVE
        self.target_priority: TargetPriority = TargetPriority.CLOSEST
        self.auto_attack: bool = True
        self.chase_monsters: bool = True
        self.max_chase_distance: int = 5  # Tiles máximos para perseguir

        # Lista de monstruos peligrosos (mayor prioridad)
        self.dangerous_monsters: List[str] = []
        # Lista de monstruos a ignorar
        self.ignore_monsters: List[str] = []

        # Configuración AOE
        self.use_aoe: bool = True
        self.aoe_min_monsters: int = 3

        # Callbacks (inyectados)
        self._on_attack_click: Optional[Callable] = None   # callback(hwnd, x, y)
        self._on_send_key: Optional[Callable] = None        # callback(hwnd, key)

        # Handle de ventana
        self.hwnd: int = 0

        # Timing
        self.attack_delay: float = 0.5
        self.last_attack_time: float = 0.0
        self.last_search_time: float = 0.0
        self.search_interval: float = 0.2

        # Métricas
        self.monsters_killed: int = 0
        self.total_attacks: int = 0
        self.spells_cast: int = 0

    # ==================================================================
    # Configuración / Inyección
    # ==================================================================
    def set_attack_click_callback(self, callback: Callable) -> None:
        """callback(hwnd: int, x: int, y: int) - Click de ataque."""
        self._on_attack_click = callback

    def set_send_key_callback(self, callback: Callable) -> None:
        """callback(hwnd: int, key: str) - Envío de tecla."""
        self._on_send_key = callback
        self.spell_rotator.set_send_key_callback(callback)

    def set_hwnd(self, hwnd: int) -> None:
        self.hwnd = hwnd

    def set_battle_list_region(self, x: int, y: int, w: int, h: int) -> None:
        self.battle_list_reader.set_region(x, y, w, h)

    def set_game_region(self, x: int, y: int, w: int, h: int) -> None:
        self.target_detector.set_game_region(x, y, w, h)

    # ==================================================================
    # Lógica principal
    # ==================================================================
    def update(self, frame: np.ndarray, current_mana: int = 999999) -> None:
        """
        Actualización principal del targeting. Llamada cada frame.

        Args:
            frame: Frame BGR de OBS.
            current_mana: Mana actual del jugador (para hechizos).
        """
        if self.state == TargetingState.PAUSED:
            return

        now = time.time()

        # 1. Leer battle list periódicamente
        if now - self.last_search_time >= self.search_interval:
            creatures = self.battle_list_reader.read(frame)
            self.last_search_time = now

            # 2. Verificar si el objetivo actual murió
            if self.current_target:
                still_alive = any(
                    c.name == self.current_target.name
                    for c in creatures
                    if c.creature_type == CreatureType.MONSTER
                )
                if not still_alive:
                    self.monsters_killed += 1
                    self.current_target = None
                    self.screen_target = None
                    self.state = TargetingState.SEARCHING

        # 3. Si no tenemos objetivo, buscar uno
        if self.current_target is None and self.auto_attack:
            self._select_target()

        # 4. Si tenemos objetivo, atacar
        if self.current_target is not None:
            self._attack_cycle(frame, current_mana, now)
        else:
            self.state = TargetingState.IDLE if not self.battle_list_reader.has_monsters() else TargetingState.SEARCHING

    def _select_target(self) -> None:
        """Selecciona un nuevo objetivo basado en la prioridad configurada."""
        monsters = self.battle_list_reader.get_monsters()

        # Filtrar ignorados
        if self.ignore_monsters:
            monsters = [
                m for m in monsters
                if m.name.lower() not in [n.lower() for n in self.ignore_monsters]
            ]

        if not monsters:
            self.current_target = None
            return

        # Priorizar peligrosos
        dangerous = [
            m for m in monsters
            if m.name.lower() in [n.lower() for n in self.dangerous_monsters]
        ]
        if dangerous:
            monsters = dangerous

        # Seleccionar según prioridad
        if self.target_priority == TargetPriority.LOWEST_HP:
            target = min(monsters, key=lambda m: m.hp_percent)
        elif self.target_priority == TargetPriority.HIGHEST_HP:
            target = max(monsters, key=lambda m: m.hp_percent)
        elif self.target_priority == TargetPriority.CLOSEST:
            target = monsters[0]  # La battle list suele tener los cercanos primero
        else:
            target = monsters[0]

        self.current_target = target
        self.state = TargetingState.ATTACKING

    def _attack_cycle(self, frame: np.ndarray, current_mana: int, now: float) -> None:
        """Ciclo de ataque al objetivo actual."""
        # Verificar si ya estamos atacando (indicador en battle list)
        is_already_attacking = (
            self.current_target and self.current_target.is_attacking
        )

        # Si no estamos atacando, hacer click de ataque
        if not is_already_attacking and now - self.last_attack_time >= self.attack_delay:
            self._click_attack()
            self.last_attack_time = now

        # Castear hechizos (rotación)
        monster_count = self.battle_list_reader.creature_count
        target_dist = 1.0  # Default, se actualiza con screen detection

        # Detectar monstruos en pantalla para distancia real
        screen_targets = self.target_detector.detect(frame)
        if screen_targets:
            closest = screen_targets[0]
            target_dist = closest.distance

        # Intentar castear hechizo
        spell_cast = self.spell_rotator.cast_best(
            hwnd=self.hwnd,
            monster_count=monster_count,
            current_mana=current_mana,
            target_distance=target_dist,
        )
        if spell_cast:
            self.spells_cast += 1
            self.state = TargetingState.CASTING

    def _click_attack(self) -> None:
        """Hace click de ataque en el objetivo."""
        if not self._on_attack_click or self.hwnd == 0:
            return

        # Usar posición de la battle list (click en la entry)
        # O usar screen target si está disponible
        if self.screen_target:
            self._on_attack_click(
                self.hwnd,
                self.screen_target.screen_x,
                self.screen_target.screen_y,
            )
            self.total_attacks += 1

    # ==================================================================
    # Control
    # ==================================================================
    def start(self) -> None:
        """Inicia el targeting."""
        self.state = TargetingState.SEARCHING

    def pause(self) -> None:
        """Pausa el targeting."""
        self.state = TargetingState.PAUSED

    def resume(self) -> None:
        """Reanuda el targeting."""
        if self.state == TargetingState.PAUSED:
            self.state = TargetingState.SEARCHING

    def stop(self) -> None:
        """Detiene el targeting y limpia estado."""
        self.state = TargetingState.IDLE
        self.current_target = None
        self.screen_target = None

    def clear_target(self) -> None:
        """Limpia el objetivo actual."""
        self.current_target = None
        self.screen_target = None
        self.state = TargetingState.SEARCHING

    # ==================================================================
    # Configuración de listas
    # ==================================================================
    def add_dangerous_monster(self, name: str) -> None:
        if name not in self.dangerous_monsters:
            self.dangerous_monsters.append(name)

    def remove_dangerous_monster(self, name: str) -> None:
        if name in self.dangerous_monsters:
            self.dangerous_monsters.remove(name)

    def add_ignore_monster(self, name: str) -> None:
        if name not in self.ignore_monsters:
            self.ignore_monsters.append(name)

    def remove_ignore_monster(self, name: str) -> None:
        if name in self.ignore_monsters:
            self.ignore_monsters.remove(name)

    # ==================================================================
    # Info
    # ==================================================================
    def get_status(self) -> Dict:
        return {
            "state": self.state.value,
            "attack_mode": self.attack_mode.value,
            "target_priority": self.target_priority.value,
            "current_target": self.current_target.to_dict() if self.current_target else None,
            "battle_list_count": self.battle_list_reader.creature_count,
            "screen_targets": self.target_detector.target_count,
            "monsters_killed": self.monsters_killed,
            "total_attacks": self.total_attacks,
            "spells_cast": self.spells_cast,
            "auto_attack": self.auto_attack,
            "use_aoe": self.use_aoe,
        }

    def __repr__(self) -> str:
        target_name = self.current_target.name if self.current_target else "None"
        return (
            f"<TargetingEngine state={self.state.value} "
            f"target='{target_name}' "
            f"kills={self.monsters_killed}>"
        )
