#!/usr/bin/env python3
"""
Sistema mejorado de detección de condiciones para Tibia
Modular y adaptable como las barras de HP/Mana
"""

import cv2
import numpy as np
import time
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

class EnhancedConditionDetector:
    """Detector mejorado de condiciones con múltiples métodos de detección."""
    
    def __init__(self):
        self.templates_dir = Path("assets/conditions")
        self.templates = {}
        self.conditions = {}
        
        # Calibración
        self.calibrated = False
        self.condition_bar_row = None
        self.condition_bar_x1 = None
        self.condition_bar_x2 = None
        
        # Configuración de detección
        self.detection_methods = ['template', 'color', 'edge']
        self.confidence_threshold = 0.4  # Más bajo por defecto
        
        # Cargar todos los templates
        self._load_all_templates()
        
        # Configuración de colores para cada condición
        self.condition_colors = {
            'haste': [(0, 255, 0), (50, 255, 50)],      # Verde
            'paralyze': [(0, 0, 255), (50, 50, 255)],    # Rojo
            'poison': [(0, 255, 255), (50, 255, 255)],    # Amarillo
            'burning': [(0, 100, 255), (50, 150, 255)],  # Naranja
            'curse': [(128, 0, 128), (178, 50, 178)],    # Púrpura
            'hunger': [(0, 165, 255), (50, 215, 255)],  # Amarillo oscuro
            'manashield': [(255, 0, 255), (255, 50, 255)], # Magenta
            'pz_zone': [(255, 255, 255), (255, 255, 255)] # Blanco
        }
    
    def _load_all_templates(self):
        """Carga todos los templates PNG disponibles."""
        if not self.templates_dir.exists():
            print(f"Directorio de templates no encontrado: {self.templates_dir}")
            return
        
        for template_file in self.templates_dir.glob("*.png"):
            condition_name = template_file.stem
            try:
                template = cv2.imread(str(template_file), cv2.IMREAD_COLOR)
                if template is not None:
                    self.templates[condition_name] = template
                    print(f"Template cargado: {condition_name}")
                else:
                    print(f"No se pudo cargar template: {template_file}")
            except Exception as e:
                print(f"Error cargando template {template_file}: {e}")
    
    def configure_condition(self, condition_name: str, config: Dict[str, Any]):
        """Configura una condición específica."""
        self.conditions[condition_name] = {
            'enabled': config.get('enabled', False),
            'hotkey': config.get('hotkey', ''),
            'threshold': config.get('threshold', self.confidence_threshold),
            'cooldown': config.get('cooldown', 1.0),
            'last_triggered': 0.0,
            'detection_method': config.get('detection_method', 'template')
        }
    
    def calibrate_conditions_bar(self, frame: np.ndarray) -> bool:
        """
        Calibra la posición de la barra de condiciones usando múltiples métodos.
        """
        try:
            print("🔍 Calibrando barra de condiciones mejorada...")
            
            h, w = frame.shape[:2]
            
            # Método 1: Búsqueda por líneas horizontales (método actual)
            bar_info = self._calibrate_by_lines(frame)
            
            # Método 2: Búsqueda por regiones de color
            if not bar_info:
                bar_info = self._calibrate_by_color_regions(frame)
            
            # Método 3: Búsqueda por detección de iconos
            if not bar_info:
                bar_info = self._calibrate_by_icon_detection(frame)
            
            if bar_info:
                self.condition_bar_row = bar_info['row']
                self.condition_bar_x1 = bar_info['x1']
                self.condition_bar_x2 = bar_info['x2']
                self.calibrated = True
                
                print(f"✅ Barra de condiciones calibrada:")
                print(f"   Y: {self.condition_bar_row}")
                print(f"   X1-X2: {self.condition_bar_x1} - {self.condition_bar_x2}")
                return True
            else:
                print("❌ No se pudo calibrar la barra de condiciones")
                return False
                
        except Exception as e:
            print(f"Error en calibración mejorada: {e}")
            return False
    
    def _calibrate_by_lines(self, frame: np.ndarray) -> Optional[Dict[str, int]]:
        """Calibración usando detección de líneas horizontales."""
        try:
            h, w = frame.shape[:2]
            scan_height = min(200, h // 3)
            scan_region = frame[h - scan_height:h, :]
            
            gray = cv2.cvtColor(scan_region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            lines = cv2.HoughLinesP(edges, 1, np.pi/2, 100, minLineLength=50, maxLineGap=10)
            
            if lines is not None and len(lines) > 0:
                # Encontrar la línea más baja
                lowest_y = 0
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    global_y = (h - scan_height) + y1
                    if global_y > lowest_y:
                        lowest_y = global_y
                
                if lowest_y > h - 100:  # Validar que esté en la parte inferior
                    # Estimar límites horizontales
                    row_region = frame[lowest_y-5:lowest_y+5, :]
                    row_gray = cv2.cvtColor(row_region, cv2.COLOR_BGR2GRAY)
                    horizontal_sum = np.sum(row_gray, axis=0)
                    threshold = np.max(horizontal_sum) * 0.3
                    active_pixels = np.where(horizontal_sum > threshold)[0]
                    
                    if len(active_pixels) > 0:
                        return {
                            'row': lowest_y,
                            'x1': active_pixels[0],
                            'x2': active_pixels[-1]
                        }
        except Exception as e:
            print(f"Error en calibración por líneas: {e}")
        
        return None
    
    def _calibrate_by_color_regions(self, frame: np.ndarray) -> Optional[Dict[str, int]]:
        """Calibración usando detección de regiones de color."""
        try:
            h, w = frame.shape[:2]
            
            # Buscar en la parte inferior
            scan_region = frame[h - 150:h, :]
            hsv = cv2.cvtColor(scan_region, cv2.COLOR_BGR2HSV)
            
            # Buscar múltiples colores característicos
            color_masks = []
            
            # Verde (haste)
            green_mask = cv2.inRange(hsv, (40, 50, 50), (80, 255, 255))
            color_masks.append(green_mask)
            
            # Rojo (paralyze)
            red_mask1 = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
            red_mask2 = cv2.inRange(hsv, (170, 50, 50), (180, 255, 255))
            red_mask = cv2.bitwise_or(red_mask1, red_mask2)
            color_masks.append(red_mask)
            
            # Amarillo (poison)
            yellow_mask = cv2.inRange(hsv, (20, 50, 50), (30, 255, 255))
            color_masks.append(yellow_mask)
            
            # Combinar todas las máscaras
            combined_mask = cv2.bitwise_or(color_masks[0], color_masks[1])
            for mask in color_masks[2:]:
                combined_mask = cv2.bitwise_or(combined_mask, mask)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Encontrar el contorno más bajo
                lowest_y = h
                for contour in contours:
                    x, y, w_cont, h_cont = cv2.boundingRect(contour)
                    global_y = (h - 150) + y
                    if global_y < lowest_y and global_y > h - 150:
                        lowest_y = global_y
                
                if lowest_y < h - 50:  # Validar posición
                    return {
                        'row': lowest_y,
                        'x1': 0,
                        'x2': w
                    }
                    
        except Exception as e:
            print(f"Error en calibración por color: {e}")
        
        return None
    
    def _calibrate_by_icon_detection(self, frame: np.ndarray) -> Optional[Dict[str, int]]:
        """Calibración usando detección de iconos conocidos."""
        try:
            h, w = frame.shape[:2]
            
            # Buscar en la parte inferior
            scan_region = frame[h - 150:h, :]
            
            best_matches = []
            
            # Probar cada template
            for condition_name, template in self.templates.items():
                if template is None:
                    continue
                    
                result = cv2.matchTemplate(scan_region, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > 0.3:  # Umbral bajo para encontrar cualquier cosa
                    global_y = (h - 150) + max_loc[1]
                    best_matches.append({
                        'condition': condition_name,
                        'y': global_y,
                        'confidence': max_val,
                        'loc': max_loc
                    })
            
            if best_matches:
                # Agrupar por posición Y para encontrar la barra
                best_matches.sort(key=lambda x: x['y'])
                
                # Encontrar el grupo más grande de Y similares
                if len(best_matches) >= 1:
                    base_y = best_matches[0]['y']
                    nearby_matches = [m for m in best_matches if abs(m['y'] - base_y) < 20]
                    
                    if nearby_matches:
                        avg_y = int(np.mean([m['y'] for m in nearby_matches]))
                        return {
                            'row': avg_y,
                            'x1': 0,
                            'x2': w
                        }
                        
        except Exception as e:
            print(f"Error en calibración por iconos: {e}")
        
        return None
    
    def detect_conditions_enhanced(self, frame: np.ndarray) -> Dict[str, bool]:
        """
        Detección mejorada de condiciones usando múltiples métodos.
        """
        results = {}
        current_time = time.time()
        
        if not self.calibrated:
            # Intentar calibrar
            if self.calibrate_conditions_bar(frame):
                print("🎯 Barra calibrada, iniciando detección...")
            return results
        
        try:
            # Extraer región de condiciones
            y1 = max(0, self.condition_bar_row - 20)
            y2 = min(frame.shape[0], self.condition_bar_row + 20)
            x1 = max(0, self.condition_bar_x1 - 50)
            x2 = min(frame.shape[1], self.condition_bar_x2 + 50)
            condition_region = frame[y1:y2, x1:x2]
            
            print(f"🔍 Analizando región de condiciones: {condition_region.shape}")
            
            # Detectar cada condición activa
            for condition_name, condition_config in self.conditions.items():
                if not condition_config.get('enabled', False):
                    continue
                
                # Verificar cooldown
                if current_time - condition_config.get('last_triggered', 0.0) < condition_config.get('cooldown', 1.0):
                    results[condition_name] = False
                    continue
                
                # Usar método de detección configurado
                detection_method = condition_config.get('detection_method', 'template')
                threshold = condition_config.get('threshold', self.confidence_threshold)
                
                detected = False
                
                if detection_method == 'template' and condition_name in self.templates:
                    detected = self._detect_by_template(condition_region, condition_name, threshold)
                elif detection_method == 'color':
                    detected = self._detect_by_color(condition_region, condition_name, threshold)
                elif detection_method == 'hybrid':
                    detected = self._detect_hybrid(condition_region, condition_name, threshold)
                
                if detected:
                    condition_config['last_triggered'] = current_time
                    results[condition_name] = True
                    print(f"✅ {condition_name.upper()} DETECTADO!")
                else:
                    results[condition_name] = False
                    
            # Mostrar resumen
            detected_conds = [name for name, detected in results.items() if detected]
            if detected_conds:
                print(f"🎯 Condiciones detectadas: {detected_conds}")
                    
        except Exception as e:
            print(f"Error en detección mejorada: {e}")
        
        return results
    
    def _detect_by_template(self, region: np.ndarray, condition_name: str, threshold: float) -> bool:
        """Detección usando template matching."""
        if condition_name not in self.templates:
            return False
            
        template = self.templates[condition_name]
        if template is None:
            return False
        
        try:
            result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            print(f"📊 {condition_name}: max_val={max_val:.3f}, threshold={threshold:.3f}")
            
            return max_val >= threshold
        except Exception as e:
            print(f"Error en template matching para {condition_name}: {e}")
            return False
    
    def _detect_by_color(self, region: np.ndarray, condition_name: str, threshold: float) -> bool:
        """Detección usando análisis de color."""
        if condition_name not in self.condition_colors:
            return False
        
        try:
            hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            color_ranges = self.condition_colors[condition_name]
            
            # Crear máscara para el rango de color
            masks = []
            for i in range(0, len(color_ranges), 2):
                if i + 1 < len(color_ranges):
                    lower = color_ranges[i]
                    upper = color_ranges[i + 1]
                    mask = cv2.inRange(hsv, lower, upper)
                    masks.append(mask)
            
            if masks:
                combined_mask = cv2.bitwise_or(masks[0], masks[1]) if len(masks) > 1 else masks[0]
                
                # Encontrar contornos
                contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Calcular área total
                    total_area = sum(cv2.contourArea(contour) for contour in contours)
                    region_area = region.shape[0] * region.shape[1]
                    coverage = total_area / region_area
                    
                    print(f"🎨 {condition_name}: coverage={coverage:.3f}, threshold={threshold:.3f}")
                    
                    return coverage >= threshold
        
        except Exception as e:
            print(f"Error en detección por color para {condition_name}: {e}")
        
        return False
    
    def _detect_hybrid(self, region: np.ndarray, condition_name: str, threshold: float) -> bool:
        """Detección híbrida combinando template y color."""
        template_result = self._detect_by_template(region, condition_name, threshold * 0.8)
        color_result = self._detect_by_color(region, condition_name, threshold * 0.6)
        
        # Ambos métodos deben detectar
        result = template_result or color_result
        
        print(f"🔀 {condition_name}: template={template_result}, color={color_result}, hybrid={result}")
        
        return result
    
    def get_bar_info(self) -> Optional[Dict[str, int]]:
        """Obtiene información de la barra calibrada."""
        if self.calibrated:
            return {
                'row': self.condition_bar_row,
                'x1': self.condition_bar_x1,
                'x2': self.condition_bar_x2
            }
        return None
    
    def get_condition_config(self, condition_name: str) -> Dict[str, Any]:
        """Obtiene configuración de una condición."""
        return self.conditions.get(condition_name, {})
    
    def update_condition(self, condition_name: str, enabled: bool, hotkey: str, threshold: float = 0.4):
        """Actualiza configuración de una condición."""
        if condition_name not in self.conditions:
            self.conditions[condition_name] = {}
        
        self.conditions[condition_name].update({
            'enabled': enabled,
            'hotkey': hotkey,
            'threshold': threshold
        })
        
        print(f"⚙️ {condition_name} actualizado: enabled={enabled}, hotkey={hotkey}, threshold={threshold}")
