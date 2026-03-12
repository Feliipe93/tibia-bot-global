import cv2
import numpy as np
import time
from typing import Dict, Optional, List
import os

class ConditionDetector:
    def __init__(self):
        # Rangos de color HSV para cada condición (más específicos)
        self.condition_colors = {
            'haste': [(40, 100, 100), (80, 255, 255)],  # Verde
            'paralyze': [(140, 100, 100), (170, 255, 255)],  # Rosa/Morado
            'poison': [(40, 100, 100), (80, 255, 255)],  # Verde (mismo que haste)
            'burning': [(10, 100, 100), (25, 255, 255)],  # Naranja
            'curse': [(120, 100, 100), (150, 255, 255)],  # Morado
            'hunger': [(20, 100, 100), (35, 255, 255)],  # Amarillo
            'manashield': [(140, 100, 100), (170, 255, 255)],  # Rosa
            'pz_zone': [(0, 0, 100), (180, 50, 255)]  # Blanco
        }
        
        self.confidence_threshold = 0.8
        self.calibrated = False
        self.condition_bar_row = 0
        self.condition_bar_x1 = 0
        self.condition_bar_x2 = 0
        
        # Templates de iconos
        self.templates = {}
        
        # Estado de condiciones
        self.conditions = {
            'haste': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0},
            'paralyze': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0},
            'poison': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0},
            'burning': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0},
            'curse': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0},
            'hunger': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0},
            'manashield': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0},
            'pz_zone': {'enabled': False, 'hotkey': '', 'threshold': 0.8, 'last_triggered': 0.0}
        }
        
        self._load_templates()
    
    def _load_templates(self):
        """Carga los templates PNG de condiciones."""
        template_dir = "images/Conditions"
        if os.path.exists(template_dir):
            for filename in os.listdir(template_dir):
                if filename.endswith('.png'):
                    condition_name = filename.replace('.png', '').lower()
                    template_path = os.path.join(template_dir, filename)
                    try:
                        template = cv2.imread(template_path)
                        if template is not None:
                            self.templates[condition_name] = template
                            print(f"Template cargado: {condition_name}")
                        else:
                            print(f"No se pudo cargar template: {filename}")
                    except Exception as e:
                        print(f"Error cargando template {filename}: {e}")
    
    def calibrate(self, frame: np.ndarray) -> Optional[Dict[str, int]]:
        """
        Calibra la posición de la barra de condiciones usando múltiples métodos mejorados.
        """
        try:
            print(" Calibrando barra de condiciones mejorada...")
            
            h, w = frame.shape[:2]
            
            # Método 1: Búsqueda por líneas horizontales mejorado
            bar_info = self._calibrate_by_lines(frame)
            print(f" Método 1 (líneas): {bar_info}")
            
            # Método 2: Búsqueda por regiones de color mejorado
            if not bar_info:
                bar_info = self._calibrate_by_color_regions(frame)
                print(f" Método 2 (color): {bar_info}")
            
            # Método 3: Búsqueda por detección de iconos mejorado
            if not bar_info:
                bar_info = self._calibrate_by_icon_detection(frame)
                print(f" Método 3 (iconos): {bar_info}")
            
            if bar_info:
                self.condition_bar_row = bar_info['row']
                self.condition_bar_x1 = bar_info['x1']
                self.condition_bar_x2 = bar_info['x2']
                self.calibrated = True
                
                print(f" Barra de condiciones calibrada:")
                print(f"   Y: {self.condition_bar_row}")
                print(f"   X1-X2: {self.condition_bar_x1} - {self.condition_bar_x2}")
                return bar_info
            else:
                print(" No se pudo calibrar la barra de condiciones")
                return False
                
        except Exception as e:
            print(f"Error en calibración mejorada: {e}")
            return False
    
    def _calibrate_by_lines(self, frame: np.ndarray) -> Optional[Dict[str, int]]:
        """Calibración usando detección de líneas horizontales mejorada y enfocada."""
        try:
            h, w = frame.shape[:2]
            
            # ENFOCAR ESPECÍFICAMENTE en el área donde están las condiciones
            # Área: entre la barra de maná y el chat (aprox 80% desde arriba)
            scan_start_y = int(h * 0.65)  # Empezar al 65% desde arriba
            scan_end_y = int(h * 0.85)    # Terminar al 85% desde arriba
            scan_height = scan_end_y - scan_start_y
            
            if scan_height <= 0:
                return None
                
            scan_region = frame[scan_start_y:scan_end_y, :]
            gray = cv2.cvtColor(scan_region, cv2.COLOR_BGR2GRAY)
            
            # Detectar bordes con sensibilidad ajustada
            edges = cv2.Canny(gray, 30, 100)
            
            # Buscar líneas horizontales
            lines = cv2.HoughLinesP(edges, 1, np.pi/2, 50, minLineLength=50, maxLineGap=10)
            
            if lines is not None and len(lines) > 0:
                horizontal_lines = []
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    if abs(y2 - y1) < 3:  # Línea casi horizontal
                        global_y = scan_start_y + y1
                        horizontal_lines.append(global_y)
                
                if horizontal_lines:
                    horizontal_lines.sort()
                    
                    # Buscar la línea más probable para la barra de condiciones
                    # Preferir líneas en la parte inferior del área de escaneo
                    best_line = None
                    for y in reversed(horizontal_lines):  # Empezar desde abajo
                        if scan_start_y < y < scan_end_y - 10:
                            # Verificar si hay estructura de barra en esta línea
                            row_region = frame[y-3:y+3, :]
                            if row_region.size > 0:
                                row_gray = cv2.cvtColor(row_region, cv2.COLOR_BGR2GRAY)
                                
                                # Buscar variación en la línea (indicativo de iconos)
                                row_std = np.std(row_gray)
                                if row_std > 20:  # Hay variación (iconos)
                                    best_line = y
                                    break
                    
                    if best_line:
                        # Encontrar los límites horizontales de la barra
                        row_region = frame[best_line-3:best_line+3, :]
                        row_gray = cv2.cvtColor(row_region, cv2.COLOR_BGR2GRAY)
                        horizontal_sum = np.sum(row_gray, axis=0)
                        
                        # Buscar donde empieza y termina la estructura
                        threshold = np.max(horizontal_sum) * 0.8
                        active_pixels = np.where(horizontal_sum < threshold)[0]
                        
                        if len(active_pixels) > 50:
                            return {
                                'row': best_line,
                                'x1': active_pixels[0],
                                'x2': active_pixels[-1]
                            }
        
        except Exception as e:
            print(f"Error en calibración por líneas enfocada: {e}")
        
        return None
    
    def _calibrate_by_color_regions(self, frame: np.ndarray) -> Optional[Dict[str, int]]:
        """Calibración usando detección de regiones de color enfocada."""
        try:
            h, w = frame.shape[:2]
            
            # ENFOCAR en el área específico donde están las condiciones
            scan_start_y = int(h * 0.65)  # 65% desde arriba
            scan_end_y = int(h * 0.85)    # 85% desde arriba
            scan_height = scan_end_y - scan_start_y
            
            if scan_height <= 0:
                return None
                
            scan_region = frame[scan_start_y:scan_end_y, :]
            hsv = cv2.cvtColor(scan_region, cv2.COLOR_BGR2HSV)
            
            # Buscar colores de condiciones específicos
            color_masks = []
            
            # Verde (poison/haste)
            green_mask = cv2.inRange(hsv, (40, 100, 100), (80, 255, 255))
            color_masks.append(green_mask)
            
            # Amarillo (hunger)
            yellow_mask = cv2.inRange(hsv, (20, 100, 100), (35, 255, 255))
            color_masks.append(yellow_mask)
            
            # Rosa/Morado (paralyze/manashield)
            pink_mask = cv2.inRange(hsv, (140, 100, 100), (170, 255, 255))
            color_masks.append(pink_mask)
            
            # Combinar todas las máscaras
            combined_mask = cv2.bitwise_or(color_masks[0], color_masks[1])
            for mask in color_masks[2:]:
                combined_mask = cv2.bitwise_or(combined_mask, mask)
            
            # Limpiar la máscara
            kernel = np.ones((3, 3), np.uint8)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Buscar el contorno más grande y bien posicionado
                best_contour = None
                best_area = 0
                
                for contour in contours:
                    x, y, w_cont, h_cont = cv2.boundingRect(contour)
                    global_y = scan_start_y + y
                    area = cv2.contourArea(contour)
                    
                    # Filtrar contornos muy pequeños
                    if area < 20:
                        continue
                    
                    # Preferir contornos en el área central horizontal
                    center_x = x + w_cont // 2
                    if w * 0.2 < center_x < w * 0.8 and area > best_area:
                        best_contour = contour
                        best_area = area
                
                if best_contour:
                    x, y, w_cont, h_cont = cv2.boundingRect(best_contour)
                    bar_y = scan_start_y + y
                    
                    # Estimar límites horizontales basados en el contorno
                    bar_x1 = max(0, x - 20)
                    bar_x2 = min(w, x + w_cont + 20)
                    
                    return {
                        'row': bar_y,
                        'x1': bar_x1,
                        'x2': bar_x2
                    }
        
        except Exception as e:
            print(f"Error en calibración por color enfocada: {e}")
        
        return None
    
    def _calibrate_by_icon_detection(self, frame: np.ndarray) -> Optional[Dict[str, int]]:
        """Calibración usando detección de iconos conocidos enfocada."""
        try:
            h, w = frame.shape[:2]
            
            # ENFOCAR en el área específico donde están las condiciones
            scan_start_y = int(h * 0.65)  # 65% desde arriba
            scan_end_y = int(h * 0.85)    # 85% desde arriba
            scan_height = scan_end_y - scan_start_y
            
            if scan_height <= 0:
                return None
                
            scan_region = frame[scan_start_y:scan_end_y, :]
            
            # Buscar iconos conocidos en el área
            best_matches = []
            for condition_name, template in self.templates.items():
                if template is None or condition_name == 'base_image':
                    continue
                    
                # Template matching con umbral ajustado
                result = cv2.matchTemplate(scan_region, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > 0.7:  # Umbral alto para evitar falsos positivos
                    global_y = scan_start_y + max_loc[1]
                    best_matches.append({
                        'condition': condition_name,
                        'y': global_y,
                        'confidence': max_val,
                        'loc': max_loc
                    })
            
            if best_matches:
                # Agrupar detecciones por Y (misma fila)
                best_matches.sort(key=lambda x: x['y'])
                
                # Buscar el grupo con más detecciones
                if len(best_matches) >= 1:
                    base_y = best_matches[0]['y']
                    nearby_matches = [m for m in best_matches if abs(m['y'] - base_y) < 20]
                    
                    if nearby_matches:
                        # Calcular posición promedio
                        avg_y = int(np.mean([m['y'] for m in nearby_matches]))
                        
                        # Estimar límites horizontales
                        min_x = min([m['loc'][0] for m in nearby_matches])
                        max_x = max([m['loc'][0] + self.templates[nearby_matches[0]['condition']].shape[1] for m in nearby_matches])
                        
                        return {
                            'row': avg_y,
                            'x1': max(0, min_x - 30),
                            'x2': min(w, max_x + 30)
                        }
        
        except Exception as e:
            print(f"Error en calibración por iconos enfocada: {e}")
        
        return None
    
    def detect_conditions(self, frame: np.ndarray) -> Dict[str, bool]:
        """Detecta condiciones en el frame actual."""
        results = {}
        current_time = time.time()
        
        if not self.calibrated:
            # Intentar calibrar
            if self.calibrate(frame):
                print(" Barra calibrada, iniciando detección...")
            return results
        
        try:
            # Extraer región de condiciones más grande
            y1 = max(0, self.condition_bar_row - 25)
            y2 = min(frame.shape[0], self.condition_bar_row + 25)
            x1 = max(0, self.condition_bar_x1 - 100)
            x2 = min(frame.shape[1], self.condition_bar_x2 + 100)
            condition_region = frame[y1:y2, x1:x2]
            
            # Detectar cada condición activa
            for condition_name, condition_config in self.conditions.items():
                if not condition_config.get('enabled', False):
                    continue
                
                # Verificar cooldown
                if current_time - condition_config.get('last_triggered', 0.0) < condition_config.get('cooldown', 1.0):
                    results[condition_name] = False
                    continue
                
                # Usar detección híbrida
                threshold = condition_config.get('threshold', self.confidence_threshold)
                detected = self._detect_hybrid(condition_region, condition_name, threshold)
                
                if detected:
                    condition_config['last_triggered'] = current_time
                    results[condition_name] = True
                    print(f" {condition_name.upper()} DETECTADO!")
                else:
                    results[condition_name] = False
                    
            # Mostrar resumen solo si hay detecciones
            detected_conds = [name for name, detected in results.items() if detected]
            if detected_conds:
                print(f" Condiciones detectadas: {detected_conds}")
                    
        except Exception as e:
            print(f"Error en detección mejorada: {e}")
        
        return results
    
    def _detect_hybrid(self, region: np.ndarray, condition_name: str, threshold: float) -> bool:
        """Detección híbrida combinando template y color."""
        template_result = self._detect_by_template(region, condition_name, threshold)
        color_result = self._detect_by_color(region, condition_name, threshold)
        
        # REQUERIR AMBOS MÉTODOS para reducir falsos positivos
        result = template_result and color_result
        
        if template_result or color_result:
            print(f" {condition_name}: template={template_result}, color={color_result}, hybrid={result}")
        
        return result
    
    def _detect_by_template(self, region: np.ndarray, condition_name: str, threshold: float) -> bool:
        """Detección usando template matching mejorada."""
        # Primero intentar con el nombre exacto
        if condition_name in self.templates and self.templates[condition_name] is not None:
            template = self.templates[condition_name]
            try:
                result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val >= threshold:
                    print(f"  Template {condition_name} detectado con confianza: {max_val:.3f}")
                    return True
            except Exception as e:
                print(f"Error en template matching para {condition_name}: {e}")
        
        # Si no funciona, intentar con variantes
        for template_name, template in self.templates.items():
            if template is None:
                continue
                
            # Buscar si el template_name contiene el condition_name
            if condition_name.lower() in template_name.lower():
                try:
                    result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    
                    if max_val >= threshold:
                        print(f"  Template variant {template_name} detectado para {condition_name} con confianza: {max_val:.3f}")
                        return True
                except Exception as e:
                    print(f"Error en template matching para {template_name}: {e}")
        
        return False
    
    def _detect_by_color(self, region: np.ndarray, condition_name: str, threshold: float) -> bool:
        """Detección usando análisis de color más estricta."""
        if condition_name not in self.condition_colors:
            return False
        
        try:
            hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            color_ranges = self.condition_colors[condition_name]
            
            # Crear máscara para el rango de color
            if len(color_ranges) >= 2:
                lower, upper = color_ranges[0], color_ranges[1]
                mask = cv2.inRange(hsv, lower, upper)
                
                # Encontrar contornos
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Filtrar contornos muy pequeños (ruido)
                    valid_contours = [c for c in contours if cv2.contourArea(c) > 5]
                    
                    if valid_contours:
                        # Calcular área total
                        total_area = sum(cv2.contourArea(contour) for contour in valid_contours)
                        region_area = region.shape[0] * region.shape[1]
                        coverage = total_area / region_area
                        
                        # Requerir cobertura mínima más alta
                        return coverage >= (threshold * 2)  # Más estricto
        
        except Exception as e:
            print(f"Error en detección por color para {condition_name}: {e}")
        
        return False
    
    def update_condition(self, condition_name: str, enabled: bool, hotkey: str, threshold: float):
        """Actualiza la configuración de una condición."""
        if condition_name in self.conditions:
            self.conditions[condition_name]['enabled'] = enabled
            self.conditions[condition_name]['hotkey'] = hotkey
            self.conditions[condition_name]['threshold'] = threshold
    
    def get_all_conditions(self) -> Dict:
        """Retorna una copia de todas las condiciones."""
        return self.conditions.copy()
    
    def get_bar_info(self) -> Optional[Dict[str, int]]:
        """Obtiene información de la barra calibrada."""
        if self.calibrated:
            return {
                'row': self.condition_bar_row,
                'x1': self.condition_bar_x1,
                'x2': self.condition_bar_x2
            }
        return None
    
    def force_recalibration(self):
        """Fuerza la recalibración."""
        self.calibrated = False
        print(" Recalibración forzada de la barra de condiciones")
