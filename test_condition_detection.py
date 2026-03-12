#!/usr/bin/env python3
"""
Script para probar el sistema de detección de condiciones
"""

import cv2
import numpy as np
from condition_detector import ConditionDetector
import time

def test_condition_detection():
    """Prueba el sistema de detección con la imagen capturada."""
    
    print("Cargando imagen capturada desde OBS...")
    img = cv2.imread("debug/obs_capture_1773264272.png")
    
    if img is None:
        print("Error: No se pudo cargar la imagen")
        return
    
    print(f"Imagen cargada: {img.shape}")
    
    # Inicializar detector
    detector = ConditionDetector()
    
    # Configurar condiciones de prueba
    test_conditions = {
        'hunger': {'enabled': True, 'hotkey': 'F10', 'threshold': 0.2},
        'poison': {'enabled': True, 'hotkey': 'F2', 'threshold': 0.2},
        'haste': {'enabled': True, 'hotkey': 'F3', 'threshold': 0.2},
        'paralyze': {'enabled': True, 'hotkey': 'F4', 'threshold': 0.2}
    }
    
    for cond_name, cond_config in test_conditions.items():
        detector.configure_condition(cond_name, cond_config)
        print(f"Configurado {cond_name}: threshold={cond_config['threshold']}")
    
    # Calibrar
    print("\nCalibrando detector...")
    calibration_result = detector.calibrate(img)
    
    if calibration_result:
        print("Calibracion exitosa!")
        bar_info = detector.get_bar_info()
        print(f"Barra calibrada: {bar_info}")
        
        # Dibujar región calibrada
        if bar_info:
            h, w = img.shape[:2]
            y = bar_info['row']
            x1 = bar_info['x1']
            x2 = bar_info['x2']
            
            # Dibujar línea de calibración
            cv2.line(img, (x1, y), (x2, y), (0, 255, 0), 2)
            cv2.putText(img, "Barra de Condiciones", (x1, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Guardar imagen con calibración
            cv2.imwrite("debug/calibration_test.png", img)
            print("Imagen con calibracion guardada: debug/calibration_test.png")
        
        # Probar detección
        print("\nProbando detección de condiciones...")
        results = detector.detect_conditions(img)
        
        print("Resultados de detección:")
        for condition_name, detected in results.items():
            status = "DETECTADO" if detected else "no detectado"
            print(f"  {condition_name}: {status}")
        
        # Si no hay detecciones, probar con umbrales más bajos
        if not any(results.values()):
            print("\nNo se detectaron condiciones. Probando con umbrales más bajos...")
            
            for cond_name in test_conditions.keys():
                detector.update_condition(cond_name, True, test_conditions[cond_name]['hotkey'], 0.1)
            
            results2 = detector.detect_conditions(img)
            print("Resultados con umbrales bajos:")
            for condition_name, detected in results2.items():
                status = "DETECTADO" if detected else "no detectado"
                print(f"  {condition_name}: {status}")
        
    else:
        print("Calibracion fallida")

def test_with_condition_image():
    """Prueba con una imagen que tenga condiciones visibles."""
    
    print("\nBuscando imágenes con condiciones...")
    
    # Buscar imágenes de condiciones en assets
    import os
    from pathlib import Path
    
    conditions_dir = Path("assets/conditions")
    if conditions_dir.exists():
        print(f"Templates encontrados: {list(conditions_dir.glob('*.png'))}")
        
        # Probar template matching directo
        img = cv2.imread("debug/obs_capture_1773264272.png")
        detector = ConditionDetector()
        
        if detector.calibrate(img):
            bar_info = detector.get_bar_info()
            if bar_info:
                y = bar_info['row']
                x1 = bar_info['x1']
                x2 = bar_info['x2']
                
                # Extraer región de condiciones
                h, w = img.shape[:2]
                condition_region = img[max(0, y-25):min(h, y+25), max(0, x1-100):min(w, x2+100)]
                
                print(f"Región de condiciones: {condition_region.shape}")
                
                # Probar cada template
                for condition_name, template in detector.templates.items():
                    if template is not None:
                        try:
                            result = cv2.matchTemplate(condition_region, template, cv2.TM_CCOEFF_NORMED)
                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                            
                            print(f"{condition_name}: max_val={max_val:.3f}")
                            
                            if max_val > 0.3:
                                print(f"  -> Posible detección en {max_loc}")
                                
                                # Dibujar rectángulo
                                h_t, w_t = template.shape[:2]
                                cv2.rectangle(condition_region, max_loc, 
                                             (max_loc[0] + w_t, max_loc[1] + h_t), 
                                             (0, 255, 0), 2)
                                
                        except Exception as e:
                            print(f"Error probando {condition_name}: {e}")
                
                # Guardar resultado
                cv2.imwrite("debug/template_matching_test.png", condition_region)
                print("Resultado de template matching guardado")

if __name__ == "__main__":
    print("Prueba del sistema de detección de condiciones")
    print("=" * 50)
    
    test_condition_detection()
    test_with_condition_image()
    
    print("\nPrueba completada. Revisa las imágenes en debug/")
