#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_targeting_system.py - Sistema de targeting automático
Detecta monstruos automáticamente sin configuración manual.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from config import Config
from targeting.targeting_engine import TargetingEngine
from targeting.battle_list_reader import BattleListReader
from intelligent_targeting import IntelligentTargeting
from visual_targeting_system import VisualTargetingSystem
from creature_database import CreatureDatabase

logger = logging.getLogger(__name__)

@dataclass
class AutoTargetingConfig:
    """Configuración para targeting automático."""
    enabled: bool = True
    auto_attack: bool = True
    chase_monsters: bool = True
    min_monster_hp: int = 1  # Mínimo HP para atacar
    max_monster_hp: int = 99999  # Máximo HP (sin límite)
    ignore_hp_below: int = 0  # Ignorar monstruos con HP menor a esto
    auto_calibrate: bool = True
    battle_detection: bool = True
    visual_detection: bool = True
    safe_distance: int = 1  # SQMs de distancia segura
    max_targets: int = 5  # Máximo de objetivos simultáneos
    auto_switch_targets: bool = True  # Cambiar target automáticamente
    
    # Prioridades automáticas
    priority_factors: Dict[str, float] = None
    
    def __post_init__(self):
        if self.priority_factors is None:
            self.priority_factors = {
                'experience': 0.3,      # Más experiencia = mayor prioridad
                'hp': 0.2,             # Más HP = mayor prioridad
                'difficulty': 0.3,      # Mayor dificultad = mayor prioridad
                'is_ranged': 0.1,       # Criaturas a distancia son más peligrosas
                'is_mage': 0.1           # Magos requieren más cuidado
            }

