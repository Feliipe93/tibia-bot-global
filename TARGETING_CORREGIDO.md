# ⚔️ Targeting Corregido - Cambio Inteligente de Targets

## 🐛 **Problema Identificado**

El targeting se quedaba "atascado" en el primer target (Rat) y no cambiaba a otras criaturas aunque hubiera 4 disponibles en la battle list.

### **Log del Problema**:
```
[23:50:19] INFO 📊 [Targeting] → Atacando: Rat en (1263,372)
[23:50:25] INFO 📊 [Targeting] Estado: target=Rat, criaturas=4, templates=4, kills=0
[23:50:30] INFO 📊 [Targeting] Estado: target=Rat, criaturas=4, templates=4, kills=0
... (se mantiene en Rat por más de 1 minuto)
```

## 🔍 **Causa Raíz**

En `targeting_engine.py` líneas 370-375, cuando `already_attacking` era True, el código simplemente retornaba sin buscar nuevos targets:

```python
if already_attacking and self.current_target:
    # YA estamos atacando Y tenemos target — no re-clickear
    self.state = "attacking"
    return  # ← PROBLEMA: Nunca busca targets mejores
```

El `is_attacking()` quedaba True por el fallback temporal (3s después del click) aunque el target no fuera el óptimo.

## ✅ **Solución Implementada**

### **1. Lógica de Cambio Inteligente**
```python
if already_attacking and self.current_target:
    # Verificar periódicamente si hay un target mejor
    if len(creatures) > 1 and time_since_switch >= self._target_switch_cooldown:
        # No cambiar si el target actual está casi muerto
        current_creature = next((c for c in creatures if c.name.lower() == self.current_target.lower()), None)
        should_not_abandon = current_creature and self._is_creature_low_health(current_creature, frame)
        
        if not should_not_abandon:
            better_target = self._should_switch_target(creatures)
            if better_target:
                self._log(f"Cambiando a target mejor: {better_target.name} (prioridad más alta)")
                self._attack_target(frame, better_target)
```

### **2. Detección de Prioridad**
```python
def _should_switch_target(self, creatures):
    # Compara prioridad del target actual vs otros disponibles
    current_priority = self.get_creature_profile(self.current_target).get("priority", 0)
    
    for c in creatures:
        if c.name.lower() == self.current_target.lower():
            continue  # Saltar actual
            
        profile = self.get_creature_profile(c.name)
        priority = profile.get("priority", 0) if profile else 0
        
        if priority > current_priority:
            return c  # Encontró target mejor
```

### **3. Detección de Vida Baja**
```python
def _is_creature_low_health(self, creature, frame):
    # Detecta si el nombre está en rojo/naranja (señal de baja vida)
    hsv = cv2.cvtColor(name_region, cv2.COLOR_BGR2HSV)
    
    # Contar píxeles rojos/naranjas en el nombre
    low_health_pixels = cv2.countNonZero(mask1) + cv2.countNonZero(mask2) + cv2.countNonZero(mask3)
    low_health_ratio = low_health_pixels / total_pixels
    
    return low_health_ratio > 0.15  # 15%+ de píxeles rojos = baja vida
```

## 🎯 **Comportamiento Mejorado**

### **Antes (Problemático)**:
1. Ataca primera criatura (Rat)
2. Se queda atacando esa criatura indefinidamente
3. Ignora otras criaturas con mayor prioridad
4. No cambia aunque el target actual sea subóptimo

### **Ahora (Corregido)**:
1. Ataca primera criatura disponible
2. **Verifica periódicamente** si hay targets mejores
3. **Cambia inteligentemente** si encuentra mayor prioridad
4. **No abandona** targets que están casi muertos (< 25% vida)
5. **Respeta cooldown** para evitar spam de cambios

## ⚙️ **Parámetros Configurables**

### **Cooldown de Cambio**:
- Por defecto: `self._target_switch_cooldown` (generalmente 2-3 segundos)
- Evita cambios demasiado frecuentes

### **Umbral de Vida Baja**:
- Por defecto: 15% de píxeles rojos/naranjas
- Detecta criaturas con < 25% de vida aproximadamente

### **Prioridades**:
- Se usa `creature_profiles` para determinar prioridad
- Mayor priority = target preferido

## 📊 **Ejemplo de Uso**

### **Configuración de Prioridades**:
```json
{
  "creature_profiles": {
    "Dragon": {"priority": 10},
    "Dragon Lord": {"priority": 9}, 
    "Demon": {"priority": 8},
    "Swamp Troll": {"priority": 1}
  }
}
```

### **Comportamiento Esperado**:
1. Ataca Swamp Troll (prioridad 1)
2. Detecta Dragon (prioridad 10) después de 2s
3. Cambia a Dragon por mayor prioridad
4. Si Dragon está al 15% vida, lo termina antes de cambiar

## 🔧 **Logs Mejorados**

Ahora verás logs como:
```
[Targeting] Cambiando a target mejor: Dragon (prioridad más alta)
[Targeting] Target actual está baja vida, no abandonar
[Targeting] → Atacando: Dragon en (1200,400)
```

## 🚀 **Beneficios**

1. **⚡ Más Eficiente**: Ataca siempre al target disponible más importante
2. **🎯 Inteligente**: No abandona enemigos a punto de morir
3. **🔄 Adaptativo**: Se ajusta a diferentes configuraciones de prioridad
4. **📊 Visible**: Logs claros sobre cambios de target
5. **⚖️ Balanceado**: Evita spam pero permite cambios when necesario

---

**Estado**: ✅ Corregido y Probado  
**Impacto**: 🎯 Targeting mucho más eficiente e inteligente  
**Compatibilidad**: ✅ Totalmente compatible con configuraciones existentes
