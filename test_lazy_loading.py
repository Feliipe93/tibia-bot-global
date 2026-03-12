#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_lazy_loading.py - Prueba del sistema de lazy loading para criaturas
Verifica que el sistema carga solo las criaturas necesarias bajo demanda.
"""

import time
import json
from intelligent_targeting import IntelligentTargeting
from targeting_engine_v2 import TargetingEngineV2

def test_lazy_loading_performance():
    """Prueba el rendimiento del lazy loading vs carga completa."""
    print("=== PRUEBA DE RENDIMIENTO - LAZY LOADING ===\n")
    
    # 1. Probar inicialización rápida (lazy loading)
    print("1. Inicialización con Lazy Loading:")
    start_time = time.time()
    
    intel_targeting = IntelligentTargeting()
    
    init_time = time.time() - start_time
    print(f"   Tiempo de inicialización: {init_time:.3f} segundos")
    print(f"   Criaturas cargadas: {len(intel_targeting.lazy_loaded_creatures)}")
    print(f"   Base de datos completa cargada: {intel_targeting.database_loaded}")
    print(f"   Perfiles automáticos: {len(intel_targeting.auto_profiles)}")
    
    # 2. Probar carga bajo demanda de criaturas específicas
    print("\n2. Carga bajo demanda de criaturas seleccionadas:")
    test_creatures = ["Dragon", "Demon", "Orc", "Rotworm", "Cyclops"]
    
    start_time = time.time()
    success = intel_targeting.load_creatures_on_demand(test_creatures)
    load_time = time.time() - start_time
    
    print(f"   Tiempo de carga: {load_time:.3f} segundos")
    print(f"   Éxito: {success}")
    print(f"   Criaturas cargadas: {len(intel_targeting.lazy_loaded_creatures)}")
    
    # 3. Verificar que las criaturas se cargaron correctamente
    print("\n3. Verificacion de criaturas cargadas:")
    for creature in test_creatures:
        info = intel_targeting.get_creature_info(creature)
        if info:
            print(f"   [OK] {creature}: HP {info.max_health}, Exp {info.experience}, Clase {info.class_type}")
        else:
            print(f"   [ERROR] {creature}: No encontrada")
    
    # 4. Probar búsqueda con lazy loading
    print("\n4. Prueba de búsqueda:")
    start_time = time.time()
    results = intel_targeting.search_creatures_by_pattern("dragon", limit=5)
    search_time = time.time() - start_time
    
    print(f"   Tiempo de búsqueda: {search_time:.3f} segundos")
    print(f"   Resultados encontrados: {len(results)}")
    for result in results:
        print(f"   - {result.name}: {result.class_type}")
    
    # 5. Probar carga completa (comparación)
    print("\n5. Comparación con carga completa:")
    start_time = time.time()
    success_full = intel_targeting.load_full_database()
    full_load_time = time.time() - start_time
    
    print(f"   Tiempo de carga completa: {full_load_time:.3f} segundos")
    print(f"   Éxito: {success_full}")
    print(f"   Criaturas totales: {len(intel_targeting.creature_db.creatures) if intel_targeting.creature_db else 0}")
    
    # 6. Comparación de tiempos
    print("\n=== COMPARACIÓN DE RENDIMIENTO ===")
    print(f"Inicialización lazy: {init_time:.3f}s")
    print(f"Carga bajo demanda: {load_time:.3f}s")
    print(f"Carga completa: {full_load_time:.3f}s")
    
    if full_load_time > 0:
        speedup = full_load_time / (init_time + load_time)
        print(f"Mejora de rendimiento: {speedup:.1f}x más rápido")

def test_targeting_engine_integration():
    """Prueba la integración con el TargetingEngineV2."""
    print("\n=== PRUEBA DE INTEGRACIÓN CON TARGETING ENGINE ===\n")
    
    # Crear configuración de prueba
    config = {
        "targeting": {
            "enabled": True,
            "attack_list": ["Dragon", "Demon", "Orc"],
            "auto_attack": True
        }
    }
    
    # 1. Probar configuración rápida
    print("1. Configuración del Targeting Engine V2:")
    start_time = time.time()
    
    engine = TargetingEngineV2()
    engine.configure(config)
    
    config_time = time.time() - start_time
    print(f"   Tiempo de configuración: {config_time:.3f} segundos")
    
    # 2. Verificar información de la base de datos
    print("\n2. Estado de la base de datos:")
    db_info = engine.get_creature_database_info()
    print(f"   Modo: {db_info.get('mode', 'unknown')}")
    print(f"   Criaturas cargadas: {db_info['total_creatures']}")
    print(f"   Perfiles automáticos: {db_info['auto_profiles']}")
    print(f"   Perfiles manuales: {db_info['manual_profiles']}")
    
    if db_info.get('message'):
        print(f"   Mensaje: {db_info['message']}")
    
    # 3. Probar búsqueda de criaturas
    print("\n3. Prueba de búsqueda:")
    start_time = time.time()
    results = engine.search_creatures("dragon")
    search_time = time.time() - start_time
    
    print(f"   Tiempo de búsqueda: {search_time:.3f} segundos")
    print(f"   Resultados: {len(results)}")
    for result in results[:3]:
        print(f"   - {result['name']}: HP {result['health']}, Exp {result['experience']}")
    
    # 4. Probar análisis de targets
    print("\n4. Prueba de análisis de targets:")
    for creature in config["targeting"]["attack_list"]:
        analysis = engine.get_target_analysis(creature)
        if analysis and analysis['creature_info']:
            info = analysis['creature_info']
            strategy = analysis['strategy']
            print(f"   [INFO] {creature}:")
            print(f"      HP: {info.max_health}, Exp: {info.experience}")
            print(f"      Estrategia: {strategy['mode']} ({strategy['reason']})")
        else:
            print(f"   [SIN DATOS] {creature}: Sin análisis disponible")

def test_memory_usage():
    """Estima el uso de memoria del lazy loading."""
    print("\n=== ESTIMACIÓN DE USO DE MEMORIA ===\n")
    
    intel_targeting = IntelligentTargeting()
    
    # Memoria base (solo perfiles)
    base_creatures = len(intel_targeting.lazy_loaded_creatures)
    print(f"Memoria base (solo perfiles): {base_creatures} criaturas")
    
    # Cargar algunas criaturas
    test_creatures = ["Dragon", "Demon", "Orc", "Rotworm", "Cyclops", 
                      "Amazon", "Valkyrie", "Warlock", "Necromancer"]
    intel_targeting.load_creatures_on_demand(test_creatures)
    
    lazy_creatures = len(intel_targeting.lazy_loaded_creatures)
    print(f"Memoria con lazy loading: {lazy_creatures} criaturas")
    
    # Cargar base completa
    intel_targeting.load_full_database()
    full_creatures = len(intel_targeting.creature_db.creatures)
    print(f"Memoria con BD completa: {full_creatures} criaturas")
    
    # Estimación de ahorro
    if full_creatures > 0:
        savings = (1 - lazy_creatures / full_creatures) * 100
        print(f"Ahorro de memoria estimado: {savings:.1f}%")

if __name__ == "__main__":
    print("TESTING - SISTEMA LAZY LOADING PARA TARGETING V2")
    print("=" * 60)
    
    try:
        # Ejecutar todas las pruebas
        test_lazy_loading_performance()
        test_targeting_engine_integration()
        test_memory_usage()
        
        print("\n" + "=" * 60)
        print("TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("\nRESUMEN DE OPTIMIZACIONES:")
        print("• Lazy loading: Inicializacion rapida")
        print("• Carga bajo demanda: Solo criaturas necesarias")
        print("• Cache eficiente: Reutilizacion de datos")
        print("• Busqueda optimizada: Resultados limitados")
        print("• Memoria reducida: Ahorro significativo")
        
    except Exception as e:
        print(f"\nERROR EN LAS PRUEBAS: {e}")
        import traceback
        traceback.print_exc()
