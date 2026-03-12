#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
creature_hp_detector.py - Detector de HP y nombres de criaturas.
Lee el HP y nombre de las criaturas desde el game screen o battle list.
"""

import cv2
import numpy as np
import re
import time
from typing import Dict, List, Optional, Tuple

from utils.ocr_helper import OCRHelper
from utils.template_matcher import TemplateMatcher


class CreatureHPDetector:
    """
    Detector de HP y nombres de criaturas.
    Soporta lectura desde battle list y game screen.
    """
    
    def __init__(self):
        self.ocr = OCRHelper()
        self.template_matcher = TemplateMatcher()
        
        # Región donde aparece el HP de la criatura targeteada
        self.hp_bar_region: Optional[Tuple[int, int, int, int]] = None
        self.name_region: Optional[Tuple[int, int, int, int]] = None
        
        # Cache de HP por criatura
        self.hp_cache: Dict[str, Dict] = {}
        self.cache_timeout = 2.0  # segundos
        
        # Templates para detectar bordes de selección
        self.selection_templates = []
        self.load_selection_templates()
        
        # Callback para logging
        self.log_callback: Optional[callable] = None
        
    def load_selection_templates(self):
        """Carga templates para detectar cuando una criatura está seleccionada."""
        try:
            # Intentar cargar templates de selección
            template_dir = "images/MonstersAttack/"
            selection_files = [
                "BottomPink.png", "LeftPink.png", "RightPink.png",
                "BottomRed.png", "LeftRed.png", "RightRed.png"
            ]
            
            for filename in selection_files:
                template_path = f"{template_dir}{filename}"
                template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                if template is not None:
                    self.selection_templates.append((filename.replace('.png', ''), template))
                    
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"Error cargando templates de selección: {e}")
            else:
                print(f"Error cargando templates de selección: {e}")
    
    def set_log_callback(self, callback: callable):
        """Establece el callback para logging."""
        self.log_callback = callback
    
    def set_hp_region(self, x1: int, y1: int, x2: int, y2: int):
        """Establece la región donde buscar la barra de HP."""
        self.hp_bar_region = (x1, y1, x2, y2)
        
    def set_name_region(self, x1: int, y1: int, x2: int, y2: int):
        """Establece la región donde buscar el nombre de la criatura."""
        self.name_region = (x1, y1, x2, y2)
    
    def is_creature_selected(self, frame: np.ndarray) -> bool:
        """
        Verifica si hay una criatura seleccionada (bordes de ataque visibles).
        """
        if not self.selection_templates:
            return False
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        matches = 0
        
        for name, template in self.selection_templates:
            res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            
            # Umbral diferente para templates pequeños vs grandes
            threshold = 0.92 if "Small" in name else 0.65
            if max_val >= threshold:
                matches += 1
                
        # Consideramos seleccionado si hay al menos 3 matches
        return matches >= 3
    
    def extract_hp_percentage(self, frame: np.ndarray) -> Optional[float]:
        """
        Extrae el porcentaje de HP de la criatura seleccionada.
        Busca el texto "HP: XX%" o analiza la barra de HP visualmente.
        """
        if not self.hp_bar_region:
            return None
            
        x1, y1, x2, y2 = self.hp_bar_region
        hp_roi = frame[y1:y2, x1:x2]
        
        # Método 1: Intentar leer con OCR
        try:
            # Convertir a formato para OCR
            hp_gray = cv2.cvtColor(hp_roi, cv2.COLOR_BGR2GRAY)
            
            # Mejorar contraste
            hp_gray = cv2.threshold(hp_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            
            # OCR
            text = self.ocr.read_text(hp_gray)
            
            # Buscar patrones de HP
            hp_patterns = [
                r'HP:\s*(\d+)%',      # HP: 75%
                r'(\d+)%',           # 75%
                r'(\d+)/(\d+)',       # 150/200
            ]
            
            for pattern in hp_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
                        # Caso 150/200
                        current = int(match.group(1))
                        max_hp = int(match.group(2))
                        return (current / max_hp) * 100
                    else:
                        # Caso 75%
                        return float(match.group(1))
                        
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"Error en OCR de HP: {e}")
            else:
                print(f"Error en OCR de HP: {e}")
        
        # Método 2: Analizar barra de HP visualmente
        try:
            hp_gray = cv2.cvtColor(hp_roi, cv2.COLOR_BGR2GRAY)
            
            # Buscar la barra roja de HP
            # Umbral para detectar píxeles de HP (rojos/oscuros)
            hp_mask = cv2.inRange(hp_gray, 50, 150)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(hp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Tomar el contorno más grande (la barra de HP)
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                # Calcular porcentaje basado en el ancho
                bar_width = w
                total_width = hp_gray.shape[1]
                
                if total_width > 0:
                    return (bar_width / total_width) * 100
                    
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"Error analizando barra de HP: {e}")
            else:
                print(f"Error analizando barra de HP: {e}")
            
        return None
    
    def extract_creature_name(self, frame: np.ndarray) -> Optional[str]:
        """
        Extrae el nombre de la criatura seleccionada.
        """
        if not self.name_region:
            return None
            
        x1, y1, x2, y2 = self.name_region
        name_roi = frame[y1:y2, x1:x2]
        
        try:
            # Preparar para OCR
            name_gray = cv2.cvtColor(name_roi, cv2.COLOR_BGR2GRAY)
            
            # Mejorar contraste
            name_gray = cv2.threshold(name_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            
            # OCR
            text = self.ocr.read_text(name_gray)
            
            # Limpiar texto
            text = re.sub(r'[^a-zA-Z\s]', '', text).strip()
            
            if text and len(text) > 2:
                return text.title()  # Capitalizar como nombres propios
                
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"Error en OCR de nombre: {e}")
            else:
                print(f"Error en OCR de nombre: {e}")
            
        return None
    
    def update_creature_hp(self, creature_name: str, hp_percentage: float):
        """
        Actualiza el cache de HP para una criatura.
        """
        if creature_name not in self.hp_cache:
            self.hp_cache[creature_name] = {
                'hp': hp_percentage,
                'last_update': time.time(),
                'trend': 'stable'  # stable, decreasing, increasing
            }
        else:
            old_hp = self.hp_cache[creature_name]['hp']
            trend = 'stable'
            
            if hp_percentage < old_hp - 2:
                trend = 'decreasing'
            elif hp_percentage > old_hp + 2:
                trend = 'increasing'
                
            self.hp_cache[creature_name] = {
                'hp': hp_percentage,
                'last_update': time.time(),
                'trend': trend
            }
    
    def get_creature_hp(self, creature_name: str) -> Optional[Dict]:
        """
        Obtiene el HP cacheado de una criatura.
        """
        if creature_name not in self.hp_cache:
            return None
            
        cache_entry = self.hp_cache[creature_name]
        
        # Verificar si el cache está expirado
        if time.time() - cache_entry['last_update'] > self.cache_timeout:
            del self.hp_cache[creature_name]
            return None
            
        return cache_entry
    
    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Procesa un frame y extrae información de la criatura seleccionada.
        """
        result = {
            'selected': False,
            'name': None,
            'hp_percentage': None,
            'hp_info': None
        }
        
        # Verificar si hay criatura seleccionada
        if not self.is_creature_selected(frame):
            return result
            
        result['selected'] = True
        
        # Extraer nombre
        name = self.extract_creature_name(frame)
        if name:
            result['name'] = name
            
            # Extraer HP
            hp_percentage = self.extract_hp_percentage(frame)
            if hp_percentage is not None:
                result['hp_percentage'] = hp_percentage
                self.update_creature_hp(name, hp_percentage)
                
                # Obtener información del cache
                hp_info = self.get_creature_hp(name)
                if hp_info:
                    result['hp_info'] = hp_info
                    
        return result
    
    def auto_calibrate_regions(self, frame: np.ndarray, battle_region: Tuple[int, int, int, int]):
        """
        Auto-calibra las regiones de HP y nombre basándose en la battle region.
        """
        if not battle_region:
            return False
            
        x1, y1, x2, y2 = battle_region
        
        # Región de nombre: arriba de la battle list
        self.name_region = (x1 - 50, y1 - 30, x1 + 200, y1 - 10)
        
        # Región de HP: al lado derecho del nombre
        self.hp_bar_region = (x1 + 210, y1 - 30, x1 + 350, y1 - 10)
        
        return True
