# Sistema de Condiciones - Auto Haste, Paralyze, Poison, y más

## 🎯 Overview

Sistema avanzado de detección automática de condiciones de estado para Tibia, basado en el sistema del OldBot pero completamente expandido y modernizado para soportar todas las condiciones posibles del juego.

## 🚀 Funcionalidades

### ✅ Condiciones Soportadas (15 totales)

#### 🎯 Condiciones Principales
- **🏃 Haste**: Detecta ausencia de lentitud y activa hechizos de velocidad
- **⚡ Paralyze**: Detecta parálisis del personaje y activa hechizos de curación  
- **☠️ Poison**: Detecta envenenamiento y activa hechizos antídotos

#### 🔥 Condiciones de Daño Over Time (DOT)
- **🔥 Burning**: Daño por fuego (fire damage)
- **🍺 Drunk**: Personaje ebrio, afecta movimiento y combate
- **🩸 Bleeding**: Personaje sangrando continuamente
- **� Drowning**: Personaje ahogándose en agua
- **👻 Curse**: Personaje maldito, afecta estadísticas
- **⚡ Electrified**: Personaje electrificado, daño reducido
- **❄️ Freezing**: Personaje congelado, movimiento muy lento
- **🍽 Hunger**: Personaje con hambre, regeneración lenta
- **🛡️ Mana Shield**: Escudo mágico activo
- **💪 Physical**: Personaje con daño físico reducido
- **💨 Speed**: Personaje con velocidad aumentada

### �🔧 Características Principales

#### 🎯 Detección por Template Matching
- Usa imágenes PNG templates para cada condición
- Umbral de sensibilidad ajustable (0.5 - 1.0)
- Calibración automática de la barra de condiciones
- Detección robusta con múltiples colores específicos

#### 🔄 Calibración Dinámica
- **Auto-adaptativa**: Se recalibra automáticamente cada 20 frames
- **Sensible a cambios**: Detecta movimientos de paneles y recoloca
- **Fallback agresivo**: Si no detecta, busca en toda la región inferior

#### ⚙️ Configuración Individual
- **Activación/Desactivación** individual por condición
- **Hotkey personalizable** por condición (F1-F12)
- **Sensibilidad ajustable** por condición
- **Cooldown individual** por condición para evitar spam
- **Interfaz dinámica** que se genera automáticamente

#### 📊 Estadísticas y Estado
- Contador de activaciones por condición
- Estado de calibración en tiempo real
- Información de debug detallada

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                GUI (customtkinter)              │
├─────────────────────────────────────────────────────────────────────────┤
│  Configuración │  HealerBot (main loop)    │
│  - Pestaña     │  - Captura de frames          │
│  - Hotkeys      │  - Detección HP/Mana         │
│  - Umbral      │  - Procesamiento de condiciones │
│  - ConditionEngine (motor)             │
│  - Lógica de activación                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 📁 Archivos Clave

### Core del Sistema
- **`condition_detector.py`**: Detección de barras y condiciones (15 condiciones)
- **`condition_engine.py`**: Motor de procesamiento y activación
- **`config.py`**: Gestión de configuración (extendido)
- **Imágenes de Templates**: 15 archivos PNG para cada condición

### Integración con Módulos Existentes
- **`healer_bot.py`**: Integrado en el loop principal
- **`gui.py`**: Pestaña de configuración profesional dinámica
- **`config.json`**: Persistencia automática de todas las configuraciones

## 🎮 Flujo de Operación

1. **Calibración Inicial**:
   - Busca automáticamente la barra de condiciones (debajo de mana)
   - Detecta límites horizontales usando análisis de proyección
   - Guarda posición para futuras detecciones

2. **Detección Continua**:
   - Extrae región de la barra de condiciones calibrada
   - Aplica template matching para cada condición activa
   - Usa umbrales configurables y colores específicos

3. **Activación Inteligente**:
   - Respeta cooldowns individuales por condición
   - Envía hotkeys correspondientes via PostMessage
   - Logging detallado de cada activación

4. **Recalibración Automática**:
   - Se recalibra si la detección falla consistentemente
   - Se adapta a cambios en la UI del juego
   - Detección de cambios drásticos en posición de barras

## 🎛️ Configuración

