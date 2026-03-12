#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeting_v2_integration.py - Integración completa del targeting V2 con selección de criaturas
Integra toda la información visual con el sistema de targeting existente.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from config import Config
from targeting_engine_v2 import TargetingEngineV2
from intelligent_targeting import IntelligentTargeting
from visual_targeting_system import VisualTargetingSystem
from creature_database import CreatureDatabase

logger = logging.getLogger(__name__)

class TargetingV2Integration:
    """Integración completa del targeting V2 con selección de criaturas."""
    
    def __init__(self, tibia_files_path: str = "tibia_files_canary"):
        self.tibia_files_path = tibia_files_path
        
        # Componentes del sistema
        self.targeting_engine: Optional[TargetingEngineV2] = None
        self.intelligent_targeting: Optional[IntelligentTargeting] = None
        self.visual_system: Optional[VisualTargetingSystem] = None
        self.creature_db: Optional[CreatureDatabase] = None
        
        # Configuración
        self.selected_creatures: List[str] = []
        self.ignored_creatures: List[str] = []
        self.creature_priorities: Dict[str, float] = {}
        
        # Estado
        self.is_initialized = False
    
    def initialize(self) -> bool:
        """Inicializa el sistema completo."""
        logger.info("Inicializando Targeting V2 Integration...")
        
        try:
            # 1. Inicializar componentes
            self._initialize_components()
            
            # 2. Descubrir criaturas
            self._discover_creatures()
            
            # 3. Calcular prioridades
            self._calculate_priorities()
            
            # 4. Configurar targeting engine
            self._configure_targeting_engine()
            
            self.is_initialized = True
            logger.info("Targeting V2 Integration inicializado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error inicializando Targeting V2 Integration: {e}")
            return False
    
    def _initialize_components(self):
        """Inicializa los componentes del sistema."""
        # Intelligent Targeting
        self.intelligent_targeting = IntelligentTargeting(self.tibia_files_path)
        
        # Visual Targeting System
        self.visual_system = VisualTargetingSystem(self.tibia_files_path)
        
        # Creature Database
        self.creature_db = CreatureDatabase(self.tibia_files_path)
        
        # Targeting Engine V2
        self.targeting_engine = TargetingEngineV2()
        
        logger.info("Componentes inicializados")
    
    def _discover_creatures(self):
        """Descubre todas las criaturas disponibles."""
        logger.info("Descubriendo criaturas...")
        
        discovered_creatures = set()
        
        # Desde la base de datos de criaturas
        if self.creature_db and self.creature_db.creatures:
            discovered_creatures.update(self.creature_db.creature_names)
            logger.info(f"Criaturas desde base de datos: {len(self.creature_db.creatures)}")
        
        # Desde el sistema visual
        if self.visual_system and self.visual_system.visual_database:
            visual_creatures = set(self.visual_system.visual_database.keys())
            discovered_creatures.update(visual_creatures)
            logger.info(f"Criaturas desde sistema visual: {len(visual_creatures)}")
        
        # Desde el sistema inteligente
        if self.intelligent_targeting and self.intelligent_targeting.creature_db:
            intelligent_creatures = set(self.intelligent_targeting.creature_db.creature_names)
            discovered_creatures.update(intelligent_creatures)
            logger.info(f"Criaturas desde sistema inteligente: {len(intelligent_creatures)}")
        
        # Criaturas comunes conocidas
        common_creatures = {
            "rat", "cave rat", "spider", "bat", "bug", "wolf", "bear", "pig", "snake",
            "orc", "orc warrior", "orc shaman", "orc berserker",
            "troll", "frost troll", "swamp troll", "mountain troll",
            "goblin", "goblin scavenger", "goblin assassin",
            "dwarf", "dwarf soldier", "dwarf geomancer", "dwarf guard",
            "elf", "elf arcanist", "elf scout",
            "minotaur", "minotaur archer", "minotaur mage",
            "dragon", "dragon hatchling", "dragon lord",
            "demon", "demon skeleton", "demon outcast",
            "amazon", "amazon warrior", "amazon valkyrie",
            "pirate", "pirate marauder", "pirate cutthroat",
            "slime", "carrion worm", "cave crawler",
            "skeleton", "skeleton warrior", "skeleton mage",
            "ghoul", "ghost",
            "vampire", "vampire spawn", "vampire bride",
            "wyvern", "dragon lord", "demon"
        }
        
        discovered_creatures.update(common_creatures)
        
        # Seleccionar criaturas por defecto (las más comunes)
        default_creatures = [
            "rat", "cave rat", "spider", "bat", "bug",
            "orc", "orc warrior", "orc shaman",
            "troll", "goblin", "goblin scavenger",
            "dwarf", "dwarf soldier",
            "minotaur", "minotaur archer",
            "skeleton", "skeleton warrior",
            "ghoul", "ghost",
            "vampire", "vampire spawn",
            "pirate", "pirate marauder",
            "slime", "carrion worm"
        ]
        
        self.selected_creatures = [c for c in default_creatures if c in discovered_creatures]
        self.ignored_creatures = list(discovered_creatures - set(self.selected_creatures))
        
        logger.info(f"Criaturas descubiertas: {len(discovered_creatures)}")
        logger.info(f"Seleccionadas por defecto: {len(self.selected_creatures)}")
        logger.info(f"Ignoradas por defecto: {len(self.ignored_creatures)}")
    
    def _calculate_priorities(self):
        """Calcula prioridades para las criaturas."""
        logger.info("Calculando prioridades...")
        
        for creature_name in self.selected_creatures + self.ignored_creatures:
            priority = self._calculate_creature_priority(creature_name)
            self.creature_priorities[creature_name] = priority
        
        # Ordenar seleccionadas por prioridad
        self.selected_creatures.sort(key=lambda x: self.creature_priorities.get(x, 50), reverse=True)
        
        logger.info(f"Prioridades calculadas para {len(self.creature_priorities)} criaturas")
    
    def _calculate_creature_priority(self, creature_name: str) -> float:
        """Calcula la prioridad de una criatura."""
        priority = 50.0  # Base priority
        
        # Obtener información
        creature_info = None
        visual_info = None
        
        if self.creature_db:
            creature_info = self.creature_db.get_creature(creature_name)
        
        if self.visual_system:
            visual_info = self.visual_system.get_visual_targeting_info(creature_name)
        
        if not creature_info and not visual_info:
            return priority
        
        # Aplicar factores de prioridad
        if creature_info:
            priority += creature_info.experience * 0.3
            priority += creature_info.max_health * 0.2
            priority += creature_info.difficulty_level * 100 * 0.3
            
            if creature_info.is_ranged:
                priority += 100 * 0.1
            if creature_info.is_mage:
                priority += 100 * 0.1
        
        if visual_info:
            indicators = visual_info.visual_indicators
            if indicators.get('is_ranged', False):
                priority += 100 * 0.1
            if indicators.get('is_mage', False):
                priority += 100 * 0.1
        
        # Ajustes específicos por tipo de criatura
        if "dragon" in creature_name.lower():
            priority += 500
        elif "demon" in creature_name.lower():
            priority += 400
        elif "amazon" in creature_name.lower():
            priority += 200
        elif "orc" in creature_name.lower() and ("shaman" in creature_name.lower() or "warrior" in creature_name.lower()):
            priority += 150
        elif "minotaur" in creature_name.lower() and ("lord" in creature_name.lower() or "mage" in creature_name.lower()):
            priority += 300
        
        return priority
    
    def _configure_targeting_engine(self):
        """Configura el targeting engine."""
        if not self.targeting_engine:
            return
        
        # Crear configuración
        targeting_config = {
            "enabled": True,
            "auto_attack": True,
            "chase_monsters": True,
            "attack_delay": 0.5,
            "re_attack_delay": 0.6,
            "chase_key": "",
            "stand_key": "",
            "attack_list": self.selected_creatures,
            "ignore_list": self.ignored_creatures,
            "priority_list": [],
            "creature_profiles": {}
        }
        
        # Configurar profiles para criaturas seleccionadas
        for creature_name in self.selected_creatures:
            profile = self._generate_creature_profile(creature_name)
            targeting_config["creature_profiles"][creature_name] = profile
        
        # Configurar el engine
        self.targeting_engine.configure(targeting_config)
        
        logger.info("Targeting engine configurado")
    
    def _generate_creature_profile(self, creature_name: str) -> Dict:
        """Genera un profile para una criatura."""
        profile = {
            "enabled": True,
            "chase_mode": "auto",
            "attack_mode": "offensive",
            "hp_thresholds": {
                "chase": 100,
                "stand": 30
            },
            "spells": []
        }
        
        # Obtener información
        creature_info = None
        visual_info = None
        
        if self.creature_db:
            creature_info = self.creature_db.get_creature(creature_name)
        
        if self.visual_system:
            visual_info = self.visual_system.get_visual_targeting_info(creature_name)
        
        # Ajustar profile según características
        if creature_info:
            # Ajustar según HP
            if creature_info.max_health >= 1000:
                profile["chase_mode"] = "careful"
                profile["attack_mode"] = "defensive"
                profile["hp_thresholds"]["chase"] = 200
                profile["hp_thresholds"]["stand"] = 50
            elif creature_info.max_health >= 500:
                profile["chase_mode"] = "auto"
                profile["hp_thresholds"]["chase"] = 150
                profile["hp_thresholds"]["stand"] = 40
            
            # Ajustar según tipo
            if creature_info.is_mage:
                profile["chase_mode"] = "aggressive"
                profile["attack_mode"] = "offensive"
                profile["hp_thresholds"]["chase"] = 80
                profile["hp_thresholds"]["stand"] = 20
            
            if creature_info.is_ranged:
                profile["chase_mode"] = "aggressive"
                profile["hp_thresholds"]["chase"] = 120
                profile["hp_thresholds"]["stand"] = 30
        
        if visual_info:
            indicators = visual_info.visual_indicators
            threat_level = indicators.get('threat_level', 'low')
            
            # Ajustar según nivel de amenaza
            if threat_level in ['high', 'extreme']:
                profile["chase_mode"] = "careful"
                profile["attack_mode"] = "defensive"
                profile["hp_thresholds"]["chase"] = 250
                profile["hp_thresholds"]["stand"] = 60
            elif threat_level == 'medium':
                profile["chase_mode"] = "auto"
                profile["hp_thresholds"]["chase"] = 150
                profile["hp_thresholds"]["stand"] = 40
        
        return profile
    
    def add_creature_to_attack(self, creature_name: str) -> bool:
        """Agrega una criatura a la lista de ataque."""
        if creature_name in self.ignored_creatures:
            self.ignored_creatures.remove(creature_name)
        
        if creature_name not in self.selected_creatures:
            # Calcular prioridad
            priority = self._calculate_creature_priority(creature_name)
            self.creature_priorities[creature_name] = priority
            
            # Agregar a seleccionadas en orden de prioridad
            self.selected_creatures.append(creature_name)
            self.selected_creatures.sort(key=lambda x: self.creature_priorities.get(x, 50), reverse=True)
            
            # Actualizar configuración
            self._configure_targeting_engine()
            
            logger.info(f"Criatura agregada a ataque: {creature_name}")
            return True
        
        return False
    
    def remove_creature_from_attack(self, creature_name: str) -> bool:
        """Quita una criatura de la lista de ataque."""
        if creature_name in self.selected_creatures:
            self.selected_creatures.remove(creature_name)
            self.ignored_creatures.append(creature_name)
            
            # Actualizar configuración
            self._configure_targeting_engine()
            
            logger.info(f"Criatura removida de ataque: {creature_name}")
            return True
        
        return False
    
    def get_creature_info(self, creature_name: str) -> Optional[Dict]:
        """Obtiene información completa de una criatura."""
        info = {
            "name": creature_name,
            "priority": self.creature_priorities.get(creature_name, 50.0),
            "selected": creature_name in self.selected_creatures,
            "ignored": creature_name in self.ignored_creatures
        }
        
        # Información de la base de datos
        if self.creature_db:
            creature_info = self.creature_db.get_creature(creature_name)
            if creature_info:
                info.update({
                    "hp": creature_info.max_health,
                    "experience": creature_info.experience,
                    "difficulty": creature_info.difficulty_level,
                    "is_ranged": creature_info.is_ranged,
                    "is_mage": creature_info.is_mage,
                    "is_healer": creature_info.is_healer,
                    "class_type": creature_info.class_type
                })
        
        # Información visual
        if self.visual_system:
            visual_info = self.visual_system.get_visual_targeting_info(creature_name)
            if visual_info:
                indicators = visual_info.visual_indicators
                info.update({
                    "look_type": visual_info.look_type,
                    "outfit": visual_info.outfit,
                    "corpse_info": visual_info.corpse_info,
                    "loot_info": visual_info.loot_info,
                    "threat_level": indicators.get('threat_level', 'unknown'),
                    "has_valuable_loot": indicators.get('has_valuable_loot', False)
                })
        
        return info
    
    def get_all_creatures(self) -> List[Dict]:
        """Obtiene información de todas las criaturas."""
        all_creatures = self.selected_creatures + self.ignored_creatures
        return [self.get_creature_info(c) for c in all_creatures]
    
    def get_selected_creatures(self) -> List[Dict]:
        """Obtiene información de las criaturas seleccionadas."""
        return [self.get_creature_info(c) for c in self.selected_creatures]
    
    def get_ignored_creatures(self) -> List[Dict]:
        """Obtiene información de las criaturas ignoradas."""
        return [self.get_creature_info(c) for c in self.ignored_creatures]
    
    def get_creatures_by_priority(self, limit: int = 20) -> List[Dict]:
        """Obtiene criaturas ordenadas por prioridad."""
        all_creatures = self.selected_creatures + self.ignored_creatures
        sorted_creatures = sorted(
            all_creatures,
            key=lambda x: self.creature_priorities.get(x, 50),
            reverse=True
        )
        
        return [self.get_creature_info(c) for c in sorted_creatures[:limit]]
    
    def search_creatures(self, query: str) -> List[Dict]:
        """Busca criaturas por nombre."""
        query_lower = query.lower()
        all_creatures = self.selected_creatures + self.ignored_creatures
        
        results = []
        for creature_name in all_creatures:
            if query_lower in creature_name.lower():
                results.append(self.get_creature_info(creature_name))
        
        return results
    
    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del sistema."""
        stats = {
            "total_creatures": len(self.selected_creatures) + len(self.ignored_creatures),
            "selected_creatures": len(self.selected_creatures),
            "ignored_creatures": len(self.ignored_creatures),
            "visual_database": len(self.visual_system.visual_database) if self.visual_system else 0,
            "corpse_templates": len(self.visual_system.corpse_templates) if self.visual_system else 0,
            "creature_database": len(self.creature_db.creatures) if self.creature_db else 0
        }
        
        # Estadísticas por tipo
        type_counts = {"mage": 0, "ranged": 0, "healer": 0, "melee": 0}
        threat_counts = {}
        
        for creature_name in self.selected_creatures + self.ignored_creatures:
            info = self.get_creature_info(creature_name)
            
            # Contar por tipo
            if info.get("is_mage", False):
                type_counts["mage"] += 1
            if info.get("is_ranged", False):
                type_counts["ranged"] += 1
            if info.get("is_healer", False):
                type_counts["healer"] += 1
            if not (info.get("is_mage", False) or info.get("is_ranged", False) or info.get("is_healer", False)):
                type_counts["melee"] += 1
            
            # Contar por amenaza
            threat = info.get("threat_level", "unknown")
            threat_counts[threat] = threat_counts.get(threat, 0) + 1
        
        stats.update({
            "type_counts": type_counts,
            "threat_counts": threat_counts
        })
        
        return stats
    
    def save_configuration(self, config_path: str = "targeting_v2_config.json"):
        """Guarda la configuración actual."""
        try:
            config = {
                "selected_creatures": self.selected_creatures,
                "ignored_creatures": self.ignored_creatures,
                "creature_priorities": self.creature_priorities,
                "statistics": self.get_statistics()
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuración guardada en: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False
    
    def load_configuration(self, config_path: str = "targeting_v2_config.json"):
        """Carga la configuración desde archivo."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.selected_creatures = config.get("selected_creatures", [])
            self.ignored_creatures = config.get("ignored_creatures", [])
            self.creature_priorities = config.get("creature_priorities", {})
            
            # Actualizar configuración del targeting engine
            self._configure_targeting_engine()
            
            logger.info(f"Configuración cargada desde: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return False
    
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
                "ignored_creatures": len(self.ignored_creatures),
                "is_initialized": self.is_initialized
            })
            return status
            
        except Exception as e:
            return {"error": f"Error obteniendo estado: {e}"}

