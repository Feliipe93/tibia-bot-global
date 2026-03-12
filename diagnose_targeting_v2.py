#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_targeting_v2.py - Diagnóstico completo del targeting V2
Verifica por qué no está funcionando aunque está habilitado.
"""

import cv2
import numpy as np
from obswebsocket import obsws, requests as obs_requests
from config import Config
from targeting.battle_list_reader import BattleListReader
from targeting.targeting_engine import TargetingEngine
from targeting.creature_hp_detector import CreatureHPDetector
from targeting.spell_manager import SpellManager
from screen_calibrator import ScreenCalibrator
import json

def diagnose_targeting_v2():
    """Diagnóstico completo del targeting V2."""
    
    print("=== DIAGNÓSTICO TARGETING V2 ===\n")
    
    # 1. Verificar configuración
    print("1. [LIST] VERIFICANDO CONFIGURACION...")
    try:
        config = Config()
        targeting_config = config.targeting
        
        print(f"   [OK] Targeting enabled: {targeting_config.get('enabled', False)}")
        print(f"   [OK] Auto attack: {targeting_config.get('auto_attack', False)}")
        print(f"   [OK] Chase monsters: {targeting_config.get('chase_monsters', False)}")
        print(f"   [OK] Attack list: {targeting_config.get('attack_list', [])}")
        print(f"   [OK] Creature profiles: {list(targeting_config.get('creature_profiles', {}).keys())}")
        
        if not targeting_config.get('enabled', False):
            print("   [ERROR] TARGETING NO ESTÁ HABILITADO EN CONFIG")
            return False
            
        if not targeting_config.get('attack_list', []):
            print("   [ERROR] NO HAY CRIATURAS EN LA ATTACK LIST")
            return False
            
    except Exception as e:
        print(f"   [ERROR] Error leyendo configuración: {e}")
        return False
    
    # 2. Conectar a OBS y obtener frame
    print("\n2. [OBS] OBTENIENDO FRAME DE OBS...")
    try:
        # Cargar configuración
        config = Config()
        obs_config = config.data.get('obs', {})
        
        host = obs_config.get('host', 'localhost')
        port = obs_config.get('port', 4455)
        password = obs_config.get('password', '')
        source_name = obs_config.get('source_name', 'Captura de juego')
        
        print(f"   Conectando a OBS en {host}:{port}")
        
        # Conectar a OBS
        ws = obsws(host, port, password)
        ws.connect()
        
        # Obtener screenshot
        response = ws.call('GetSourceScreenshot', {
            'sourceName': source_name,
            'imageFormat': 'png',
            'width': 1920,
            'height': 1080,
            'compressionQuality': -1
        })
        
        if 'imageData' in response.datain:
            import base64
            image_data = base64.b64decode(response.datain['imageData'])
            frame = cv2.imdecode(np.frombuffer(image_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            
            if frame is None:
                print("   [ERROR] No se pudo decodificar la imagen")
                return False
                
            print(f"   [OK] Frame obtenido: {frame.shape}")
            
            # Guardar frame para análisis
            cv2.imwrite("debug/diagnosis_current_frame.png", frame)
            print("   [OK] Frame guardado en debug/diagnosis_current_frame.png")
        else:
            print("   [ERROR] No se pudo obtener screenshot de OBS")
            return False
            
        ws.disconnect()
        
    except Exception as e:
        print(f"   [ERROR] Error conectando a OBS: {e}")
        return False
    
    # 3. Calibrar regiones
    print("\n3. [TARGET] CALIBRANDO REGIONES...")
    try:
        calibrator = ScreenCalibrator()
        success = calibrator.calibrate(frame)
        
        if not success:
            print(f"   [ERROR] Falló calibración: {calibrator.last_error}")
            return False
            
        print(f"   [OK] Battle region: {calibrator.battle_region}")
        print(f"   [OK] Game region: {calibrator.game_region}")
        print(f"   [OK] Player center: {calibrator.player_center}")
        
    except Exception as e:
        print(f"   [ERROR] Error en calibración: {e}")
        return False
    
    # 4. Probar Battle List Reader
    print("\n4. [MONSTER] PROBANDO BATTLE LIST READER...")
    try:
        battle_reader = BattleListReader()
        
        # Configurar región
        if calibrator.battle_region:
            battle_reader.set_battle_region(*calibrator.battle_region)
        
        # Cargar templates
        attack_list = targeting_config.get('attack_list', [])
        if attack_list:
            battle_reader.load_monster_templates(attack_list)
            print(f"   [OK] Templates cargados: {len(battle_reader._name_templates)}")
            print(f"   [LIST] Templates disponibles: {list(battle_reader._name_templates.keys())}")
        else:
            print("   [ERROR] No hay criaturas en attack_list para cargar templates")
            return False
        
        # Leer battle list
        creatures = battle_reader.read(frame)
        print(f"   [OK] Criaturas detectadas: {len(creatures)}")
        
        if creatures:
            for creature in creatures[:5]:  # Mostrar primeras 5
                print(f"      - {creature.name} en ({creature.screen_x}, {creature.screen_y})")
        else:
            print("   [ERROR] NO SE DETECTARON CRIATURAS EN LA BATTLE LIST")
            
            # Guardar región de battle list para análisis
            if calibrator.battle_region:
                x1, y1, x2, y2 = calibrator.battle_region
                battle_roi = frame[y1:y2, x1:x2]
                cv2.imwrite("debug/diagnosis_battle_region.png", battle_roi)
                print("   [CAMERA] Región de battle list guardada en debug/diagnosis_battle_region.png")
            
            return False
            
    except Exception as e:
        print(f"   [ERROR] Error en battle list reader: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. Probar Targeting Engine
    print("\n5. [SWORD] PROBANDO TARGETING ENGINE...")
    try:
        targeting_engine = TargetingEngine()
        
        # Configurar callbacks
        clicks = []
        keys = []
        logs = []
        
        def mock_click(x, y):
            clicks.append((x, y))
            print(f"   [CLICK] CLICK en ({x}, {y})")
            return True
        
        def mock_key(key):
            keys.append(key)
            print(f"   [KEY] TECLA: {key}")
            return True
        
        def mock_log(msg):
            logs.append(msg)
            try:
                print(f"   [LOG] LOG: {msg}")
            except UnicodeEncodeError:
                print(f"   [LOG] LOG: {msg.encode('ascii', 'ignore').decode('ascii')}")
        
        targeting_engine.set_click_callback(mock_click)
        targeting_engine.set_key_callback(mock_key)
        targeting_engine.set_log_callback(mock_log)
        
        # Configurar
        targeting_engine.set_battle_region(*calibrator.battle_region)
        targeting_engine.configure(targeting_config)
        
        # Iniciar
        targeting_engine.start()
        print("   [OK] Targeting engine iniciado")
        
        # Procesar frame
        print("   🔄 Procesando frame...")
        targeting_engine.process_frame(frame)
        
        # Ver resultados
        status = targeting_engine.get_status()
        print(f"   [OK] Estado: {status['state']}")
        print(f"   [OK] Target actual: {status['current_target']}")
        print(f"   [OK] Criaturas: {status['monster_count']}")
        print(f"   [OK] Clicks realizados: {len(clicks)}")
        print(f"   [OK] Teclas enviadas: {len(keys)}")
        
        if status['state'] == 'idle' and len(creatures) > 0:
            print("   [ERROR] TARGETING EN IDLE PERO HAY CRIATURAS - PROBLEMA")
            return False
        
        targeting_engine.stop()
        
    except Exception as e:
        print(f"   [ERROR] Error en targeting engine: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 6. Probar HP Detector
    print("\n6. [HP] PROBANDO HP DETECTOR...")
    try:
        hp_detector = CreatureHPDetector()
        hp_detector.set_log_callback(lambda msg: print(f"   [HP] HP: {msg}"))
        
        # Auto-configurar
        if calibrator.battle_region:
            hp_detector.auto_calibrate_regions(frame, calibrator.battle_region)
        
        # Procesar frame
        hp_info = hp_detector.process_frame(frame)
        print(f"   [OK] Criatura seleccionada: {hp_info['selected']}")
        if hp_info['selected']:
            print(f"   [OK] Nombre: {hp_info['name']}")
            print(f"   [OK] HP: {hp_info['hp_percentage']}%")
        
    except Exception as e:
        print(f"   [ERROR] Error en HP detector: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 7. Probar Spell Manager
    print("\n7. [SPELL] PROBANDO SPELL MANAGER...")
    try:
        spell_manager = SpellManager()
        spell_manager.set_log_callback(lambda msg: print(f"   [SPELL] Spell: {msg}"))
        
        # Configurar spells de prueba
        test_spells = {
            'spells_by_count': {
                1: ['f1'],
                2: ['f2', 'f1'],
                3: ['f3', 'f2', 'f1'],
                'default': ['f1']
            },
            'spell_cooldown': 1.0
        }
        spell_manager.configure_spells('test', test_spells)
        
        # Simular criaturas
        nearby = ['amazon', 'rat']
        result = spell_manager.process_spells_for_creature('test', nearby)
        print(f"   [OK] Spells procesados: {result}")
        
    except Exception as e:
        print(f"   [ERROR] Error en spell manager: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n=== DIAGNOSTICO COMPLETADO ===")
    print("[OK] Todos los componentes funcionan correctamente")
    print("[OK] Si el targeting no funciona en el bot principal, revisa:")
    print("   1. Que OBS esté capturando la ventana correcta")
    print("   2. Que la battle list sea visible en el juego")
    print("   3. Que las criaturas estén en la attack list")
    print("   4. Que los templates de criaturas existan")
    print("   5. Que la calibración detecte las regiones correctamente")
    
    return True

if __name__ == "__main__":
    import os
    os.makedirs("debug", exist_ok=True)
    
    success = diagnose_targeting_v2()
    if success:
        print("\n[TARGET] DIAGNOSTICO EXITOSO - El targeting V2 funciona correctamente")
    else:
        print("\n[ERROR] DIAGNÓSTICO FALLÓ - Hay problemas que resolver")