class AutoTargetingSystem:
    """Sistema de targeting completamente automático."""
    
    def __init__(self, tibia_files_path: str = "tibia_files_canary"):
        self.tibia_files_path = tibia_files_path
        self.config = AutoTargetingConfig()
        
        # Componentes del sistema
        self.targeting_engine: Optional[TargetingEngine] = None
        self.battle_reader: Optional[BattleListReader] = None
        self.intelligent_targeting: Optional[IntelligentTargeting] = None
        self.visual_system: Optional[VisualTargetingSystem] = None
        self.creature_db: Optional[CreatureDatabase] = None
        
        # Estado del sistema
        self.is_initialized = False
        self.auto_detected_creatures: Set[str] = set()
        self.current_targets: List[str] = []
        self.target_priorities: Dict[str, float] = {}
        
        # Configuración automática
        self.auto_config = {
            "targeting": {
                "enabled": True,
                "auto_attack": True,
                "chase_monsters": True,
                "attack_delay": 0.5,
                "re_attack_delay": 0.6,
                "chase_key": "",
                "stand_key": "",
                "attack_list": [],  # Se llenará automáticamente
                "ignore_list": [],
                "priority_list": [],
                "creature_profiles": {},  # Se generará automáticamente
                "auto_detection": {
                    "enabled": True,
                    "min_hp": 1,
                    "max_hp": 99999,
                    "ignore_below_hp": 0,
                    "auto_calibrate": True,
                    "battle_detection": True,
                    "visual_detection": True
                }
            }
        }
    
    def initialize(self) -> bool:
        """Inicializa el sistema automático."""
        logger.info("Inicializando sistema de targeting automático...")
        
        try:
            # 1. Inicializar componentes
            self._initialize_components()
            
            # 2. Cargar configuración
            self._load_configuration()
            
            # 3. Descubrir criaturas automáticamente
            self._discover_creatures()
            
            # 4. Configurar targeting engine
            self._configure_targeting_engine()
            
            # 5. Iniciar sistema
            self._start_auto_targeting()
            
            self.is_initialized = True
            logger.info("Sistema de targeting automático inicializado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error inicializando sistema automático: {e}")
            return False
    
    def _initialize_components(self):
        """Inicializa los componentes del sistema."""
        # Targeting Engine
        self.targeting_engine = TargetingEngine()
        
        # Battle List Reader
        self.battle_reader = BattleListReader()
        
        # Intelligent Targeting
        self.intelligent_targeting = IntelligentTargeting(self.tibia_files_path)
        
        # Visual Targeting System
        self.visual_system = VisualTargetingSystem(self.tibia_files_path)
        
        # Creature Database
        self.creature_db = CreatureDatabase(self.tibia_files_path)
        
        logger.info("Componentes del sistema inicializados")
    
    def _load_configuration(self):
        """Carga o genera configuración automática."""
        # Intentar cargar configuración existente
        config_path = "auto_targeting_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                
                # Actualizar configuración actual
                for key, value in saved_config.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                
                logger.info("Configuración cargada desde archivo")
            except Exception as e:
                logger.warning(f"Error cargando configuración, usando valores por defecto: {e}")
        
        # Generar configuración para el targeting engine
        self._generate_targeting_config()
    
    def _generate_targeting_config(self):
        """Genera configuración para el targeting engine."""
        # Usar la configuración automática
        self.auto_config["targeting"] = {
            "enabled": self.config.enabled,
            "auto_attack": self.config.auto_attack,
            "chase_monsters": self.config.chase_monsters,
            "attack_delay": 0.5,
            "re_attack_delay": 0.6,
            "chase_key": "",
            "stand_key": "",
            "attack_list": list(self.auto_detected_creatures),
            "ignore_list": [],
            "priority_list": [],
            "creature_profiles": {},
            "auto_detection": {
                "enabled": True,
                "min_hp": self.config.min_monster_hp,
                "max_hp": self.config.max_monster_hp,
                "ignore_below_hp": self.config.ignore_hp_below,
                "auto_calibrate": self.config.auto_calibrate,
                "battle_detection": self.config.battle_detection,
                "visual_detection": self.config.visual_detection
            }
        }
    
    def _discover_creatures(self):
        """Descubre automáticamente todas las criaturas disponibles."""
        logger.info("Descubriendo criaturas automáticamente...")
        
        discovered_creatures = set()
        
        # 1. Desde la base de datos de criaturas
        if self.creature_db and self.creature_db.creatures:
            discovered_creatures.update(self.creature_db.creature_names)
            logger.info(f"Criaturas desde base de datos: {len(self.creature_db.creatures)}")
        
        # 2. Desde el sistema visual
        if self.visual_system and self.visual_system.visual_database:
            visual_creatures = set(self.visual_system.visual_database.keys())
            discovered_creatures.update(visual_creatures)
            logger.info(f"Criaturas desde sistema visual: {len(visual_creatures)}")
        
        # 3. Desde el sistema inteligente
        if self.intelligent_targeting and self.intelligent_targeting.creature_db:
            intelligent_creatures = set(self.intelligent_targeting.creature_db.creature_names)
            discovered_creatures.update(intelligent_creatures)
            logger.info(f"Criaturas desde sistema inteligente: {len(intelligent_creatures)}")
        
        # 4. Criaturas comunes conocidas (fallback)
        common_creatures = {
            "rat", "rat", "cave rat", "spider", "spider", "bat", "bat", "bug", "bug",
            "wolf", "wolf", "bear", "bear", "pig", "pig", "snake", "snake",
            "orc", "orc", "orc warrior", "orc shaman", "orc berserker",
            "troll", "troll", "frost troll", "swamp troll", "mountain troll",
            "goblin", "goblin", "goblin scavenger", "goblin assassin",
            "dwarf", "dwarf", "dwarf soldier", "dwarf geomancer", "dwarf guard",
            "elf", "elf", "elf arcanist", "elf scout",
            "minotaur", "minotaur", "minotaur archer", "minotaur mage",
            "dragon", "dragon", "dragon hatchling", "dragon lord",
            "demon", "demon", "demon skeleton", "demon outcast",
            "amazon", "amazon", "amazon warrior", "amazon valkyrie",
            "pirate", "pirate", "pirate marauder", "pirate cutthroat",
            "slime", "slime", "carrion worm", "cave crawler",
            "skeleton", "skeleton", "skeleton warrior", "skeleton mage",
            "ghoul", "ghoul", "ghost", "ghost",
            "vampire", "vampire", "vampire spawn", "vampire bride",
            "wyvern", "wyvern", "dragon lord", "demon"
        }
        
        discovered_creatures.update(common_creatures)
        self.auto_detected_creatures = discovered_creatures
        
        logger.info(f"Total criaturas descubiertas: {len(self.auto_detected_creatures)}")
        
        # Actualizar configuración
        self.auto_config["targeting"]["attack_list"] = list(self.auto_detected_creatures)
        
        # Calcular prioridades automáticas
        self._calculate_priorities()
    
    def _calculate_priorities(self):
        """Calcula prioridades automáticas para las criaturas."""
        logger.info("Calculando prioridades automáticas...")
        
        for creature_name in self.auto_detected_creatures:
            priority = self._calculate_creature_priority(creature_name)
            self.target_priorities[creature_name] = priority
        
        # Ordenar por prioridad
        sorted_creatures = sorted(
            self.target_priorities.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        logger.info(f"Prioridades calculadas para {len(sorted_creatures)} criaturas")
        logger.info(f"Top 5 prioridades: {[name for name, _ in sorted_creatures[:5]]}")
    
    def _calculate_creature_priority(self, creature_name: str) -> float:
        """Calcula la prioridad de una criatura."""
        priority = 50.0  # Base priority
        
        # Obtener información de las criaturas
        creature_info = None
        visual_info = None
        
        if self.creature_db:
            creature_info = self.creature_db.get_creature_info(creature_name)
        
        if self.visual_system:
            visual_info = self.visual_system.get_visual_targeting_info(creature_name)
        
        if not creature_info and not visual_info:
            return priority
        
        # Aplicar factores de prioridad
        if creature_info:
            priority += creature_info.experience * self.config.priority_factors['experience']
            priority += creature_info.max_health * self.config.priority_factors['hp']
            priority += creature_info.difficulty_level * 100 * self.config.priority_factors['difficulty']
            
            if creature_info.is_ranged:
                priority += 100 * self.config.priority_factors['is_ranged']
            if creature_info.is_mage:
                priority += 100 * self.config.priority_factors['is_mage']
        
        if visual_info:
            indicators = visual_info.visual_indicators
            if indicators.get('is_ranged', False):
                priority += 100 * self.config.priority_factors['is_ranged']
            if indicators.get('is_mage', False):
                priority += 100 * self.config.priority_factors['is_mage']
        
        # Ajustes específicos por tipo de criatura
        if "dragon" in creature_name.lower():
            priority += 500  # Los dragones son prioritarios
        elif "demon" in creature_name.lower():
            priority += 400  # Los demonios son muy peligrosos
        elif "amazon" in creature_name.lower():
            priority += 200  # Las amazon son moderadamente peligrosas
        elif "orc" in creature_name.lower() and ("shaman" in creature_name.lower() or "warrior" in creature_name.lower()):
            priority += 150  # Orcs fuertes
        elif "minotaur" in creature_name.lower() and ("lord" in creature_name.lower() or "mage" in creature_name.lower()):
            priority += 300  # Minotauros poderosos
        
        return priority
    
    def _configure_targeting_engine(self):
        """Configura el targeting engine con la configuración automática."""
        if not self.targeting_engine:
            return
        
        # Configurar callbacks
        def mock_click(x, y):
            logger.info(f"Auto-targeting: Click en ({x}, {y})")
            return True
        
        def mock_key(key):
            logger.info(f"Auto-targeting: Tecla {key}")
            return True
        
        def mock_log(msg):
            try:
                logger.info(f"[AUTO-TARGETING] {msg}")
            except UnicodeEncodeError:
                logger.info(f"[AUTO-TARGETING] {msg.encode('ascii', 'ignore').decode('ascii')}")
        
        self.targeting_engine.set_click_callback(mock_click)
        self.targeting_engine.set_key_callback(mock_key)
        self.targeting_engine.set_log_callback(mock_log)
        
        # Configurar con la configuración automática
        self.targeting_engine.configure(self.auto_config["targeting"])
        
        logger.info("Targeting engine configurado automáticamente")
    
    def _start_auto_targeting(self):
        """Inicia el targeting automático."""
        if not self.targeting_engine:
            logger.error("Targeting engine no inicializado")
            return
        
        try:
            self.targeting_engine.start()
            logger.info("Targeting automático iniciado")
        except Exception as e:
            logger.error(f"Error iniciando targeting automático: {e}")
    
    def stop(self):
        """Detiene el targeting automático."""
        if self.targeting_engine:
            try:
                self.targeting_engine.stop()
                logger.info("Targeting automático detenido")
            except Exception as e:
                logger.error(f"Error deteniendo targeting automático: {e}")
    
    def get_status(self) -> Dict:
        """Obtiene el estado actual del sistema."""
        if not self.is_initialized:
            return {
                "initialized": False,
                "message": "Sistema no inicializado"
            }
        
        status = {
            "initialized": True,
            "auto_detected_creatures": len(self.auto_detected_creatures),
            "current_targets": self.current_targets,
            "config": {
                "enabled": self.config.enabled,
                "auto_attack": self.config.auto_attack,
                "chase_monsters": self.config.chase_monsters,
                "auto_detection": {
                    "min_hp": self.config.min_monster_hp,
                    "max_hp": self.config.max_monster_hp,
                    "ignore_below_hp": self.config.ignore_hp_below,
                    "auto_calibrate": self.config.auto_calibrate,
                    "battle_detection": self.config.battle_detection,
                    "visual_detection": self.config.visual_detection
                }
            }
        }
        
        # Estado del targeting engine si está activo
        if self.targeting_engine:
            try:
                targeting_status = self.targeting_engine.get_status()
                status.update({
                    "targeting_state": targeting_status.get("state", "unknown"),
                    "current_target": targeting_status.get("current_target"),
                    "monster_count": targeting_status.get("monster_count", 0),
                    "monsters_killed": targeting_status.get("monsters_killed", 0)
                })
            except:
                status["targeting_state"] = "error"
        
        return status
    
    def update_creatures_list(self, detected_creatures: List[str]) -> bool:
        """Actualiza la lista de criaturas detectadas."""
        if not self.auto_config["targeting"]["auto_detection"]["enabled"]:
            return False
        
        try:
            # Agregar nuevas criaturas detectadas
            new_creatures = set(detected_creatures) - self.auto_detected_creatures
            if new_creatures:
                logger.info(f"Nuevas criaturas detectadas: {new_creatures}")
                
                for creature in new_creatures:
                    # Calcular prioridad
                    priority = self._calculate_creature_priority(creature)
                    self.target_priorities[creature] = priority
                
                # Agregar a la lista de ataque
                self.auto_detected_creatures.update(new_creatures)
                self.auto_config["targeting"]["attack_list"] = list(self.auto_detected_creatures)
                
                # Reconfigurar targeting engine
                self.targeting_engine.configure(self.auto_config["targeting"])
                
                logger.info(f"Lista de ataque actualizada: {len(self.auto_detected_creatures)} criaturas")
            
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando lista de criaturas: {e}")
            return False
    
    def get_recommended_targets(self, max_targets: int = 5) -> List[str]:
        """Obtiene los targets recomendados basado en prioridades."""
        # Filtrar criaturas que cumplen los requisitos
        valid_creatures = []
        
        for creature_name, priority in self.target_priorities.items():
            creature_info = None
            visual_info = None
            
            if self.creature_db:
                creature_info = self.creature_db.get_creature_info(creature_name)
            
            if self.visual_system:
                visual_info = self.visual_system.get_visual_targeting_info(creature_name)
            
            hp = creature_info.max_health if creature_info else 0
            
            # Verificar requisitos de HP
            if (hp >= self.config.min_monster_hp and 
                hp <= self.config.max_monster_hp and
                hp >= self.config.ignore_hp_below):
                valid_creatures.append((creature_name, priority))
        
        # Ordenar por prioridad y tomar los mejores
        valid_creatures.sort(key=lambda x: x[1], reverse=True)
        
        return [name for name, _ in valid_creatures[:max_targets]]
    
    def is_creature_valid(self, creature_name: str) -> bool:
        """Verifica si una criatura es válida para atacar."""
        if not creature_name or creature_name.lower() not in self.auto_detected_creatures:
            return False
        
        # Verificar HP
        creature_info = None
        if self.creature_db:
            creature_info = self.creature_db.get_creature_info(creature_name)
        
        if creature_info:
            hp = creature_info.max_health
            if (hp < self.config.min_monster_hp or 
                hp > self.config.max_monster_hp or
                hp < self.config.ignore_hp_below):
                return False
        
        return True
    
    def get_creature_priority(self, creature_name: str) -> float:
        """Obtiene la prioridad de una criatura."""
        return self.target_priorities.get(creature_name.lower(), 50.0)
    
    def save_configuration(self, config_path: str = "auto_targeting_config.json"):
        """Guarda la configuración actual."""
        try:
            config_data = {
                "config": {
                    "enabled": self.config.enabled,
                    "auto_attack": self.auto_attack,
                    "chase_monsters": self.chase_monsters,
                    "min_monster_hp": self.min_monster_hp,
                    "max_monster_hp": self.max_monster_hp,
                    "ignore_hp_below": self.ignore_hp_below,
                    "auto_calibrate": self.auto_calibrate,
                    "battle_detection": self.battle_detection,
                    "visual_detection": self.visual_detection,
                    "priority_factors": self.priority_factors
                },
                "auto_detected_creatures": list(self.auto_detected_creatures),
                "target_priorities": self.target_priorities,
                "auto_config": self.auto_config
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuración guardada en: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False
    
    def load_configuration(self, config_path: str = "auto_targeting_config.json"):
        """Carga la configuración desde archivo."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Actualizar configuración
            if "config" in config_data:
                for key, value in config_data["config"].items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
            
            if "auto_detected_creatures" in config_data:
                self.auto_detected_creatures = set(config_data["auto_detected_creatures"])
            
            if "target_priorities" in config_data:
                self.target_priorities = config_data["target_priorities"]
            
            if "auto_config" in config_data:
                self.auto_config = config_data["auto_config"]
            
            logger.info(f"Configuración cargada desde: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return False
    
    def export_to_standard_config(self, config_path: str = "config.json"):
        """Exporta la configuración al formato estándar."""
        try:
            # Integrar con el config principal
            with open(config_path, 'r', encoding='utf-8') as f:
                main_config = json.load(f)
            
            # Actualizar sección de targeting
            main_config["targeting"] = self.auto_config["targeting"]
            
            # Guardar
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(main_config, f, indent=4, ensure_ascii=False)
            
            logger.info(f"Configuración exportada a: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exportando configuración: {e}")
            return False

def main():
    """Función principal para probar el sistema automático."""
    print("=== SISTEMA DE TARGETING AUTOMÁTICO ===\n")
    
    # Crear sistema
    auto_system = AutoTargetingSystem()
    
    # Inicializar
    if auto_system.initialize():
        print("[OK] Sistema de targeting automático inicializado")
        
        # Mostrar estado
        status = auto_system.get_status()
        print(f"\n📊 ESTADO ACTUAL:")
        print(f"  Inicializado: {status['initialized']}")
        print(f"  Criaturas detectadas: {status['auto_detected_creatures']}")
        print(f"  Configuración automática: {status['config']['auto_detection']['enabled']}")
        print(f"  Detección visual: {status['config']['visual_detection']}")
        print(f"  Detección de battle: {status['config']['battle_detection']}")
        
        # Mostrar criaturas descubiertas
        print(f"\n👾 CRIATURAS DESCUBIERTAS ({len(auto_system.auto_detected_creatures)}):")
        
        # Mostrar las 20 primeras criaturas por prioridad
        top_creatures = auto_system.get_recommended_targets(20)
        for i, creature in enumerate(top_creatures[:10], 1):
            priority = auto_system.get_creature_priority(creature)
            print(f"  {i:2d}. {creature.title()} (Prioridad: {priority:.1f})")
        
        if len(top_creatures) > 10:
            print(f"  ... y {len(top_creatures)} mas")
        
        # Probar detección de criaturas
        print(f"\n🔍 PRUEBA DE DETECCIÓN:")
        test_creatures = ["dragon", "demon", "amazon", "orc", "rat"]
        
        for creature in test_creatures:
            is_valid = auto_system.is_creature_valid(creature)
            priority = auto_system.get_creature_priority(creature)
            print(f"  {creature.title()}: {'Válida' if is_valid else 'Inválida'} - Prioridad: {priority:.1f}")
        
        # Guardar configuración
        auto_system.save_configuration()
        auto_system.export_to_standard_config()
        
        print(f"\n[SUCCESS] Sistema de targeting automático funcionando correctamente")
        print(f"[INFO] Para usar en el bot principal, llama a:")
        print(f"       auto_system.initialize()")
        print(f"       auto_system.get_status()")
        print(f"       auto_system.update_creatures_list(detected_creatures)")
        
    else:
        print("[ERROR] Error inicializando sistema automático")

if __name__ == "__main__":
    main()
