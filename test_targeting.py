#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar que el targeting funciona correctamente.
"""

import cv2
import numpy as np
from config import Config
from targeting.battle_list_reader import BattleListReader
from targeting.targeting_engine import TargetingEngine
from screen_calibrator import ScreenCalibrator

def test_targeting():
    """Prueba el sistema de targeting completo."""
    
    print("=== PRUEBA DE TARGETING ===\n")
    
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
    
    # Inicializar targeting engine
    config = Config()
    targeting_engine = TargetingEngine()
    targeting_engine.configure(config.targeting)
    targeting_engine.set_battle_region(*calibrator.battle_region)
    
    # Configurar callbacks de prueba
    clicks_realizados = []
    
    def mock_click(x, y):
        clicks_realizados.append((x, y))
        print(f"CLICK en ({x}, {y})")
        return True
    
    def mock_log(msg):
        try:
            print(f"[LOG] {msg}")
        except UnicodeEncodeError:
            print(f"[LOG] {msg.encode('ascii', 'ignore').decode('ascii')}")
    
    targeting_engine.set_click_callback(mock_click)
    targeting_engine.set_log_callback(mock_log)
    
    # Iniciar targeting
    targeting_engine.start()
    
    print("\nProcesando frame...")
    targeting_engine.process_frame(frame)
    
    print(f"\nResultados:")
    print(f"- Criaturas detectadas: {targeting_engine.get_creature_count()}")
    print(f"- Target actual: {targeting_engine.current_target}")
    print(f"- Estado: {targeting_engine.state}")
    print(f"- Clicks realizados: {len(clicks_realizados)}")
    
    if clicks_realizados:
        print(f"- Coordenadas de clicks: {clicks_realizados}")
    
    # Mostrar criaturas detectadas
    counts = targeting_engine.get_creature_counts_by_name()
    if counts:
        print(f"- Criaturas por nombre:")
        for name, count in counts.items():
            print(f"  * {name}: {count}")
    
    targeting_engine.stop()
    print("\n=== PRUEBA COMPLETADA ===")

if __name__ == "__main__":
    test_targeting()