### Estructura en config.json
```json
{
  "conditions": {
    "enabled": false,
    "debug_mode": false,
    "global_cooldown": 0.5,
    "haste": {
      "enabled": false,
      "hotkey": "F3",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "paralyze": {
      "enabled": false,
      "hotkey": "F4", 
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "poison": {
      "enabled": false,
      "hotkey": "F5",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "burning": {
      "enabled": false,
      "hotkey": "F6",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "drunk": {
      "enabled": false,
      "hotkey": "F7",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "bleeding": {
      "enabled": false,
      "hotkey": "F8",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "drowning": {
      "enabled": false,
      "hotkey": "F9",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "curse": {
      "enabled": false,
      "hotkey": "F10",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "electrified": {
      "enabled": false,
      "hotkey": "F11",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "freezing": {
      "enabled": false,
      "hotkey": "F12",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "hunger": {
      "enabled": false,
      "hotkey": "F13",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "manashield": {
      "enabled": false,
      "hotkey": "F14",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "physical": {
      "enabled": false,
      "hotkey": "F15",
      "threshold": 0.7,
      "cooldown": 1.0
    },
    "speed": {
      "enabled": false,
      "hotkey": "F16",
      "threshold": 0.7,
      "cooldown": 1.0
    }
  }
}
```

### Controles Principales
- **Activador principal**: Enable/Disable del sistema completo
- **Botón de recalibración**: Forzar calibración manual de barras

### Configuración Dinámica
El sistema genera automáticamente controles para todas las 15 condiciones configuradas:

#### 🎛️ Controles por Condición
Cada condición tiene:
- **Icono único** representativo (🏃, ⚡, ☠️, 🔥, 🍺, 🩸, 💧, 💧, 👻, 🛡️, ❄️, 💨, 🛡️, 💪, 💨)
- **Nombre destacado** (HASTE, PARALYZE, etc.)
- **Checkbox de activación**: Activar/desactivar condición específica
- **Selector de hotkey**: Menú desplegable con F1-F12 + vacío
- **Control de sensibilidad**: Slider numérico (0.5 - 1.0)
- **Color de indicador**: Único para cada tipo de condición

#### 🎨 Colores de Indicadores
- **🟢 Haste**: Verde - Ausencia de lentitud
- **🔴 Paralyze**: Rojo - Parálisis
- **🔵 Poison**: Azul - Envenenamiento
- **🔥 Burning**: Naranja - Daño por fuego
- **🍺 Drunk**: Amarillo - Personaje ebrio
- **🩸 Bleeding**: Rojo - Sangrando
- **💧 Drowning**: Azul claro - Ahogándose
- **👻 Curse**: Gris - Maldición
- **⚡ Electrified**: Blanco - Personaje electrificado
- **❄️ Freezing**: Celeste claro - Personaje congelado
- **🍽 Hunger**: Amarillo oscuro - Hambre
- **🛡️ Mana Shield**: Rojo - Escudo mágico activo
- **💪 Physical**: Rojo - Daño físico reducido
- **💨 Speed**: Azul - Velocidad aumentada

## 🎯 Ventajas Técnicas

### ✨ Precisión Mejorada
- Template matching con OpenCV (máxima precisión)
- Calibración automática continuamente
- Detección robusta ante cambios de UI
- Colores diferenciados para cada condición

### 🔄 Adaptabilidad
- Se adapta a diferentes clientes de Tibia
- Compatible con cambios en paneles del juego
- Recalibración dinámica sin intervención manual
- Interfaz dinámica que se genera automáticamente

### ⚡ Rendimiento
- Procesamiento eficiente con threading
- Uso óptimo de recursos (CPU mínima)
- Sin impacto en el rendimiento del juego

### 🛡️ Confiabilidad
- Manejo robusto de errores
- Fallback automático ante fallos
- Logging detallado para diagnóstico

## 🚀 Uso Recomendado

1. **Configurar Hotkeys**: Asignar hechizos apropiados a cada condición
2. **Ajustar Sensibilidad**: Comenzar con 0.7 y ajustar según necesidad
3. **Probar en Juego**: Verificar detección con condiciones reales
4. **Monitorear Logs**: Revisar activaciones y falsos positivos
5. **Recalibrar si es Necesario**: Usar botón de recalibración manual
6. **Usar Overlay**: Verificar detecciones en Screen View con el overlay "Conditions"

## 🔧 Integración

El sistema está completamente integrado en la arquitectura existente:

- **HealerBot**: Procesa condiciones en cada frame
- **GUI**: Configuración profesional con pestaña dedicada
- **Config**: Persistencia automática de todas las configuraciones
- **Screen View**: Overlay para visualizar barras detectadas
- **Templates**: 15 imágenes PNG importadas del OldBot

## 📝 Notas de Desarrollo

- Basado en el sistema probado del OldBot pero completamente modernizado
- Arquitectura extensible para futuras condiciones adicionales
- Compatible con sistema de calibración dinámica existente
- Interfaz profesional y fácil de usar
- Colores diferenciados para mejor visualización

---

**Sistema creado y completamente expandido para soportar las 15 condiciones más comunes de Tibia con la máxima calidad y flexibilidad.**
