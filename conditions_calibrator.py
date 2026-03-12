import cv2
import numpy as np
import time
from typing import Dict, Optional, Tuple, Any
import json
import os

class ConditionCalibrator:
    def __init__(self, obs_capture=None):
        self.obs_capture = obs_capture
        self.calibration_active = False
        self.selection_start = None
        self.selection_end = None
        self.current_frame = None
        
        # Configuración por defecto para 1366x768
        self.default_config = {
            'resolution': [1366, 768],
            'conditions_bar': {
                'x1': 200,
                'y': 400,  # Justo debajo de mana (aprox)
                'x2': 600,
                'height': 20
            }
        }
        
        # Cargar configuración guardada si existe
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """Carga configuración desde archivo."""
        config_file = "conditions_calibration.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error cargando config: {e}")
        return self.default_config.copy()
    
    def save_config(self):
        """Guarda configuración a archivo."""
        config_file = "conditions_calibration.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"Configuración guardada en {config_file}")
        except Exception as e:
            print(f"Error guardando config: {e}")
    
    def start_calibration(self):
        """Inicia el modo de calibración."""
        self.calibration_active = True
        self.selection_start = None
        self.selection_end = None
        print("=== INICIANDO CALIBRACIÓN MANUAL DE CONDICIONES ===")
        print("Instrucciones:")
        print("1. Haz clic y arrastra para seleccionar el área de la barra de condiciones")
        print("2. Debe estar justo debajo de la barra de maná")
        print("3. Presiona 'g' para guardar, 'r' para reiniciar, 'ESC' para cancelar")
        return True
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Captura frame desde OBS."""
        if self.obs_capture:
            try:
                frame = self.obs_capture.capture_source()
                if frame is not None:
                    self.current_frame = frame.copy()
                    return frame
            except Exception as e:
                print(f"Error capturando frame: {e}")
        return None
    
    def draw_selection_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Dibuja el overlay de selección en el frame."""
        if frame is None:
            return None
            
        display = frame.copy()
        h, w = frame.shape[:2]
        
        # Dibujar área configurada actual
        if 'conditions_bar' in self.config:
            bar = self.config['conditions_bar']
            cv2.rectangle(display, 
                        (bar['x1'], bar['y']), 
                        (bar['x2'], bar['y'] + bar['height']), 
                        (0, 255, 0), 2)
            cv2.putText(display, "CONFIGURADO", (bar['x1'], bar['y'] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Dibujar selección actual
        if self.selection_start and self.selection_end:
            cv2.rectangle(display, self.selection_start, self.selection_end, (0, 255, 255), 2)
            
            # Mostrar dimensiones
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            
            cv2.putText(display, f"Area: {width}x{height}", (x1, y1 - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            cv2.putText(display, f"Pos: ({x1},{y1})", (x1, y1 + height + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
        # Instrucciones
        cv2.putText(display, "Click & Arrastrar: Seleccionar | G: Guardar | R: Reiniciar | ESC: Salir", 
                   (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return display
    
    def handle_mouse_click(self, event, x, y, flags, param):
        """Maneja eventos del mouse para selección."""
        if not self.calibration_active:
            return
            
        if event == cv2.EVENT_LBUTTONDOWN:
            self.selection_start = (x, y)
            self.selection_end = None
            print(f"Inicio selección en: ({x}, {y})")
            
        elif event == cv2.EVENT_MOUSEMOVE and flags == cv2.EVENT_FLAG_LBUTTON:
            if self.selection_start:
                self.selection_end = (x, y)
                
        elif event == cv2.EVENT_LBUTTONUP:
            if self.selection_start:
                self.selection_end = (x, y)
                print(f"Fin selección en: ({x}, {y})")
                
                # Calcular área
                x1 = min(self.selection_start[0], self.selection_end[0])
                y1 = min(self.selection_start[1], self.selection_end[1])
                x2 = max(self.selection_start[0], self.selection_end[0])
                y2 = max(self.selection_start[1], self.selection_end[1])
                
                width = x2 - x1
                height = y2 - y1
                
                print(f"Área seleccionada: {width}x{height} píxeles")
                print(f"Coordenadas: X1={x1}, Y1={y1}, X2={x2}, Y2={y2}")
    
    def save_selection(self):
        """Guarda la selección actual como configuración."""
        if not self.selection_start or not self.selection_end:
            print("Error: No hay selección para guardar")
            return False
            
        # Calcular coordenadas normalizadas
        x1 = min(self.selection_start[0], self.selection_end[0])
        y1 = min(self.selection_start[1], self.selection_end[1])
        x2 = max(self.selection_start[0], self.selection_end[0])
        y2 = max(self.selection_start[1], self.selection_end[1])
        
        # Actualizar configuración
        self.config['conditions_bar'] = {
            'x1': x1,
            'y': y1,
            'x2': x2,
            'height': y2 - y1,
            'center_x': (x1 + x2) // 2,
            'center_y': (y1 + y2) // 2
        }
        
        # Guardar en archivo
        self.save_config()
        
        print("=== CONFIGURACIÓN GUARDADA ===")
        print(f"Barra de condiciones:")
        print(f"  X1: {x1}")
        print(f"  Y:  {y1}")
        print(f"  X2: {x2}")
        print(f"  Alto: {y2 - y1}")
        print(f"  Centro: ({(x1 + x2) // 2}, {(y1 + y2) // 2})")
        
        return True
    
    def reset_selection(self):
        """Reinicia la selección actual."""
        self.selection_start = None
        self.selection_end = None
        print("Selección reiniciada")
    
    def stop_calibration(self):
        """Detiene el modo de calibración."""
        self.calibration_active = False
        self.selection_start = None
        self.selection_end = None
        print("Calibración detenida")
    
    def get_config_for_detector(self) -> Dict[str, int]:
        """Retorna configuración en formato para ConditionDetector."""
        if 'conditions_bar' in self.config:
            bar = self.config['conditions_bar']
            return {
                'row': bar['y'],
                'x1': bar['x1'],
                'x2': bar['x2']
            }
        return None
    
    def apply_to_detector(self, detector):
        """Aplica la configuración al ConditionDetector."""
        config = self.get_config_for_detector()
        if config:
            detector.calibrated = True
            detector.condition_bar_row = config['row']
            detector.condition_bar_x1 = config['x1']
            detector.condition_bar_x2 = config['x2']
            print("Configuración aplicada al ConditionDetector")
            return True
        return False
    
    def run_calibration_window(self):
        """Ejecuta la ventana de calibración interactiva."""
        if not self.start_calibration():
            return False
            
        cv2.namedWindow("Calibración de Condiciones")
        cv2.setMouseCallback("Calibración de Condiciones", self.handle_mouse_click)
        
        print("Ventana de calibración abierta. Presiona ESC para salir.")
        
        while self.calibration_active:
            # Capturar frame
            frame = self.capture_frame()
            if frame is None:
                # Frame de prueba si no hay OBS
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "Esperando frame de OBS...", (50, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Dibujar overlay
            display = self.draw_selection_overlay(frame)
            if display is not None:
                cv2.imshow("Calibración de Condiciones", display)
            
            # Manejar teclas
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                self.stop_calibration()
                break
            elif key == ord('g'):  # Guardar
                self.save_selection()
            elif key == ord('r'):  # Reiniciar
                self.reset_selection()
        
        cv2.destroyAllWindows()
        return True

# Función de logging
def log_calibration(message: str, level: str = "INFO"):
    """Función de logging para calibración."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    
    # Guardar en archivo de log
    try:
        with open("conditions_calibration.log", "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"Error escribiendo log: {e}")

if __name__ == "__main__":
    print("=== MÓDULO DE CALIBRACIÓN MANUAL DE CONDICIONES ===")
    print("Para usar desde el GUI:")
    print("1. Importar: from conditions_calibrator import ConditionCalibrator")
    print("2. Crear: calibrator = ConditionCalibrator(obs_capture)")
    print("3. Iniciar: calibrator.run_calibration_window()")
    print("4. Aplicar: calibrator.apply_to_detector(detector)")
