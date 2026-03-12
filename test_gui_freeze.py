#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_gui_freeze.py - Diagnóstico del problema de congelación de la GUI
"""

import time
import threading
from config import Config

def test_targeting_loading():
    """Prueba la carga del targeting V2 para identificar el cuelgue."""
    print("DIAGNOSTICO - CONGELACION DE GUI")
    print("=" * 40)
    
    try:
        print("1. Cargando TargetingEngineV2...")
        start_time = time.time()
        
        from targeting_engine_v2 import TargetingEngineV2
        engine = TargetingEngineV2()
        
        load_time = time.time() - start_time
        print(f"   Tiempo de carga: {load_time:.3f} segundos")
        
        print("2. Cargando configuración...")
        start_time = time.time()
        
        config = Config()
        engine.configure(config)
        
        config_time = time.time() - start_time
        print(f"   Tiempo de configuración: {config_time:.3f} segundos")
        
        print("3. Verificando estado...")
        db_info = engine.get_creature_database_info()
        print(f"   Base de datos: {db_info.get('mode', 'unknown')}")
        print(f"   Criaturas cargadas: {db_info.get('total_creatures', 0)}")
        
        print("4. Probando búsqueda...")
        start_time = time.time()
        results = engine.search_creatures("Rotworm")
        search_time = time.time() - start_time
        print(f"   Tiempo de búsqueda: {search_time:.3f} segundos")
        print(f"   Resultados: {len(results)}")
        
        print("✅ Targeting V2 funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en Targeting V2: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_lazy_loading():
    """Prueba específica del lazy loading."""
    print("\nDIAGNOSTICO - LAZY LOADING")
    print("=" * 30)
    
    try:
        print("1. Cargando IntelligentTargeting...")
        start_time = time.time()
        
        from intelligent_targeting import IntelligentTargeting
        intel = IntelligentTargeting()
        
        init_time = time.time() - start_time
        print(f"   Tiempo de inicialización: {init_time:.3f} segundos")
        
        print("2. Cargando Rotworm bajo demanda...")
        start_time = time.time()
        
        success = intel.load_creatures_on_demand(["Rotworm"])
        
        load_time = time.time() - start_time
        print(f"   Tiempo de carga: {load_time:.3f} segundos")
        print(f"   Éxito: {success}")
        
        print("3. Obteniendo info de Rotworm...")
        start_time = time.time()
        
        rotworm_info = intel.get_creature_info("Rotworm")
        
        info_time = time.time() - start_time
        print(f"   Tiempo de consulta: {info_time:.3f} segundos")
        
        if rotworm_info:
            print(f"   HP: {rotworm_info.max_health}")
            print(f"   Exp: {rotworm_info.experience}")
        else:
            print("   No se encontró información")
        
        print("✅ Lazy loading funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en lazy loading: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gui_components():
    """Prueba los componentes de la GUI por separado."""
    print("\nDIAGNOSTICO - COMPONENTES GUI")
    print("=" * 35)
    
    try:
        print("1. Importando customtkinter...")
        import customtkinter
        print("   ✅ customtkinter importado")
        
        print("2. Creando ventana de prueba...")
        root = customtkinter.CTk()
        root.title("Test")
        root.geometry("300x200")
        
        print("3. Creando frame...")
        frame = customtkinter.CTkFrame(root)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        print("4. Creando widgets...")
        label = customtkinter.CTkLabel(frame, text="Test Label")
        label.pack(pady=10)
        
        button = customtkinter.CTkButton(frame, text="Test Button")
        button.pack(pady=5)
        
        print("5. Cerrando ventana de prueba...")
        root.destroy()
        
        print("✅ Componentes GUI funcionan correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en componentes GUI: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal de diagnóstico."""
    print("DIAGNOSTICO COMPLETO - CONGELACION GUI")
    print("=" * 50)
    
    # Probar componentes por separado
    gui_ok = test_gui_components()
    lazy_ok = test_lazy_loading()
    targeting_ok = test_targeting_loading()
    
    print("\n" + "=" * 50)
    print("RESUMEN:")
    print(f"GUI Components: {'✅' if gui_ok else '❌'}")
    print(f"Lazy Loading: {'✅' if lazy_ok else '❌'}")
    print(f"Targeting V2: {'✅' if targeting_ok else '❌'}")
    
    if gui_ok and lazy_ok and targeting_ok:
        print("\n✅ Todos los componentes funcionan correctamente")
        print("El problema puede estar en la inicialización de la GUI principal")
        print("Posibles causas:")
        print("1. Problema con el dispatcher de frames")
        print("2. Problema con la conexión OBS WebSocket")
        print("3. Problema con el hilo principal de la GUI")
    else:
        print("\n❌ Se encontraron problemas en los componentes")
    
    print("\nPASOS RECOMENDADOS:")
    print("1. Ejecuta este script para identificar el componente problemático")
    print("2. Si falla la GUI, el problema está en customtkinter")
    print("3. Si falla lazy loading, el problema está en la base de datos")
    print("4. Si falla targeting V2, el problema está en el motor de targeting")

if __name__ == "__main__":
    main()
