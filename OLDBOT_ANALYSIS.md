# Análisis Completo del Repositorio `alfredomtx/oldbot`
## Patrones Arquitectónicos para Bot de Tibia en Python + OBS WebSocket

> **Nota**: OldBot usa AutoHotkey con lectura de memoria + pixel/image search. Nuestro enfoque es **solo pixel/image analysis** vía OBS WebSocket. Se destacan los patrones adaptables.

---

## 1. 🗺️ Sistema de Waypoints

### Estructura de Datos
```python
# Adaptación Python del waypoint system de OldBot
# Original: waypointsObj[tabName][waypointNumber] := {type, label, coordinates, rangeX, rangeY, action, marker, image, sqm}

@dataclass
class Waypoint:
    type: str          # Walk, Stand, Action, Door, Ladder, Stair, Rope, Shovel, Machete, Use, Node
    label: str         # Nombre descriptivo
    x: int             # Coordenada X del mapa
    y: int             # Coordenada Y del mapa
    z: int             # Piso (0-15)
    range_x: int       # Rango de llegada horizontal (1-500 para Walk, 1 para tipos fijos)
    range_y: int       # Rango de llegada vertical
    action: str        # Acción a ejecutar al llegar (hotkey, script, etc.)
    marker: str        # Marcador visual en minimapa
    image: str         # Imagen asociada (para Use items)
    sqm: int           # SQM específico (1-9)

@dataclass
class WaypointTab:
    name: str
    waypoints: List[Waypoint]
```

### Tipos de Waypoint y su Lógica
```
Tipo         | Rango Fijo | Acción al Llegar
-------------|------------|--------------------------------------------------
Walk         | No (1-500) | Solo navegar, continuar al siguiente
Stand        | Sí (1)     | Debe estar en la coordenada exacta
Action       | No (1-500) | Ejecutar acción (hotkey, script) al llegar
Door         | Sí (1)     | Pararse sobre el tile de puerta
Ladder Up    | Sí (1)     | Usar escalera (cambiar piso +1)
Ladder Down  | Sí (1)     | Usar escalera (cambiar piso -1)
Stair Up     | Sí (1)     | Caminar sobre escalera (piso +1)
Stair Down   | Sí (1)     | Caminar sobre escalera (piso -1)
Rope         | Sí (1)     | Usar cuerda en el tile (UseChangeFloorItem)
Shovel       | Sí (1)     | Usar pala en el tile (UseChangeFloorItem)
Machete      | Sí (1)     | Usar machete en vegetación
Use          | Sí (1)     | Usar item específico en el tile
Node         | -          | Punto de decisión (bifurcación condicional)
```

### Loop de Navegación Principal
```python
# Patrón del loop de cavebot (adaptado de Cavebot.ahk líneas 650-735)
class CavebotLoop:
    def run(self):
        while self.enabled:
            tab = self.current_tab
            for waypoint in self.waypoints[tab]:
                if self.check_arrived(waypoint):
                    waypoint.arrived = True
                    self.execute_arrival_action(waypoint)
                    continue

                # Intentar caminar al waypoint
                success = self.walk_to_waypoint(waypoint)
                if not success:
                    # Manejar fallo - skip o retry
                    pass

            # Al completar todos los waypoints, volver al primero
            self.reset_to_first_waypoint()

    def check_arrived(self, wp):
        """Verifica si el personaje llegó al waypoint"""
        if wp.type in ['Stand', 'Door', 'Ladder', 'Rope', 'Shovel', 'Machete', 'Use']:
            return self.is_same_coord(wp.x, wp.y, wp.z)
        elif wp.type in ['Walk', 'Action']:
            if self.is_same_coord(wp.x, wp.y, wp.z):
                return True
            return self.is_in_range(wp.x, wp.y, wp.range_x, wp.range_y)
```

---

## 2. ⚔️ Sistema de Targeting/Combate

### Estructura de Spells
```python
@dataclass
class AttackSpell:
    hotkey: str              # Tecla para lanzar
    type: str                # "Attack" o "Support"
    rune: bool               # Si es una runa
    cooldown: float          # Cooldown del spell (ms)
    cooldown_spell: float    # Cooldown del grupo de spells
    support_spell: str       # Spell de soporte asociado
    mana: int                # Mana requerido
    target_life: int         # % de vida del target para activar
    creature_count: str      # "Any", "Only 1", "1+", "2+", "3+", "4+", "5+"
    sqm_distance: int        # Distancia máxima
    count_method: str        # "Battle list" o "Around character"
    count_policy: str        # Política de conteo
    mode: int                # 1 = sin restricción dirección, 2 = chequear dirección
    turn_to_direction: bool  # Girar hacia criaturas para AOE
    player_safe: bool        # No lanzar si hay players cerca
    enabled: bool
```

### Spells por Vocación (Referencia)
```python
SPELL_DATABASE = {
    "knight": [
        {"name": "Exori",     "cooldown": 2000, "type": "Attack", "mana": 115},
        {"name": "Exori gran","cooldown": 4000, "type": "Attack", "mana": 340},
        {"name": "Exori mas", "cooldown": 4000, "type": "Attack", "mana": 160},
        {"name": "Exori min", "cooldown": 2000, "type": "Attack", "mana": 200},
    ],
    "paladin": [
        {"name": "Exori san", "cooldown": 2000, "type": "Attack", "mana": 20},
        {"name": "Exori con", "cooldown": 2000, "type": "Attack", "mana": 25},
        {"name": "Exevo mas san", "cooldown": 4000, "type": "Attack", "mana": 150},
    ],
    "sorcerer": [
        {"name": "Exori vis",     "cooldown": 2000, "type": "Attack", "mana": 20},
        {"name": "Exori gran vis","cooldown": 4000, "type": "Attack", "mana": 60},
    ],
    "druid": [
        {"name": "Exori tera",     "cooldown": 2000, "type": "Attack", "mana": 20},
        {"name": "Exori gran tera","cooldown": 4000, "type": "Attack", "mana": 60},
    ],
}
```

