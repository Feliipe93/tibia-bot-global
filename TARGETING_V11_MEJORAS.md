# TARGETING V11 - MEJORAS IMPLEMENTADAS

## Resumen de Mejoras

He implementado un sistema de targeting avanzado (v11) con las siguientes mejoras solicitadas:

### 1. ✅ Perfiles Individuales por Criatura

El modo de ataque ahora es independiente por cada criatura en lugar de general.

**Configuración en `creature_profiles`:**
```json
"creature_profiles": {
    "Amazon": {
        "attack_mode": "offensive",  // offensive, balanced, defensive
        "chase_mode": "chase",      // chase, stand, auto
        "priority": 100,             // Mayor prioridad = ataca primero
        "is_ranged": true,           // true = ranged, false = melee
        "flees_at_hp": 0.0          // Huye al % de HP (0.0 = no huye)
    }
}
```

### 2. ✅ Detección de HP para Cambio Chase/Stand

El sistema ahora detecta el HP de la criatura y cambia automáticamente entre chase/stand.

**Nuevos parámetros:**
```json
{
    "hp_threshold_chase": 0.3,  // Cambia a chase cuando HP ≤ 30%
    "hp_threshold_stand": 0.8   // Cambia a stand cuando HP ≥ 80%
}
```

### 3. ✅ Sistema de Spells por Número de Criaturas

Spells diferentes según el número de criaturas cercanas.

**Configuración:**
```json
{
    "spells_by_count": {
        "1": ["f1"],                    // 1 criatura
        "2": ["f2", "f1"],              // 2 criaturas  
        "3": ["f3", "f2", "f1"],        // 3+ criaturas
        "default": ["f1"]                 // Por defecto
    },
    "spell_cooldown": 2.0                // Cooldown entre spells
}
```

### 4. ✅ Detección de Muerte Mejorada

Corregido el problema donde dejaba de atacar y volvía a atacar la misma criatura.

**Mejoras implementadas:**
- Detección por HP = 0% del target actual
- Estado actualizado a "searching" después de kill
- Detección combinada: conteo battle list + HP target

### 5. ✅ Lectura de HP y Nombre desde Game Screen

Nuevo módulo `CreatureHPDetector` que lee:
- Nombre de la criatura seleccionada
- Porcentaje de HP (OCR + análisis visual)
- Bordes de selección para confirmar target

## Componentes Nuevos

### CreatureHPDetector (`targeting/creature_hp_detector.py`)
- Detecta criaturas seleccionadas (bordes de ataque)
- Lee HP mediante OCR y análisis de barra
- Cache de HP con tendencia (decreasing/stable)
- Auto-calibración de regiones

### SpellManager (`targeting/spell_manager.py`)
- Gestiona spells por número de criaturas
- Cooldowns individuales por spell
- Integración con sistema de targeting

## Configuración Completa de Ejemplo

```json
"targeting": {
    "enabled": true,
    "auto_attack": true,
    "chase_monsters": true,
    "attack_list": ["Rotworm", "Amazon", "Rat"],
    "creature_profiles": {
        "Amazon": {
            "chase_mode": "chase",
            "attack_mode": "offensive",
            "priority": 100,
            "is_ranged": true,
            "flees_at_hp": 0.0,
            "hp_threshold_chase": 0.3,
            "hp_threshold_stand": 0.8,
            "spells_by_count": {
                "1": ["f1"],
                "2": ["f2", "f1"],
                "3": ["f3", "f2", "f1"],
                "default": ["f1"]
            },
            "spell_cooldown": 2.0
        },
        "Rotworm": {
            "chase_mode": "chase",
            "attack_mode": "offensive", 
            "priority": 90,
            "is_ranged": false,
            "flees_at_hp": 0.0,
            "hp_threshold_chase": 0.0,
            "hp_threshold_stand": 0.0,
            "spells_by_count": {
                "1": ["exori"],
                "2": ["exori gran"],
                "3": ["exori mas"],
                "default": ["exori"]
            },
            "spell_cooldown": 1.5
        }
    },
    "chase_key": "f8",    // Hotkey para chase mode
    "stand_key": "f7"     // Hotkey para stand mode
}
```

## Flujo de Mejorado

1. **Detección**: Lee battle list y detecta criaturas
2. **Selección**: Elige target según prioridad y distancia
3. **Ataque**: Click en target + aplica chase/stand del perfil
4. **HP Tracking**: Monitorea HP del target actual
5. **Spells**: Lanza spells según número de criaturas
6. **Chase/Stand Dinámico**: Cambia modo según umbrales de HP
7. **Kill Detection**: Detecta muerte por conteo + HP=0%
8. **Limpieza**: Resetea target y busca siguiente

## Problemas Corregidos

### ❌ Antes:
- Umbral de detección muy alto (0.8)
- Auto-ataque desactivado
- Chase mode desactivado
- Detección de muerte poco fiable
- Modo de ataque global (no por criatura)

### ✅ Ahora:
- Umbral optimizado (0.35)
- Auto-ataque activado
- Sistema de HP y chase/stand inteligente
- Spells por número de criaturas
- Perfiles individuales completos
- Detección de muerte mejorada

## Uso

1. **Configurar**: Editar `config.json` con los perfiles deseados
2. **Calibrar**: Presionar botón "Calibrar" en la GUI
3. **Activar**: Activar targeting desde la pestaña Targeting
4. **Monitorear**: Revisar logs para ver actividad

El sistema ahora es completamente granular e inteligente, adaptándose a cada tipo de criatura según su configuración específica.
