#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rotworm_attack_optimized.py - Script de ataque optimizado para Rotworm y Carrion Worm
"""

import time
import logging
from rotworm_optimized_simple import OptimizedRotwormSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== ATAQUE OPTIMIZADO - ROTWORM + CARRION WORM ===\n")
    
    # 1. Crear sistema optimizado
    print("1. Creando sistema optimizado...")
    system = OptimizedRotwormSystem(["rotworm", "carrion worm"])
    
    # 2. Inicializar
    print("2. Inicializando sistema...")
    if not system.initialize():
        print("[ERROR] No se pudo inicializar el sistema")
        return
    
    print("[OK] Sistema inicializado")
    
    # 3. Mostrar información
    print(f"\n3. Información del sistema:")
    print(f"   Criaturas cargadas: {len(system.selected_creatures)}")
    print(f"   Criaturas objetivo: {system.target_creatures}")
    
    print(f"\n4. Criaturas configuradas:")
    for creature in system.get_selected_creatures():
        print(f"   • {creature['name'].title()}")
        print(f"     HP: {creature['hp']}, EXP: {creature['experience']}")
        print(f"     Look Type: {creature['look_type']}, Prioridad: {creature['priority']}")
    
    # 4. Iniciar targeting
    print(f"\n5. Iniciando targeting...")
    try:
        if system.start_targeting():
            print("[OK] Targeting iniciado")
        else:
            print("[ERROR] No se pudo iniciar el targeting")
            return
    except Exception as e:
        print(f"[ERROR] Error iniciando targeting: {e}")
        return
    
    # 5. Monitorear ataque
    print(f"\n6. Monitoreando ataque...")
    print(f"El bot atacará automáticamente Rotworms y Carrion Worms")
    print(f"Presiona Ctrl+C para detener")
    
    attack_count = 0
    rotworm_count = 0
    carrion_count = 0
    
    try:
        while True:
            # Obtener estado
            status = system.get_targeting_status()
            
            # Verificar si está atacando
            if status.get('is_attacking', False):
                attack_count += 1
                print(f"[ATAQUE #{attack_count}] Atacando objetivo...")
            
            # Mostrar información
            current_target = status.get('current_target')
            if current_target:
                print(f"[TARGET] Objetivo actual: {current_target}")
                if 'rotworm' in current_target.lower():
                    rotworm_count += 1
                elif 'carrion' in current_target.lower():
                    carrion_count += 1
            
            # Mostrar estadísticas cada 10 segundos
            if attack_count > 0 and attack_count % 5 == 0:
                print(f"[STATS] Rotworms: {rotworm_count}, Carrion Worms: {carrion_count}, Total: {attack_count}")
            
            # Esperar
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        print(f"\n[STOP] Deteniendo ataque...")
        system.stop_targeting()
        print(f"[OK] Targeting detenido")
    
    # 6. Resumen
    print(f"\n=== RESUMEN DEL ATAQUE ===")
    print(f"Ataques totales: {attack_count}")
    print(f"Rotworms eliminados: {rotworm_count}")
    print(f"Carrion Worms eliminados: {carrion_count}")
    print(f"Experiencia ganada: {rotworm_count * 40 + carrion_count * 70}")
    
    print(f"\n=== CONFIGURACIÓN GUARDADA ===")
    print(f"Archivo: rotworm_optimized_config.json")
    print(f"Sistema optimizado para solo 2 criaturas")
    
    print(f"\n=== VENTAJAS DEL SISTEMA OPTIMIZADO ===")
    print(f"• Carga rápida: Solo 2 criaturas vs 1429")
    print(f"• Menos memoria: Datos específicos solo")
    print(f"• Respuesta rápida: Sin procesamiento innecesario")
    print(f"• Configuración simple: Fácil de modificar")
    
    print(f"\n=== PARA CAMBIAR LAS CRIATURAS ===")
    print(f"Modifica la línea:")
    print(f"system = OptimizedRotwormSystem(['rotworm', 'carrion worm'])")
    print(f"")
    print(f"Ejemplos:")
    print(f"• Solo Rotworm: OptimizedRotwormSystem(['rotworm'])")
    print(f"• Añadir Dragon: OptimizedRotwormSystem(['rotworm', 'carrion worm', 'dragon'])")
    print(f"• Cambiar a Orcs: OptimizedRotwormSystem(['orc', 'orc warrior'])")

if __name__ == "__main__":
    main()