### Selección de Spell (Patrón)
```python
def select_spell_to_cast(self, spells, current_mana, target_life_pct, creatures_around):
    """
    Patrón de OldBot: selectSpellToCast()
    Itera secuencialmente, chequea condiciones, retorna el primero válido.
    """
    for spell in spells:
        if not spell.enabled:
            continue
        if self.is_on_cooldown(spell):
            continue
        if current_mana < spell.mana:
            continue
        if not self.check_creature_count(spell.creature_count, creatures_around):
            continue
        if not self.check_target_life(spell.target_life, target_life_pct):
            continue
        return spell
    return None

def check_creature_count(self, condition, count):
    """Evalúa condición de conteo de criaturas"""
    mapping = {
        "Any": lambda c: True,
        "Only 1": lambda c: c == 1,
        "1+": lambda c: c >= 1,
        "2+": lambda c: c >= 2,
        "3+": lambda c: c >= 3,
        "4+": lambda c: c >= 4,
        "5+": lambda c: c >= 5,
    }
    return mapping.get(condition, lambda c: True)(count)
```

### Prioridad de Criaturas (Danger System)
```python
class TargetingSystem:
    def __init__(self):
        # creatures_danger: dict indexado por nivel de peligro
        # Se itera de mayor a menor prioridad
        self.creatures_danger = {}  # {danger_level: [creature_names]}

    def search_target(self):
        """Busca criaturas en battle list por prioridad de peligro"""
        # Iterar de mayor a menor peligro
        for danger_level in sorted(self.creatures_danger.keys(), reverse=True):
            for creature_name in self.creatures_danger[danger_level]:
                found = self.search_creature_in_battle_list(creature_name)
                if found:
                    return found
        return None
```

### Lógica AOE Direccional
```python
# OldBot cuenta criaturas en 4 direcciones usando grid 3x3 de SQMs
# SQMs layout:
#   7  8  9
#   4  5  6   (5 = personaje)
#   1  2  3

DIRECTION_SQMS = {
    "Up":    {1: 7, 2: 8, 3: 9},
    "Down":  {1: 1, 2: 2, 3: 3},
    "Right": {1: 9, 2: 6, 3: 3},
    "Left":  {1: 1, 2: 4, 3: 7},
}

def find_best_aoe_direction(self, creatures_by_sqm):
    """Cuenta criaturas por dirección, gira hacia la que tiene más"""
    counts = {}
    for direction, sqms in DIRECTION_SQMS.items():
        counts[direction] = sum(1 for sqm in sqms.values()
                                if sqm in creatures_by_sqm)
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else None
```

### Configuración por Criatura
```python
@dataclass
class CreatureConfig:
    name: str
    danger: int              # Nivel de peligro/prioridad
    only_if_trapped: bool    # Solo atacar si estamos trapped
    must_attack_me: bool     # Solo si nos ataca
    use_item_on_corpse: bool # Usar item en cadáver
    dont_loot: bool          # No lootear
    play_alarm: bool         # Sonar alarma
    ignore_unreachable: bool # Ignorar si no alcanzable
    ignore_attacking: bool   # Ignorar si ya atacando otro
    ring_hotkey: str         # Hotkey de anillo especial
    amulet_hotkey: str       # Hotkey de amuleto especial
    exeta_res_hotkey: str    # Hotkey de exeta res
    attack_mode: str         # Modo de ataque
    attack_spells: List[AttackSpell]
```

---

## 3. 💰 Sistema de Looting

### Listas de Items
```python
@dataclass
class LootItem:
    name: str
    action: str    # "loot", "deposit", "sell", "trash", "ignore", "use", "drop"
    tries: int     # Intentos máximos de búsqueda
    image: str     # Ruta a imagen del item

class LootingHandler:
    def __init__(self):
        self.deposit_list: List[LootItem] = []   # Items para depositar en depot
        self.loot_list: List[LootItem] = []       # Items para recoger
        self.sell_list: List[LootItem] = []       # Items para vender en NPC
        self.trash_list: List[LootItem] = []      # Items para descartar
```

### Métodos de Quick Loot
```python
QUICK_LOOT_METHODS = {
    "shift_right": "Shift + Right Click",
    "ctrl_right":  "Ctrl + Right Click",
    "right":       "Right Click",
}

LOOTING_METHODS = {
    "click_around":  "Shift+Right Click en los 8 SQMs alrededor",
    "click_on_item": "Click directo en el item encontrado",
    "press_hotkey":  "Presionar hotkey de loot",
}
```

### Flujo de Looting
```python
class LootingSystem:
    def loot_all_sqms(self):
        """
        Patrón de OldBot: lootAllSqms()
        Recorre los 9 SQMs (o los relevantes) y abre cadáveres en cada uno.
        """
        for sqm in range(1, 10):  # SQM1 a SQM9
            self.open_corpse_on_sqm(sqm)
            self.search_and_collect_loot()

    def open_corpse_on_sqm(self, sqm):
        """Abre cadáver: right-click → menú 'Open' o Ctrl+Click"""
        sqm_pos = self.get_sqm_position(sqm)
        # Método 1: Right click → buscar opción "Open" en menú
        # Método 2: Classic control click (Ctrl+Click)
        pass

    def search_and_collect_loot(self):
        """Busca items en el cadáver abierto y los recoge"""
        # 1. Buscar imagen de bag dentro del cadáver
        # 2. Si hay bag, abrirlo
        # 3. Buscar items de la loot_list por imagen
        # 4. Drag & drop al backpack/personaje
        pass

    def drag_loot(self, from_x, from_y, to_x, to_y):
        """Arrastra item desde cadáver al inventario"""
        # MouseDrag de posición de item a posición de backpack
        pass
```

