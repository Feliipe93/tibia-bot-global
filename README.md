# ⚔️ Tibia Auto Bot (Healer + Targeting + Looter)

> Bot multi-módulo para Tibia con detección por visión computarizada (OpenCV), captura vía OBS WebSocket y envío de teclas/clicks en segundo plano.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Windows](https://img.shields.io/badge/OS-Windows_10/11-0078D6?logo=windows)
![OBS](https://img.shields.io/badge/OBS-28+-purple?logo=obsstudio)
![Status](https://img.shields.io/badge/Módulo-Healer_✅-success)
![Status](https://img.shields.io/badge/Módulo-Targeting_⚠️_Beta-yellow)
![Status](https://img.shields.io/badge/Módulo-Looter_⚠️_Beta-yellow)
![Status](https://img.shields.io/badge/Módulo-Cavebot_❌_Pendiente-red)

---

## 📋 Tabla de Contenidos

- [Cómo Funciona](#-cómo-funciona)
- [Flujo Completo del Sistema](#-flujo-completo-del-sistema)
- [Arquitectura de Archivos](#-arquitectura-de-archivos)
- [Detección de Barras (Visión Computarizada)](#-detección-de-barras-visión-computarizada)
- [Captura vía OBS WebSocket](#-captura-vía-obs-websocket)
- [Envío de Teclas (PostMessage)](#-envío-de-teclas-postmessage)
- [Parámetros y Configuración](#️-parámetros-y-configuración)
- [Requisitos del Sistema](#-requisitos-del-sistema)
- [Instalación](#-instalación)
- [Uso Paso a Paso](#-uso-paso-a-paso)
- [Roadmap / TODO](#-roadmap--todo)

---

## 🧠 Cómo Funciona

El bot **NO** inyecta código ni modifica la memoria del cliente de Tibia.
Opera 100% externamente leyendo píxeles de la pantalla y enviando pulsaciones de teclas.

```
┌──────────────────────────────────────────────────────────────────┐
│                      FLUJO SIMPLIFICADO                         │
│                                                                  │
│   OBS Studio ──WebSocket──▶ Bot Python ──PostMessage──▶ Tibia   │
│   (captura)     (frames)    (analiza)    (teclas F1-F12)        │
└──────────────────────────────────────────────────────────────────┘
```

**Principio:** OBS Studio captura el juego internamente. El bot pide frames a OBS vía WebSocket, analiza los colores de las barras de HP/Mana con OpenCV, y si detecta HP o Mana bajo, envía la tecla de curación configurada directamente a la ventana de Tibia.

---

## 🔄 Flujo Completo del Sistema

```
┌─────────────┐    WebSocket     ┌─────────────────┐
│  OBS Studio │◄────────────────►│  screen_capture  │
│             │  GetSource       │     .py          │
│  Fuente:    │  Screenshot      │                  │
│  Game       │  (base64 PNG)    │  Decodifica:     │
│  Capture    │                  │  base64 → bytes  │
│             │                  │  → numpy BGR     │
└─────────────┘                  └────────┬─────────┘
                                          │ numpy array (BGR)
                                          ▼
                                 ┌─────────────────┐
                                 │  bar_detector    │
                                 │     .py          │
                                 │                  │
                                 │  1. Recorta 10%  │
                                 │     superior     │
                                 │  2. BGR → HSV    │
                                 │  3. Máscaras de  │
                                 │     color        │
                                 │  4. Cuenta px    │
                                 │     por fila     │
                                 │  5. % = ancho_px │
                                 │     / ancho_max  │
                                 └────────┬─────────┘
                                          │ (hp%, mana%)
                                          ▼
                                 ┌─────────────────┐
                                 │  healer_bot      │
                                 │     .py          │
                                 │                  │
                                 │  Si hp < umbral: │
                                 │   → elegir spell │
                                 │  Si mana < umbr: │
                                 │   → mana potion  │
                                 │  Respetar CD     │
                                 └────────┬─────────┘
                                          │ (key_name, hwnd)
                                          ▼
                                 ┌─────────────────┐     PostMessage     ┌──────────┐
                                 │  key_sender      │──────────────────►│  Tibia   │
                                 │     .py          │  WM_KEYDOWN +     │  Client  │
                                 │                  │  WM_KEYUP         │          │
                                 │  VK_F1..F12      │  (no necesita     │  HWND:   │
                                 │  VK_0..9         │   estar en foco)  │  0x1234  │
                                 └─────────────────┘                    └──────────┘
```

### Paso a paso detallado

| # | Paso | Componente | Detalle |
|---|------|-----------|---------|
| 1 | **Captura** | `screen_capture.py` | Llama `GetSourceScreenshot` vía OBS WebSocket → recibe PNG en base64 |
| 2 | **Decodificación** | `screen_capture.py` | `base64.b64decode()` → `np.frombuffer()` → `cv2.imdecode()` → array BGR |
| 3 | **Recorte** | `bar_detector.py` | Toma solo el **10% superior** de la imagen (donde están las barras) |
| 4 | **Conversión HSV** | `bar_detector.py` | `cv2.cvtColor(region, COLOR_BGR2HSV)` para trabajar con colores |
| 5 | **Máscaras de color** | `bar_detector.py` | `cv2.inRange()` para cada rango HSV (verde, amarillo, rojo, azul) |
| 6 | **Cálculo de %** | `bar_detector.py` | `píxeles_de_color / ancho_esperado_barra_completa` × 100 |
| 7 | **Decisión** | `healer_bot.py` | Compara % con umbrales configurados → elige el spell más fuerte necesario |
| 8 | **Cooldown** | `healer_bot.py` | Espera `cooldown_seconds` entre curaciones para no spamear |
| 9 | **Envío** | `key_sender.py` | `PostMessage(hwnd, WM_KEYDOWN, VK_code, lparam)` al HWND de Tibia |
| 10 | **Loop** | `healer_bot.py` | Repite cada `check_interval_seconds` (default: 0.25s = 4 checks/seg) |

---

## 📁 Arquitectura de Archivos

```
bot_ia_claude/
│
├── main.py                  # 🚀 Punto de entrada — verifica deps y lanza GUI
├── gui.py                   # 🖥️ Interfaz gráfica 7 pestañas (customtkinter)
├── healer_bot.py            # 🧠 Orquestador principal (healer + wiring módulos)
├── dispatcher.py            # 📡 Distribuye frames a healer→targeting→cavebot→looter
├── screen_capture.py        # 📸 Captura de frames vía OBS WebSocket
├── screen_calibrator.py     # 🎯 Calibración automática de regiones (template matching)
├── bar_detector.py          # 🔍 Detección de barras HP/Mana con OpenCV HSV
├── key_sender.py            # ⌨️ Envío de teclas via PostMessage (Win32)
├── mouse_click_sender.py    # 🖱️ Envío de clicks via PostMessage (Win32)
├── window_finder.py         # 🪟 Búsqueda de ventanas por título (EnumWindows)
├── config.py                # ⚙️ Configuración con persistencia JSON
├── logger.py                # 📝 Sistema de logging con callbacks para GUI
├── debug_visual.py          # 🔬 Generación de imágenes de debug
│
├── targeting/               # ⚔️ Módulo de auto-targeting
│   ├── targeting_engine.py  #   Motor de ataque (battle list reader + click)
│   └── battle_list_reader.py#   Template matching de nombres en battle list
│
├── looter/                  # 💰 Módulo de auto-loot
│   └── looter_engine.py     #   Looteo brute-force 9 SQMs (estilo TibiaAuto12)
│
├── cavebot/                 # 🗺️ Módulo de navegación (WIP)
│   └── cavebot_engine.py    #   Waypoints + template matching minimapa
│
├── game_data/               # 📊 Base de datos del juego
│   ├── loader.py            #   Cargador singleton de datos
│   ├── monsters.json        #   Info de monstruos (HP, exp, loot, etc.)
│   ├── items.json           #   Info de items del juego
│   └── npcs.json            #   Info de NPCs
│
├── images/                  # 🖼️ Templates para calibración y detección
│   ├── Targets/Names/       #   PNGs de nombres de monstruos
│   ├── MonstersAttack/      #   Templates de estado de ataque
│   └── MapSettings/         #   Marcas del minimapa (cavebot)
│
├── config.json              # 💾 Configuración del usuario (autogenerado)
├── requirements.txt         # 📦 Dependencias Python
├── iniciar.bat              # 🏃 Launcher para Windows (doble clic)
├── skills.md                # 📓 Documentación técnica detallada del proyecto
├── README.md                # 📖 Este archivo
│
├── logs/                    # 📂 Archivos de log por sesión
├── debug/                   # 📂 Capturas de debug con análisis visual
└── .venv/                   # 📂 Entorno virtual Python
```

---

## 🔍 Detección de Barras (Visión Computarizada)

### Espacio de Color HSV

El bot convierte la imagen de **BGR** (como la entrega OpenCV) a **HSV** (Hue, Saturation, Value) porque HSV separa el "color" (Hue) del "brillo" (Value), haciendo la detección más robusta ante cambios de iluminación.

```
BGR (Blue-Green-Red)  ──cv2.cvtColor──▶  HSV (Hue-Saturation-Value)
                                          H: 0-180 (color)
                                          S: 0-255 (saturación)
                                          V: 0-255 (brillo)
```

### Rangos HSV por Color de Barra

| Barra | Color | HP Range | H min | H max | S min | S max | V min | V max |
|-------|-------|----------|-------|-------|-------|-------|-------|-------|
| **HP** | 🟢 Verde | 100% → 60% | 35 | 90 | 60 | 255 | 60 | 255 |
| **HP** | 🟡 Amarillo | 60% → 30% | 20 | 35 | 100 | 255 | 100 | 255 |
| **HP** | 🔴 Rojo (rango 1) | 30% → 0% | 0 | 10 | 100 | 255 | 100 | 255 |
| **HP** | 🔴 Rojo (rango 2) | 30% → 0% | 170 | 180 | 100 | 255 | 100 | 255 |
| **Mana** | 🔵 Azul | 100% → 0% | 95 | 135 | 60 | 255 | 60 | 255 |

> ⚠️ El rojo tiene **dos rangos** porque en HSV el rojo está en ambos extremos del círculo de Hue (0° y 360°/180°).

### Proceso de Detección Píxel por Píxel

```
Imagen capturada (ej: 800×600 px)
│
├─▶ Recortar: solo filas 0 a 60 (10% superior = scan_height_ratio)
│
├─▶ Convertir a HSV
│
├─▶ Crear máscara HP:  mask_verde OR mask_amarillo OR mask_rojo1 OR mask_rojo2
├─▶ Crear máscara Mana: mask_azul
│
├─▶ Para cada máscara:
│   ├─▶ Contar píxeles blancos (color detectado) por fila
│   ├─▶ Tomar la fila con MÁS píxeles = fila de la barra
│   ├─▶ Encontrar el bloque continuo más largo de píxeles
│   └─▶ Porcentaje = bloque_largo / (ancho_imagen × 0.43)
│
└─▶ Resultado: (hp_pct: 0.0-1.0, mp_pct: 0.0-1.0)
```

### Parámetros de Coordenadas

| Parámetro | Valor Default | Descripción |
|-----------|--------------|-------------|
| `scan_height_ratio` | `0.10` (10%) | Porción superior de la imagen donde buscar barras |
| `expected_full_width_ratio` | `0.43` (43%) | Ancho esperado de la barra completa respecto al ancho de imagen |
| `gap_tolerance` | `3` px | Tolerancia a gaps entre píxeles para considerar bloque continuo |
| Mínimo píxeles para detección | `8` px | Si la fila tiene menos de 8 px de color, se ignora |
| Mínimo columnas para barra | `5` px | Si hay menos de 5 columnas con color, no es una barra |

### Auto-Calibración

El bot puede ejecutar `auto_calibrate()` que escanea la franja superior fila por fila buscando:
- **Fila HP:** primera fila con >30 píxeles verde/amarillo/rojo
- **Fila MP:** primera fila con >30 píxeles azules
- Guarda la posición Y exacta de cada barra para futuras detecciones

---

## 📸 Captura vía OBS WebSocket

### ¿Por qué OBS WebSocket y no captura de pantalla directa?

| Método | Problema |
|--------|---------|
| ❌ `mss` (screenshot) | Captura píxeles visibles del monitor. Si Tibia tapa el proyector OBS → captura Tibia en vez de OBS |
| ❌ `BitBlt` / `PrintWindow` | OBS usa aceleración GPU, la ventana devuelve frames negros o desactualizados |
| ✅ **OBS WebSocket** | Lee frames directamente del **pipeline interno de renderizado** de OBS. Funciona siempre, sin importar qué ventana está encima |

### Protocolo de Comunicación

```
Bot (Python)                              OBS Studio
    │                                         │
    ├──── WebSocket Connect ─────────────────►│  Puerto 4455 (default)
    │     ws://localhost:4455                  │
    │                                         │
    ├──── GetVersion ────────────────────────►│
    │◄─── { obs_version, ws_version } ────────┤
    │                                         │
    ├──── GetInputList ──────────────────────►│
    │◄─── [ {inputName, inputKind}, ... ] ────┤  Lista de fuentes
    │                                         │
    ├──── GetSourceScreenshot ───────────────►│  ← Se llama cada 0.25s
    │     { name: "Game Capture",             │
    │       img_format: "png" }               │
    │◄─── { image_data:                  ─────┤
    │       "data:image/png;base64,iVBOR..." } │  Frame actual en base64
    │                                         │
    └─── (decodifica base64 → PNG → numpy) ──┘
```

### Flujo de Decodificación

```python
# 1. OBS responde con base64
image_data = "data:image/png;base64,iVBORw0KGgo..."

# 2. Extraer solo base64 (quitar prefijo data:image/png;base64,)
b64_str = image_data.split(",", 1)[1]

# 3. Decodificar base64 → bytes PNG
img_bytes = base64.b64decode(b64_str)

# 4. Bytes → numpy array
img_array = np.frombuffer(img_bytes, dtype=np.uint8)

# 5. Decodificar PNG → imagen BGR (OpenCV)
img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
# Resultado: numpy.ndarray shape=(height, width, 3) dtype=uint8
```

### Tipos de Fuente OBS Compatibles

El bot **filtra automáticamente** las fuentes de audio y solo muestra fuentes que pueden generar screenshots:

| Tipo OBS | inputKind | ¿Compatible? | Icono en GUI |
|----------|-----------|:---:|-------|
| Captura de juego | `game_capture` | ✅ | 🎮 Juego |
| Captura de ventana | `window_capture` | ✅ | 🪟 Ventana |
| Captura de monitor | `monitor_capture` | ✅ | 🖥️ Monitor |
| Cámara / Webcam | `dshow_input` | ✅ | 📹 Cámara |
| Fuente multimedia | `ffmpeg_source` | ✅ | 🎞️ Media |
| Navegador | `browser_source` | ✅ | 🌐 Navegador |
| Escena completa | *(scene)* | ✅ | 🎬 Escena |
| Audio del escritorio | `wasapi_output_capture` | ❌ Filtrado | — |
| Micrófono | `wasapi_input_capture` | ❌ Filtrado | — |

> Las fuentes de audio provocan error **702: "Failed to render screenshot"** y son filtradas automáticamente del dropdown.

---

## ⌨️ Envío de Teclas (PostMessage)

El bot usa la API Win32 `PostMessage` para enviar teclas **directamente al HWND** de Tibia, sin necesidad de que la ventana esté en foco/primer plano.

```
PostMessage(hwnd, WM_KEYDOWN, VK_F1, lParam)
    │         │       │         │       │
    │         │       │         │       └── scan_code << 16 | 1
    │         │       │         └── Virtual Key Code (0x70 = F1)
    │         │       └── Mensaje de tecla presionada (0x0100)
    │         └── Handle de la ventana de Tibia (ej: 0x000A1B2C)
    └── Función Win32 API
```

### Teclas Disponibles

| Tecla | VK Code | Uso típico |
|-------|---------|-----------|
| F1 - F12 | `0x70` - `0x7B` | Hotkeys de spells y pociones |
| 0 - 9 | `0x30` - `0x39` | Hotbar secundaria |

### Flujo de Envío

```
1. MapVirtualKey(VK, 0)  → obtener scan_code de hardware
2. Construir lParam:
   - DOWN: (scan_code << 16) | 1
   - UP:   (scan_code << 16) | 0xC0000001
3. PostMessage(hwnd, WM_KEYDOWN, vk, lParam_down)
4. Sleep(50ms)   ← simula duración de pulsación humana
5. PostMessage(hwnd, WM_KEYUP, vk, lParam_up)
```

---

## ⚙️ Parámetros y Configuración

El archivo `config.json` se genera automáticamente al primer inicio con estos valores:

### Conexión OBS WebSocket

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `obs_websocket.host` | `"localhost"` | IP del servidor OBS |
| `obs_websocket.port` | `4455` | Puerto WebSocket de OBS |
| `obs_websocket.password` | `""` | Contraseña (vacío si no tiene) |
| `obs_websocket.source_name` | `""` | Nombre de la fuente a capturar |

### Niveles de Curación (HP)

| Campo | Default | Descripción |
|-------|---------|-------------|
| `heal_levels[0].threshold` | `0.70` (70%) | HP bajo el cual usar spell leve |
| `heal_levels[0].key` | `"F1"` | Tecla del spell leve (ej: Exura) |
| `heal_levels[1].threshold` | `0.50` (50%) | HP para spell medio |
| `heal_levels[1].key` | `"F2"` | Tecla del spell medio (ej: Exura Gran) |
| `heal_levels[2].threshold` | `0.30` (30%) | HP para spell fuerte |
| `heal_levels[2].key` | `"F6"` | Tecla del spell fuerte (ej: Exura Vita) |

> El bot evalúa **de menor a mayor** umbral: si HP está al 25%, dispara el umbral 30% (Exura Vita), no el de 70%.

### Curación de Mana

| Campo | Default | Descripción |
|-------|---------|-------------|
| `mana_heal.enabled` | `false` | Activar curación de mana |
| `mana_heal.threshold` | `0.30` (30%) | Mana por debajo del cual usar poción |
| `mana_heal.key` | `"F3"` | Tecla de la mana potion |

### Tiempos

| Campo | Default | Descripción |
|-------|---------|-------------|
| `cooldown_seconds` | `1.2` | Tiempo mínimo entre curaciones (evita spam) |
| `check_interval_seconds` | `0.25` | Intervalo entre checks (4 por segundo) |

### Hotkeys Globales

| Campo | Default | Descripción |
|-------|---------|-------------|
| `hotkey_toggle` | `"F9"` | Activar / Desactivar el bot |
| `hotkey_exit` | `"F10"` | Cerrar el bot completamente |

### Detección de Barras

| Campo | Default | Descripción |
|-------|---------|-------------|
| `bar_detection.expected_full_width_ratio` | `0.43` | Ratio del ancho de la barra llena vs ancho total de imagen |
| `bar_detection.scan_height_ratio` | `0.10` | Porción superior de la imagen a escanear (10%) |

### Debug

| Campo | Default | Descripción |
|-------|---------|-------------|
| `debug_save_images` | `true` | Guardar imágenes de debug en `/debug` |
| `debug_every_n_cycles` | `40` | Guardar imagen cada N ciclos (~10 segundos) |

---

## 💻 Requisitos del Sistema

### Sistema Operativo

| OS | Soportado | Notas |
|----|:---------:|-------|
| **Windows 10** | ✅ | Requiere OBS 28+ con WebSocket |
| **Windows 11** | ✅ | Totalmente compatible |
| **Linux** | ❌ | `PostMessage` y `pywin32` son exclusivos de Windows |
| **macOS** | ❌ | `PostMessage` y `pywin32` son exclusivos de Windows |

> **Nota:** La captura vía OBS WebSocket es cross-platform en teoría, pero el envío de teclas depende de la API Win32 (`PostMessage`, `EnumWindows`, `GetWindowRect`), que solo existe en Windows.

### Software Requerido

| Software | Versión Mínima | Para qué |
|----------|:--------------:|----------|
| **Python** | 3.10+ | Ejecutar el bot |
| **OBS Studio** | 28+ | Captura del juego + servidor WebSocket |
| **OBS WebSocket** | 5.0+ | Protocolo de comunicación (incluido en OBS 28+) |
| **Tibia Client** | Cualquiera | El juego |

### Dependencias Python

| Paquete | Versión | Propósito |
|---------|---------|-----------|
| `obsws-python` | ≥ 1.7.0 | SDK Python para OBS WebSocket v5 |
| `opencv-python` | ≥ 4.8.0 | Visión computarizada (HSV, máscaras, decodificación) |
| `numpy` | ≥ 1.24.0 | Arrays numéricos para manipulación de imágenes |
| `pywin32` | ≥ 306 | Win32 API (PostMessage, EnumWindows, GetWindowRect) |
| `keyboard` | ≥ 0.13.5 | Hotkeys globales (F9 toggle, F10 salir) |
| `customtkinter` | ≥ 5.2.0 | GUI moderna con tema oscuro |
| `Pillow` | ≥ 10.0.0 | Conversión de imágenes para mostrar en GUI |

---

## 🚀 Instalación

### Opción 1: Manual (recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/bot_ia_claude.git
cd bot_ia_claude

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
.venv\Scripts\activate          # Windows CMD
.venv\Scripts\Activate.ps1      # Windows PowerShell

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Ejecutar
python main.py
```

### Opción 2: Doble clic

Ejecuta **`iniciar.bat`** — automáticamente busca Python, crea el entorno virtual si no existe, instala dependencias si faltan, y lanza el bot.

---

## 🎮 Uso Paso a Paso

### 1. Configurar OBS Studio

1. Abrir **OBS Studio**
2. Crear una fuente de **"Captura de juego"** o **"Captura de ventana"** apuntando a Tibia
3. Ir a **Herramientas → Configuración del servidor WebSocket**
4. ✅ Habilitar servidor WebSocket
5. Anotar el **puerto** (default: `4455`) y la **contraseña** (si la configuraste)

### 2. Conectar el Bot

1. Ejecutar `python main.py` o hacer doble clic en `iniciar.bat`
2. Ir a la pestaña **🪟 Ventanas**
3. Ingresar **Host** (`localhost`), **Puerto** (`4455`) y **Contraseña**
4. Clic en **🔗 Conectar**
5. En el dropdown **"Fuente OBS"** seleccionar tu captura de Tibia (busca `🎮 Juego | ...`)
6. En **"Cliente Tibia"** seleccionar la ventana de Tibia (para envío de teclas)

### 3. Configurar Spells

1. Ir a la pestaña **⚙️ Configuración**
2. Ajustar los umbrales de HP y las teclas correspondientes a tus spells
3. Activar curación de mana si la necesitas

### 4. Activar

- Presionar **F9** para activar/desactivar el bot
- Presionar **F10** para cerrar

### 5. Verificar

- Usa **📸 Tomar captura de prueba** para confirmar que la captura funciona
- Usa **🔬 Mostrar análisis de barras** para ver las máscaras de detección HSV
- Revisa la carpeta `/debug` para imágenes con anotaciones de HP/Mana

---

## 🗺️ Roadmap / TODO

### ✅ v1.0 — Healer (Completado)

- [x] Detección de HP/Mana por visión computarizada (HSV)
- [x] Múltiples niveles de curación (3 umbrales configurables)
- [x] Curación de mana con toggle independiente
- [x] Captura vía OBS WebSocket (funciona sin foco de ventana)
- [x] Envío de teclas vía PostMessage (funciona sin foco)
- [x] Envío de clicks via PostMessage (izquierdo/derecho, con modificadores)
- [x] Auto-filtrado de fuentes de audio en el selector de OBS
- [x] GUI completa con customtkinter (tema oscuro, 7 pestañas)
- [x] Sistema de configuración persistente (JSON)
- [x] Hotkeys globales (F9 toggle, F10 salir)
- [x] Sistema de logging con niveles y panel en GUI
- [x] Debug visual con imágenes anotadas
- [x] Auto-calibración de posición de barras
- [x] Calibración automática de regiones (battle list, minimapa, game window, SQMs)
- [x] Cooldown configurable entre curaciones
- [x] Dispatcher multi-módulo (healer→targeting→cavebot→looter)
- [x] Base de datos de monstruos/items/NPCs (`game_data/`)
- [x] Launcher `.bat` para Windows

### ⚠️ v1.1 — Auto-Targeting (Beta — funcional, falta mejorar)

- [x] Detección de monstruos en battle list por template matching (OpenCV)
- [x] Auto-attack al monstruo detectado (click en battle list)
- [x] Prioridad de targets configurable por nombre
- [x] Detección de kills por cambio de conteo en battle list
- [x] Detección de target perdido (desaparece N frames → busca otro)
- [x] Re-attack delay configurable para evitar spam de clicks
- [x] Log separado en pestaña propia de la GUI
- [ ] **FALTA MEJORAR:** Combos de spells de ataque (exori, exori gran, etc.)
- [ ] **FALTA MEJORAR:** Conteo de monstruos más robusto (a veces pierde kills)
- [ ] **FALTA MEJORAR:** A veces no re-ataca al perder target
- [ ] **FALTA MEJORAR:** AOE vs single target automático

### ⚠️ v1.2 — Auto-Loot (Beta — funcional, falta mejorar)

- [x] Looteo brute-force de 9 SQMs adyacentes (estilo TibiaAuto12)
- [x] Click rápido en cada SQM (~0.05s entre clicks = ~0.5s total)
- [x] Lootea inmediatamente tras cada kill (no espera a matar todo)
- [x] NO pausa el targeting durante el looteo
- [x] Soporta left_click y right_click según config de Tibia
- [x] Modo "always_loot" (recomendado) y modo "threshold" opcional
- [x] Log separado en pestaña propia de la GUI
- [ ] **FALTA MEJORAR:** Detección de dónde cayó el cadáver (ahora clickea todos los SQMs)
- [ ] **FALTA MEJORAR:** Lectura del canal de loot para confirmar si se loteó
- [ ] **FALTA MEJORAR:** Filtro de items por nombre (solo lootear items valiosos)
- [ ] **FALTA MEJORAR:** Drop de items no deseados al piso
- [ ] **FALTA MEJORAR:** Detección de backpack lleno

### ❌ v2.0 — Cavebot (No funcional aún)

- [x] Estructura base: waypoints, rutas cíclicas, template matching de marcas
- [x] Carga/guarda rutas desde JSON
- [x] Templates de marcas del minimapa cargados
- [ ] **NO FUNCIONA:** Navegación no es confiable (template matching del minimapa falla)
- [ ] **PENDIENTE:** Editor visual de waypoints
- [ ] **PENDIENTE:** Detección de posición actual por minimapa
- [ ] **PENDIENTE:** Pausa al detectar otros jugadores
- [ ] **PENDIENTE:** Reconocimiento de tiles bloqueados

### 🔜 v3.0 — Sistema Completo (Futuro)

- [ ] Anti-AFK — Movimientos aleatorios periódicos
- [ ] Mana Trainer — Usar spell de training cuando mana > X%
- [ ] Alertas — Notificación por Discord cuando HP crítico o PK detectado
- [ ] Reconexión automática
- [ ] Estadísticas (XP/hora, curaciones, loot)
- [ ] Profiles por personaje
- [ ] Multi-cliente
- [ ] Dashboard web (Flask/FastAPI)

### 💡 Ideas Futuras

- [ ] Detección por OCR del HP numérico exacto
- [ ] Integración con TibiaData API (info de monstruos y drops en tiempo real)
- [ ] Mapa interactivo con editor de rutas drag & drop
- [ ] Machine Learning para detección más robusta
- [ ] Lectura del canal de loot/server log para confirmar kills y loot
- [ ] Soporte para Tibia en Linux vía Wine + xdotool

---

## ⚠️ Aviso Legal

Este bot es un **proyecto educativo** de visión computarizada y automatización con Python.
El uso de bots en Tibia puede violar los Términos de Servicio de CipSoft.
**Úsalo bajo tu propia responsabilidad.**

---

## 📄 Licencia

Este proyecto es de código abierto con fines educativos.

---

*Hecho con ❤️, Python, OpenCV, OBS WebSocket y muchas tazas de café.*
