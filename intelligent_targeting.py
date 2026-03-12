#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
intelligent_targeting.py - Sistema de targeting inteligente
Integra la base de datos de criaturas con el targeting V2 para comportamiento adaptativo.
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from creature_database import CreatureDatabase, CreatureInfo
from config import Config
import logging

logger = logging.getLogger(__name__)

class IntelligentTargeting:
    """Sistema de targeting inteligente que se adapta a cada criatura."""
    
    def __init__(self, tibia_files_path: str = "tibia_files_canary"):
        self.db_path = "creature_database.json"
        self.profiles_path = "auto_targeting_profiles.json"
        self.creature_db: Optional[CreatureDatabase] = None
        self.auto_profiles: Dict[str, Dict] = {}
        self.manual_profiles: Dict[str, Dict] = {}
        self.current_target_info: Optional[CreatureInfo] = None
        self.lazy_loaded_creatures: Dict[str, CreatureInfo] = {}  # Cache de criaturas cargadas bajo demanda
        self.database_loaded = False
        
        # Cargar perfiles automáticos (sin cargar la base de datos completa)
        self._load_profiles_only()
    
    def _load_profiles_only(self):
        """Carga solo los perfiles sin cargar la base de datos completa."""
        # Cargar perfiles automáticos
        if os.path.exists(self.profiles_path):
            with open(self.profiles_path, 'r', encoding='utf-8') as f:
                self.auto_profiles = json.load(f)
            logger.info(f"Perfiles automáticos cargados: {len(self.auto_profiles)}")
        
        logger.info("Sistema inicializado en modo lazy-loading")
    
    def load_creatures_on_demand(self, creature_names: List[str]) -> bool:
        """Carga criaturas específicas bajo demanda."""
        if self.database_loaded:
            return True
        
        try:
            # Crear base de datos temporal para carga selectiva
            temp_db = CreatureDatabase("tibia_files_canary")
            
            if not temp_db.load_database(self.db_path):
                logger.error("No se pudo cargar la base de datos")
                return False
            
            # Cargar solo las criaturas solicitadas
            loaded_count = 0
            for name in creature_names:
                creature_info = temp_db.get_creature(name)
                if creature_info:
                    self.lazy_loaded_creatures[name.lower()] = creature_info
                    loaded_count += 1
            
            logger.info(f"Cargadas {loaded_count} criaturas bajo demanda")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando criaturas bajo demanda: {e}")
            return False
    
    def load_full_database(self) -> bool:
        """Carga la base de datos completa (solo cuando se necesita)."""
        if self.database_loaded:
            return True
        
        if not os.path.exists(self.db_path):
            logger.warning("No existe la base de datos de criaturas")
            return False
        
        try:
            self.creature_db = CreatureDatabase("tibia_files_canary")
            if self.creature_db.load_database(self.db_path):
                self.database_loaded = True
                logger.info(f"Base de datos completa cargada: {len(self.creature_db.creatures)} criaturas")
                return True
            else:
                logger.error("Error cargando base de datos completa")
                self.creature_db = None
                return False
                
        except Exception as e:
            logger.error(f"Error cargando base de datos completa: {e}")
            self.creature_db = None
            return False
    
    def get_creature_info(self, creature_name: str) -> Optional[CreatureInfo]:
        """Obtiene información completa de una criatura (con lazy loading)."""
        creature_name_lower = creature_name.lower()
        
        # 1. Buscar en el cache de criaturas cargadas bajo demanda
        if creature_name_lower in self.lazy_loaded_creatures:
            return self.lazy_loaded_creatures[creature_name_lower]
        
        # 2. Si la base de datos completa está cargada, buscar ahí
        if self.database_loaded and self.creature_db:
            return self.creature_db.get_creature(creature_name)
        
        # 3. Intentar cargar esta criatura específica bajo demanda
        if self.load_creatures_on_demand([creature_name]):
            return self.lazy_loaded_creatures.get(creature_name_lower)
        
        # 4. No se encontró la criatura
        return None
    
    def get_effective_profile(self, creature_name: str) -> Dict:
        """Obtiene el perfil efectivo para una criatura (manual > automático > default)."""
        creature_name_lower = creature_name.lower()
        
        # 1. Buscar perfil manual primero
        if creature_name_lower in self.manual_profiles:
            return self.manual_profiles[creature_name_lower]
        
        # 2. Buscar perfil automático
        if creature_name_lower in self.auto_profiles:
            return self.auto_profiles[creature_name_lower]
        
        # 3. Buscar en nombres similares (para variaciones)
        for name, profile in self.auto_profiles.items():
            if creature_name_lower in name or name in creature_name_lower:
                logger.info(f"Usando perfil similar: {name} -> {creature_name}")
                return profile
        
        # 4. Perfil por defecto
        return self._get_default_profile()
    
    def _get_default_profile(self) -> Dict:
        """Retorna el perfil por defecto para criaturas desconocidas."""
        return {
            "chase_mode": "auto",
            "attack_mode": "offensive",
            "flees_at_hp": 0.0,
            "is_ranged": False,
            "priority": 50,
            "use_chase_on_flee": True,
            "hp_threshold_chase": 0.0,
            "hp_threshold_stand": 0.0,
            "spells_by_count": {
                "1": ["exori"],
                "2": ["exori gran", "exori"],
                "3": ["exori mas", "exori gran", "exori"],
                "default": ["exori"]
            },
            "spell_cooldown": 1.5,
            "auto_generated": False,
            "unknown_creature": True
        }
    
    def set_manual_profile(self, creature_name: str, profile: Dict):
        """Establece un perfil manual para una criatura."""
        self.manual_profiles[creature_name.lower()] = profile
        logger.info(f"Perfil manual establecido para: {creature_name}")
    
    def update_target_info(self, creature_name: str):
        """Actualiza la información del target actual."""
        self.current_target_info = self.get_creature_info(creature_name)
        
        if self.current_target_info:
            logger.info(f"Target detectado: {creature_name}")
            logger.info(f"  HP: {self.current_target_info.max_health}")
            logger.info(f"  Exp: {self.current_target_info.experience}")
            logger.info(f"  Clase: {self.current_target_info.class_type}")
            logger.info(f"  Ranged: {self.current_target_info.is_ranged}")
            logger.info(f"  Mage: {self.current_target_info.is_mage}")
            logger.info(f"  Dificultad: {self.current_target_info.difficulty_level}")
    
    def get_recommended_spells(self, creature_name: str, nearby_creatures: List[str]) -> List[str]:
        """Obtiene los spells recomendados basados en las criaturas cercanas."""
        if not self.current_target_info:
            return []
        
        creature_count = len(nearby_creatures)
        profile = self.get_effective_profile(creature_name)
        
        spells_by_count = profile.get("spells_by_count", {})
        
        # Determinar qué spells usar basados en la cantidad
        if creature_count >= 3:
            return spells_by_count.get("3", [])
        elif creature_count == 2:
            return spells_by_count.get("2", [])
        elif creature_count == 1:
            return spells_by_count.get("1", [])
        else:
            return spells_by_count.get("default", [])
    
    def get_attack_strategy(self, creature_name: str) -> Dict:
        """Obtiene la estrategia de ataque recomendada."""
        creature_info = self.get_creature_info(creature_name)
        if not creature_info:
            return {"mode": "offensive", "distance": 1, "reason": "unknown_creature"}
        
        profile = self.get_effective_profile(creature_name)
        
        strategy = {
            "mode": profile.get("attack_mode", "offensive"),
            "distance": creature_info.target_distance,
            "chase_mode": profile.get("chase_mode", "auto"),
            "hp_threshold_chase": profile.get("hp_threshold_chase", 0.0),
            "hp_threshold_stand": profile.get("hp_threshold_stand", 0.0),
            "reason": self._get_strategy_reason(creature_info, profile)
        }
        
        return strategy
    
    def _get_strategy_reason(self, creature: CreatureInfo, profile: Dict) -> str:
        """Obtiene la razón de la estrategia seleccionada."""
        reasons = []
        
        if creature.is_mage:
            reasons.append("criatura_maga")
        if creature.is_ranged:
            reasons.append("criatura_a_distancia")
        if creature.is_healer:
            reasons.append("criatura_curandera")
        if creature.max_health >= 1000:
            reasons.append("criatura_fuerte")
        if creature.difficulty_level >= 4:
            reasons.append("alta_dificultad")
        if creature.can_summon:
            reasons.append("puede_invocar")
        
        return ", ".join(reasons) if reasons else "criatura_estandar"
    
    def should_use_chase_mode(self, creature_name: str, current_hp_percentage: float) -> bool:
        """Determina si debe usar chase mode basado en el HP de la criatura."""
        profile = self.get_effective_profile(creature_name)
        
        chase_threshold = profile.get("hp_threshold_chase", 0.0)
        stand_threshold = profile.get("hp_threshold_stand", 0.0)
        
        if chase_threshold > 0 and current_hp_percentage <= (chase_threshold * 100):
            return True
        
        if stand_threshold > 0 and current_hp_percentage >= (stand_threshold * 100):
            return False
        
        # Si no hay umbrales, usar el modo configurado
        chase_mode = profile.get("chase_mode", "auto")
        return chase_mode == "chase"
    
    def search_creatures_by_pattern(self, query: str, limit: int = 10) -> List[CreatureInfo]:
        """Busca criaturas por patrón (con lazy loading)."""
        query = query.lower()
        results = []
        
        # 1. Buscar en el cache de criaturas cargadas
        for creature in self.lazy_loaded_creatures.values():
            if query in creature.name.lower():
                results.append(creature)
                if len(results) >= limit:
                    return results
        
        # 2. Si no hay suficientes resultados y la BD completa está cargada
        if self.database_loaded and self.creature_db:
            all_results = self.creature_db.search_creatures(query)
            # Combinar con resultados existentes (sin duplicados)
            existing_names = {c.name.lower() for c in results}
            for creature in all_results:
                if creature.name.lower() not in existing_names:
                    results.append(creature)
                    if len(results) >= limit:
                        break
        
        # 3. Si no hay resultados y la BD no está cargada, cargarla para búsqueda completa
        elif not self.database_loaded and len(results) < limit:
            logger.info("Cargando base de datos completa para búsqueda...")
            if self.load_full_database():
                all_results = self.creature_db.search_creatures(query)
                results.extend(all_results[:limit - len(results)])
        
        return results[:limit]
    
    def get_target_priority(self, creature_name: str) -> int:
        """Obtiene la prioridad de ataque para una criatura."""
        profile = self.get_effective_profile(creature_name)
        return profile.get("priority", 50)
    
    def analyze_creatures_in_area(self, detected_creatures: List[str]) -> Dict:
        """Analiza las criaturas detectadas en el área."""
        analysis = {
            "total_creatures": len(detected_creatures),
            "unique_types": len(set(detected_creatures)),
            "known_creatures": 0,
            "unknown_creatures": 0,
            "threat_level": "low",
            "recommended_spells": [],
            "creatures_by_class": {},
            "highest_priority": None,
            "dangerous_creatures": []
        }
        
        creature_priorities = {}
        
        for creature_name in detected_creatures:
            creature_info = self.get_creature_info(creature_name)
            
            if creature_info:
                analysis["known_creatures"] += 1
                
                # Agrupar por clase
                class_type = creature_info.class_type
                analysis["creatures_by_class"][class_type] = analysis["creatures_by_class"].get(class_type, 0) + 1
                
                # Calcular prioridad
                priority = self.get_target_priority(creature_name)
                creature_priorities[creature_name] = priority
                
                # Identificar criaturas peligrosas
                if (creature_info.difficulty_level >= 4 or 
                    creature_info.max_health >= 1000 or 
                    creature_info.is_mage and creature_info.is_ranged):
                    analysis["dangerous_creatures"].append({
                        "name": creature_name,
                        "reason": f"HP:{creature_info.max_health}, Diff:{creature_info.difficulty_level}, Mage:{creature_info.is_mage}, Ranged:{creature_info.is_ranged}"
                    })
            else:
                analysis["unknown_creatures"] += 1
        
        # Determinar criatura de mayor prioridad
        if creature_priorities:
            analysis["highest_priority"] = max(creature_priorities, key=creature_priorities.get)
        
        # Determinar nivel de amenaza
        if analysis["dangerous_creatures"]:
            analysis["threat_level"] = "high"
        elif analysis["known_creatures"] >= 5:
            analysis["threat_level"] = "medium"
        else:
            analysis["threat_level"] = "low"
        
        # Spells recomendados basados en las criaturas presentes
        if detected_creatures:
            analysis["recommended_spells"] = self.get_recommended_spells(
                analysis["highest_priority"] or detected_creatures[0], 
                detected_creatures
            )
        
        return analysis
    
    def get_creature_weaknesses(self, creature_name: str) -> Dict[str, float]:
        """Obtiene las debilidades de una criatura."""
        creature_info = self.get_creature_info(creature_name)
        if not creature_info:
            return {}
        
        weaknesses = {}
        
        # Analizar elementos
        for element, percent in creature_info.elements.items():
            if percent < 0:  # Vulnerabilidad
                element_name = element.replace("COMBAT_", "").replace("DAMAGE", "").lower()
                weaknesses[element_name] = abs(percent) / 100.0
        
        return weaknesses
    
    def get_creature_immunities(self, creature_name: str) -> List[str]:
        """Obtiene las inmunidades de una criatura."""
        creature_info = self.get_creature_info(creature_name)
        if not creature_info:
            return []
        
        immunities = []
        for immunity, active in creature_info.immunities.items():
            if active:
                immunities.append(immunity)
        
        return immunities
    
    def export_profiles_to_config(self, config_path: str = "config.json"):
        """Exporta los perfiles al archivo de configuración."""
        try:
            # Cargar configuración existente
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Combinar perfiles manuales y automáticos
            all_profiles = {}
            all_profiles.update(self.auto_profiles)
            all_profiles.update(self.manual_profiles)
            
            # Actualizar configuración
            if "targeting" not in config:
                config["targeting"] = {}
            
            config["targeting"]["creature_profiles"] = all_profiles
            
            # Guardar configuración
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            logger.info(f"Perfiles exportados a {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exportando perfiles: {e}")
            return False
    
    def import_manual_profiles(self, config_path: str = "config.json"):
        """Importa perfiles manuales desde la configuración."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            manual_profiles = config.get("targeting", {}).get("creature_profiles", {})
            
            # Separar perfiles manuales (los que no tienen auto_generated)
            for name, profile in manual_profiles.items():
                if not profile.get("auto_generated", False):
                    self.manual_profiles[name.lower()] = profile
            
            logger.info(f"Importados {len(self.manual_profiles)} perfiles manuales")
            return True
            
        except Exception as e:
            logger.error(f"Error importando perfiles: {e}")
            return False

class TargetingIntegrator:
    """Integrador del targeting inteligente con el targeting engine."""
    
    def __init__(self, targeting_engine):
        self.targeting_engine = targeting_engine
        self.intelligent_targeting = IntelligentTargeting()
        
        # Importar perfiles manuales existentes
        self.intelligent_targeting.import_manual_profiles()
        
        # Conectar callbacks
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Configura los callbacks para integración."""
        # Override del método de configuración de perfiles
        original_configure = self.targeting_engine.configure
        
        def enhanced_configure(config):
            # Configuración original
            original_configure(config)
            
            # Actualizar perfiles con inteligencia artificial
            self._enhance_creature_profiles()
        
        self.targeting_engine.configure = enhanced_configure
    
    def _enhance_creature_profiles(self):
        """Mejora los perfiles de criaturas con información de la base de datos."""
        if not self.intelligent_targeting.creature_db:
            return
        
        # Obtener perfiles actuales
        current_profiles = getattr(self.targeting_engine, 'creature_profiles', {})
        
        # Mejorar cada perfil
        for creature_name, profile in current_profiles.items():
            creature_info = self.intelligent_targeting.get_creature_info(creature_name)
            
            if creature_info and not profile.get("auto_generated"):
                # Actualizar perfil con información real
                profile["source_data"] = {
                    "experience": creature_info.experience,
                    "health": creature_info.max_health,
                    "class": creature_info.class_type,
                    "difficulty": creature_info.difficulty_level,
                    "is_mage": creature_info.is_mage,
                    "is_ranged": creature_info.is_ranged,
                    "is_healer": creature_info.is_healer
                }
                
                # Ajustar prioridad basada en experiencia real
                if "priority" not in profile or profile["priority"] == 50:
                    profile["priority"] = creature_info.experience + (creature_info.difficulty_level * 100)
        
        logger.info("Perfiles de criaturas mejorados con información de la base de datos")
    
    def get_target_analysis(self, creature_name: str) -> Dict:
        """Obtiene análisis completo del target actual."""
        return {
            "creature_info": self.intelligent_targeting.get_creature_info(creature_name),
            "profile": self.intelligent_targeting.get_effective_profile(creature_name),
            "strategy": self.intelligent_targeting.get_attack_strategy(creature_name),
            "weaknesses": self.intelligent_targeting.get_creature_weaknesses(creature_name),
            "immunities": self.intelligent_targeting.get_creature_immunities(creature_name)
        }
    
    def analyze_area(self, detected_creatures: List[str]) -> Dict:
        """Analiza el área actual."""
        return self.intelligent_targeting.analyze_creatures_in_area(detected_creatures)