### Distance Looting (Cola de Posiciones)
```python
class DistanceLooting:
    """
    OldBot: _DistanceLooting - mantiene cola de coordenadas donde murieron criaturas.
    Ordena por distancia al personaje, camina a cada una y lootea.
    """
    def __init__(self):
        self.queue: List[Tuple[int, int, int]] = []  # (x, y, z)

    def add_death_position(self, x, y, z):
        """Añade posición donde murió una criatura"""
        self.queue.append((x, y, z))

    def process_queue(self):
        """Procesa cola ordenada por distancia"""
        char_x, char_y = self.get_char_position()
        self.queue.sort(key=lambda pos: abs(pos[0]-char_x) + abs(pos[1]-char_y))

        for pos in self.queue:
            if self.walk_to(pos[0], pos[1]):
                self.loot_sqms_at(pos[0], pos[1])
        self.queue.clear()
```

### Detección de Cadáveres (Image Search)
```python
# OldBot usa imágenes de cadáveres organizadas por tamaño de ventana:
# corpsesFolder\Size{WINDOW_SIZE_LEVEL}\{creatureName}.png
#
# Para nuestro enfoque con OBS:
# - Capturar frame de pantalla
# - Template matching con imágenes de cadáveres pre-guardadas
# - Cada criatura tiene su imagen de cadáver específica
```

---

## 4. 🧭 Pathfinding (A* / Astar)

### Implementación A* de OldBot
```python
class AstarPath:
    """
    Adaptación directa del A* de OldBot (_AstarPath.ahk)
    Usa heurística Manhattan. Timeout de 2 segundos.
    Solo movimiento 4-direccional (N, S, E, W).
    """
    TIMEOUT = 2.0  # segundos

    def __init__(self, dest_x, dest_y, char_x, char_y, walkable_map):
        self.dest = (dest_x, dest_y)
        self.start = (char_x, char_y)
        self.walkable_map = walkable_map

    def find_path(self):
        """A* grid search - traducción directa del AHK"""
        open_set = {self.start: True}
        closed_set = {}
        came_from = {}
        g_score = {self.start: 0}
        f_score = {self.start: self.heuristic(self.start, self.dest)}

        start_time = time.time()

        while open_set:
            if time.time() - start_time > self.TIMEOUT:
                raise TimeoutError("A* path timed out")

            current = self.lowest_f(f_score, open_set)

            if current == self.dest:
                return self.reconstruct_path(came_from, current)

            del open_set[current]
            closed_set[current] = True

            # Solo 4 vecinos: N, S, E, W (OldBot no usa diagonales en A*)
            for neighbor in self.get_neighbors(current):
                if neighbor in closed_set:
                    continue

                tentative_g = g_score[current] + 1

                if neighbor not in open_set:
                    open_set[neighbor] = True
                elif tentative_g >= g_score.get(neighbor, float('inf')):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + self.heuristic(neighbor, self.dest)

        return None  # No path found

    def heuristic(self, a, b):
        """Manhattan distance - Estimate_F en OldBot"""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def get_neighbors(self, pos):
        """4 direcciones: arriba, abajo, izquierda, derecha"""
        x, y = pos
        neighbors = [(x, y-1), (x-1, y), (x+1, y), (x, y+1)]
        return [n for n in neighbors if self.walkable_map.get(n, False)]

    def reconstruct_path(self, came_from, current):
        """From_Path en OldBot - reconstruye camino desde parent pointers"""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.insert(0, current)
        return path

    def lowest_f(self, f_score, open_set):
        """Lowest_F_Set en OldBot"""
        return min(open_set.keys(), key=lambda pos: f_score.get(pos, float('inf')))
```

### Walkability (Colores de Minimapa)
```python
# OldBot determina si una coordenada es caminable por el color del pixel en el minimapa
# Estos colores son ESTÁNDAR de Tibia (archivos .png del minimapa)

NON_WALKABLE_COLORS = {
    "0x000000": "black (void)",
    "0xFF3300": "red (wall)",
    "0x3300CC": "blue (sea)",
    "0x006600": "green (trees)",
    "0x00FF00": "lime (swamps)",
    "0x666666": "gray (rocks)",
    "0x993300": "brown (cave wall)",
    "0xFF6600": "orange (lava)",
}

STAIR_COLOR = "0xFFFF00"  # Yellow = escalera en minimapa

# Para nuestro enfoque sin memoria:
# - Podemos usar las imágenes del minimapa que Tibia guarda localmente
# - O analizar el minimapa visible en pantalla por colores de pixel
```

### Flujo de Caminado (3 métodos en cascada)
```python
class WalkToCoordinate:
    """
    OldBot usa 3 métodos en cascada:
    1. Click en minimapa (más rápido, más lejos)
    2. A* path + flechas del teclado (preciso)
    3. Caminar por dirección con flechas (fallback)
    """
    def walk(self, dest_x, dest_y, dest_z):
        # Método 1: Click en minimapa
        if self.walk_by_map_click(dest_x, dest_y):
            return True

        # Método 2: Generar ruta A* y caminar con flechas
        if self.walk_by_astar(dest_x, dest_y):
            return True

        # Método 3: Caminar por dirección (fallback)
        if self.walk_by_direction(dest_x, dest_y):
            return True

        return False  # No se pudo llegar

    WALK_BY_ARROW_LIMIT = 45   # Límite de pasos con flechas
    WALK_BY_CLICK_LIMIT = 45   # Límite de clicks en minimapa
```

