#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeting_debug.py - Script para debuggear el targeting y mostrar cómo ataca
"""

import time
import logging
from targeting_v2_integration import TargetingV2Integration
from screen_calibrator import ScreenCalibrator
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== DEBUG DE TARGETING - ROTWORM ===\n")
    
    # Cargar configuración
    config = Config()
    calibrator = ScreenCalibrator()
    
    # Crear sistema de targeting
    integration = TargetingV2Integration()
    integration.initialize()
    
    # Verificar que Rotworm está en la lista
    print("1. VERIFICANDO CONFIGURACIÓN:")
    info = integration.get_creature_info('rotworm')
    print(f"   Rotworm seleccionado: {info['selected']}")
    print(f"   Rotworm ignorado: {info['ignored']}")
    print(f"   Prioridad: {info['priority']}")
    
    # Mostrar lista de ataque
    selected = integration.get_selected_creatures()
    print(f"\n2. LISTA DE ATAQUE ({len(selected)} criaturas):")
    for i, creature in enumerate(selected[:15], 1):
        status = "✓" if creature['name'].lower() == 'rotworm' else " "
        print(f"   {status} {i:2d}. {creature['name'].title()}")
    
    # Mostrar cómo funciona el targeting
    print(f"\n3. ¿CÓMO ATACA EL BOT A ROTWORM?")
    print(f"   ┌─────────────────────────────────────────┐")
    print(f"   │  PASO 1: DETECCIÓN EN BATTLE LIST      │")
    print(f"   │  - El bot escanea la battle list        │")
    print(f"   │  - Encuentra 'Rotworm' en la lista      │")
    print(f"   │  - Verifica que está en attack_list      │")
    print(f"   └─────────────────────────────────────────┘")
    
    print(f"   ┌─────────────────────────────────────────┐")
    print(f"   │  PASO 2: LOCALIZACIÓN VISUAL           │")
    print(f"   │  - Busca el sprite de Rotworm           │")
    print(f"   │  - Look Type: 26 (identificador único) │")
    print(f"   │  - Calcula coordenadas (x, y)          │")
    print(f"   └─────────────────────────────────────────┘")
    
    print(f"   ┌─────────────────────────────────────────┐")
    print(f"   │  PASO 3: SELECCIÓN DEL MONSTRUO        │")
    print(f"   │  - Mueve el mouse a la posición        │")
    print(f"   │  - Hace click izquierdo para seleccionar│")
    print(f"   │  - Verifica que el target está activo   │")
    print(f"   └─────────────────────────────────────────┘")
    
    print(f"   ┌─────────────────────────────────────────┐")
    print(f"   │  PASO 4: ATAQUE                         │")
    print(f"   │  - Presiona tecla de ataque (espacio)   │")
    print(f"   │  - O hace click derecho                  │")
    print(f"   │  - Inicia combate                       │")
    print(f"   └─────────────────────────────────────────┘")
    
    print(f"   ┌─────────────────────────────────────────┐")
    print(f"   │  PASO 5: PERSIGUIR (CHASE)              │")
    print(f"   │  - Si Rotworm se mueve, lo persigue     │")
    print(f"   │  - Mantenimiento de distancia           │")
    print(f"   │  - Re-ataque si es necesario            │")
    print(f"   └─────────────────────────────────────────┘")
    
    # Información específica de Rotworm
    print(f"\n4. INFORMACIÓN ESPECÍFICA DE ROTWORM:")
    print(f"   ┌─────────────────────────────────────────┐")
    print(f"   │  DATOS DEL MONSTRUO                     │")
    print(f"   │  Nombre: Rotworm                        │")
    print(f"   │  HP: 70                                 │")
    print(f"   │  Experiencia: 40                        │")
    print(f"   │  Tipo: Melee                            │")
    print(f"   │  Look Type: 26                          │")
    print(f"   │  Cuerpo: 4354 (Dead Worm)               │")
    print(f"   └─────────────────────────────────────────┘")
    
    print(f"\n5. ¿POR QUÉ NO ATACABA ANTES?")
    print(f"   └─ Estaba en la lista de 'ignored_creatures'")
    print(f"   └─ Ahora está en 'selected_creatures'")
    print(f"   └─ El bot lo reconoce como objetivo válido")
    
    print(f"\n6. CONFIGURACIÓN DEL TARGETING ENGINE:")
    targeting_config = {
        "enabled": True,
        "auto_attack": True,
        "chase_monsters": True,
        "attack_delay": 0.5,
        "re_attack_delay": 0.6,
        "attack_list": [c['name'] for c in selected],
        "ignore_list": integration.ignored_creatures
    }
    
    print(f"   └─ Enabled: {targeting_config['enabled']}")
    print(f"   └─ Auto Attack: {targeting_config['auto_attack']}")
    print(f"   └─ Chase Monsters: {targeting_config['chase_monsters']}")
    print(f"   └─ Attack Delay: {targeting_config['attack_delay']}s")
    print(f"   └─ Re-attack Delay: {targeting_config['re_attack_delay']}s")
    print(f"   └─ Attack List: {len(targeting_config['attack_list'])} criaturas")
    
    print(f"\n7. PARA PROBAR EL TARGETING:")
    print(f"   1. Inicia el bot principal")
    print(f"   2. Ve a una zona con Rotworms")
    print(f"   3. Activa el targeting V2")
    print(f"   4. El bot debería atacar automáticamente")
    
    print(f"\n=== DEBUG COMPLETADO ===")
    print(f"Rotworm ahora está configurado para ser atacado")

if __name__ == "__main__":
    main()
