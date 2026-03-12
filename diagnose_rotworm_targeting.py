#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_rotworm_targeting.py - Diagnóstico específico para problemas de targeting con Rotworm
"""

import os
import cv2
import numpy as np
from targeting.battle_list_reader import BattleListReader, CreatureEntry
from screen_capture import ScreenCapture
from config import Config

def diagnose_rotworm_detection():
    """Diagnostica por qué el bot no detecta Rotworms."""
    print("DIAGNOSTICO - DETECCION DE ROTWORM")
    print("=" * 50)
    
    # 1. Verificar que existe el template de Rotworm
    print("\n1. VERIFICACIÓN DE TEMPLATE:")
    template_path = "images/Targets/Names/Rotworm.png"
    if os.path.exists(template_path):
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template is not None:
            print(f"   [OK] Template encontrado: {template.shape}")
        else:
            print(f"   [ERROR] Template corrupto o no legible")
            return False
    else:
        print(f"   [ERROR] Template NO encontrado en: {template_path}")
        print("   Solucion: Captura un Rotworm en la battle list y guarda como Rotworm.png")
        return False
    
    # 2. Verificar configuración del battle reader
    print("\n2. CONFIGURACIÓN BATTLE READER:")
    config = Config()
    reader = BattleListReader()
    
    # Cargar templates
    loaded = reader.load_all_available_templates()
    print(f"   Templates cargados: {loaded}")
    print(f"   Nombres disponibles: {reader.get_loaded_monster_names()}")
    
    if "Rotworm" not in reader.get_loaded_monster_names():
        print("   [ERROR] Rotworm NO esta en los templates cargados")
        return False
    else:
        print("   [OK] Rotworm SI esta en los templates cargados")
    
    # 3. Verificar configuración de región
    print("\n3. CONFIGURACIÓN DE REGIÓN:")
    battle_region = config.get("targeting", {}).get("battle_list_region", {})
    if battle_region:
        print(f"   Region configurada: {battle_region}")
        # Convertir formato x,y,w,h a x1,y1,x2,y2
        x = battle_region.get("x", 0)
        y = battle_region.get("y", 0)
        w = battle_region.get("w", 0)
        h = battle_region.get("h", 0)
        reader.set_region(x, y, x + w, y + h)
        print("   [OK] Region de battle list configurada")
    else:
        print("   [ERROR] No hay region de battle list configurada")
        print("   Solucion: Debes calibrar la region de la battle list en la GUI")
        return False
    
    # 4. Intentar captura y detección
    print("\n4. PRUEBA DE DETECCIÓN:")
    try:
        capture = ScreenCapture()
        frame = capture.get_frame()
        if frame is not None:
            print(f"   Frame capturado: {frame.shape}")
            
            # Recortar battle list
            x1, y1, x2, y2 = battle_region["x1"], battle_region["y1"], battle_region["x2"], battle_region["y2"]
            roi = frame[y1:y2, x1:x2]
            print(f"   ROI battle list: {roi.shape}")
            
            # Guardar ROI para debug
            cv2.imwrite("debug_battle_list.png", roi)
            print("   ROI guardado como debug_battle_list.png")
            
            # Detectar criaturas
            creatures = reader.read(frame)
            print(f"   Criaturas detectadas: {len(creatures)}")
            
            if creatures:
                for creature in creatures:
                    print(f"   - {creature.name} en ({creature.screen_x}, {creature.screen_y})")
            else:
                print("   [ERROR] NO se detectaron criaturas")
                
                # Debug: intentar template matching manual
                print("\n   DEBUG TEMPLATE MATCHING:")
                roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                
                if roi_gray.shape[0] >= template.shape[0] and roi_gray.shape[1] >= template.shape[1]:
                    res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                    print(f"   Similitud maxima: {max_val:.3f} en {max_loc}")
                    
                    if max_val >= 0.8:
                        print("   [OK] Template deberia detectar (similitud >= 0.8)")
                    else:
                        print("   [ERROR] Template NO detecta (similitud < 0.8)")
                        print("   Posibles causas:")
                        print("      - El template no coincide con el texto actual")
                        print("      - Diferente fuente/tamaño/color")
                        print("      - Resolucion diferente")
                else:
                    print("   [ERROR] Template mas grande que el ROI")
            
        else:
            print("   [ERROR] No se pudo capturar frame")
            return False
            
    except Exception as e:
        print(f"   [ERROR] Error en captura: {e}")
        return False
    
    return True

def check_targeting_engine_state():
    """Verifica el estado del targeting engine."""
    print("\n5. ESTADO DEL TARGETING ENGINE:")
    
    try:
        from targeting_engine_v2 import TargetingEngineV2
        
        engine = TargetingEngineV2()
        config = Config()
        engine.configure(config)
        
        # Verificar estado
        print(f"   Engine habilitado: {engine.enabled}")
        print(f"   Auto-ataque: {engine.auto_attack}")
        print(f"   Target actual: {engine.current_target}")
        print(f"   Estado: {engine.state}")
        
        # Verificar lista de ataque
        attack_list = config.get("targeting", {}).get("attack_list", [])
        print(f"   Criaturas en lista de ataque: {attack_list}")
        
        if "Rotworm" in attack_list:
            print("   ✅ Rotworm está en la lista de ataque")
        else:
            print("   ❌ Rotworm NO está en la lista de ataque")
            print("   💡 Agrega 'Rotworm' a la lista de ataque en la GUI")
        
        # Verificar battle reader
        if hasattr(engine, 'battle_reader'):
            reader = engine.battle_reader
            templates = reader.get_loaded_monster_names()
            print(f"   Templates cargados: {len(templates)}")
            
            if "Rotworm" in templates:
                print("   ✅ Template de Rotworm cargado")
            else:
                print("   ❌ Template de Rotworm NO cargado")
        
    except Exception as e:
        print(f"   ❌ Error verificando engine: {e}")

def generate_rotworm_template():
    """Instrucciones para generar template de Rotworm."""
    print("\n6. GENERAR TEMPLATE DE ROTWORM:")
    print("   Si el template no existe o no funciona, sigue estos pasos:")
    print("   1. Ve a una zona con Rotworms")
    print("   2. Abre la battle list")
    print("   3. Haz screenshot de la battle list")
    print("   4. Recorta el texto 'Rotworm' exactamente como aparece")
    print("   5. Guarda como 'images/Targets/Names/Rotworm.png'")
    print("   6. Asegúrate que sea escala de grises y sin fondo")
    print("   7. Reinicia el bot")

def main():
    """Función principal de diagnóstico."""
    print("DIAGNOSTICO COMPLETO - ROTWORM TARGETING")
    print("=" * 60)
    
    # Ejecutar diagnósticos
    success = diagnose_rotworm_detection()
    check_targeting_engine_state()
    
    if not success:
        generate_rotworm_template()
    
    print("\n" + "=" * 60)
    print("RESUMEN:")
    if success:
        print("Todo parece configurado correctamente")
        print("Si aun no funciona, revisa:")
        print("   - Que la battle list este visible")
        print("   - Que la region calibrada sea correcta")
        print("   - Que no haya otros problemas en el log")
    else:
        print("Se encontraron problemas que deben solucionarse")
    
    print("\nPASOS RECOMENDADOS:")
    print("1. Verifica que exista el template Rotworm.png")
    print("2. Calibra la region de la battle list en la GUI")
    print("3. Agrega 'Rotworm' a la lista de ataque")
    print("4. Habilita el targeting y auto-ataque")
    print("5. Prueba con un Rotworm visible en pantalla")

if __name__ == "__main__":
    main()
