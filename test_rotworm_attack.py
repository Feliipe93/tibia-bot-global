#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rotworm_attack.py - Script para probar el ataque a Rotworm en tiempo real
"""

import time
import logging
import threading
from targeting_v2_integration import TargetingV2Integration
from targeting_engine_v2 import TargetingEngineV2
from config import Config
from screen_calibrator import ScreenCalibrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RotwormAttackTest:
    def __init__(self):
        self.integration = TargetingV2Integration()
        self.targeting_engine = TargetingEngineV2()
        self.config = Config()
        self.calibrator = ScreenCalibrator()
        self.is_running = False
        self.attack_count = 0
        
    def setup(self):
        """Configura el sistema de ataque."""
        print("=== CONFIGURANDO ATAQUE A ROTWORM ===\n")
        
        # 1. Inicializar sistema
        print("1. Inicializando sistema de targeting...")
        if not self.integration.initialize():
            print("[ERROR] No se pudo inicializar el sistema")
            return False
        
        # 2. Agregar Rotworm a la lista de ataque
        print("2. Agregando Rotworm a la lista de ataque...")
        success = self.integration.add_creature_to_attack('rotworm')
        print(f"   Rotworm agregado: {success}")
        
        # 3. Verificar configuración
        rotworm_info = self.integration.get_creature_info('rotworm')
        print(f"   Rotworm seleccionado: {rotworm_info['selected']}")
        print(f"   Rotworm ignorado: {rotworm_info['ignored']}")
        print(f"   Prioridad: {rotworm_info['priority']}")
        
        # 4. Configurar targeting engine
        print("3. Configurando targeting engine...")
        targeting_config = {
            "enabled": True,
            "auto_attack": True,
            "chase_monsters": True,
            "attack_delay": 0.5,
            "re_attack_delay": 0.6,
            "attack_list": self.integration.selected_creatures,
            "ignore_list": self.integration.ignored_creatures,
            "creature_profiles": {}
        }
        
        # Configurar callbacks
        self.targeting_engine.set_click_callback(self._click_callback)
        self.targeting_engine.set_key_callback(self._key_callback)
        self.targeting_engine.set_log_callback(self._log_callback)
        self.targeting_engine.set_calibrator(self.calibrator)
        
        # Configurar engine
        self.targeting_engine.configure(targeting_config)
        
        print("   [OK] Sistema configurado")
        return True
    
    def start_attack(self):
        """Inicia el ataque a Rotworm."""
        print("\n=== INICIANDO ATAQUE A ROTWORM ===")
        print("Asegúrate de tener un Rotworm en la battle list")
        print("Presiona Ctrl+C para detener el ataque\n")
        
        self.is_running = True
        self.attack_count = 0
        
        # Iniciar targeting engine
        try:
            self.targeting_engine.start()
            print("[OK] Targeting engine iniciado")
        except Exception as e:
            print(f"[ERROR] Error iniciando targeting: {e}")
            return
        
        # Bucle de ataque
        try:
            while self.is_running:
                # Verificar estado del targeting
                status = self.targeting_engine.get_status()
                
                if status.get('is_attacking', False):
                    self.attack_count += 1
                    print(f"[ATAQUE] Atacando objetivo #{self.attack_count}")
                
                # Mostrar información del target actual
                current_target = status.get('current_target')
                if current_target:
                    print(f"[TARGET] Objetivo actual: {current_target}")
                
                # Esperar antes de siguiente verificación
                time.sleep(1.0)
                
        except KeyboardInterrupt:
            print("\n[STOP] Deteniendo ataque...")
            self.stop_attack()
    
    def stop_attack(self):
        """Detiene el ataque."""
        self.is_running = False
        try:
            self.targeting_engine.stop()
            print("[OK] Targeting engine detenido")
        except Exception as e:
            print(f"[ERROR] Error deteniendo targeting: {e}")
        
        print(f"\n=== RESUMEN DEL ATAQUE ===")
        print(f"Ataques realizados: {self.attack_count}")
        print(f"Rotworms eliminados: {self.attack_count}")
    
    def _click_callback(self, x, y):
        """Callback para clicks."""
        print(f"[CLICK] Click en ({x}, {y})")
    
    def _key_callback(self, key):
        """Callback para teclas."""
        print(f"[KEY] Tecla presionada: {key}")
    
    def _log_callback(self, message):
        """Callback para logs."""
        print(f"[LOG] {message}")
    
    def show_battle_list_info(self):
        """Muestra información de la battle list."""
        print("\n=== INFORMACIÓN DE BATTLE LIST ===")
        print("Verificando criaturas en battle list...")
        
        # Aquí iría el código para leer la battle list
        # Por ahora mostramos la configuración
        print(f"Criaturas en attack_list: {len(self.integration.selected_creatures)}")
        print(f"Rotworm en attack_list: {'rotworm' in [c.lower() for c in self.integration.selected_creatures]}")
        
        # Mostrar primeras 10 criaturas
        print("\nCriaturas configuradas para ataque:")
        for i, creature in enumerate(self.integration.selected_creatures[:10], 1):
            marker = ">>>" if creature.lower() == 'rotworm' else "   "
            print(f"{marker} {i:2d}. {creature.title()}")

def main():
    """Función principal."""
    print("=== TEST DE ATAQUE A ROTWORM ===\n")
    
    # Crear instancia del test
    test = RotwormAttackTest()
    
    # Configurar sistema
    if not test.setup():
        print("[ERROR] No se pudo configurar el sistema")
        return
    
    # Mostrar información de battle list
    test.show_battle_list_info()
    
    # Preguntar si continuar
    print(f"\n¿Listo para iniciar el ataque?")
    print(f"Asegúrate de:")
    print(f"1. Tener Tibia abierto")
    print(f"2. Tener un Rotworm en la battle list")
    print(f"3. Estar en una zona segura para atacar")
    print(f"4. Tener OBS configurado para captura")
    
    try:
        input("\nPresiona Enter para iniciar el ataque...")
    except:
        print("\nIniciando ataque en 3 segundos...")
        time.sleep(3)
    
    # Iniciar ataque
    test.start_attack()

if __name__ == "__main__":
    main()