def main():
    """Función principal para probar la integración."""
    print("=== TARGETING V2 INTEGRATION ===\n")
    
    # Crear sistema de integración
    integration = TargetingV2Integration()
    
    # Inicializar
    if integration.initialize():
        print("[OK] Sistema de integración inicializado")
        
        # Mostrar estadísticas
        stats = integration.get_statistics()
        print(f"\n[STATS] ESTADISTICAS:")
        print(f"  Total criaturas: {stats['total_creatures']}")
        print(f"  Seleccionadas: {stats['selected_creatures']}")
        print(f"  Ignoradas: {stats['ignored_creatures']}")
        print(f"  Base de datos visual: {stats['visual_database']}")
        print(f"  Templates de cuerpos: {stats['corpse_templates']}")
        
        # Mostrar criaturas seleccionadas
        print(f"\n[TARGETS] CRIATURAS SELECCIONADAS ({len(integration.selected_creatures)}):")
        for i, creature in enumerate(integration.get_selected_creatures()[:10], 1):
            print(f"  {i:2d}. {creature['name'].title()} (Prioridad: {creature['priority']:.1f})")
        
        if len(integration.selected_creatures) > 10:
            print(f"  ... y {len(integration.selected_creatures) - 10} mas")
        
        # Probar búsqueda
        print(f"\n[SEARCH] PRUEBA DE BUSQUEDA:")
        search_results = integration.search_creatures("dragon")
        for result in search_results:
            print(f"  {result['name'].title()} - Prioridad: {result['priority']:.1f}")
        
        # Guardar configuración
        integration.save_configuration()
        
        print(f"\n[SUCCESS] Sistema de integracion funcionando correctamente")
        print(f"[INFO] Para usar en el bot principal:")
        print(f"       integration = TargetingV2Integration()")
        print(f"       integration.initialize()")
        print(f"       integration.start_targeting()")
        
    else:
        print("[ERROR] Error inicializando sistema de integración")

if __name__ == "__main__":
    main()
