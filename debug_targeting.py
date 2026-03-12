#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para el sistema de targeting.
Verifica la detección de criaturas en la battle list.
"""

import cv2
import numpy as np
import time
from obswebsocket import obsws, requests
from config import Config
from targeting.battle_list_reader import BattleListReader
from screen_calibrator import ScreenCalibrator

def capture_obs_frame():
    """Captura un frame desde OBS."""
    config = Config()
    obs_config = config.data.get('obs_websocket', {})
    
    host = obs_config.get('host', 'localhost')
    port = obs_config.get('port', 4455)
    password = obs_config.get('password', '')
    source_name = obs_config.get('source_name', 'Captura de juego')
    
    try:
        ws = obsws(host, port, password)
        ws.connect()
        
        response = ws.call(requests.GetSourceScreenshot(sourceName=source_name, imageFormat="png"))
        
        if hasattr(response, 'datain') and 'imageData' in response.datain:
            import base64
            img_data = base64.b64decode(response.datain['imageData'])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            ws.disconnect()
            return img
        else:
            print(f"Error capturando screenshot: {response}")
            ws.disconnect()
            return None
            
    except Exception as e:
        print(f"Error conectando a OBS: {e}")
        return None

def diagnose_targeting():
    """Diagnostica el sistema de targeting."""
    
    print("=== DIAGNÓSTICO DE TARGETING ===\n")
    
    # 1. Capturar frame
    print("1. Capturando frame desde OBS...")
    frame = capture_obs_frame()
    if frame is None:
        print("X No se pudo capturar frame de OBS")
        return
    
    print(f"OK Frame capturado: {frame.shape}")
    
    # Guardar frame para análisis
    cv2.imwrite("debug/targeting_diagnosis_frame.png", frame)
    print("   Guardado: debug/targeting_diagnosis_frame.png")
    
    # 2. Calibrar regiones
    print("\n2. Calibrando regiones...")
    calibrator = ScreenCalibrator()
    success = calibrator.calibrate(frame)
    
    if not success:
        print("X Falló calibración")
        return
    
    print(f"OK Battle region: {calibrator.battle_region}")
    print(f"OK Map region: {calibrator.map_region}")
    print(f"OK Game region: {calibrator.game_region}")
    
    # 3. Inicializar battle reader
    print("\n3. Inicializando BattleListReader...")
    reader = BattleListReader()
    
    # Cargar configuración
    config = Config()
    targeting_config = config.targeting
    
    # Configurar región
    if calibrator.battle_region:
        reader.set_region(*calibrator.battle_region)
    
    # Configurar listas
    attack_list = targeting_config.get('attack_list', [])
    ignore_list = targeting_config.get('ignore_list', [])
    priority_list = targeting_config.get('priority_list', [])
    
    reader.attack_list = set(attack_list)
    reader.ignore_list = set(ignore_list)
    reader.priority_list = set(priority_list)
    
    print(f"   Attack list: {attack_list}")
    print(f"   Ignore list: {ignore_list}")
    print(f"   Priority list: {priority_list}")
    
    # Cargar templates
    loaded = reader.load_monster_templates(attack_list)
    print(f"OK Templates cargados: {loaded}/{len(attack_list)}")
    
    if not reader._name_templates:
        print("X No hay templates cargados")
        return
    
    print(f"   Templates disponibles: {list(reader._name_templates.keys())}")
    
    # 4. Extraer y analizar battle ROI
    print("\n4. Analizando Battle ROI...")
    if calibrator.battle_region:
        x1, y1, x2, y2 = calibrator.battle_region
        battle_roi = frame[y1:y2, x1:x2]
        cv2.imwrite("debug/targeting_battle_roi.png", battle_roi)
        print(f"OK Battle ROI extraído: {battle_roi.shape}")
        print("   Guardado: debug/targeting_battle_roi.png")
        
        # Convertir a grises
        battle_gray = cv2.cvtColor(battle_roi, cv2.COLOR_BGR2GRAY)
        cv2.imwrite("debug/targeting_battle_gray.png", battle_gray)
        print("   Guardado: debug/targeting_battle_gray.png")
    
    # 5. Detectar criaturas
    print("\n5. Detectando criaturas...")
    creatures = reader.read(frame)
    print(f"OK Criaturas detectadas: {len(creatures)}")
    
    for creature in creatures:
        print(f"   - {creature.name} en ({creature.screen_x}, {creature.screen_y})")
    
    # 6. Verificar is_attacking
    print("\n6. Verificando estado de ataque...")
    is_attacking = reader.is_attacking(frame)
    print(f"OK is_attacking: {is_attacking}")
    
    # 7. Análisis detallado de templates
    print("\n7. Análisis detallado de templates...")
    if calibrator.battle_region and battle_roi is not None:
        x1, y1, x2, y2 = calibrator.battle_region
        battle_gray = cv2.cvtColor(battle_roi, cv2.COLOR_BGR2GRAY)
        
        for monster_name, template in reader._name_templates.items():
            if monster_name.lower() in {n.lower() for n in ignore_list}:
                continue
                
            print(f"\n   Analizando template: {monster_name}")
            print(f"   Template shape: {template.shape}")
            print(f"   ROI shape: {battle_gray.shape}")
            
            if battle_gray.shape[0] < template.shape[0] or battle_gray.shape[1] < template.shape[1]:
                print(f"   X Template más grande que ROI")
                continue
            
            res = cv2.matchTemplate(battle_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            print(f"   Max confidence: {max_val:.3f} (threshold: {reader.name_precision})")
            print(f"   Max location: {max_loc}")
            
            if max_val >= reader.name_precision:
                print(f"   OK DETECTADO")
                # Dibujar rectángulo en el ROI
                th, tw = template.shape[:2]
                cv2.rectangle(battle_roi, max_loc, (max_loc[0] + tw, max_loc[1] + th), (0, 255, 0), 2)
            else:
                print(f"   X No detectado")
    
    # Guardar ROI con detecciones
    if calibrator.battle_region:
        cv2.imwrite("debug/targeting_battle_with_detections.png", battle_roi)
        print("\nOK Guardado: debug/targeting_battle_with_detections.png")
    
    print("\n=== DIAGNÓSTICO COMPLETADO ===")

if __name__ == "__main__":
    import os
    os.makedirs("debug", exist_ok=True)
    diagnose_targeting()
