"""
Condition Engine - Motor de procesamiento de condiciones
Maneja la lógica de curación de condiciones basada en detecciones.
"""

import time
from typing import Dict, Any, Optional, Callable
from condition_detector import ConditionDetector


class ConditionEngine:
    """Motor principal para el sistema de condiciones."""
    
    def __init__(self, key_sender=None, log_callback: Optional[Callable] = None):
        self.detector = ConditionDetector()
        self.key_sender = key_sender
        self.log_callback = log_callback
        
        # Estadísticas
        self.trigger_count = 0
        self.last_check_time = 0.0
        self.enabled = True
        
        # Configuración global
        self.global_cooldown = 0.5  # segundos entre checks
        self.debug_mode = False
    
    def update_from_config(self, conditions_config: Dict[str, Any]):
        """Actualiza la configuración desde el archivo de config."""
        for condition_name, config in conditions_config.items():
            # Solo procesar configuraciones individuales (no globales)
            if condition_name in ["enabled", "debug_mode", "global_cooldown"]:
                continue
            if not isinstance(config, dict):
                continue
                
            enabled = config.get("enabled", False)
            hotkey = config.get("hotkey", "")
            threshold = config.get("threshold", 0.7)
            
            self.detector.update_condition(condition_name, enabled, hotkey, threshold)
    
    def process_frame(self, frame) -> Dict[str, bool]:
        """
        Procesa un frame y maneja las condiciones detectadas.
        Returns: Dict con resultados de detección
        """
        current_time = time.time()
        
        # Verificar cooldown global
        if current_time - self.last_check_time < self.global_cooldown:
            return {}
        
        # Si no está calibrado, intentar calibrar
        if not self.detector.is_calibrated():
            if self.debug_mode:
                self._log("Intentando calibrar barra de condiciones...")
            success = self.detector.calibrate(frame)
            if not success:
                return {}
        
        # Detectar condiciones
        results = self.detector.detect_conditions(frame)
        
        # Procesar condiciones detectadas
        for condition_name, detected in results.items():
            if detected:
                self._handle_condition_detected(condition_name)
        
        self.last_check_time = current_time
        return results
    
    def _handle_condition_detected(self, condition_name: str):
        """Maneja una condición detectada."""
        try:
            condition_config = self.detector.get_condition_config(condition_name)
            hotkey = condition_config.get("hotkey", "")
            
            if hotkey:
                # Enviar hotkey
                if self.key_sender:
                    success = self.key_sender.send_key(hotkey)
                    if success:
                        self.trigger_count += 1
                        self._log(f"{condition_name.capitalize()} activado -> {hotkey}", "OK")
                    else:
                        self._log(f"Error enviando {hotkey} para {condition_name}", "ERROR")
                else:
                    self._log(f"Key sender no disponible para {condition_name}", "WARN")
            else:
                self._log(f"{condition_name.capitalize()} detectado pero sin hotkey configurado", "WARN")
                
        except Exception as e:
            self._log(f"Error procesando {condition_name}: {e}", "ERROR")
    
    def _log(self, message: str, level: str = "INFO"):
        """Función de logging."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[ConditionEngine] {level}: {message}")
    
    def set_enabled(self, enabled: bool):
        """Activa/desactiva el motor de condiciones."""
        self.enabled = enabled
        self._log(f"Motor de condiciones {'activado' if enabled else 'desactivado'}")
    
    def set_debug_mode(self, debug: bool):
        """Activa/desactiva modo debug."""
        self.debug_mode = debug
        self._log(f"Modo debug {'activado' if debug else 'desactivado'}")
    
    def force_recalibration(self):
        """Fuerza recalibración de la barra de condiciones."""
        self.detector.force_recalibration()
        self._log("Recalibración forzada de barra de condiciones")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado actual del motor."""
        return {
            "enabled": self.enabled,
            "calibrated": self.detector.is_calibrated(),
            "trigger_count": self.trigger_count,
            "last_check": self.last_check_time,
            "conditions": self.detector.get_all_conditions()
        }
    
    def get_debug_info(self, frame) -> Dict[str, Any]:
        """Genera información de debug para visualización."""
        debug_info = {
            "calibrated": self.detector.is_calibrated(),
            "bar_position": None,
            "detections": {}
        }
        
        if self.detector.condition_bar_row is not None:
            debug_info["bar_position"] = {
                "row": self.detector.condition_bar_row,
                "x1": self.detector.condition_bar_x1,
                "x2": self.detector.condition_bar_x2
            }
        
        # Realizar detección para debug
        if self.detector.is_calibrated():
            debug_info["detections"] = self.detector.detect_conditions(frame)
        
        return debug_info
