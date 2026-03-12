#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rotworm_detection_simple.py - Prueba simple de detección de Rotworm
"""

import cv2
import numpy as np
from targeting.battle_list_reader import BattleListReader
from config import Config

def test_rotworm_detection():
    """Prueba simple de detección sin captura de pantalla."""
    print("PRUEBA SIMPLE - DETECCION DE ROTWORM")
    print("=" * 40)
    
    # 1. Cargar configuración
    config = Config()
    battle_region = config.get("targeting", {}).get("battle_list_region", {})
    print(f"Region de battle list: {battle_region}")
    
    # 2. Crear battle reader
    reader = BattleListReader()
    
    # 3. Cargar templates
    loaded = reader.load_all_available_templates()
    print(f"Templates cargados: {loaded}")
    
    # 4. Verificar Rotworm
    templates = reader.get_loaded_monster_names()
    print(f"Templates disponibles: {templates}")
    
    if "Rotworm" in templates:
        print("Rotworm: DISPONIBLE")
    else:
        print("Rotworm: NO DISPONIBLE")
        return
    
    # 5. Configurar región
    if battle_region:
        x = battle_region.get("x", 0)
        y = battle_region.get("y", 0)
        w = battle_region.get("w", 0)
        h = battle_region.get("h", 0)
        reader.set_region(x, y, x + w, y + h)
        print(f"Region configurada: ({x},{y}) -> ({x+w},{y+h})")
    
    # 6. Probar con una imagen de prueba si existe
    try:
        # Intentar cargar una captura de pantalla existente
        import os
        test_files = ["debug_battle_list.png", "test_frame.png", "screenshot.png"]
        
        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"\nProbando con imagen: {test_file}")
                frame = cv2.imread(test_file)
                if frame is not None:
                    creatures = reader.read(frame)
                    print(f"Criaturas detectadas: {len(creatures)}")
                    for creature in creatures:
                        print(f"  - {creature.name} en ({creature.screen_x}, {creature.screen_y})")
                    return
        else:
            print("\nNo hay imágenes de prueba disponibles")
            print("Para probar:")
            print("1. Haz una captura de pantalla con Rotworms visibles")
            print("2. Guardala como test_frame.png")
            print("3. Ejecuta este script nuevamente")
    
    except Exception as e:
        print(f"Error: {e}")

def check_targeting_config():
    """Verifica la configuración de targeting."""
    print("\nCONFIGURACION DE TARGETING:")
    print("=" * 30)
    
    config = Config()
    targeting = config.get("targeting", {})
    
    print(f"enabled: {targeting.get('enabled', False)}")
    print(f"auto_attack: {targeting.get('auto_attack', False)}")
    print(f"chase_monsters: {targeting.get('chase_monsters', False)}")
    
    attack_list = targeting.get("attack_list", [])
    print(f"attack_list: {attack_list}")
    
    if "Rotworm" in attack_list:
        print("Rotworm: EN LISTA DE ATAQUE")
    else:
        print("Rotworm: NO EN LISTA DE ATAQUE")

if __name__ == "__main__":
    test_rotworm_detection()
    check_targeting_config()
