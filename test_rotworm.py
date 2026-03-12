#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rotworm.py - Script para agregar Rotworm al targeting
"""

from targeting_v2_integration import TargetingV2Integration

def main():
    # Crear sistema
    integration = TargetingV2Integration()
    integration.initialize()
    
    # Agregar Rotworm a la lista de ataque
    print('=== AGREGANDO ROTWORM ===')
    success = integration.add_creature_to_attack('rotworm')
    print(f'Rotworm agregado: {success}')
    
    # Ver información del Rotworm
    info = integration.get_creature_info('rotworm')
    print(f'\n=== INFO DE ROTWORM ===')
    print(f'Nombre: {info["name"]}')
    print(f'Prioridad: {info["priority"]}')
    print(f'Seleccionado: {info["selected"]}')
    print(f'Ignorado: {info["ignored"]}')
    
    # Mostrar criaturas seleccionadas
    selected = integration.get_selected_creatures()
    print(f'\n=== CRIATURAS SELECCIONADAS ({len(selected)}) ===')
    for i, creature in enumerate(selected[:10], 1):
        print(f'{i:2d}. {creature["name"].title()} (Prioridad: {creature["priority"]:.1f})')
    
    # Guardar configuración
    integration.save_configuration()
    print(f'\n[OK] Configuración guardada')
    
    print(f'\n=== COMO ATACA EL BOT ===')
    print(f'1. El bot detecta Rotworm en la battle list')
    print(f'2. Verifica que está en la lista de ataque')
    print(f'3. Calcula la posición del monstruo')
    print(f'4. Hace click en el monstruo para seleccionarlo')
    print(f'5. Presiona la tecla de ataque (usualmente espacio o click derecho)')
    print(f'6. Si el monstruo se mueve, lo persigue (chase)')
    print(f'7. Si hay múltiples monstruos, ataca por prioridad')

if __name__ == "__main__":
    main()
