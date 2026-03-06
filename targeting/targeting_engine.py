"""
targeting/targeting_engine.py - Motor de targeting/ataque v3.
Mejoras sobre v2:
  - Kill detection POR NOMBRE de monstruo (no solo conteo total)
  - Doble-scan estilo TibiaAuto12 (scan→ataque→scan→compara→loot)
  - Re-ataque agresivo (0.6s en vez de 2.0s)
  - Detección de is_attacking corregida (ya no invertida en la lógica)
  - Integración directa con looter vía notify_kill
  - Follow mode detection
  - Per-creature profiles: chase/stand mode, attack mode per creature
  - Auto chase/stand switching when changing targets
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from targeting.battle_list_reader import BattleListReader, CreatureEntry


# Default creature profile
DEFAULT_CREATURE_PROFILE = {
    "chase_mode": "auto",       # "chase", "stand", "auto" (auto = use global setting)
    "attack_mode": "auto",      # "offensive", "balanced", "defensive", "auto"
    "flees_at_hp": 0.0,         # 0.0 = doesn't flee, 0.3 = flees at 30% HP
    "is_ranged": False,         # True = ranged creature (keep stand), False = melee
    "priority": 0,              # Higher = attacked first (0 = use global priority)
    "use_chase_on_flee": True,  # Auto-switch to chase when creature flees
}


class TargetingEngine:
    """
    Motor de targeting v3.
    Basado en TibiaAuto12 CaveBotController + TibiaPilotNG attackClosestCreature.
    Usa BattleListReader para encontrar monstruos y click para atacarlos.
    Soporta perfiles por criatura: chase/stand, modo ataque, detección de huida.
    """

    def __init__(self):
        self.battle_reader = BattleListReader()

        # Estado
        self.enabled: bool = False
        self.current_target: Optional[str] = None
        self.state: str = "idle"  # idle, attacking, searching

        # Configuración global
        self.attack_mode: str = "offensive"
        self.auto_attack: bool = True
        self.chase_monsters: bool = True

        # Per-creature profiles
        self.creature_profiles: Dict[str, Dict] = {}

        # Hotkeys para cambiar chase/stand mode en Tibia
        self.chase_key: str = ""    # Hotkey para activar chase mode
        self.stand_key: str = ""    # Hotkey para activar stand mode

        # Estado actual de chase/stand (para evitar enviar keys innecesariamente)
        self._current_chase_mode: str = "unknown"  # "chase", "stand", "unknown"

        # Listas de monstruos
        self.monsters_to_attack: List[str] = []

        # Callbacks inyectados
        self._click_fn: Optional[Callable] = None
        self._log_fn: Optional[Callable] = None
        self._key_fn: Optional[Callable] = None

        # Referencia al calibrator (para chase/stand mode via UI clicks)
        self._calibrator = None

        # Referencia al looter (para notify_kill directo)
        self._looter_engine = None

        # Timing — más agresivo que v1
        self.attack_delay: float = 0.3        # Delay ataques a NUEVOS targets
        self.re_attack_delay: float = 0.6     # Re-ataque (era 2.0s → ahora 0.6s)
        self.search_interval: float = 0.2     # Scan cada 200ms
        self.last_attack_time: float = 0.0
        self.last_search_time: float = 0.0

        # Métricas
        self.monsters_killed: int = 0
        self.total_attacks: int = 0

        # Última posición de ataque (para el looter)
        self.last_attack_position: Tuple[int, int] = (0, 0)
        self.last_attack_name: str = ""

        # --- Kill detection por nombre (v2) ---
        self._prev_counts_by_name: Dict[str, int] = {}
        self._prev_total_count: int = 0

        # --- Lost target detection ---
        self._target_missing_frames: int = 0
        self.max_target_missing: int = 6       # ~1.2s → soltar (era 8)
        self._target_switch_cooldown: float = 0.3
        self._last_target_switch: float = 0.0

        # --- Status logging ---
        self._last_status_log: float = 0.0

    # ==================================================================
    # Configuración
    # ==================================================================
    def set_click_callback(self, fn: Callable):
        """fn(x, y) - click izquierdo en coordenadas de cliente."""
        self._click_fn = fn

    def set_key_callback(self, fn: Callable):
        """fn(key_name) - envía tecla a Tibia."""
        self._key_fn = fn

    def set_log_callback(self, fn: Callable):
        """fn(msg) - log del módulo."""
        self._log_fn = fn

    def set_looter_engine(self, engine):
        """Referencia al LooterEngine para notificar kills directamente."""
        self._looter_engine = engine

    def set_calibrator(self, calibrator):
        """Referencia al ScreenCalibrator para detectar chase/stand mode."""
        self._calibrator = calibrator

    def set_battle_region(self, x1, y1, x2, y2):
        """Configura la región de la battle list."""
        self.battle_reader.set_region(x1, y1, x2, y2)

    def configure(self, config: dict):
        """Aplica configuración desde el dict de config."""
        targeting = config if isinstance(config, dict) else {}
        self.attack_mode = targeting.get("attack_mode", "offensive")
        self.auto_attack = targeting.get("auto_attack", True)
        self.chase_monsters = targeting.get("chase_monsters", True)
        self.attack_delay = targeting.get("attack_delay", 0.3)
        self.re_attack_delay = targeting.get("re_attack_delay", 0.6)

        # Chase/stand hotkeys
        self.chase_key = targeting.get("chase_key", "")
        self.stand_key = targeting.get("stand_key", "")

        atk = targeting.get("attack_list", [])
        ign = targeting.get("ignore_list", [])
        pri = targeting.get("priority_list", [])

        self.monsters_to_attack = atk
        self.battle_reader.attack_list = set(atk)
        self.battle_reader.ignore_list = set(ign)
        self.battle_reader.priority_list = set(pri)

        # Per-creature profiles
        raw_profiles = targeting.get("creature_profiles", {})
        self.creature_profiles = {}
        for name, profile in raw_profiles.items():
            merged = dict(DEFAULT_CREATURE_PROFILE)
            merged.update(profile)
            self.creature_profiles[name.lower()] = merged

        if self.creature_profiles:
            self._log(f"Perfiles de criaturas: {list(self.creature_profiles.keys())}")
        if self.chase_key or self.stand_key:
            self._log(f"Chase key: '{self.chase_key}', Stand key: '{self.stand_key}'")

        if atk:
            loaded = self.battle_reader.load_monster_templates(atk)
            self._log(f"Templates cargados: {loaded}/{len(atk)}")
        else:
            loaded = self.battle_reader.load_all_available_templates()
            self._log(f"Templates disponibles cargados: {loaded}")

    def _log(self, msg: str):
        if self._log_fn:
            self._log_fn(f"[Targeting] {msg}")
        # Also wire to battle_reader for diagnostics
        if not self.battle_reader._log_fn and self._log_fn:
            self.battle_reader.set_log_callback(self._log_fn)

    # ==================================================================
    # Per-creature profile helpers
    # ==================================================================
    def get_creature_profile(self, creature_name: str) -> Dict:
        """Obtiene el perfil de una criatura (o default si no tiene)."""
        return self.creature_profiles.get(
            creature_name.lower(),
            dict(DEFAULT_CREATURE_PROFILE)
        )

    def _apply_chase_mode_for_creature(self, creature_name: str, frame: Optional[np.ndarray] = None):
        """
        Aplica el chase/stand mode apropiado según el perfil de la criatura.
        v3.2: Usa CLICKS en los iconos de la UI de Tibia (no hotkeys).
        
        Lógica (basada en TibiaAuto12 NeedFollow/NeedIdle):
        1. Detecta modo actual (chase/stand) via template matching del frame
        2. Si el modo deseado != modo actual → busca el botón para cambiar y clickea
        3. Solo cambia si realmente es necesario (evita clicks innecesarios)
        """
        if not self._click_fn or frame is None or self._calibrator is None:
            return

        profile = self.get_creature_profile(creature_name)
        chase_mode = profile.get("chase_mode", "auto")

        # "auto" = usar configuración global
        if chase_mode == "auto":
            desired = "chase" if self.chase_monsters else "stand"
        else:
            desired = chase_mode

        # Detectar modo actual desde el frame
        current = self._calibrator.detect_combat_mode(frame)

        # Si ya estamos en el modo deseado, no hacer nada
        if current == desired:
            if self._current_chase_mode != desired:
                self._current_chase_mode = desired
            return

        # Si no pudimos detectar el modo actual, no hacer nada (evitar clicks ciegos)
        if current == "unknown":
            return

        # Necesitamos cambiar el modo
        if desired == "chase":
            # Buscar botón NotFollow (para activar chase)
            pos = self._calibrator.get_switch_to_chase_pos(frame)
            if pos:
                self._click_fn(pos[0], pos[1])
                self._current_chase_mode = "chase"
                self._log(f"Chase mode activado para {creature_name} (click en {pos})")
        elif desired == "stand":
            # Buscar botón NotIdle (para activar stand)
            pos = self._calibrator.get_switch_to_stand_pos(frame)
            if pos:
                self._click_fn(pos[0], pos[1])
                self._current_chase_mode = "stand"
                self._log(f"Stand mode activado para {creature_name} (click en {pos})")

        # Fallback a hotkeys si los templates no funcionan
        if self._current_chase_mode != desired and self._key_fn:
            if desired == "chase" and self.chase_key:
                self._key_fn(self.chase_key)
                self._current_chase_mode = "chase"
                self._log(f"Chase mode via hotkey '{self.chase_key}' para {creature_name}")
            elif desired == "stand" and self.stand_key:
                self._key_fn(self.stand_key)
                self._current_chase_mode = "stand"
                self._log(f"Stand mode via hotkey '{self.stand_key}' para {creature_name}")

    # ==================================================================
    # Loop principal — Estilo TibiaAuto12 doble-scan
    # ==================================================================
    def process_frame(self, frame: np.ndarray):
        """
        Procesamiento v3 estilo TibiaAuto12:
        1. Scan battle list → obtener criaturas + conteo por nombre
        2. Comparar conteo por nombre con frame anterior → detectar kills
        3. Si no estamos atacando → seleccionar target y click
        4. Si target desaparece → soltar y buscar otro (rápido)
        5. Auto-switch chase/stand según perfil de criatura
        """
        if not self.enabled or frame is None:
            return
        if not self.auto_attack:
            return

        now = time.time()

        # Respetar intervalo de búsqueda
        if now - self.last_search_time < self.search_interval:
            return
        self.last_search_time = now

        # Log periódico de estado (~cada 5s)
        if now - self._last_status_log >= 5.0:
            self._last_status_log = now
            tpl_count = len(self.battle_reader._name_templates)
            self._log(
                f"Estado: target={self.current_target}, "
                f"criaturas={self._prev_total_count}, "
                f"templates={tpl_count}, kills={self.monsters_killed}"
            )

        # ========== SCAN: Leer battle list ==========
        creatures = self.battle_reader.read(frame)
        current_counts = self._count_by_name(creatures)
        current_total = len(creatures)

        # ========== KILL DETECTION por nombre (v2) ==========
        self._detect_kills_by_name(current_counts)

        # Actualizar conteo previo
        self._prev_counts_by_name = current_counts.copy()
        self._prev_total_count = current_total

        # ========== Sin criaturas → idle ==========
        if not creatures:
            if self.current_target:
                self._log(f"Battle list vacía — '{self.current_target}' perdido")
            self.current_target = None
            self.state = "idle"
            self._target_missing_frames = 0
            return

        # ========== Verificar si target actual sigue presente ==========
        if self.current_target:
            target_still_there = any(
                c.name.lower() == self.current_target.lower()
                for c in creatures
            )
            if not target_still_there:
                self._target_missing_frames += 1
                if self._target_missing_frames >= self.max_target_missing:
                    self._log(
                        f"Target '{self.current_target}' desapareció "
                        f"({self._target_missing_frames} frames) — buscando otro"
                    )
                    self.current_target = None
                    self._target_missing_frames = 0
                    self.state = "searching"
            else:
                self._target_missing_frames = 0

        # ========== ¿Necesitamos atacar? ==========
        already_attacking = self.battle_reader.is_attacking(frame)

        if already_attacking:
            # YA estamos atacando — NO re-clickear, mantener estado
            self.state = "attacking"
            return

        # NO estamos atacando → buscar target
        # Si teníamos target y desapareció, usar delay corto
        # Si es target nuevo, usar delay normal
        delay = self.re_attack_delay if self.current_target else self.attack_delay

        if now - self.last_attack_time >= delay:
            if now - self._last_target_switch < self._target_switch_cooldown:
                return
            target = self._select_target(creatures)
            if target:
                self._attack_target(frame, target)
                self.state = "attacking"

    def _count_by_name(self, creatures: List[CreatureEntry]) -> Dict[str, int]:
        """Cuenta criaturas POR NOMBRE para kill detection precisa."""
        counts: Dict[str, int] = {}
        for c in creatures:
            name = c.name.lower()
            counts[name] = counts.get(name, 0) + 1
        return counts

    def _detect_kills_by_name(self, current_counts: Dict[str, int]):
        """
        Kill detection v2: compara conteo POR MONSTRUO ESPECÍFICO.
        Si había 3 Rotworm y ahora hay 2 → 1 kill de Rotworm.
        """
        if not self._prev_counts_by_name:
            return

        for name, prev_count in self._prev_counts_by_name.items():
            curr_count = current_counts.get(name, 0)
            if prev_count > curr_count:
                kills = prev_count - curr_count
                self.monsters_killed += kills

                display_name = name.title()
                self._log(f"¡Kill! {display_name} x{kills} — Total: {self.monsters_killed}")

                for _ in range(kills):
                    self._notify_kill(display_name)

    def _notify_kill(self, monster_name: str):
        """Notifica una kill al looter directamente."""
        if self._looter_engine:
            self._looter_engine.notify_kill(
                monster_name,
                self.last_attack_position[0],
                self.last_attack_position[1],
            )

    def _select_target(self, creatures: List[CreatureEntry]) -> Optional[CreatureEntry]:
        """
        Selecciona el mejor objetivo según prioridad.
        v3: Respeta per-creature priority si hay perfiles configurados.
        """
        # Si hay perfiles, usar priority de perfil
        if self.creature_profiles:
            scored = []
            for c in creatures:
                profile = self.get_creature_profile(c.name)
                p = profile.get("priority", 0)
                scored.append((p, c))
            # Ordenar por priority descendente (mayor = primero)
            scored.sort(key=lambda x: x[0], reverse=True)
            # Si hay alguno con priority > 0, retornar ese
            if scored and scored[0][0] > 0:
                return scored[0][1]

        # 1. Prioridad alta (priority_list)
        priority = self.battle_reader.get_priority_targets()
        if priority:
            return priority[0]

        # 2. Atacables (filtrados por attack_list / ignore_list)
        attackable = self.battle_reader.get_attackable_monsters()
        if attackable:
            return attackable[0]

        # 3. Fallback: primera criatura
        return creatures[0] if creatures else None

    def _attack_target(self, frame: np.ndarray, target: CreatureEntry):
        """Hace click en el monstruo en la battle list para atacarlo."""
        if not self._click_fn:
            return

        x, y = target.screen_x, target.screen_y
        if x == 0 and y == 0:
            x, y = self.battle_reader.find_target(frame, target.name)

        if x != 0 and y != 0:
            old_target = self.current_target

            # Si cambiamos de target, aplicar chase/stand mode del nuevo
            if old_target != target.name:
                self._apply_chase_mode_for_creature(target.name, frame)

            self._click_fn(x, y)
            self.current_target = target.name
            self.last_attack_position = (x, y)
            self.last_attack_name = target.name
            self.total_attacks += 1
            self.last_attack_time = time.time()
            self._last_target_switch = time.time()
            self._target_missing_frames = 0

            # Notificar al battle_reader para fallback temporal de is_attacking
            self.battle_reader.notify_attack_click(target.name)

            if old_target != target.name:
                self._log(f"Atacando: {target.name} en ({x},{y})")
            else:
                self._log(f"Re-atacando: {target.name}")

    # ==================================================================
    # API pública
    # ==================================================================
    def get_creature_count(self) -> int:
        """Cuántas criaturas hay actualmente en la battle list."""
        return self._prev_total_count

    def get_creature_counts_by_name(self) -> Dict[str, int]:
        """Conteo detallado por nombre de monstruo."""
        return self._prev_counts_by_name.copy()

    def is_in_combat(self) -> bool:
        """True si estamos activamente atacando algo."""
        return self.current_target is not None and self.state == "attacking"

    # ==================================================================
    # Control
    # ==================================================================
    def start(self):
        self.enabled = True
        self._target_missing_frames = 0
        self._prev_counts_by_name.clear()
        self._prev_total_count = 0
        self._current_chase_mode = "unknown"
        self.state = "idle"
        tpl_count = len(self.battle_reader._name_templates)
        region = self.battle_reader.battle_region
        self._log("Targeting v3 activado")
        self._log(f"  Templates: {tpl_count} ({list(self.battle_reader._name_templates.keys())})")
        self._log(f"  Battle region: {region}")
        self._log(f"  Attack list: {self.monsters_to_attack}")
        self._log(f"  Delays: attack={self.attack_delay}s re-attack={self.re_attack_delay}s")
        if self.creature_profiles:
            self._log(f"  Perfiles: {list(self.creature_profiles.keys())}")
        if self.chase_key or self.stand_key:
            self._log(f"  Chase/Stand keys: chase='{self.chase_key}' stand='{self.stand_key}'")
        if not self.battle_reader._name_templates:
            self._log("⚠ Sin templates — configura monstruos y guarda")
        if region is None:
            self._log("⚠ Sin battle region — presiona 'Calibrar' primero")

    def stop(self):
        self.enabled = False
        self.current_target = None
        self.state = "idle"
        self._target_missing_frames = 0
        self._prev_counts_by_name.clear()
        self._current_chase_mode = "unknown"
        self._log("Targeting desactivado")

    def get_kill_count(self) -> int:
        return self.monsters_killed

    def get_monster_count(self) -> int:
        return self._prev_total_count

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "current_target": self.current_target,
            "monster_count": self._prev_total_count,
            "monsters_killed": self.monsters_killed,
            "total_attacks": self.total_attacks,
            "templates_loaded": len(self.battle_reader._name_templates),
            "target_missing_frames": self._target_missing_frames,
            "counts_by_name": self._prev_counts_by_name.copy(),
            "creature_profiles": len(self.creature_profiles),
            "current_chase_mode": self._current_chase_mode,
        }