### Coordenadas Bloqueadas
```python
class BlockedCoordinates:
    """
    OldBot mantiene listas de coordenadas bloqueadas que se actualizan dinámicamente:
    - blocked_coordinates: coords donde falló caminar (se agregan en runtime)
    - blocked_by_creatures: coords con life bars detectadas (criaturas bloqueando)
    - NON_WALKABLE_COORDINATES: permanentes del minimapa
    - BLACKLISTED_COORDINATES: lista negra manual

    Estas se usan como "Closed" set adicional al generar el A*.
    """
    def __init__(self):
        self.blocked = {}            # {(x,y,z): True}
        self.blocked_by_creatures = {} # Temporal, se resetea cada path

    def add_blocked(self, x, y, z):
        self.blocked[(x, y, z)] = True

    def is_walkable(self, x, y, z):
        if (x, y, z) in self.blocked:
            return False
        if (x, y, z) in self.blocked_by_creatures:
            return False
        return True
```

---

## 5. ⌨️🖱️ Interacción Mouse/Keyboard (PostMessage/SendMessage)

### Patrón de Background Input (Clave para nuestro bot)
```python
# OldBot usa SendMessage/PostMessage de Windows para enviar input sin necesitar foco.
# Esto es CRÍTICO porque permite operar en segundo plano.

# Mensajes Windows usados:
WM_KEYDOWN    = 0x0100
WM_KEYUP      = 0x0101
WM_CHAR       = 0x0102  # Para input de caracteres
WM_SETFOCUS   = 0x0007
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP   = 0x0205
WM_MOUSEMOVE   = 0x0200
WM_SETCURSOR   = 0x0020
WM_NCHITTEST   = 0x0084

# Parámetros de fwKeys para mouse:
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_SHIFT   = 0x0004
```

### Formato lParam para Mouse
```python
# El lParam para mensajes de mouse combina X e Y:
# lParam = (x & 0xFFFF) | (y << 16)

def make_lparam(x, y):
    """Construye lParam para PostMessage de mouse"""
    return (x & 0xFFFF) | (y << 16)

# Ejemplo de click izquierdo en background:
# PostMessage(WM_LBUTTONDOWN, MK_LBUTTON, make_lparam(cx, cy), hwnd)
# PostMessage(WM_LBUTTONUP,   0,          make_lparam(cx, cy), hwnd)
```

### Tabla de Scan Codes (lParam para teclas)
```python
# OldBot tiene hardcoded el lParam para cada tecla.
# El lParam de keyboard contiene el scan code: 0x{SCANCODE}0001
# Donde SCANCODE es el hardware scan code de la tecla.

KEY_PARAMS = {
    # Letras
    "a": {"vk": 0x41, "lparam": 0x01E0001},
    "b": {"vk": 0x42, "lparam": 0x0300001},
    "c": {"vk": 0x43, "lparam": 0x02E0001},
    "d": {"vk": 0x44, "lparam": 0x0200001},
    "e": {"vk": 0x45, "lparam": 0x0120001},
    "f": {"vk": 0x46, "lparam": 0x0210001},
    "g": {"vk": 0x47, "lparam": 0x0220001},
    "h": {"vk": 0x48, "lparam": 0x0230001},
    "i": {"vk": 0x49, "lparam": 0x0170001},
    "j": {"vk": 0x4A, "lparam": 0x0240001},
    "k": {"vk": 0x4B, "lparam": 0x0250001},
    "l": {"vk": 0x4C, "lparam": 0x0260001},
    "m": {"vk": 0x4D, "lparam": 0x0320001},
    "n": {"vk": 0x4E, "lparam": 0x0310001},
    "o": {"vk": 0x4F, "lparam": 0x0180001},
    "p": {"vk": 0x50, "lparam": 0x0190001},
    "q": {"vk": 0x51, "lparam": 0x0100001},
    "r": {"vk": 0x52, "lparam": 0x0130001},
    "s": {"vk": 0x53, "lparam": 0x01F0001},
    "t": {"vk": 0x54, "lparam": 0x0140001},
    "u": {"vk": 0x55, "lparam": 0x0160001},
    "v": {"vk": 0x56, "lparam": 0x02F0001},
    "w": {"vk": 0x57, "lparam": 0x0110001},
    "x": {"vk": 0x58, "lparam": 0x02D0001},
    "y": {"vk": 0x59, "lparam": 0x0150001},
    "z": {"vk": 0x5A, "lparam": 0x02C0001},

    # Números
    "0": {"vk": 0x30, "lparam": 0x0B0001},
    "1": {"vk": 0x31, "lparam": 0x020001},
    "2": {"vk": 0x32, "lparam": 0x030001},
    "3": {"vk": 0x33, "lparam": 0x040001},
    "4": {"vk": 0x34, "lparam": 0x050001},
    "5": {"vk": 0x35, "lparam": 0x060001},
    "6": {"vk": 0x36, "lparam": 0x070001},
    "7": {"vk": 0x37, "lparam": 0x080001},
    "8": {"vk": 0x38, "lparam": 0x090001},
    "9": {"vk": 0x39, "lparam": 0x0A0001},

    # F-Keys
    "F1":  {"vk": 0x70, "lparam": 0x03B0001},
    "F2":  {"vk": 0x71, "lparam": 0x03C0001},
    "F3":  {"vk": 0x72, "lparam": 0x03D0001},
    "F4":  {"vk": 0x73, "lparam": 0x03E0001},
    "F5":  {"vk": 0x74, "lparam": 0x03F0001},
    "F6":  {"vk": 0x75, "lparam": 0x0400001},
    "F7":  {"vk": 0x76, "lparam": 0x0410001},
    "F8":  {"vk": 0x77, "lparam": 0x0420001},
    "F9":  {"vk": 0x78, "lparam": 0x0430001},
    "F10": {"vk": 0x79, "lparam": 0x0440001},
    "F11": {"vk": 0x7A, "lparam": 0x0570001},
    "F12": {"vk": 0x7B, "lparam": 0x0580001},

    # Flechas
    "Up":    {"vk": 0x26, "lparam": 0x01480001},
    "Down":  {"vk": 0x28, "lparam": 0x01500001},
    "Left":  {"vk": 0x25, "lparam": 0x014B0001},
    "Right": {"vk": 0x27, "lparam": 0x014D0001},

    # Otros
    "Enter":     {"vk": 0x0D, "lparam": 0x01C0001},
    "Esc":       {"vk": 0x1B, "lparam": 0x010001},
    "Space":     {"vk": 0x20, "lparam": 0x0390001},
    "Backspace": {"vk": 0x08, "lparam": 0x0E0001},
    "Tab":       {"vk": 0x09, "lparam": 0x0F0001},

    # Numpad
    "Numpad0": {"vk": 0x60, "lparam": 0x0520001},
    "Numpad1": {"vk": 0x61, "lparam": 0x04F0001},
    "Numpad2": {"vk": 0x62, "lparam": 0x0500001},
    "Numpad3": {"vk": 0x63, "lparam": 0x0510001},
    "Numpad4": {"vk": 0x64, "lparam": 0x04B0001},
    "Numpad5": {"vk": 0x65, "lparam": 0x04C0001},
    "Numpad6": {"vk": 0x66, "lparam": 0x04D0001},
    "Numpad7": {"vk": 0x67, "lparam": 0x0470001},
    "Numpad8": {"vk": 0x68, "lparam": 0x0480001},
    "Numpad9": {"vk": 0x69, "lparam": 0x0490001},

    # Modificadores
    "Ctrl":  {"vk": 0x11, "lparam": 0x021D0001},
    "Shift": {"vk": 0x10, "lparam": 0x02A0001},
}
```

