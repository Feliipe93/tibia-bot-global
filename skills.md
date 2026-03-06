# 📓 Skills.md — Documentación Técnica Completa del Proyecto

> **Última actualización:** 5 de marzo de 2026
> **Proyecto:** Tibia Auto Bot (Healer + Targeting + Looter + Cavebot)
> **Stack:** Python 3.13.2 · OpenCV · OBS WebSocket · Win32 API · customtkinter

Este documento contiene **TODO** lo que se ha hecho, cómo funciona, qué falta, y las decisiones técnicas tomadas. Está diseñado para que cualquier IA o desarrollador pueda entender el proyecto completo sin contexto previo.

---

## 📋 Índice

1. [Resumen del Proyecto](#1-resumen-del-proyecto)
2. [Arquitectura General](#2-arquitectura-general)
3. [Módulo 1: Healer (✅ Completo)](#3-módulo-1-healer--completo)
4. [Módulo 2: Targeting (⚠️ Beta)](#4-módulo-2-targeting-️-beta)
5. [Módulo 3: Looter (⚠️ Beta)](#5-módulo-3-looter-️-beta)
6. [Módulo 4: Cavebot (❌ No funcional)](#6-módulo-4-cavebot--no-funcional)
7. [Sistema de Captura (OBS WebSocket)](#7-sistema-de-captura-obs-websocket)
8. [Sistema de Input (PostMessage)](#8-sistema-de-input-postmessage)
9. [Calibración Automática](#9-calibración-automática)
10. [Base de Datos del Juego (game_data)](#10-base-de-datos-del-juego-game_data)
11. [GUI (customtkinter)](#11-gui-customtkinter)
12. [Dispatcher — Coordinación de Módulos](#12-dispatcher--coordinación-de-módulos)
13. [Proyectos Analizados (TibiaAuto12, OldBot, TibiaData API)](#13-proyectos-analizados)
14. [Problemas Conocidos y Bugs](#14-problemas-conocidos-y-bugs)
15. [Qué Falta por Hacer](#15-qué-falta-por-hacer)
16. [Configuración y Parámetros](#16-configuración-y-parámetros)
17. [Cómo Ejecutar el Proyecto](#17-cómo-ejecutar-el-proyecto)

---

## 1. Resumen del Proyecto

Bot de automatización para el juego Tibia que opera **100% externamente** — no inyecta código, no modifica memoria, no usa hooks. Lee píxeles de la pantalla vía OBS y envía inputs vía Win32 PostMessage.

### Módulos

| Módulo | Estado | Descripción |
|--------|--------|-------------|
| **Healer** | ✅ Completo | Auto-curación HP/Mana por detección de barras de colores |
| **Targeting** | ⚠️ Beta | Auto-ataque a monstruos detectados en battle list |
| **Looter** | ⚠️ Beta | Auto-loot clickeando SQMs alrededor del jugador |
| **Cavebot** | ❌ Pendiente | Navegación por waypoints en minimapa — no funciona bien |

### Stack Tecnológico

| Tecnología | Versión | Uso |
|-----------|---------|-----|
| Python | 3.13.2 | Lenguaje principal |
| OpenCV (cv2) | 4.8+ | Template matching, detección HSV, procesamiento de imagen |
| obsws-python | 1.7+ | Conexión con OBS WebSocket para captura de frames |
| pywin32 | 306+ | PostMessage para envío de teclas y clicks sin foco |
| customtkinter | 5.2+ | GUI moderna con tema oscuro |
| numpy | 1.24+ | Arrays para manipulación de imágenes |
| Pillow | 10.0+ | Conversión de imágenes para mostrar en GUI |
| keyboard | 0.13.5+ | Hotkeys globales (F9/F10) |

### Entorno de Desarrollo

- **OS:** Windows 10/11
- **venv:** `c:\Users\felip\Documents\GitHub\bot_ia_claude\.venv\`
- **Tibia Config:** Classic Controls, Loot: Left
- **OBS:** Resolución de captura 1366×705 (mismo que cliente Tibia)
- **Escala OBS→Tibia:** 1.000:1.000 (sin escalado)

---

## 2. Arquitectura General

### Flujo de Datos

```
┌─────────────┐    WebSocket     ┌─────────────────┐
│  OBS Studio │◄────────────────►│  screen_capture  │
│  (Game      │  GetSource       │     .py          │
│   Capture)  │  Screenshot      │  → numpy BGR     │
└─────────────┘  (base64 PNG)    └────────┬─────────┘
                                          │ frame (numpy array)
                                          ▼
                                 ┌─────────────────┐
                                 │   dispatcher.py  │
                                 │  Orden de ejecución:
                                 │  1. Healer       │
                                 │  2. Targeting     │
                                 │  3. Cavebot       │
                                 │  4. Looter        │
                                 └────────┬─────────┘
                                          │
                    ┌─────────┬───────────┼───────────┬─────────┐
                    ▼         ▼           ▼           ▼         │
              ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Healer   │ │Targeting │ │ Cavebot  │ │ Looter   │
              │bar_detect│ │battle_   │ │cavebot_  │ │looter_   │
              │  or.py   │ │list_     │ │engine.py │ │engine.py │
              │          │ │reader.py │ │          │ │          │
              └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
                   │            │            │            │
                   ▼            ▼            ▼            ▼
              ┌─────────────────────────────────────────────────┐
              │           PostMessage (Win32 API)               │
              │   key_sender.py + mouse_click_sender.py         │
              │   → Teclas F1-F12 | Clicks izq/der              │
              └─────────────────────┬───────────────────────────┘
                                    ▼
                              ┌──────────┐
                              │  Tibia   │
                              │  Client  │
                              └──────────┘
```

### Archivos Principales y Responsabilidades

| Archivo | Líneas | Responsabilidad |
|---------|--------|----------------|
| `gui.py` | ~2130 | Interfaz gráfica con 7 pestañas, log routing, controles |
| `healer_bot.py` | ~698 | Orquestador principal: wiring de módulos, loop del healer, calibración |
| `dispatcher.py` | ~222 | Distribuye frames a módulos en orden: healer→targeting→cavebot→looter |
| `screen_capture.py` | ~150 | Conexión OBS WebSocket, captura de screenshots en base64→numpy |
| `screen_calibrator.py` | ~362 | Template matching para localizar regiones del juego |
| `bar_detector.py` | ~250 | Detección HSV de barras HP/Mana |
| `key_sender.py` | ~120 | PostMessage WM_KEYDOWN/WM_KEYUP para teclas |
| `mouse_click_sender.py` | ~205 | PostMessage para clicks izquierdo/derecho con coordenadas |
| `targeting/targeting_engine.py` | ~315 | Motor de targeting (scan battle list + click ataque) |
| `targeting/battle_list_reader.py` | ~276 | Template matching de nombres de monstruos en battle list |
| `looter/looter_engine.py` | ~260 | Looteo brute-force de 9 SQMs (estilo TibiaAuto12) |
| `cavebot/cavebot_engine.py` | ~343 | Navegación por waypoints en minimapa (no funcional) |
| `config.py` | ~411 | Persistencia JSON con defaults y validación |
| `game_data/loader.py` | ~234 | Singleton que carga monsters.json, items.json, npcs.json |
| `window_finder.py` | ~80 | EnumWindows para buscar ventanas de Tibia |
| `logger.py` | ~100 | BotLogger con callbacks para GUI |

---

## 3. Módulo 1: Healer (✅ Completo)

### Qué hace
Detecta los porcentajes de HP y Mana del personaje analizando los colores de las barras en la parte superior de la pantalla, y envía teclas de curación cuando bajan de umbrales configurados.

### Cómo funciona

1. **Captura:** `screen_capture.py` pide un screenshot a OBS vía WebSocket
2. **Detección:** `bar_detector.py` convierte la franja superior (10%) a HSV y busca colores:
   - **HP:** Verde (100-60%), Amarillo (60-30%), Rojo (30-0%)
   - **Mana:** Azul (100-0%)
3. **Decisión:** `healer_bot.py` compara porcentajes con umbrales configurados
4. **Acción:** `key_sender.py` envía la tecla del spell más fuerte necesario

### Detección de Barras — Detalles

```python
# Rangos HSV para cada color de barra
VERDE:    H=[35,90]   S=[60,255]  V=[60,255]   # HP alto
AMARILLO: H=[20,35]   S=[100,255] V=[100,255]  # HP medio
ROJO_1:   H=[0,10]    S=[100,255] V=[100,255]  # HP bajo
ROJO_2:   H=[170,180] S=[100,255] V=[100,255]  # HP bajo (wraparound)
AZUL:     H=[95,135]  S=[60,255]  V=[60,255]   # Mana
```

El proceso:
1. Recorta el 10% superior de la imagen (`scan_height_ratio = 0.10`)
2. Convierte BGR→HSV con `cv2.cvtColor()`
3. Crea máscara con `cv2.inRange()` para cada rango
4. Cuenta píxeles blancos por fila → toma la fila con más
5. Busca el bloque continuo más largo de píxeles
6. Porcentaje = `bloque / (ancho × 0.43)` donde 0.43 es el ratio de la barra completa

### Auto-calibración
El bot puede ejecutar `auto_calibrate()` que escanea la franja superior buscando filas con >30 píxeles de cada color para detectar la posición Y exacta de las barras.

### Parámetros clave

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `cooldown_seconds` | 1.2 | Tiempo mínimo entre curaciones |
| `check_interval_seconds` | 0.25 | Intervalo entre checks (4/seg) |
| `scan_height_ratio` | 0.10 | Porción superior a escanear |
| `expected_full_width_ratio` | 0.43 | Ancho de barra completa vs imagen |
| `gap_tolerance` | 3 px | Tolerancia a gaps en detección |

### Niveles de curación (configurables)

| Nivel | Threshold | Key | Descripción |
|-------|-----------|-----|-------------|
| 1 | 70% | F1 | Spell leve (Exura) |
| 2 | 50% | F2 | Spell medio (Exura Gran) |
| 3 | 30% | F6 | Spell fuerte (Exura Vita) |
| Mana | 30% | F3 | Mana potion |

---

## 4. Módulo 2: Targeting (⚠️ Beta)

### Qué hace
Detecta monstruos en la battle list del juego usando template matching y hace click para atacarlos automáticamente.

### Archivos

- `targeting/targeting_engine.py` — Motor principal
- `targeting/battle_list_reader.py` — Lector de battle list por template matching

### Cómo funciona

1. **Calibración:** `screen_calibrator.py` encuentra la región de la battle list buscando el template `BattleList.png`
2. **Escaneo:** `battle_list_reader.py` busca templates PNG de nombres de monstruos en la región de la battle list
3. **Selección de target:** Prioriza monstruos de la `priority_list`, luego `attack_list`
4. **Ataque:** Click izquierdo en la posición del nombre del monstruo en la battle list
5. **Kill detection:** Compara el conteo de monstruos entre frames — si bajó, es una kill

### Template Matching — Detalles

```python
# Ubicación de templates
images/Targets/Names/      # PNGs con nombres de monstruos (ej: Rotworm.png)
images/MonstersAttack/     # Templates de estado de ataque
```

El `BattleListReader` usa `cv2.matchTemplate()` con `TM_CCOEFF_NORMED`:
- `name_precision = 0.80` para nombres
- `attack_precision = 0.80` para estado de ataque
- Escanea la `battle_region` (detectada por calibración)
- Retorna `List[CreatureEntry]` con `name`, `screen_x`, `screen_y`

### Detección de kills

```python
# En targeting_engine.py process_frame():
creatures = self.battle_reader.read(frame)
current_count = len(creatures)

if self._prev_count > current_count:
    kills = self._prev_count - current_count
    self.monsters_killed += kills
    # El wrapper _targeting_with_loot notifica al looter
```

### Detección de target perdido

Si el target actual desaparece de la battle list por `max_target_missing` frames consecutivos (default: 8, ~1.6s), se suelta y busca otro target.

### Wrapper _targeting_with_loot (healer_bot.py)

```python
def _targeting_with_loot(frame):
    prev_kills = self.targeting_engine.monsters_killed
    original_process(frame)                              # Ejecuta targeting
    new_kills = self.targeting_engine.monsters_killed
    if new_kills > prev_kills:
        # Notificar al looter de cada kill
        for _ in range(new_kills - prev_kills):
            self.looter_engine.notify_kill(name, px, py)
```

Este wrapper envuelve `targeting_engine.process_frame()` y detecta si hubo kills comparando `monsters_killed` antes y después. Si hubo, notifica al looter con `notify_kill()`.

### Parámetros clave

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `attack_delay` | 0.4s | Delay mínimo entre ataques a nuevos targets |
| `re_attack_delay` | 2.0s | Delay entre re-ataques al mismo target |
| `search_interval` | 0.2s | Intervalo entre escaneos de battle list |
| `max_target_missing` | 8 frames | Frames antes de soltar target perdido |
| `target_switch_cooldown` | 0.5s | Cooldown entre cambios de target |
| `name_precision` | 0.80 | Umbral de confianza para template matching |

### Problemas conocidos

1. **Pierde kills:** Si el template matching es inconsistente (detecta 3, luego 2, luego 3), puede registrar kills fantasma o perder reales
2. **Re-ataque lento:** `re_attack_delay = 2.0s` puede ser demasiado largo en combate rápido
3. **Sin combos:** No tiene rotación de spells de ataque — solo hace click para atacar
4. **Battle list naming:** Los templates son PNGs de los nombres exactos como aparecen en la battle list de Tibia. Si el nombre tiene un formato distinto, no lo detecta
5. **`is_attacking()` invertido:** `battle_list_reader.is_attacking(frame)` retorna `True` cuando NO está atacando (confuso naming heredado)

---

## 5. Módulo 3: Looter (⚠️ Beta)

### Qué hace
Después de cada kill, clickea los 9 SQMs alrededor del jugador para recoger loot automáticamente. Estilo brute-force como TibiaAuto12.

### Archivo
- `looter/looter_engine.py` — Motor de looteo v4

### Cómo funciona (estilo TibiaAuto12)

1. **Kill detectada:** El wrapper `_targeting_with_loot` detecta que `monsters_killed` subió
2. **Notificación:** Llama `looter_engine.notify_kill(name, px, py)` → incrementa `_pending_loots`
3. **Siguiente frame:** `process_frame()` ve `pending_loots > 0` → ejecuta `_take_loot()`
4. **Brute-force:** Click rápido en los 9 SQMs alrededor del jugador:
   ```
   SW(0) → S(1) → SE(2) → W(3) → Centro(4) → E(5) → NW(6) → N(7) → NE(8)
   ```
5. **Timing:** ~0.05s entre clicks = ~0.5s total para los 9 SQMs
6. **Sin pausa:** El targeting NO se pausa durante el looteo

### Coordinación con Targeting

**Antes (v3, tenía problemas):**
- `_is_looting` flag pausaba targeting → targeting dejaba de atacar
- Delay de 0.20s entre clicks → 1.6s de loot → 8+ frames sin targeting
- `loot_cooldown = 1.5s` → esperaba mucho entre looteos
- Threshold bloqueaba looteo durante combate activo

**Ahora (v4, estilo TibiaAuto12):**
- NO se pausa el targeting nunca
- Delay de 0.05s entre clicks → ~0.5s total
- `loot_cooldown = 0.3s`
- `always_loot = True` por defecto → lootea inmediatamente tras cada kill
- Incluye SQM central (9 total, no 8) como TibiaAuto12

### SQMs — Cómo se calculan

Los 9 SQMs se calculan en `screen_calibrator.py`:
```python
# Orden: SW(0), S(1), SE(2), W(3), Center(4), E(5), NW(6), N(7), NE(8)
# Se calculan desde player_center ± sqm_size
# sqm_size se detecta por calibración (depende de resolución)
# En 1366x705: sqm_size ≈ 32px
```

El centro del game window se detecta por template matching de los bordes del área de juego.

### Parámetros clave

| Parámetro | Default v4 | Antes (v3) | Descripción |
|-----------|-----------|-----------|-------------|
| `loot_delay` | 0.05s | 0.20s | Delay entre clicks en SQMs |
| `loot_cooldown` | 0.3s | 1.5s | Cooldown entre sesiones de loot |
| `max_loot_sqms` | 9 | 8 | SQMs a clickear (9=incluye centro) |
| `always_loot` | True | False | Ignorar threshold, lootear siempre |
| `loot_threshold` | 0 | 2 | Máx criaturas para lootear (si always_loot=False) |
| `loot_method` | left_click | left_click | Método de click (left/right según config Tibia) |

### Problemas conocidos

1. **Clickea todo:** No sabe dónde cayó el cadáver — clickea los 9 SQMs siempre
2. **Sin filtro de items:** No distingue qué items lootear
3. **Sin lectura de loot channel:** No verifica si el loot fue recogido
4. **Drop no funcional:** Placeholder para tirar items no deseados
5. **Kill detection dependiente:** Si el targeting pierde una kill, el looter no lootea

---

## 6. Módulo 4: Cavebot (❌ No funcional)

### Qué debería hacer
Navegar automáticamente por waypoints haciendo click en marcas del minimapa.

### Archivo
- `cavebot/cavebot_engine.py` — Motor de navegación (~343 líneas)

### Cómo está diseñado

1. **Waypoints:** Lista de marcas (`Waypoint`) con tipo: walk, rope, shovel, stand
2. **Rutas:** Se cargan/guardan como JSON
3. **Navegación:** Template matching de marcas en el minimapa → click para caminar
4. **Llegada:** Si la marca está en la zona central del minimapa (±`arrival_zone` px), se considera que llegó
5. **Cíclico:** Al llegar al último waypoint, vuelve al primero

### Templates de marcas

```
images/MapSettings/          # Templates de marcas del minimapa
  ├── CheckMark.png          # Marca de verificación
  ├── CrossMark.png          # X
  ├── position.png           # Posición actual (excluida)
  └── MapSettings.png        # Header del minimapa (excluida)
```

### Por qué NO funciona

1. **Template matching del minimapa es inconsistente:** Las marcas del minimapa son muy pequeñas (~6-10 px) y el template matching falla con frecuencia
2. **No detecta posición actual:** No sabe dónde está el jugador exactamente
3. **No maneja obstáculos:** Si hay un muro o tile bloqueado entre el jugador y la marca, sigue clickeando sin avanzar
4. **Detección de "llegada" poco confiable:** La zona central del minimapa (±48px) a veces detecta falsos positivos
5. **Sin pathfinding:** No calcula rutas alternativas cuando el camino está bloqueado

### Estructura del Waypoint

```python
class Waypoint:
    mark: str        # Nombre de la marca (ej: "CheckMark")
    wp_type: str     # "walk", "rope", "shovel", "stand"
    status: bool     # True si es el waypoint actual
```

### Parámetros

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `walk_mode` | "click" | Modo de movimiento (click o arrow keys) |
| `nav_interval` | 1.0s | Intervalo entre acciones de navegación |
| `arrival_zone` | 48 px | Distancia para considerar "llegó" |
| `mark_precision` | 0.70 | Umbral de template matching |
| `cyclic` | True | Repetir ruta al terminar |

### Qué falta para que funcione

1. **OCR de coordenadas:** Leer la posición X,Y,Z del minimapa (hay un template `position.png` pero no se usa)
2. **Mejor detección de marcas:** Usar multi-scale template matching o feature matching
3. **Pathfinding básico:** Detectar si está atascado y tomar acciones (walk aleatorio, usar otro waypoint)
4. **Editor visual de rutas:** Actualmente las rutas son JSON manuales
5. **Integración con targeting:** Pausar navegación cuando hay monstruos y reanudar al limpiar

---

## 7. Sistema de Captura (OBS WebSocket)

### Por qué OBS y no captura directa

| Método | Problema |
|--------|---------|
| `mss` (screenshot) | Captura pantalla visible — si otra ventana tapa Tibia, captura eso |
| `BitBlt` / `PrintWindow` | OBS usa GPU, ventana devuelve frames negros |
| ✅ **OBS WebSocket** | Lee del pipeline interno de OBS — funciona SIEMPRE |

### Conexión

```python
# screen_capture.py
import obsws_python as obs

client = obs.ReqClient(host='localhost', port=4455, password='')
response = client.get_source_screenshot(
    name='Game Capture',
    img_format='png',
    width=1366,       # Resolución de captura
    height=705
)
# response.image_data = "data:image/png;base64,iVBOR..."
```

### Decodificación

```python
b64_str = image_data.split(",", 1)[1]      # Quitar prefijo
img_bytes = base64.b64decode(b64_str)       # base64 → bytes
img_array = np.frombuffer(img_bytes, np.uint8)  # bytes → numpy
frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)  # PNG → BGR
# frame.shape = (705, 1366, 3) dtype=uint8
```

### Resolución y Escala

- OBS captura a **1366×705** (resolución del cliente Tibia)
- El cliente Tibia es **1366×705** (Classic Client)
- Escala = **1.000:1.000** (sin escalado necesario)
- Si las resoluciones difieren, se aplica scaling en `_scaled_left_click()` y `_scaled_right_click()`

---

## 8. Sistema de Input (PostMessage)

### Teclas (key_sender.py)

Envía pulsaciones de tecla directamente al HWND de Tibia sin necesidad de foco:

```python
# Flujo:
# 1. MapVirtualKey(VK, 0) → scan_code
# 2. lParam_down = (scan_code << 16) | 1
# 3. PostMessage(hwnd, WM_KEYDOWN, vk, lParam_down)
# 4. Sleep(50ms)
# 5. PostMessage(hwnd, WM_KEYUP, vk, lParam_up)
```

Teclas soportadas: F1-F12, 0-9

### Clicks (mouse_click_sender.py)

Envía clicks del mouse a coordenadas específicas del cliente:

```python
# Flujo:
# 1. lParam = (y << 16) | (x & 0xFFFF)
# 2. PostMessage(hwnd, WM_MOUSEMOVE, 0, lParam)          # Mover cursor
# 3. Sleep(15ms)
# 4. PostMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)  # Click down
# 5. Sleep(15ms)
# 6. PostMessage(hwnd, WM_LBUTTONUP, 0, lParam)          # Click up
```

**Clicks soportados:**
- Click izquierdo (`left_click`)
- Click derecho (`right_click`)
- Con modificadores: Shift+click, Ctrl+click
- Coordenadas en espacio de cliente (relativas a la ventana Tibia)

### Escala de Coordenadas

Cuando OBS y Tibia tienen resoluciones diferentes:
```python
# healer_bot.py
def _scaled_left_click(self, x, y):
    cx = int(x * self._scale_x)
    cy = int(y * self._scale_y)
    self.mouse_sender.left_click(cx, cy)
```

---

## 9. Calibración Automática

### Archivo: `screen_calibrator.py` (~362 líneas)

### Qué calibra

1. **Battle List:** Busca template `BattleList.png` → detecta esquina superior izquierda → calcula región
2. **Minimapa:** Busca template `MapSettings.png` → detecta header del minimapa → calcula región
3. **Game Window:** Busca bordes izquierdo/derecho/inferior del área de juego
4. **Player Center:** Centro del game window = centro de la pantalla de juego
5. **9 SQMs:** Calcula las 9 posiciones alrededor del jugador basándose en `sqm_size`

### Orden de SQMs

```
NW(6)  N(7)   NE(8)
W(3)   C(4)   E(5)
SW(0)  S(1)   SE(2)
```

El SQM size se calcula dividiendo el ancho del game window entre la cantidad de SQMs visibles (15 horizontales, 11 verticales en Tibia Classic).

### Templates usados

```
images/
  ├── BattleList.png       # Header "Battle List"
  ├── MapSettings.png      # Icono de settings del minimapa
  ├── GameBorderLeft.png   # Borde izquierdo del game area
  ├── GameBorderRight.png  # Borde derecho
  └── GameBorderBottom.png # Borde inferior
```

---

## 10. Base de Datos del Juego (game_data)

### Archivos

- `game_data/monsters.json` — Información de monstruos (HP, exp, loot, etc.)
- `game_data/items.json` — Información de items del juego
- `game_data/npcs.json` — Información de NPCs
- `game_data/loader.py` — Singleton `GameData` para acceso rápido

### Fuente de datos

Los JSON fueron generados consultando la **TibiaData API** (https://api.tibiadata.com/v4/) y almacenados localmente para acceso offline rápido.

### TibiaData API

API pública que provee datos del juego Tibia en formato JSON:

```
GET https://api.tibiadata.com/v4/creature/{name}
GET https://api.tibiadata.com/v4/creatures
GET https://api.tibiadata.com/v4/item/{name}
```

Se usó para:
- Obtener lista completa de monstruos con HP, exp, loot drops
- Información de items (peso, valor NPC, atributos)
- Datos de NPCs para potencial auto-venta

### Uso en el bot

```python
from game_data.loader import GameData

gd = GameData.instance()
gd.load()

# Buscar info de un monstruo
monster = gd.get_monster("Rotworm")
# → {"name": "Rotworm", "hitpoints": 65, "experience": 40, "loot": [...]}

# Buscar items valiosos para filtrar loot
item = gd.get_item("Gold Coin")
```

Actualmente la base de datos está cargada pero **no se usa activamente** en el looter ni targeting — está preparada para futuras features como filtro de loot por valor.

---

## 11. GUI (customtkinter)

### Archivo: `gui.py` (~2130 líneas)

### 7 Pestañas

| # | Pestaña | Contenido |
|---|---------|-----------|
| 1 | 🪟 Ventanas | Conexión OBS, selección de fuente, selección de ventana Tibia |
| 2 | ⚙️ Configuración | Umbrales HP/Mana, teclas de curación, cooldowns |
| 3 | 📋 Log | Log principal del bot (filtrado — no muestra logs de módulos) |
| 4 | 🎯 Targeting | Config de targeting + log separado de targeting |
| 5 | 💰 Looter | Config de looter + log separado de looter |
| 6 | 🗺️ Cavebot | Config de cavebot + log separado de cavebot |
| 7 | 📊 Status | Vista de estado general |

### Sistema de Logging

El log se separó en Phase 15:
- **Log principal** (pestaña 3): Mensajes generales, conexión, healer
- **Log de Targeting** (pestaña 4): Solo mensajes `[Targeting]`
- **Log de Looter** (pestaña 5): Solo mensajes `[Looter]`
- **Log de Cavebot** (pestaña 6): Solo mensajes `[Cavebot]`

Implementación:
```python
def _route_module_log(self, msg):
    """Rutea logs de módulos a sus textboxes correspondientes."""
    if "[Targeting]" in msg:
        self._append_to_textbox(self.targeting_log_textbox, msg)
        return True  # fue ruteado → no mostrar en log principal
    if "[Looter]" in msg:
        self._append_to_textbox(self.looter_log_textbox, msg)
        return True
    if "[Cavebot]" in msg:
        self._append_to_textbox(self.cavebot_log_textbox, msg)
        return True
    return False  # no fue ruteado → mostrar en log principal

def _drain_log_queue(self):
    """Drena la cola de logs cada 50ms."""
    while not self._log_queue.empty():
        msg = self._log_queue.get_nowait()
        if not self._route_module_log(msg):
            self._append_log(msg)  # Al log principal
    self.after(50, self._drain_log_queue)
```

### Thread Safety

La GUI usa `customtkinter` que corre en el hilo principal. Los módulos corren en hilos de dispatcher. Para comunicación segura:
- Log usa `queue.Queue` (thread-safe) + `after(50ms, drain)` en hilo GUI
- Callbacks de módulos se ejecutan en el hilo de dispatcher (no en GUI)
- Actualizaciones de GUI van siempre por la cola

---

## 12. Dispatcher — Coordinación de Módulos

### Archivo: `dispatcher.py` (~222 líneas)

### Orden de ejecución

Cada ciclo del dispatcher:
1. Captura un frame de OBS
2. Ejecuta **healer** (siempre primero — curación es prioridad)
3. Ejecuta **targeting** (a través del wrapper `_targeting_with_loot`)
4. Ejecuta **cavebot**
5. Ejecuta **looter**

Todos procesan el **mismo frame** en secuencia.

### Wiring en healer_bot.py _init_modules()

```python
def _init_modules(self):
    # Targeting
    self.targeting_engine.set_click_callback(self._scaled_left_click)
    self.targeting_engine.set_key_callback(self.key_sender.send_key)
    self.targeting_engine.set_log_callback(lambda msg: self.log.info(msg))
    self.targeting_engine.configure(self.config.targeting)

    # Looter
    self.looter_engine.set_right_click_callback(self._scaled_right_click)
    self.looter_engine.set_left_click_callback(self._scaled_left_click)
    self.looter_engine.set_log_callback(lambda msg: self.log.info(msg))
    self.looter_engine.set_targeting_engine(self.targeting_engine)
    self.looter_engine.configure(self.config.looter)

    # Cavebot
    self.cavebot_engine.set_click_callback(self._scaled_left_click)
    self.cavebot_engine.set_key_callback(self.key_sender.send_key)
    self.cavebot_engine.set_log_callback(lambda msg: self.log.info(msg))

    # Cross-references
    self.targeting_engine.set_looter_engine(self.looter_engine)

    # Wrapper targeting→looter (kill notification)
    # ... _targeting_with_loot wraps process_frame

    # Registrar en dispatcher
    self.dispatcher.register_handler("targeting", self._targeting_with_loot)
    self.dispatcher.register_handler("cavebot", self.cavebot_engine.process_frame)
    self.dispatcher.register_handler("looter", self.looter_engine.process_frame)
```

---

## 13. Proyectos Analizados

### TibiaAuto12 (Python — Análisis completo)

**Repo:** `https://github.com/Flaviol-git/TibiaAuto12`
**Qué es:** Bot de Tibia escrito en Python con PyAutoGUI + OpenCV.

**Cómo funciona su loot:**
- Archivo: `engine/CaveBot/CaveBotController.py`
- Kill detection: Cuenta monstruos en battle list, si el conteo bajó → `TakeLoot()`
- Lootea INMEDIATAMENTE entre kills, NO después de todos
- Click en ALL 9 SQMs incluyendo centro (brute-force)
- NO delay entre clicks de loot
- NO pausa combate durante loot
- Usa right click hardcoded
- La carpeta `DeadCorpses/` existe pero NUNCA fue implementada

**Cómo funciona su targeting:**
- Lee battle list por template matching (PNGs de nombres)
- Usa `VerifyAttacking.png` para saber si ya está atacando
- Click en el nombre del monstruo para atacar
- Prioridad por orden en la lista

**Cómo funciona su cavebot:**
- Navegación por marcas en el minimapa (template matching)
- Waypoints con tipos: walk, rope, shovel, stand
- Detección de "llegada" por cercanía de la marca al centro del minimapa

**Lecciones aprendidas de TibiaAuto12:**
1. El loot debe ser RÁPIDO e INMEDIATO — no esperar
2. NO pausar combate durante loot
3. 9 SQMs brute-force funciona bien — no es necesario detectar dónde cayó el cadáver
4. Template matching para battle list es suficiente

### OldBot (AutoHotkey — Referencia)

**Qué es:** Bot de Tibia en AHK con muchas funcionalidades.
**Repo local:** `c:\Users\felip\Documents\GitHub\oldbot-main\`

**Lo que usamos de referencia:**
- Patrón de PostMessage para envío de clicks (MOUSEMOVE → BUTTONDOWN → BUTTONUP)
- Método de lParam para coordenadas: `(y << 16) | (x & 0xFFFF)`
- El concepto de "Click around" para lootear SQMs adyacentes

### TibiaData API

**URL:** `https://api.tibiadata.com/v4/`
**Qué es:** API REST pública con datos del juego Tibia.

**Endpoints usados:**
```
GET /v4/creatures               → Lista de todos los monstruos
GET /v4/creature/{name}         → Detalle de un monstruo (HP, exp, loot)
GET /v4/boostablebosses         → Jefes con boost
```

**Datos extraídos:**
- `game_data/monsters.json` — Todos los monstruos con HP, experiencia, loot drops
- `game_data/items.json` — Items del juego
- `game_data/npcs.json` — NPCs

---

## 14. Problemas Conocidos y Bugs

### Targeting

| Problema | Severidad | Descripción |
|----------|-----------|-------------|
| Pierde kills | Media | Kill detection por conteo de battle list es inconsistente |
| `is_attacking()` invertido | Baja | Naming confuso: retorna True cuando NO está atacando |
| Sin combos de spell | Baja | Solo hace click para atacar, no usa spells ofensivos |
| Re-attack lento | Media | `re_attack_delay = 2.0s` puede ser demasiado largo |

### Looter

| Problema | Severidad | Descripción |
|----------|-----------|-------------|
| Clickea todo | Baja | Brute-force 9 SQMs — no sabe dónde cayó el cadáver |
| Sin filtro items | Media | No distingue qué items recoger |
| Sin confirmación | Baja | No lee canal de loot para verificar |
| Drop no funcional | Baja | Placeholder — requiere detección de inventario |

### Cavebot

| Problema | Severidad | Descripción |
|----------|-----------|-------------|
| No funciona | Crítica | Template matching de minimapa falla frecuentemente |
| Sin posición | Crítica | No detecta coordenadas actuales del jugador |
| Sin pathfinding | Alta | No maneja obstáculos ni caminos bloqueados |

### GUI

| Problema | Severidad | Descripción |
|----------|-----------|-------------|
| `_ctk_image` warning | Cosmética | Hack para evitar garbage collection de CTkLabel |

### General

| Problema | Severidad | Descripción |
|----------|-----------|-------------|
| Solo Windows | N/A | Depende de Win32 PostMessage — no portable |
| Requiere OBS | N/A | Necesita OBS Studio corriendo + WebSocket habilitado |

---

## 15. Qué Falta por Hacer

### Prioridad Alta

1. **Mejorar kill detection** — El conteo de battle list es inconsistente. Posibles mejoras:
   - Leer el server log/loot channel para confirmar kills
   - Comparar nombres específicos en vez de solo conteo
   - Usar frame diff para detectar animaciones de muerte

2. **Mejorar re-attack** — A veces no re-ataca cuando pierde target. Reducir `re_attack_delay` o implementar lógica más agresiva.

3. **Hacer funcionar el cavebot** — Necesita:
   - OCR de coordenadas del minimapa
   - Mejor detección de marcas (multi-scale matching)
   - Detección de atascamiento + recovery
   - Editor visual de rutas

### Prioridad Media

4. **Combos de spells** — Rotación de spells ofensivos (exori, exori gran, etc.) con cooldowns individuales

5. **Filtro de loot** — Usar `game_data/items.json` para filtrar items por valor

6. **Lectura del server log** — OCR o template matching en la ventana de chat para:
   - Confirmar kills y loot
   - Detectar PK
   - Detectar nivel up

### Prioridad Baja

7. **Drop de items** — Tirar items no deseados al piso
8. **Anti-AFK** — Movimientos aleatorios periódicos
9. **Estadísticas** — XP/hora, loot value, kills/hora
10. **Profiles** — Configuración por personaje
11. **Dashboard web** — Monitoreo remoto

---

## 16. Configuración y Parámetros

### Archivo: `config.json` (autogenerado)

### Estructura completa

```json
{
  "tibia_window_title": "Tibia - Pastero codode bronze",
  "obs_websocket": {
    "host": "localhost",
    "port": 4455,
    "password": "",
    "source_name": "Game Capture"
  },
  "heal_levels": [
    {"threshold": 0.70, "key": "F1", "description": "Exura"},
    {"threshold": 0.50, "key": "F2", "description": "Exura Gran"},
    {"threshold": 0.30, "key": "F6", "description": "Exura Vita"}
  ],
  "mana_heal": {
    "enabled": false,
    "threshold": 0.30,
    "key": "F3"
  },
  "cooldown_seconds": 1.2,
  "check_interval_seconds": 0.25,
  "hotkey_toggle": "F9",
  "hotkey_exit": "F10",
  "targeting": {
    "enabled": false,
    "auto_attack": true,
    "attack_mode": "offensive",
    "attack_delay": 0.4,
    "re_attack_delay": 2.0,
    "attack_list": ["Rotworm", "Carrion Worm"],
    "ignore_list": [],
    "priority_list": []
  },
  "looter": {
    "loot_method": "left_click",
    "loot_delay": 0.05,
    "loot_cooldown": 0.3,
    "max_loot_sqms": 9,
    "always_loot": true,
    "loot_threshold": 0,
    "drop_enabled": false,
    "drop_items": ""
  },
  "cavebot": {
    "enabled": false,
    "cyclic": true,
    "walk_mode": "click",
    "nav_interval": 1.0,
    "current_route": ""
  }
}
```

---

## 17. Cómo Ejecutar el Proyecto

### Pre-requisitos

1. **Python 3.10+** instalado
2. **OBS Studio 28+** con WebSocket habilitado (puerto 4455)
3. **Tibia** corriendo con captura de juego en OBS

### Pasos

```powershell
# 1. Ir al directorio del proyecto
cd C:\Users\felip\Documents\GitHub\bot_ia_claude

# 2. Activar entorno virtual
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias (si es primera vez)
pip install -r requirements.txt

# 4. Ejecutar
python main.py
```

O simplemente doble click en `iniciar.bat`.

### Configuración inicial

1. Conectar a OBS (pestaña Ventanas → Conectar)
2. Seleccionar fuente de captura (Game Capture)
3. Seleccionar ventana de Tibia
4. Presionar "Calibrar" para detectar regiones
5. Configurar spells en pestaña Configuración
6. Configurar monstruos en pestaña Targeting
7. Presionar F9 para activar

### Orden recomendado de activación

1. ✅ Healer (siempre activo)
2. ⚠️ Targeting (configurar monstruos primero)
3. ⚠️ Looter (activar después de targeting)
4. ❌ Cavebot (no activar — no funciona bien)

---

*Documento generado el 5 de marzo de 2026. Para actualizaciones, revisar el historial de commits.*
