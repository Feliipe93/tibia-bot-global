"""
Condition Detector - Sistema de detección de condiciones de estado
Basado en el sistema del OldBot para detectar: paralyze, poison, haste, etc.
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any
import time


class ConditionDetector:
    """Detecta condiciones de estado como paralyze, poison, haste usando imágenes template."""
    
    def __init__(self):
        self.condition_bar_row = None
        self.condition_bar_x1 = None
        self.condition_bar_x2 = None
        self.calibrated = False
        self.last_detection_time = 0.0
        
        # Configuración de condiciones (extensible)
        self.conditions = {
            "haste": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/haste.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0  # segundos
            },
            "paralyze": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/paralyze.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "poison": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/poison.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            # Condiciones del OldBot
            "burning": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/burning.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "curse": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/curse.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "hunger": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/hunger.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "manashield": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/manashield.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "pz_zone": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/pz_zone.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            # Variantes de Haste
            "haste_medivia": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/haste_medivia.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "haste_otclient": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/haste_otclient.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "haste_otclientNewer": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/haste_otclientNewer.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "haste_tibia-old": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/haste_tibia-old.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "haste_wearedragons": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/haste_wearedragons.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            # Variantes de Paralyze
            "paralyze_otclientNewer": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/paralyze_otclientNewer.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            # Variantes de Poison
            "poison_likeretro": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/poison_likeretro.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "poison_medivia": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/poison_medivia.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "poison_otclientNewer": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/poison_otclientNewer.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "poison_realera": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/poison_realera.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            # Variantes de Mana Shield
            "manashield_new": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/manashield_new.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "manashield_otclient": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/manashield_otclient.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "manashield_otclientNewer": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/manashield_otclientNewer.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            # Variantes de Hunger
            "hungry_lunos": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/hungry_lunos.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "hungry_medivia": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/hungry_medivia.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "hungry_nostalgic": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/hungry_nostalgic.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            # Variantes de PZ Zone
            "pz_zone_medivia": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/pz_zone_medivia.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "pz_zone_nostalgic": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/pz_zone_nostalgic.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "pz_zone_otclient": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/pz_zone_otclient.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "pz_zone_otclientv8": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/pz_zone_otclientv8.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            },
            "pz_zone_revolution": {
                "enabled": False,
                "hotkey": "",
                "template": "assets/conditions/pz_zone_revolution.png",
                "threshold": 0.7,
                "last_triggered": 0.0,
                "cooldown": 1.0
            }
        }
        
        # Cargar templates
        self.templates = {}
        self._load_templates()
    
    def _load_templates(self):
        """Carga las imágenes template para cada condición."""
        for condition_name, condition_config in self.conditions.items():
            try:
                template = cv2.imread(condition_config["template"], cv2.IMREAD_COLOR)
                if template is not None:
                    self.templates[condition_name] = template
                    print(f"Template cargado: {condition_name}")
                else:
                    print(f"Error cargando template: {condition_config['template']}")
            except Exception as e:
                print(f"Error cargando template {condition_name}: {e}")
    
    def calibrate(self, frame: np.ndarray) -> bool:
        """
        Calibra la posición de la barra de condiciones.
        La barra de condiciones está debajo de la barra de mana.
        """
        try:
            # Buscar la barra de condiciones usando análisis de color
            # La barra de condiciones típicamente tiene colores distintivos
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Buscar en la parte inferior de la pantalla (donde están las barras)
            h, w = frame.shape[:2]
            scan_height = min(200, h // 3)  # Tercio inferior
            scan_region = frame[h - scan_height:h, :]
            
            # Convertir a escala de grises para detección de bordes
            gray = cv2.cvtColor(scan_region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # Buscar líneas horizontales (barras)
            lines = cv2.HoughLinesP(edges, 1, np.pi/2, 100, minLineLength=50, maxLineGap=10)
            
            if lines is not None:
                # Encontrar la línea más baja (barra de condiciones)
                lowest_y = 0
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Calcular posición global
                    global_y = (h - scan_height) + y1
                    if global_y > lowest_y:
                        lowest_y = global_y
                
                if lowest_y > 0:
                    # Guardar posición de la barra
                    self.condition_bar_row = lowest_y
                    
                    # Estimar límites horizontales
                    # Buscar región con mayor actividad horizontal
                    row_region = frame[lowest_y-5:lowest_y+5, :]
                    row_gray = cv2.cvtColor(row_region, cv2.COLOR_BGR2GRAY)
                    
                    # Proyección horizontal
                    horizontal_sum = np.sum(row_gray, axis=0)
                    threshold = np.max(horizontal_sum) * 0.3
                    
                    # Encontrar límites
                    active_pixels = np.where(horizontal_sum > threshold)[0]
                    if len(active_pixels) > 0:
                        self.condition_bar_x1 = active_pixels[0]
                        self.condition_bar_x2 = active_pixels[-1]
                        
                        self.calibrated = True
                        print(f"Barra de condiciones calibrada: y={lowest_y}, x1={self.condition_bar_x1}, x2={self.condition_bar_x2}")
                        return True
            
            print("No se pudo calibrar la barra de condiciones")
            return False
            
        except Exception as e:
            print(f"Error en calibración de condiciones: {e}")
            return False
    
    def detect_conditions(self, frame: np.ndarray) -> Dict[str, bool]:
        """
        Detecta todas las condiciones activas.
        Returns: Dict con nombre de condición -> bool (activada/inactivada)
        """
        results = {}
        current_time = time.time()
        
        if not self.calibrated:
            return results
        
        try:
            # Extraer región de la barra de condiciones
            if (self.condition_bar_x1 is not None and 
                self.condition_bar_x2 is not None and
                self.condition_bar_row is not None):
                
                # Región más grande para incluir iconos
                y1 = max(0, self.condition_bar_row - 15)
                y2 = min(frame.shape[0], self.condition_bar_row + 15)
                x1 = max(0, self.condition_bar_x1 - 20)
                x2 = min(frame.shape[1], self.condition_bar_x2 + 20)
                condition_region = frame[y1:y2, x1:x2]
                
                # Detectar cada condición configurada
                for condition_name, condition_config in self.conditions.items():
                    if not condition_config.get("enabled", False):
                        continue
                        
                    # Verificar cooldown
                    if current_time - condition_config.get("last_triggered", 0.0) < condition_config.get("cooldown", 1.0):
                        # Template matching
                        template = self.templates.get(condition_name)
                        if template is not None:
                            detected = self._match_template(condition_region, template, condition_config.get("threshold", 0.7))
                            
                            if detected:
                                condition_config["last_triggered"] = current_time
                                results[condition_name] = True
                            else:
                                results[condition_name] = False
                        else:
                            results[condition_name] = False
            else:
                # Si no está calibrado, intentar calibrar
                self._attempt_calibration(frame)
        
        except Exception as e:
            print(f"Error en detección de condiciones: {e}")
        
        return results
    
    def _match_template(self, region: np.ndarray, template: np.ndarray, threshold: float) -> bool:
        """Realiza template matching con umbral."""
        try:
            if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
                return False
            
            # Template matching
            result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            return max_val >= threshold
            
        except Exception as e:
            print(f"❌ Error en template matching: {e}")
            return False
    
    def update_condition(self, condition_name: str, enabled: bool, hotkey: str, threshold: float = 0.7):
        """Actualiza la configuración de una condición."""
        if condition_name in self.conditions:
            self.conditions[condition_name]["enabled"] = enabled
            self.conditions[condition_name]["hotkey"] = hotkey
            self.conditions[condition_name]["threshold"] = threshold
    
    def get_condition_config(self, condition_name: str) -> Dict[str, Any]:
        """Obtiene la configuración de una condición."""
        return self.conditions.get(condition_name, {})
    
    def get_all_conditions(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene toda la configuración de condiciones."""
        return self.conditions.copy()
    
    def is_calibrated(self) -> bool:
        """Verifica si el detector está calibrado."""
        return self.calibrated
    
    def force_recalibration(self):
        """Fuerza una recalibración."""
        self.calibrated = False
        self.condition_bar_row = None
        self.condition_bar_x1 = None
        self.condition_bar_x2 = None
