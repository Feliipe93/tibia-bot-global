#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rotworm_attack_normal.py - Script que usa el targeting normal para atacar Rotworm
"""

import time
import logging
import numpy as np
from targeting.targeting_engine import TargetingEngine
from screen_calibrator import ScreenCalibrator
from capture_obs import capture_obs_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RotwormNormalAttack:
    """Sistema que usa el targeting normal para atacar Rotworm."""
    
    def __init__(self):
        self.targeting_engine = TargetingEngine()
        self.calibrator = ScreenCalibrator()
        self.is_running = False
        self.attack_count = 0
        
        # Callbacks
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Configura los callbacks para el targeting engine."""
        
        def click_callback(x, y):
            """Callback para clicks."""
            logger.info(f"[CLICK] Click en ({x}, {y})")
            # Aquí iría el código real para hacer click
            # Por ahora solo logueamos
            return True
        
        def key_callback(key):
            """Callback para teclas."""
            logger.info(f"[KEY] Tecla: {key}")
            # Aquí iría el código real para enviar teclas
            return True
        
        def log_callback(msg):
            """Callback para logs."""
            logger.info(f"[TARGETING] {msg}")
        
        # Configurar callbacks
        self.targeting_engine.set_click_callback(click_callback)
        self.targeting_engine.set_key_callback(key_callback)
        self.targeting_engine.set_log_callback(log_callback)
        self.targeting_engine.set_calibrator(self.calibrator)
    
    def configure(self):
        """Configura el targeting engine para Rotworm."""
        logger.info("Configurando targeting para Rotworm...")
        
        # Configuración específica para Rotworm
        targeting_config = {
            "enabled": True,
            "auto_attack": True,
            "chase_monsters": True,
            "attack_delay": 0.5,
            "re_attack_delay": 0.6,
            "attack_list": ["rotworm", "carrion worm"],
            "ignore_list": [],
            "priority_list": [],
            "chase_key": "",
            "stand_key": "",
            "creature_profiles": {
                "rotworm": {
                    "enabled": True,
                    "chase_mode": "aggressive",
                    "attack_mode": "offensive",
                    "hp_thresholds": {
                        "chase": 100,
                        "stand": 30
                    },
                    "spells": [],
                    "priority": 50
                },
                "carrion worm": {
                    "enabled": True,
                    "chase_mode": "aggressive", 
                    "attack_mode": "offensive",
                    "hp_thresholds": {
                        "chase": 120,
                        "stand": 40
                    },
                    "spells": [],
                    "priority": 60
                }
            }
        }
        
        # Aplicar configuración
        self.targeting_engine.configure(targeting_config)
        
        logger.info("Targeting configurado para Rotworm y Carrion Worm")
    
    def start(self):
        """Inicia el ataque."""
        logger.info("=== INICIANDO ATAQUE A ROTWORM (TARGETING NORMAL) ===")
        
        # Configurar
        self.configure()
        
        # Iniciar targeting engine
        try:
            self.targeting_engine.start()
            logger.info("[OK] Targeting engine iniciado")
        except Exception as e:
            logger.error(f"[ERROR] Error iniciando targeting: {e}")
            return False
        
        self.is_running = True
        self.attack_count = 0
        
        logger.info("Monitoreando ataque...")
        logger.info("Presiona Ctrl+C para detener")
        
        # Bucle de monitoreo
        try:
            while self.is_running:
                # Capturar frame
                frame = self.capture_frame()
                if frame is None:
                    logger.warning("No se pudo capturar frame")
                    time.sleep(1.0)
                    continue
                
                # Procesar frame con targeting
                self.targeting_engine.process_frame(frame)
                
                # Obtener estado
                status = self.targeting_engine.get_status()
                
                # Verificar si está atacando
                if status.get('state') == 'attacking':
                    current_target = status.get('current_target')
                    if current_target:
                        self.attack_count += 1
                        logger.info(f"[ATAQUE #{self.attack_count}] Atacando: {current_target}")
                
                # Mostrar estadísticas cada 10 segundos
                if self.attack_count > 0 and self.attack_count % 10 == 0:
                    kills = status.get('monsters_killed', 0)
                    logger.info(f"[STATS] Ataques: {self.attack_count}, Kills: {kills}")
                
                # Esperar
                time.sleep(0.5)  # 2 FPS para no sobrecargar
                
        except KeyboardInterrupt:
            logger.info("\n[STOP] Deteniendo ataque...")
            self.stop()
        
        return True
    
    def capture_frame(self):
        """Captura un frame desde OBS."""
        try:
            # Usar la función existente para capturar
            import base64
            import cv2
            from obswebsocket import obsws, requests
            from config import Config
            
            # Cargar configuración
            config = Config()
            obs_config = config.data.get('obs', {})
            
            host = obs_config.get('host', 'localhost')
            port = obs_config.get('port', 4455)
            password = obs_config.get('password', '')
            source_name = obs_config.get('source_name', 'Captura de juego')
            
            # Conectar a OBS
            ws = obsws(host, port, password)
            ws.connect()
            
            # Obtener screenshot
            response = ws.call(requests.GetSourceScreenshot(sourceName=source_name, imageFormat="png"))
            
            if hasattr(response, 'datain') and 'imageData' in response.datain:
                # Decodificar imagen base64
                img_data = base64.b64decode(response.datain['imageData'])
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    return img
            
            return None
            
        except Exception as e:
            logger.error(f"Error capturando frame: {e}")
            return None
    
    def stop(self):
        """Detiene el ataque."""
        self.is_running = False
        try:
            self.targeting_engine.stop()
            logger.info("[OK] Targeting detenido")
        except Exception as e:
            logger.error(f"[ERROR] Error deteniendo targeting: {e}")
        
        # Mostrar resumen
        status = self.targeting_engine.get_status()
        kills = status.get('monsters_killed', 0)
        attacks = status.get('total_attacks', 0)
        
        logger.info(f"\n=== RESUMEN ===")
        logger.info(f"Ataques totales: {attacks}")
        logger.info(f"Monstruos eliminados: {kills}")
        logger.info(f"Rotworms eliminados: {kills}")  # Asumimos que todos son Rotworms
    
    def show_status(self):
        """Muestra el estado actual del targeting."""
        status = self.targeting_engine.get_status()
        
        logger.info(f"\n=== ESTADO DEL TARGETING ===")
        logger.info(f"Estado: {status.get('state', 'unknown')}")
        logger.info(f"Target actual: {status.get('current_target', 'none')}")
        logger.info(f"Monstruos en battle list: {status.get('monster_count', 0)}")
        logger.info(f"Monstruos eliminados: {status.get('monsters_killed', 0)}")
        logger.info(f"Total de ataques: {status.get('total_attacks', 0)}")
        logger.info(f"Templates cargados: {status.get('templates_loaded', 0)}")
        
        # Mostrar conteo por nombre
        counts = status.get('counts_by_name', {})
        if counts:
            logger.info(f"Conteo por nombre:")
            for name, count in counts.items():
                logger.info(f"  {name.title()}: {count}")