### Dos Métodos de Input de OldBot
```python
# OldBot tiene 2 métodos de envío de teclas:
# 1. WM_KEYDOWN (0x0100) - Simula presión física de tecla
# 2. WM_CHAR (0x0102) - Envía carácter directamente

# La elección depende de:
# - pressLetterKeysDefaultMethod: true = WM_KEYDOWN, false = WM_CHAR
# - Si hay modifier key (Ctrl/Shift/Alt) siempre usa WM_KEYDOWN
# - F1-F12: pressF1toF12KeysDefaultMethod
# - Flechas: pueden usar PostMessage (async) o SendMessage (sync)

# Para flechas con PostMessage (async, no bloquea):
# PostMessage(0x100, vk, lparam, hwnd)  # KEYDOWN
# PostMessage(0x101, vk, lparam, hwnd)  # KEYUP

# Para flechas con SendMessage (sync):
# SendMessage(0x100, vk, lparam, hwnd)  # KEYDOWN
# SendMessage(0x101, vk, lparam, hwnd)  # KEYUP
```

### Secuencia de Click en Background (IMPORTANTE)
```python
def background_click(hwnd, x, y, button="Left"):
    """
    Secuencia completa de click en background de OldBot.
    Orden CRÍTICO de mensajes para Tibia 11/12/13:
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    lparam = (x & 0xFFFF) | (y << 16)

    # 1. Mover mouse (PostMessage)
    user32.PostMessageW(hwnd, 0x200, 0x00000000, lparam)  # WM_MOUSEMOVE

    # 2. Hit test (SendMessage)
    user32.SendMessageW(hwnd, 0x084, 0x00000000, lparam)  # WM_NCHITTEST

    # 3. Set cursor (SendMessage)
    if button == "Left":
        user32.SendMessageW(hwnd, 0x020, hwnd, 0x02010001)  # WM_SETCURSOR
    else:
        user32.SendMessageW(hwnd, 0x020, hwnd, 0x02040001)

    # 4. Set focus
    user32.PostMessageW(hwnd, 0x07, 0, 0)  # WM_SETFOCUS

    # 5. Button down
    if button == "Left":
        user32.PostMessageW(hwnd, 0x201, 0x0001, lparam)  # WM_LBUTTONDOWN
    else:
        user32.PostMessageW(hwnd, 0x204, 0x0002, lparam)  # WM_RBUTTONDOWN

    time.sleep(0.02)

    # 6. Button up
    if button == "Left":
        user32.PostMessageW(hwnd, 0x202, 0, lparam)  # WM_LBUTTONUP
    else:
        user32.PostMessageW(hwnd, 0x205, 0, lparam)  # WM_RBUTTONUP

def background_drag(hwnd, x1, y1, x2, y2):
    """Drag & drop en background"""
    lp1 = (x1 & 0xFFFF) | (y1 << 16)
    lp2 = (x2 & 0xFFFF) | (y2 << 16)

    # Mouse down en origen
    user32.PostMessageW(hwnd, 0x201, 0x0001, lp1)  # WM_LBUTTONDOWN
    time.sleep(0.05)

    # Mouse move al destino
    user32.PostMessageW(hwnd, 0x200, 0x0001, lp2)  # WM_MOUSEMOVE
    time.sleep(0.05)

    # Mouse up en destino
    user32.PostMessageW(hwnd, 0x202, 0, lp2)  # WM_LBUTTONUP

def background_shift_click(hwnd, x, y, button="Right"):
    """Shift + Click en background (para loot rápido)"""
    # Hold shift
    user32.PostMessageW(hwnd, 0x100, 0x10, 0x02A0001)  # Shift KEYDOWN
    time.sleep(0.01)

    # Click
    lparam = (x & 0xFFFF) | (y << 16)
    if button == "Right":
        user32.PostMessageW(hwnd, 0x204, 0x0004 | 0x0002, lparam)
    else:
        user32.PostMessageW(hwnd, 0x201, 0x0004, lparam)

    time.sleep(0.01)

    # Release click
    if button == "Right":
        user32.PostMessageW(hwnd, 0x205, 0x4, lparam)
    else:
        user32.PostMessageW(hwnd, 0x202, 0x4, lparam)

    time.sleep(0.01)

    # Release shift
    user32.SendMessageW(hwnd, 0x101, 0x10, 1)  # Shift KEYUP

def hold_modifier(hwnd, modifier="Ctrl"):
    """Mantener presionada tecla modificadora"""
    if modifier == "Ctrl":
        user32.PostMessageW(hwnd, 0x100, 0x11, 0x021D0001)
        user32.PostMessageW(hwnd, 0x100, 0x11, 0x021D0001)  # Se envía 2 veces en OldBot
    elif modifier == "Shift":
        user32.PostMessageW(hwnd, 0x07, 0, 0)  # WM_SETFOCUS primero
        user32.PostMessageW(hwnd, 0x100, 0x10, 0x02A0001)
        user32.PostMessageW(hwnd, 0x100, 0x10, 0x02A0001)

def release_modifier(hwnd, modifier="Ctrl"):
    if modifier == "Ctrl":
        user32.PostMessageW(hwnd, 0x101, 0x11, 0x021D0001)
        user32.PostMessageW(hwnd, 0x101, 0x11, 0x021D0001)
    elif modifier == "Shift":
        user32.PostMessageW(hwnd, 0x101, 0x10, 1)
        user32.PostMessageW(hwnd, 0x101, 0x10, 1)
```

