"""
targeting/targeting_engine.py - Motor de targeting/ataque FUNCIONAL.
Coordina detección de monstruos en battle list y ataque via click.
Basado en TibiaAuto12/engine/CaveBot/CaveBotController.py.
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from targeting.battle_list_reader import BattleListReader, CreatureEntry


class TargetingEngine:
    """
    Motor de targeting real.
    Usa BattleListReader (template matching) para encontrar monstruos
    y MouseClickSender para hacer click de ataque en la battle list.
    """

    def __init__(self):
        self.battle_reader = BattleListReader()

        # Estado
        self.enabled: bool = False
        self.current_target: Optional[str] = None  # Nombre del monstruo atacando
        self.state: str = "idle"  # idle, attacking, searching, lost_target

        # Configuración
        self.attack_mode: str = "offensive"
        self.auto_attack: bool = True
        self.chase_monsters: bool = True

        # Listas de monstruos
        self.monsters_to_attack: List[str] = []

        # Callbacks inyectados
        self._click_fn: Optional[Callable] = None   # click(x, y) en coordenadas del frame
        self._log_fn: Optional[Callable] = None      # log(msg)
        self._key_fn: Optional[Callable] = None      # send_key(key_name)

        # Timing
        self.attack_delay: float = 0.4
        self.last_attack_time: float = 0.0
        self.search_interval: float = 0.2
        self.last_search_time: float = 0.0

        # Métricas
        self.monsters_killed: int = 0
        self.total_attacks: int = 0
        self._prev_count: int = 0

        # Última posición de ataque (para el looter)
        self.last_attack_position: Tuple[int, int] = (0, 0)
        self.last_attack_name: str = ""

        # --- Lost target detection ---
        # Si el target actual desaparece de la battle list por N frames
        # consecutivos, lo soltamos y buscamos otro.
        self._target_missing_frames: int = 0
        self.max_target_missing: int = 8  # ~1.6s a 0.2s/scan → soltar
        self._target_switch_cooldown: float = 0.5
        self._last_target_switch: float = 0.0

    # ==================================================================
    # Configuración
    # ==================================================================
    def set_click_callback(self, fn: Callable):
        """fn(x, y) - hace click izquierdo en coordenadas de cliente."""
        self._click_fn = fn

    def set_key_callback(self, fn: Callable):
        """fn(key_name) - envía tecla a Tibia."""
        self._key_fn = fn

    def set_log_callback(self, fn: Callable):
        """fn(msg) - log del módulo."""
        self._log_fn = fn

    def set_battle_region(self, x1, y1, x2, y2):
        """Configura la región de la battle list."""
        self.battle_reader.set_region(x1, y1, x2, y2)

    def configure(self, config: dict):
        """Aplica configuración desde el dict de config."""
        targeting = config if isinstance(config, dict) else {}
        self.attack_mode = targeting.get("attack_mode", "offensive")
        self.auto_attack = targeting.get("auto_attack", True)
        self.chase_monsters = targeting.get("chase_monsters", True)
        self.attack_delay = targeting.get("attack_delay", 0.4)

        # Listas
        atk = targeting.get("attack_list", [])
        ign = targeting.get("ignore_list", [])
        pri = targeting.get("priority_list", [])

        self.monsters_to_attack = atk
        self.battle_reader.attack_list = set(atk)
        self.battle_reader.ignore_list = set(ign)
        self.battle_reader.priority_list = set(pri)

        # Cargar templates
        if atk:
            loaded = self.battle_reader.load_monster_templates(atk)
            self._log(f"Templates cargados: {loaded}/{len(atk)}")
        else:
            loaded = self.battle_reader.load_all_available_templates()
            self._log(f"Templates disponibles cargados: {loaded}")

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Targeting] {msg}")

    # ==================================================================
    # Loop principal (llamado por dispatcher cada frame)
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """
        Procesamiento principal. Llamado por dispatcher en cada frame.
        1. Lee battle list
        2. Si hay monstruos y no estamos atacando → click de ataque
        3. Detecta kills por disminución de conteo
        4. Si target desaparece por muchos frames → soltar y buscar otro
        """
        if not self.enabled or frame is None:
            return
        if not self.auto_attack:
            return

        now = time.time()

        # Leer battle list periódicamente
        if now - self.last_search_time < self.search_interval:
            return
        self.last_search_time = now

        # Log periódico de estado (cada ~5 segundos)
        if not hasattr(self, '_last_status_log'):
            self._last_status_log = 0
        if now - self._last_status_log >= 5.0:
            self._last_status_log = now
            tpl_count = len(self.battle_reader._name_templates)
            region = self.battle_reader.battle_region
            self._log(
                f"Estado: target={self.current_target}, "
                f"criaturas={self._prev_count}, "
                f"templates={tpl_count}, kills={self.monsters_killed}"
            )

        # Escanear monstruos en la battle list
        creatures = self.battle_reader.read(frame)
        current_count = len(creatures)

        # Detectar kills (conteo bajó)
        if self._prev_count > current_count and current_count >= 0:
            kills = self._prev_count - current_count
            self.monsters_killed += kills
            self._log(f"¡Kill! ({kills}) Total kills: {self.monsters_killed}")
        self._prev_count = current_count

        # --- Si no hay criaturas, resetear ---
        if not creatures:
            if self.current_target:
                self._log(f"Battle list vacía — target '{self.current_target}' perdido")
            self.current_target = None
            self.state = "idle"
            self._target_missing_frames = 0
            return

        # --- Verificar si el target actual sigue en battle list ---
        if self.current_target:
            target_still_there = any(
                c.name.lower() == self.current_target.lower()
                for c in creatures
            )
            if not target_still_there:
                self._target_missing_frames += 1
                if self._target_missing_frames >= self.max_target_missing:
                    self._log(
                        f"Target '{self.current_target}' desapareció de battle list "
                        f"({self._target_missing_frames} frames) — buscando otro"
                    )
                    self.current_target = None
                    self._target_missing_frames = 0
                    self.state = "searching"
            else:
                self._target_missing_frames = 0

        # --- ¿Necesitamos atacar? ---
        needs_attack = self.battle_reader.is_attacking(frame)

        if needs_attack and (now - self.last_attack_time >= self.attack_delay):
            # No estamos atacando → seleccionar y atacar
            if now - self._last_target_switch < self._target_switch_cooldown:
                return  # Cooldown entre cambios de target
            target = self._select_target(creatures)
            if target:
                self._attack_target(frame, target)
                self.state = "attacking"
        elif not needs_attack:
            # Ya estamos atacando algo
            self.state = "attacking"

    def _select_target(self, creatures: List[CreatureEntry]) -> Optional[CreatureEntry]:
        """Selecciona el mejor objetivo según prioridad."""
        # Primero: prioridad alta
        priority = self.battle_reader.get_priority_targets()
        if priority:
            return priority[0]

        # Segundo: atacables
        attackable = self.battle_reader.get_attackable_monsters()
        if not attackable:
            return creatures[0] if creatures else None

        return attackable[0]  # El primero en la battle list (más cercano)

    def _attack_target(self, frame: np.ndarray, target: CreatureEntry):
        """Hace click en el monstruo en la battle list para atacarlo."""
        if not self._click_fn:
            return

        # Usar la posición del nombre en la battle list
        x, y = target.screen_x, target.screen_y
        if x == 0 and y == 0:
            # Buscar con find_target como fallback
            x, y = self.battle_reader.find_target(frame, target.name)

        if x != 0 and y != 0:
            old_target = self.current_target
            self._click_fn(x, y)
            self.current_target = target.name
            self.last_attack_position = (x, y)
            self.last_attack_name = target.name
            self.total_attacks += 1
            self.last_attack_time = time.time()
            self._last_target_switch = time.time()
            self._target_missing_frames = 0

            if old_target != target.name:
                self._log(f"Nuevo target: {target.name} en ({x},{y})")
            else:
                self._log(f"Re-atacando: {target.name} en ({x},{y})")

    # ==================================================================
    # API pública para otros módulos (looter)
    # ==================================================================
    def get_creature_count(self) -> int:
        """Cuántas criaturas hay actualmente en la battle list."""
        return self._prev_count

    def is_in_combat(self) -> bool:
        """True si estamos activamente atacando algo."""
        return self.current_target is not None and self.state == "attacking"

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._target_missing_frames = 0
        self.state = "idle"
        tpl_count = len(self.battle_reader._name_templates)
        region = self.battle_reader.battle_region
        self._log("Targeting activado")
        self._log(f"Templates cargados: {tpl_count} ({list(self.battle_reader._name_templates.keys())})")
        self._log(f"Battle region: {region}")
        self._log(f"Attack list: {self.monsters_to_attack}")
        if not self.battle_reader._name_templates:
            self._log("⚠ Sin templates — configura monstruos en la pestaña Targeting y guarda")
        if region is None:
            self._log("⚠ Sin battle region — presiona 'Calibrar' primero")

    def stop(self):
        self.enabled = False
        self.current_target = None
        self.state = "idle"
        self._target_missing_frames = 0
        self._log("Targeting desactivado")

    def get_kill_count(self) -> int:
        return self.monsters_killed

    def get_monster_count(self) -> int:
        return self._prev_count

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "current_target": self.current_target,
            "monster_count": self._prev_count,
            "monsters_killed": self.monsters_killed,
            "total_attacks": self.total_attacks,
            "templates_loaded": len(self.battle_reader._name_templates),
            "target_missing_frames": self._target_missing_frames,
        }
