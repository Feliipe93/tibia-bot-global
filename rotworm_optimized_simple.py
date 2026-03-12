#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rotworm_optimized_simple.py - Sistema optimizado simple para Rotworm y Carrion Worm
"""

import time
import logging
import json
from typing import Dict, List, Optional
from config import Config
from targeting_engine_v2 import TargetingEngineV2
from creature_database import CreatureDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizedRotwormSystem:
    """Sistema optimizado que carga solo los monstruos especificados."""
    
    def __init__(self, target_creatures: List[str] = None):
        # Solo los monstruos que queremos cargar
        self.target_creatures = target_creatures or ["rotworm", "carrion worm"]
        
        # Componentes del sistema
        self.targeting_engine: Optional[TargetingEngineV2] = None
        self.creature_db: Optional[CreatureDatabase] = None
        
        # Configuración
        self.selected_creatures: List[str] = []
        self.ignored_creatures: List[str] = []
        self.creature_priorities: Dict[str, float] = {}
        
        # Estado
        self.is_initialized = False
    
    def initialize(self) -> bool:
        """Inicializa el sistema optimizado."""
        logger.info(f"Inicializando sistema optimizado para: {self.target_creatures}")
        
        try:
            # 1. Inicializar componentes
            self._initialize_components()
            
            # 2. Cargar solo los monstruos especificados
            self._load_target_creatures()
            
            # 3. Configurar targeting engine
            self._configure_targeting_engine()
            
            self.is_initialized = True
            logger.info("Sistema optimizado inicializado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error inicializando sistema optimizado: {e}")
            return False
    
    def _initialize_components(self):
        """Inicializa los componentes básicos."""
        # Targeting Engine V2
        self.targeting_engine = TargetingEngineV2()
        
        # Creature Database (optimizado)
        self.creature_db = CreatureDatabase("tibia_files_canary")
        
        logger.info("Componentes inicializados")
    
    def _load_target_creatures(self):
        """Carga solo los monstruos especificados."""
        logger.info(f"Cargando solo los monstruos: {self.target_creatures}")
        
        # Datos predefinidos para los monstruos objetivo
        creature_data = {
            "rotworm": {
                "name": "Rotworm",
                "look_type": 26,
                "hp": 70,
                "experience": 40,
                "difficulty": 1,
                "is_ranged": False,
                "is_mage": False,
                "is_healer": False,
                "class_type": "melee",
                "corpse_id": 4354,
                "corpse_name": "Dead Worm",
                "priority": 50.0
            },
            "carrion worm": {
                "name": "Carrion Worm",
                "look_type": 306,
                "hp": 85,
                "experience": 70,
                "difficulty": 2,
                "is_ranged": False,
                "is_mage": False,
                "is_healer": False,
                "class_type": "melee",
                "corpse_id": 4353,
                "corpse_name": "Dead Carrion Worm",
                "priority": 60.0
            }
        }
        
        # Configurar criaturas seleccionadas
        self.selected_creatures = self.target_creatures.copy()
        
        # Calcular prioridades
        for creature_name in self.target_creatures:
            if creature_name in creature_data:
                self.creature_priorities[creature_name] = creature_data[creature_name]["priority"]
        
        logger.info(f"Criaturas cargadas: {len(self.selected_creatures)}")
        for creature in self.selected_creatures:
            logger.info(f"  - {creature.title()}: Prioridad {self.creature_priorities.get(creature, 50)}")
    
    def _configure_targeting_engine(self):
        """Configura el targeting engine."""
        if not self.targeting_engine:
            return
        
        # Crear configuración optimizada
        targeting_config = {
            "enabled": True,
            "auto_attack": True,
            "chase_monsters": True,
            "attack_delay": 0.5,
            "re_attack_delay": 0.6,
            "attack_list": self.selected_creatures,
            "ignore_list": [],
            "priority_list": [],
            "creature_profiles": {}
        }
        
        # Configurar profiles para cada criatura
        for creature_name in self.selected_creatures:
            profile = self._generate_creature_profile(creature_name)
            targeting_config["creature_profiles"][creature_name] = profile
        
        # Configurar el engine
        self.targeting_engine.configure(targeting_config)
        
        logger.info("Targeting engine configurado")
    
    def _generate_creature_profile(self, creature_name: str) -> Dict:
        """Genera un profile optimizado para una criatura."""
        
        # Profiles específicos
        profiles = {
            "rotworm": {
                "enabled": True,
                "chase_mode": "aggressive",
                "attack_mode": "offensive",
                "hp_thresholds": {
                    "chase": 100,
                    "stand": 30
                },
                "spells": [],
                "look_type": 26,
                "colors": {"head": 94, "body": 94, "legs": 94, "feet": 94}
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
                "look_type": 306,
                "colors": {"head": 94, "body": 94, "legs": 94, "feet": 94}
            }
        }
        
        return profiles.get(creature_name, {
            "enabled": True,
            "chase_mode": "auto",
            "attack_mode": "offensive",
            "hp_thresholds": {"chase": 100, "stand": 30},
            "spells": []
        })
    
    def get_creature_info(self, creature_name: str) -> Optional[Dict]:
        """Obtiene información de una criatura."""
        if creature_name not in self.selected_creatures:
            return None
        
        info = {
            "name": creature_name,
            "priority": self.creature_priorities.get(creature_name, 50.0),
            "selected": creature_name in self.selected_creatures,
            "ignored": creature_name in self.ignored_creatures
        }
        
        # Datos específicos
        if creature_name == "rotworm":
            info.update({
                "hp": 70,
                "experience": 40,
                "difficulty": 1,
                "is_ranged": False,
                "is_mage": False,
                "is_healer": False,
                "class_type": "melee",
                "look_type": 26,
                "corpse_id": 4354,
                "corpse_name": "Dead Worm"
            })
        elif creature_name == "carrion worm":
            info.update({
                "hp": 85,
                "experience": 70,
                "difficulty": 2,
                "is_ranged": False,
                "is_mage": False,
                "is_healer": False,
                "class_type": "melee",
                "look_type": 306,
                "corpse_id": 4353,
                "corpse_name": "Dead Carrion Worm"
            })
        
        return info
    
    def get_all_creatures(self) -> List[Dict]:
        """Obtiene información de todas las criaturas cargadas."""
        return [self.get_creature_info(c) for c in self.selected_creatures]
    
    def get_selected_creatures(self) -> List[Dict]:
        """Obtiene información de las criaturas seleccionadas."""
        return [self.get_creature_info(c) for c in self.selected_creatures]
    
    def start_targeting(self) -> bool:
        """Inicia el targeting."""
        if not self.targeting_engine:
            logger.error("Targeting engine no inicializado")
            return False
        
        try:
            self.targeting_engine.start()
            logger.info("Targeting iniciado")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciando targeting: {e}")
            return False
    
    def stop_targeting(self) -> bool:
        """Detiene el targeting."""
        if not self.targeting_engine:
            return False
        
        try:
            self.targeting_engine.stop()
            logger.info("Targeting detenido")
            return True
            
        except Exception as e:
            logger.error(f"Error deteniendo targeting: {e}")
            return False
    
    def get_targeting_status(self) -> Dict:
        """Obtiene el estado del targeting."""
        if not self.targeting_engine:
            return {"error": "Targeting engine no inicializado"}
        
        try:
            status = self.targeting_engine.get_status()
            status.update({
                "selected_creatures": len(self.selected_creatures),
                "target_creatures": self.target_creatures,
                "is_initialized": self.is_initialized
            })
            return status
            
        except Exception as e:
            return {"error": f"Error obteniendo estado: {e}"}
    
    def save_configuration(self, config_path: str = "rotworm_optimized_config.json"):
        """Guarda la configuración optimizada."""
        try:
            config = {
                "target_creatures": self.target_creatures,
                "selected_creatures": self.selected_creatures,
                "ignored_creatures": self.ignored_creatures,
                "creature_priorities": self.creature_priorities,
                "creature_data": {c: self.get_creature_info(c) for c in self.selected_creatures}
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuración guardada en: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False

def main():
    """Función principal para probar el sistema optimizado."""
    print("=== SISTEMA OPTIMIZADO - ROTWORM + CARRION WORM ===\n")
    
    # Crear sistema optimizado
    system = OptimizedRotwormSystem(["rotworm", "carrion worm"])
    
    # Inicializar
    if system.initialize():
        print("[OK] Sistema optimizado inicializado")
        
        # Mostrar información
        print(f"\n[STATS] ESTADISTICAS:")
        print(f"  Criaturas cargadas: {len(system.selected_creatures)}")
        print(f"  Criaturas objetivo: {system.target_creatures}")
        
        print(f"\n[TARGETS] CRIATURAS CONFIGURADAS:")
        for creature in system.get_selected_creatures():
            print(f"  • {creature['name'].title()}")
            print(f"    HP: {creature['hp']}")
            print(f"    Experiencia: {creature['experience']}")
            print(f"    Look Type: {creature['look_type']}")
            print(f"    Prioridad: {creature['priority']}")
            print(f"    Cuerpo: {creature['corpse_name']} (ID: {creature['corpse_id']})")
            print()
        
        # Guardar configuración
        system.save_configuration()
        
        print(f"[SUCCESS] Sistema optimizado funcionando")
        print(f"[INFO] Para iniciar el ataque:")
        print(f"       system.start_targeting()")
        
    else:
        print("[ERROR] Error inicializando sistema optimizado")

if __name__ == "__main__":
    main()