### ControlFromPoint (Conversión de coordenadas)
```python
# OldBot usa ControlFromPoint para convertir coordenadas relativas de ventana
# a coordenadas del control hijo correcto. Esto es necesario porque Tibia
# puede tener controles hijos y las coordenadas del PostMessage son relativas
# al control que recibe el mensaje.

def control_from_point(hwnd, x, y):
    """
    Equivalente a ControlFromPoint de OldBot.
    Convierte coordenadas de ventana a coordenadas de control hijo.
    """
    import ctypes
    from ctypes import wintypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    # Obtener posición de la ventana
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

    # Crear punto absoluto
    pt = POINT(rect.left + x, rect.top + y)

    # Encontrar control hijo bajo el punto
    child = ctypes.windll.user32.ChildWindowFromPoint(hwnd, pt)
    if child and child != hwnd:
        ctypes.windll.user32.ScreenToClient(child, ctypes.byref(pt))
        return child, pt.x, pt.y

    return hwnd, x, y
```

### DLL Externa para Mouse Hooks
```python
# OldBot también usa una DLL externa (mousehook64.dll) para clicks más confiables:
# DllCall("mousehook64.dll\LeftClick", "AStr", TibiaClientTitle, "INT", cX, "INT", cY)
# DllCall("mousehook64.dll\RightClick", "AStr", TibiaClientTitle, "INT", cX, "INT", cY)
# DllCall("mousehook64.dll\dragDrop", "AStr", Title, "INT", botProtection, "INT", x1, "INT", y1, "INT", x2, "INT", y2)
#
# Para Python podemos usar ctypes con PostMessage directo o pyautogui como fallback.
```

---

## 6. 📐 Sistema de Coordenadas de Pantalla

### Grid de SQMs (3x3 alrededor del personaje)
```python
# El personaje está SIEMPRE en el centro de la ventana del juego.
# CHAR_POS_X, CHAR_POS_Y = centro de la game window.
# SQM_SIZE = tamaño en pixels de un tile del juego.

# Layout de SQMs numerados (grid extendido de OldBot):
#
#                       29
#                       25
#              19  20  21
#         17   07  08  09  18
#   27 23 15   04  05  06  16  24  28
#         13   01  02  03  14
#              10  11  12
#                  22
#                  26

# Los SQMs 1-9 son el grid 3x3 inmediato:
#   7  8  9
#   4  5  6    (5 = posición del personaje)
#   1  2  3

class ScreenSQMs:
    def __init__(self, char_pos_x, char_pos_y, sqm_size):
        self.char_x = char_pos_x
        self.char_y = char_pos_y
        self.sqm_size = sqm_size
        self.sqms = self._calculate_sqms()

    def _calculate_sqms(self):
        """Calcula posiciones de pantalla para los 9 SQMs centrales"""
        cx, cy, s = self.char_x, self.char_y, self.sqm_size
        return {
            # Row inferior (y + sqm_size)
            1: {"x": cx - s, "y": cy + s},  # Abajo-izquierda
            2: {"x": cx,     "y": cy + s},  # Abajo-centro
            3: {"x": cx + s, "y": cy + s},  # Abajo-derecha
            # Row media (y = char_y)
            4: {"x": cx - s, "y": cy},      # Izquierda
            5: {"x": cx,     "y": cy},      # Centro (personaje)
            6: {"x": cx + s, "y": cy},      # Derecha
            # Row superior (y - sqm_size)
            7: {"x": cx - s, "y": cy - s},  # Arriba-izquierda
            8: {"x": cx,     "y": cy - s},  # Arriba-centro
            9: {"x": cx + s, "y": cy - s},  # Arriba-derecha
        }

    def get_sqm_bounds(self, sqm_num):
        """Retorna x1,y1,x2,y2 del SQM (bounding box)"""
        sqm = self.sqms[sqm_num]
        half = self.sqm_size // 2
        return {
            "x1": sqm["x"] - half,
            "y1": sqm["y"] - half,
            "x2": sqm["x"] + half,
            "y2": sqm["y"] + half,
        }
```

