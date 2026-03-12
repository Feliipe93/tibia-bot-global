#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rotworm_attack_simple.py - Script simple para atacar Rotworm
"""

import time
import logging
from targeting_v2_integration import TargetingV2Integration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== ATAQUE A ROTWORM - VERSION SIMPLE ===\n")
    
    # 1. Crear sistema de targeting
    print("1. Iniciando sistema de targeting...")
    integration = TargetingV2Integration()
    
    # 2. Inicializar
    if not integration.initialize():
        print("[ERROR] No se pudo inicializar el sistema")
        return
    
    print("[OK] Sistema inicializado")
    
    # 3. Agregar Rotworm a la lista de ataque
    print("\n2. Agregando Rotworm a la lista de ataque...")
    success = integration.add_creature_to_attack('rotworm')
    print(f"   Rotworm agregado: {success}")
    
    # 4. Verificar configuración
    rotworm_info = integration.get_creature_info('rotworm')
    print(f"   Rotworm seleccionado: {rotworm_info['selected']}")
    print(f"   Rotworm ignorado: {rotworm_info['ignored']}")
    print(f"   Prioridad: {rotworm_info['priority']}")
    
    # 5. Mostrar lista de ataque
    selected = integration.get_selected_creatures()
    print(f"\n3. Lista de ataque ({len(selected)} criaturas):")
    for i, creature in enumerate(selected[:15], 1):
        marker = ">>>" if creature['name'].lower() == 'rotworm' else "   "
        print(f"{marker} {i:2d}. {creature['name'].title()}")
    
    # 6. Iniciar targeting
    print(f"\n4. Iniciando targeting...")
    try:
        if integration.start_targeting():
            print("[OK] Targeting iniciado")
        else:
            print("[ERROR] No se pudo iniciar el targeting")
            return
    except Exception as e:
        print(f"[ERROR] Error iniciando targeting: {e}")
        return
    
    # 7. Monitorear ataque
    print(f"\n5. Monitoreando ataque...")
    print(f"El bot debería atacar automáticamente los Rotworms")
    print(f"Presiona Ctrl+C para detener")
    
    attack_count = 0
    
    try:
        while True:
            # Obtener estado
            status = integration.get_targeting_status()
            
            # Verificar si está atacando
            if status.get('is_attacking', False):
                attack_count += 1
                print(f"[ATAQUE #{attack_count}] Atacando objetivo...")
            
            # Mostrar información
            current_target = status.get('current_target')
            if current_target:
                print(f"[TARGET] Objetivo actual: {current_target}")
            
            # Esperar
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        print(f"\n[STOP] Deteniendo ataque...")
        integration.stop_targeting()
        print(f"[OK] Targeting detenido")
    
    # 8. Resumen
    print(f"\n=== RESUMEN ===")
    print(f"Ataques realizados: {attack_count}")
    print(f"Rotworms eliminados: {attack_count}")
    print(f"Configuracion guardada en: targeting_v2_config.json")
    
    print(f"\n=== INSTRUCCIONES ===")
    print(f"1. Asegúrate de tener Tibia abierto")
    print(f"2. Ve a una zona con Rotworms (ej. Sewers)")
    print(f"3. Deja que el bot detecte los Rotworms")
    print(f"4. El bot atacará automáticamente")
    print(f"5. Si no ataca, verifica:")
    print(f"   - Que OBS esté capturando la pantalla")
    print(f"   - Que el Rotworm esté visible")
    print(f"   - Que la battle list esté visible")

if __name__ == "__main__":
    main()
