#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_simple.py - Prueba simple para identificar el problema
"""

import time

def test_targeting():
    """Prueba el targeting V2."""
    print("PRUEBA TARGETING V2")
    print("=" * 20)
    
    try:
        from targeting_engine_v2 import TargetingEngineV2
        from config import Config
        
        print("Cargando engine...")
        engine = TargetingEngineV2()
        
        print("Cargando config...")
        config = Config()
        engine.configure(config)
        
        print("Verificando estado...")
        db_info = engine.get_creature_database_info()
        print(f"Modo: {db_info.get('mode', 'unknown')}")
        print(f"Criaturas: {db_info.get('total_creatures', 0)}")
        
        print("Buscando Rotworm...")
        results = engine.search_creatures("Rotworm")
        print(f"Resultados: {len(results)}")
        
        print("Targeting V2: OK")
        return True
        
    except Exception as e:
        print(f"Error en targeting: {e}")
        return False

def test_lazy_loading():
    """Prueba el lazy loading."""
    print("\nPRUEBA LAZY LOADING")
    print("=" * 20)
    
    try:
        from intelligent_targeting import IntelligentTargeting
        
        print("Cargando intelligent targeting...")
        intel = IntelligentTargeting()
        
        print("Cargando Rotworm bajo demanda...")
        success = intel.load_creatures_on_demand(["Rotworm"])
        print(f"Exito: {success}")
        
        print("Obteniendo info...")
        info = intel.get_creature_info("Rotworm")
        if info:
            print(f"HP: {info.max_health}, Exp: {info.experience}")
        
        print("Lazy loading: OK")
        return True
        
    except Exception as e:
        print(f"Error en lazy loading: {e}")
        return False

def main():
    print("DIAGNOSTICO SIMPLE")
    print("=" * 20)
    
    lazy_ok = test_lazy_loading()
    targeting_ok = test_targeting()
    
    print("\nRESUMEN:")
    print(f"Lazy Loading: {'OK' if lazy_ok else 'ERROR'}")
    print(f"Targeting V2: {'OK' if targeting_ok else 'ERROR'}")
    
    if lazy_ok and targeting_ok:
        print("\nAmbos sistemas funcionan correctamente")
        print("El problema esta en la GUI principal")
    else:
        print("\nHay problemas en los sistemas")

if __name__ == "__main__":
    main()