### Conversión Pantalla ↔ Mapa
```python
def screen_to_map_coords(screen_x, screen_y, char_x_screen, char_y_screen,
                          char_x_map, char_y_map, sqm_size):
    """
    FROM_SCREEN_POS de OldBot.
    Convierte posición de pantalla a coordenadas del mapa de Tibia.
    """
    # Calcular distancia en SQMs desde el personaje
    sqms_dist_x = (char_x_screen - screen_x) / sqm_size
    sqms_dist_y = (char_y_screen - screen_y) / sqm_size

    # Convertir a coordenadas del mapa
    if sqms_dist_x < 0:
        map_x = char_x_map + abs(int(sqms_dist_x))
    else:
        map_x = char_x_map - int(sqms_dist_x)

    if sqms_dist_y < 0:
        map_y = char_y_map + abs(int(sqms_dist_y))
    else:
        map_y = char_y_map - int(sqms_dist_y)

    return map_x, map_y

def map_to_screen_coords(map_x, map_y, char_x_map, char_y_map,
                          char_x_screen, char_y_screen, sqm_size):
    """Convierte coordenadas del mapa a posición en pantalla"""
    offset_x = (map_x - char_x_map) * sqm_size
    offset_y = (map_y - char_y_map) * sqm_size
    return char_x_screen + offset_x, char_y_screen + offset_y

def map_to_minimap_relative(coord_x, coord_y, char_x, char_y):
    """realCoordsToMinimapRelative de OldBot"""
    return {"x": coord_x - char_x, "y": coord_y - char_y}

def get_sqm_for_map_coord(coord_x, coord_y, char_x, char_y):
    """
    getSQMByMinimapDirection de OldBot.
    Dado un offset X,Y desde el personaje, retorna el número de SQM (1-9).
    """
    dx = coord_x - char_x  # >0 = derecha, <0 = izquierda
    dy = coord_y - char_y  # >0 = abajo, <0 = arriba

    # Normalizar a -1, 0, 1
    x = max(-1, min(1, dx)) if dx != 0 else 0
    y = max(-1, min(1, dy)) if dy != 0 else 0

    # Mapeo de (x, y) a SQM number
    sqm_map = {
        (-1,  1): 1, (0,  1): 2, (1,  1): 3,
        (-1,  0): 4, (0,  0): 5, (1,  0): 6,
        (-1, -1): 7, (0, -1): 8, (1, -1): 9,
    }
    return sqm_map.get((x, y), 5)
```

### Coordenadas de Mapa a Minimapa para Click
```python
def map_to_minimap_screen(coord_x, coord_y, char_x, char_y,
                           minimap_center_x, minimap_center_y):
    """
    realCoordsToMinimapScreen de OldBot.
    Convierte coordenada del mapa real a posición en la ventana del minimapa para click.
    """
    distance_x = coord_x - char_x
    distance_y = coord_y - char_y

    if distance_x < 0:
        screen_x = minimap_center_x - abs(distance_x)
    else:
        screen_x = minimap_center_x + distance_x

    if distance_y < 0:
        screen_y = minimap_center_y - abs(distance_y)
    else:
        screen_y = minimap_center_y + distance_y

    return screen_x, screen_y

# Límites de visibilidad en minimapa (Tibia 13+):
MINIMAP_VISIBLE_RANGE_X = 51  # SQMs visibles en X
MINIMAP_VISIBLE_RANGE_Y = 52  # SQMs visibles en Y
```

---

## 7. 👁️ Battle List / Detección de Criaturas

### Colores de Life Bar en Battle List
```python
# Tibia 13 (cliente actual):
LIFE_BAR_COLORS_T13 = {
    "greenFull": "0xC000",    # Vida completa
    "green":     "0x60C060",  # >75%
    "yellow":    "0xC0C000",  # 50-75%
    "orange":    "0xC00000",  # 25-50%
    "red":       "0xC03030",  # <25%
    "black":     "0x600000",  # Muerto/casi muerto
}

# Tibia 11/12 (clientes anteriores):
LIFE_BAR_COLORS_OLD = {
    "greenFull": "0x00BC00",
    "green":     "0x50A150",
    "yellow":    "0xA1A100",
    # ... más colores
}

# Colores usados en ImagesConfig:
BATTLE_LIST_LIFE_BAR_COLORS = [
    "0x00C000",  # greenFull
    "0x60C060",  # green
    "0xC0C000",  # yellow
    "0xC03030",  # red
]
```

### Estructura del Battle List Area
```python
class BattleListArea:
    """
    El Battle List es un panel del cliente que muestra criaturas visibles.
    OldBot lo detecta por image search de:
    - Título del panel ("Battle List")
    - Botones del panel (battlelist_buttons.png)
    - Posición relativa al resto del UI
    """
    def __init__(self):
        self.x1 = 0  # Esquina superior izquierda
        self.y1 = 0
        self.x2 = 0  # Esquina inferior derecha
        self.y2 = 0

    # Configuración de life bars en battle list:
    LIFE_BAR_OFFSET_X = 22   # Offset X desde imagen base de criatura
    LIFE_BAR_OFFSET_Y = 31   # Offset Y desde imagen base
    LIFE_BAR_WIDTH = 132     # Ancho de la barra (Tibia 13) / 139 (Tibia 11/12)
    SPACE_BETWEEN_BARS = 22  # Espacio vertical entre criaturas en la lista
```

### Búsqueda de Criaturas (Image-Based)
```python
class CreatureSearch:
    """
    OldBot busca criaturas por IMAGEN en el battle list.
    Cada criatura tiene una imagen pre-guardada de su nombre/icono.
    Se usa _SearchCreature → _TargetingBase64ImageSearch.
    """
    def search_creature(self, creature_name, battle_list_area):
        """
        Busca imagen de criatura en el área del battle list.
        Retorna posición si encontrada.
        """
        # Template matching de la imagen del nombre de la criatura
        # contra el área del battle list capturada
        pass

    def search_life_bars_on_screen(self):
        """
        searchLifeBarsOnScreen de OldBot.
        Busca imágenes de life bars en la game window (NO en battle list).
        Se usa para contar criaturas alrededor y detectar SQMs bloqueados.
        Busca en carpeta: lifeBarsFolder/*.png
        """
        bars_found = []
        # Para cada imagen de life bar (distintos tamaños/colores):
        #   resultado = image_search(image, game_window_area)
        #   if resultado: bars_found.append(resultado)
        return bars_found

    def get_creature_sqm_from_lifebar(self, lifebar_pos):
        """
        getCreatureSqmByLifeBarPos de OldBot.
        Dada la posición de una life bar en pantalla,
        determina en qué SQM está la criatura.
        """
        x = lifebar_pos.x + SQM_SIZE / 2
        y = lifebar_pos.y + SQM_SIZE - (SQM_SIZE / 3)

        for sqm_num in range(1, 10):
            if sqm_num == 5:  # Skip character SQM
                continue
            bounds = self.get_sqm_bounds(sqm_num)
            if bounds["x1"] < x < bounds["x2"] and bounds["y1"] < y < bounds["y2"]:
                return sqm_num
        return None
```