def main():
    """Función de prueba."""
    # Crear sistema inteligente
    intel_targeting = IntelligentTargeting()
    
    # Probar con algunas criaturas conocidas
    test_creatures = ["Orc", "Dragon", "Demon", "Amazon"]
    
    print("=== PRUEBAS DE TARGETING INTELIGENTE ===\n")
    
    for creature in test_creatures:
        print(f"Análisis de: {creature}")
        
        # Obtener información
        info = intel_targeting.get_creature_info(creature)
        if info:
            print(f"  HP: {info.max_health}")
            print(f"  Exp: {info.experience}")
            print(f"  Clase: {info.class_type}")
            print(f"  Ranged: {info.is_ranged}")
            print(f"  Mage: {info.is_mage}")
        
        # Obtener estrategia
        strategy = intel_targeting.get_attack_strategy(creature)
        print(f"  Estrategia: {strategy['mode']} ({strategy['reason']})")
        
        # Obtener debilidades
        weaknesses = intel_targeting.get_creature_weaknesses(creature)
        if weaknesses:
            print(f"  Debilidades: {weaknesses}")
        
        print()
    
    # Probar análisis de área
    area_creatures = ["Orc", "Orc Shaman", "Orc Warrior", "Troll"]
    analysis = intel_targeting.analyze_creatures_in_area(area_creatures)
    
    print("=== ANÁLISIS DE ÁREA ===")
    print(f"Total criaturas: {analysis['total_creatures']}")
    print(f"Criaturas conocidas: {analysis['known_creatures']}")
    print(f"Nivel de amenaza: {analysis['threat_level']}")
    print(f"Target prioritario: {analysis['highest_priority']}")
    print(f"Spells recomendados: {analysis['recommended_spells']}")

if __name__ == "__main__":
    main()
