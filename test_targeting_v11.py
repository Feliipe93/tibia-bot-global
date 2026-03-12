#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para el targeting v11 sin OBS.
Usa un frame guardado para probar todas las nuevas funcionalidades.
"""

import cv2
import numpy as np
from config import Config
from targeting.battle_list_reader import BattleListReader
from targeting.targeting_engine import TargetingEngine
from targeting.creature_hp_detector import CreatureHPDetector
from targeting.spell_manager import SpellManager
from screen_calibrator import ScreenCalibrator

def test_targeting_v11():
    """Prueba el sistema de targeting v11 completo."""
    
    print("=== PRUEBA TARGETING V11 ===\n")
    
    # Cargar frame de prueba
    frame = cv2.imread("debug/targeting_diagnosis_frame.png")
    if frame is None:
        print("X No se pudo cargar el frame de prueba")
        return
    
    print(f"OK Frame cargado: {frame.shape}")
    
    # Calibrar regiones
    calibrator = ScreenCalibrator()
    success = calibrator.calibrate(frame)
    
    if not success:
        print("X Falló calibración")
        return
    
    print(f"OK Battle region: {calibrator.battle_region}")
    
    # Inicializar componentes
    config = Config()
    targeting_engine = TargetingEngine()
    
    # Configurar callbacks de prueba
    clicks_realizados = []
    keys_enviadas = []
    logs = []
    
    def mock_click(x, y):
        clicks_realizados.append((x, y))
        print(f"CLICK en ({x}, {y})")
        return True
    
    def mock_key(key):
        keys_enviadas.append(key)
        print(f"TECLA: {key}")
        return True
    
    def mock_log(msg):
        logs.append(msg)
        try:
            print(f"[LOG] {msg}")
        except UnicodeEncodeError:
            print(f"[LOG] {msg.encode('ascii', 'ignore').decode('ascii')}")
    
    # Configurar callbacks
    targeting_engine.set_click_callback(mock_click)
    targeting_engine.set_key_callback(mock_key)
    targeting_engine.set_log_callback(mock_log)
    
    # Configurar región de battle
    targeting_engine.set_battle_region(*calibrator.battle_region)
    
    # Iniciar targeting
    targeting_engine.start()
    
    print("\nProcesando frame...")
    targeting_engine.process_frame(frame)
    
    print(f"\nResultados:")
    print(f"- Criaturas detectadas: {targeting_engine.get_creature_count()}")
    print(f"- Target actual: {targeting_engine.current_target}")
    print(f"- Estado: {targeting_engine.state}")
    print(f"- Clicks realizados: {len(clicks_realizados)}")
    print(f"- Teclas enviadas: {len(keys_enviadas)}")
    
    if clicks_realizados:
        print(f"- Coordenadas de clicks: {clicks_realizados}")
    
    if keys_enviadas:
        print(f"- Teclas: {keys_enviadas}")
    
    # Mostrar criaturas detectadas
    counts = targeting_engine.get_creature_counts_by_name()
    if counts:
        print(f"- Criaturas por nombre:")
        for name, count in counts.items():
            print(f"  * {name}: {count}")
    
    # Probar HP detector
    print(f"\n--- Probando HP Detector ---")
    hp_detector = CreatureHPDetector()
    hp_detector.set_log_callback(mock_log)
    hp_detector.auto_calibrate_regions(frame, calibrator.battle_region)
    
    hp_info = hp_detector.process_frame(frame)
    print(f"- Criatura seleccionada: {hp_info['selected']}")
    if hp_info['selected']:
        print(f"- Nombre: {hp_info['name']}")
        print(f"- HP: {hp_info['hp_percentage']}%")
    
    # Probar spell manager
    print(f"\n--- Probando Spell Manager ---")
    spell_manager = SpellManager()
    spell_manager.set_key_callback(mock_key)
    spell_manager.set_log_callback(mock_log)
    
    # Configurar spells para Amazon
    amazon_spells = {
        'spells_by_count': {
            1: ['f1'],
            2: ['f2', 'f1'],
            3: ['f3', 'f2', 'f1'],
            'default': ['f1']
        },
        'spell_cooldown': 1.0
    }
    spell_manager.configure_spells('amazon', amazon_spells)
    
    # Simular criaturas cercanas
    nearby_creatures = ['amazon', 'rat']
    spells_cast = spell_manager.process_spells_for_creature('amazon', nearby_creatures)
    print(f"- Spells lanzados: {spells_cast}")
    
    # Mostrar estado de spells
    spell_status = spell_manager.get_spell_status()
    if spell_status:
        print(f"- Estado de spells:")
        for spell, status in spell_status.items():
            print(f"  * {spell}: ready={status['ready']}, cooldown={status['cooldown']}s")
    
    targeting_engine.stop()
    print("\n=== PRUEBA COMPLETADA ===")

if __name__ == "__main__":
    test_targeting_v11()