### Verificación de Vida de Criatura por Pixel
```python
def creature_has_life(self, creature_battle_position, percent, battle_list_area):
    """
    creatureHasLife de OldBot.
    Verifica si la criatura tiene más vida que el % especificado.

    Método: Lee el pixel en la posición correspondiente al % de la barra de vida.
    Si el color del pixel coincide con un color de vida, la criatura tiene ≥ ese %.
    """
    # Obtener posición de la barra de vida en battle list
    position = battle_list_area.get_creature_position(creature_battle_position)
    bar_width = position.x2 - position.x1

    # Calcular X del pixel que corresponde al % de vida
    check_x = position.x1 + (percent * bar_width / 100)
    check_y = position.y1 + 17  # Offset Y fijo

    # Obtener color del pixel
    pixel_color = self.get_pixel_color(check_x, check_y)

    # Verificar si el color es de una barra de vida
    for color in LIFE_BAR_COLORS_T13.values():
        if pixel_color == color:
            return True  # Criatura tiene vida en esa posición

    return False  # No hay barra de vida → menos vida que el %
```

### Red Pixel (Indicador de Ataque)
```python
class BattleListPixelArea:
    """
    Área de "red pixel" en el battle list.
    Un pequeño rectángulo al lado de cada criatura que muestra un pixel rojo
    cuando estamos atacando a esa criatura.

    Se usa para:
    1. Verificar si estamos atacando (isAttacking)
    2. Encontrar qué criatura estamos atacando
    3. Anti-KS detection
    """
    OFFSET_FROM_BATTLELIST_X = 19  # Default offset
    OFFSET_FROM_BATTLELIST_Y = 0
    WIDTH = 4  # Ancho del área de pixel

    def is_attacking(self):
        """Busca imagen 'redline' en el área del battle list"""
        # image_search("redline", self.pixel_area)
        pass
```

### Anti-KS (Kill Steal Detection)
```python
class AntiKS:
    """
    Detecta si otro jugador ataca nuestro target.
    OldBot busca un "black pixel" en el battle list que indica la posición
    donde terminan nuestras criaturas y empiezan las de otros jugadores.
    """
    def detect_other_player_attacking(self):
        # Buscar posición del black pixel separator
        # Si criaturas aparecen DESPUÉS del separator, son de otro jugador
        pass
```

---

## 8. 🏗️ Arquitectura General Recomendada

```python
# Basado en los patrones de OldBot, la arquitectura recomendada para nuestro bot:

class TibiaBot:
    def __init__(self):
        # Sistemas principales (como en OldBot)
        self.screen_capture = ScreenCapture()      # OBS WebSocket (reemplaza memory reading)
        self.input_sender = InputSender()           # PostMessage/SendMessage
        self.cavebot = CavebotSystem()              # Waypoints + navegación
        self.targeting = TargetingSystem()           # Combate + spells
        self.looting = LootingSystem()              # Looting + distance looting
        self.healing = HealingSystem()              # Healing por pixel de barras
        self.pathfinder = AstarPathfinder()          # A* pathfinding

        # Estado global (como las variables globales de OldBot)
        self.char_pos = {"x": 0, "y": 0, "z": 0}   # Posición del personaje
        self.char_screen_pos = {"x": 0, "y": 0}     # Posición en pantalla
        self.sqm_size = 0                             # Tamaño de SQM en pixels
        self.window_pos = {"x": 0, "y": 0, "w": 0, "h": 0}
        self.hwnd = 0                                 # Handle de la ventana

    def main_loop(self):
        """
        Loop principal: cavebot → targeting → looting → healing
        Prioridades de OldBot:
        1. Healing (siempre primero, vida del personaje)
        2. Targeting (atacar criaturas)
        3. Looting (recoger loot)
        4. Cavebot (navegar waypoints)
        """
        while self.running:
            self.screen_capture.capture_frame()

            if self.healing.needs_healing():
                self.healing.heal()
                continue

            if self.targeting.has_target():
                self.targeting.attack()
                continue

            if self.looting.has_loot_pending():
                self.looting.loot()
                continue

            self.cavebot.walk_next_waypoint()
```

---

## Resumen de Adaptaciones Clave para Python + OBS WebSocket

| OldBot (AHK)                    | Nuestro Bot (Python)                          |
|----------------------------------|-----------------------------------------------|
| Memory reading (posx/posy/posz)  | Análisis de minimapa por pixel/OCR            |
| Gdip_GetPixel en bitmaps        | OpenCV template matching en frames OBS        |
| SendMessage/PostMessage          | ctypes + win32api PostMessage                 |
| mousehook64.dll                  | ctypes PostMessage directo                    |
| _ImageSearch (GDI+)             | OpenCV matchTemplate / PIL                    |
| INI files config                 | JSON config (ya lo tenemos)                   |
| Minimap .png files               | Archivos de minimap de Tibia + OCR            |
| _BitmapEngine.getClientBitmap   | OBS WebSocket screenshot                      |
| A* on minimap bitmap             | A* en grid basado en análisis de minimapa     |
| Battle list image search         | Template matching en área de battle list       |