def main():
    """Función principal."""
    print("=== ATAQUE A ROTWORM - TARGETING NORMAL ===\n")
    
    # Crear sistema
    attack_system = RotwormNormalAttack()
    
    # Mostrar información
    print("Este script usa el TARGETING NORMAL (que sí funciona)")
    print("Configurado para atacar:")
    print("• Rotworm (prioridad 50)")
    print("• Carrion Worm (prioridad 60)")
    print("\nCaracterísticas:")
    print("• Usa BattleListReader para detectar monstruos")
    print("• Hace click en la battle list para atacar")
    print("• Soporta chase/stand mode automático")
    print("• Detecta kills por nombre")
    print("• Integra con creature tracker")
    
    # Verificar estado inicial
    attack_system.show_status()
    
    print(f"\n¿Listo para iniciar el ataque?")
    print(f"Asegúrate de:")
    print(f"1. Tener Tibia abierto")
    print(f"2. Tener OBS configurado")
    print(f"3. Tener un Rotworm o Carrion Worm en la battle list")
    print(f"4. Estar en una zona segura")
    
    try:
        input("\nPresiona Enter para iniciar el ataque...")
    except:
        print("\nIniciando ataque en 3 segundos...")
        time.sleep(3)
    
    # Iniciar ataque
    success = attack_system.start()
    
    if success:
        print("\n[SUCCESS] Ataque completado")
    else:
        print("\n[ERROR] Error durante el ataque")

if __name__ == "__main__":
    main()
