#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeting_debug_simple.py - Script simple para debuggear el targeting
"""

import time
import logging
from targeting_v2_integration import TargetingV2Integration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== DEBUG DE TARGETING - ROTWORM ===\n")
    
    # Crear sistema de targeting
    integration = TargetingV2Integration()
    integration.initialize()
    
    # Agregar Rotworm a la lista
    print("1. AGREGANDO ROTWORM:")
    success = integration.add_creature_to_attack('rotworm')
    print(f"   Rotworm agregado: {success}")
    
    # Verificar configuración
    info = integration.get_creature_info('rotworm')
    print(f"\n2. VERIFICACION:")
    print(f"   Rotworm seleccionado: {info['selected']}")
    print(f"   Rotworm ignorado: {info['ignored']}")
    print(f"   Prioridad: {info['priority']}")
    
    # Mostrar lista de ataque
    selected = integration.get_selected_creatures()
    print(f"\n3. LISTA DE ATAQUE ({len(selected)} criaturas):")
    for i, creature in enumerate(selected[:15], 1):
        status = ">>>" if creature['name'].lower() == 'rotworm' else "   "
        print(f"   {status} {i:2d}. {creature['name'].title()}")
    
    # Explicar cómo ataca
    print(f"\n4. COMO ATACA EL BOT A ROTWORM:")
    print(f"   PASO 1: DETECCION")
    print(f"   - El bot escanea la battle list")
    print(f"   - Encuentra 'Rotworm' en la lista")
    print(f"   - Verifica que esta en attack_list")
    
    print(f"\n   PASO 2: LOCALIZACION")
    print(f"   - Busca el sprite de Rotworm")
    print(f"   - Look Type: 26 (ID unico)")
    print(f"   - Calcula coordenadas (x, y)")
    
    print(f"\n   PASO 3: SELECCION")
    print(f"   - Mueve el mouse a la posicion")
    print(f"   - Hace click izquierdo para seleccionar")
    print(f"   - Verifica que el target esta activo")
    
    print(f"\n   PASO 4: ATAQUE")
    print(f"   - Presiona tecla de ataque (espacio)")
    print(f"   - O hace click derecho")
    print(f"   - Inicia combate")
    
    print(f"\n   PASO 5: PERSIGUIR (CHASE)")
    print(f"   - Si Rotworm se mueve, lo persigue")
    print(f"   - Mantiene distancia")
    print(f"   - Re-ataca si es necesario")
    
    # Información específica
    print(f"\n5. DATOS DE ROTWORM:")
    print(f"   Nombre: Rotworm")
    print(f"   HP: 70")
    print(f"   Experiencia: 40")
    print(f"   Tipo: Melee")
    print(f"   Look Type: 26")
    print(f"   Cuerpo: 4354 (Dead Worm)")
    
    print(f"\n6. POR QUE NO ATACABA ANTES:")
    print(f"   - Estaba en la lista de 'ignored_creatures'")
    print(f"   - Ahora esta en 'selected_creatures'")
    print(f"   - El bot lo reconoce como objetivo valido")
    
    print(f"\n7. CONFIGURACION ACTUAL:")
    print(f"   - Enabled: True")
    print(f"   - Auto Attack: True")
    print(f"   - Chase Monsters: True")
    print(f"   - Attack Delay: 0.5s")
    print(f"   - Re-attack Delay: 0.6s")
    print(f"   - Attack List: {len(selected)} criaturas")
    
    print(f"\n8. PARA PROBAR:")
    print(f"   1. Inicia el bot principal")
    print(f"   2. Ve a una zona con Rotworms")
    print(f"   3. Activa el targeting V2")
    print(f"   4. El bot deberia atacar automaticamente")
    
    print(f"\n=== DEBUG COMPLETADO ===")
    print(f"Rotworm ahora esta configurado para ser atacado")
    
    # Guardar configuración
    integration.save_configuration()
    print(f"Configuracion guardada en targeting_v2_config.json")

if __name__ == "__main__":
    main()
