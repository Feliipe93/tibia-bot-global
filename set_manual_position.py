import cv2
import numpy as np
from condition_detector import ConditionDetector

print("=== SCRIPT PARA CONFIGURAR POSICIÓN MANUAL ===")
print()

def set_manual_position(detector, x1, y, x2):
    """Configura manualmente la posición de la barra de condiciones."""
    detector.calibrated = True
    detector.condition_bar_row = y
    detector.condition_bar_x1 = x1
    detector.condition_bar_x2 = x2
    print(f"Posición manual configurada:")
    print(f"  Y: {y}")
    print(f"  X1: {x1}")
    print(f"  X2: {x2}")

def test_detection(detector, frame):
    """Prueba la detección con la posición configurada."""
    print("\nProbando detección con posición manual...")
    
    # Configurar condiciones de prueba
    detector.update_condition('hunger', True, 'F10', 0.8)
    detector.update_condition('poison', True, 'F3', 0.8)
    
    # Probar detección
    results = detector.detect_conditions(frame)
    
    print("Resultados de detección:")
    for condition, detected in results.items():
        status = "DETECTADO" if detected else "No detectado"
        print(f"  {condition}: {status}")
    
    return results

# Ejemplo de uso
if __name__ == "__main__":
    print("Este script te permite configurar manualmente la posición de la barra")
    print("Usa las coordenadas exactas que obtuviste del script anterior")
    print()
    
    # Coordenadas de ejemplo (reemplaza con las tuyas)
    print("Ejemplo de coordenadas (reemplaza con las tuyas):")
    print("  X1: 400  (inicio de la barra)")
    print("  Y:  380  (fila de la barra)")
    print("  X2: 600  (fin de la barra)")
    print()
    
    # Crear detector y configurar posición de ejemplo
    detector = ConditionDetector()
    
    # Crea un frame de prueba
    h, w = 480, 640
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Dibujar una barra simulada en la posición de ejemplo
    y_example = 380
    cv2.rectangle(frame, (400, y_example-5), (600, y_example+5), (0, 255, 255), -1)
    
    print("=== CONFIGURACIÓN MANUAL ===")
    print("Para configurar manualmente, ejecuta:")
    print()
    print("from set_manual_position import set_manual_position, test_detection")
    print("from condition_detector import ConditionDetector")
    print("import numpy as np")
    print()
    print("# Crear detector")
    print("detector = ConditionDetector()")
    print()
    print("# Configurar posición con TUS coordenadas")
    print("set_manual_position(detector, X1, Y, X2)")
    print()
    print("# Probar detección")
    print("frame = np.zeros((480, 640, 3), dtype=np.uint8)")
    print("results = test_detection(detector, frame)")
    print()
    print("Reemplaza X1, Y, X2 con tus coordenadas reales")
