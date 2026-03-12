#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_targeting_system.py - Sistema de targeting visual completo
Integra assets de Tibia (imágenes, cuerpos, loot) con el targeting V2.
"""

import os
import xml.etree.ElementTree as ET
import struct
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from pathlib import Path
from tibia_assets_reader import TibiaAssetsReader, MonsterVisualInfo, LootInfo, ItemInfo
from intelligent_targeting import IntelligentTargeting
from targeting_engine_v2 import TargetingEngineV2

logger = logging.getLogger(__name__)

@dataclass
class VisualTargetingInfo:
    """Información visual completa para targeting."""
    monster_name: str
    look_type: int
    outfit: Dict
    corpse_info: Dict
    loot_info: Dict
    recommended_strategy: Dict
    visual_indicators: Dict

class VisualTargetingSystem:
    """Sistema de targeting visual completo."""
    
    def __init__(self, tibia_files_path: str = "tibia_files_canary"):
        self.tibia_files_path = tibia_files_path
        self.assets_reader = TibiaAssetsReader(tibia_files_path)
        self.intelligent_targeting = IntelligentTargeting(tibia_files_path)
        
        # Bases de datos
        self.visual_database: Dict[str, VisualTargetingInfo] = {}
        self.corpse_templates: Dict[int, Dict] = {}
        self.loot_templates: Dict[str, List[Dict]] = {}
        
    def initialize_system(self) -> bool:
        """Inicializa todo el sistema."""
        logger.info("Inicializando sistema de targeting visual...")
        
        success = True
        
        # 1. Cargar assets de Tibia
        if not self.assets_reader.load_all_assets():
            logger.error("Error cargando assets de Tibia")
            success = False
        
        # 2. Cargar base de datos de criaturas
        if not self.intelligent_targeting.creature_db:
            if not self.intelligent_targeting.creature_db.load_all_creatures():
                logger.error("Error cargando base de datos de criaturas")
                success = False
        
        # 3. Crear base de datos visual integrada
        if success:
            self._create_visual_database()
            self._create_corpse_templates()
            self._create_loot_templates()
        
        return success
    
    def _create_visual_database(self):
        """Crea la base de datos visual integrada."""
        logger.info("Creando base de datos visual...")
        
        # Para cada monstruo en la base de datos inteligente
        if self.intelligent_targeting.creature_db:
            for monster_name in self.intelligent_targeting.creature_db.creature_names:
                # Obtener información visual
                visual_info = self.assets_reader.get_monster_visual_info(monster_name)
                loot_info = self.assets_reader.get_loot_info(monster_name)
                creature_info = self.intelligent_targeting.get_creature_info(monster_name)
                
                if visual_info or creature_info:
                    # Crear outfit
                    outfit = {
                        'lookType': visual_info.look_type if visual_info else 0,
                        'lookHead': visual_info.look_head if visual_info else 0,
                        'lookBody': visual_info.look_body if visual_info else 0,
                        'lookLegs': visual_info.look_legs if visual_info else 0,
                        'lookFeet': visual_info.look_feet if visual_info else 0,
                        'lookAddons': visual_info.look_addons if visual_info else 0
                    }
                
                # Información del corpse
                    corpse_info = {}
                    if visual_info and visual_info.corpse_item_id:
                        corpse_item = self.assets_reader.get_corpse_info(visual_info.corpse_item_id)
                        if corpse_item:
                            corpse_info = {
                                'item_id': visual_info.corpse_item_id,
                                'name': corpse_item.name,
                                'size': corpse_item.corpse_size,
                                'duration': corpse_item.duration,
                                'decay_to': corpse_item.decay_to,
                                'weight': corpse_item.weight
                            }
                    
                    # Información del loot
                    loot_data = {}
                    if loot_info:
                        loot_data = {
                            'total_items': loot_info.total_items,
                            'rare_items': len(loot_info.rare_items),
                            'common_items': len(loot_info.common_items),
                            'items': loot_info.items[:10]  # Primeros 10 items
                        }
                    
                    # Estrategia recomendada
                    strategy = self.intelligent_targeting.get_attack_strategy(monster_name)
                    
                    # Indicadores visuales
                    visual_indicators = {
                        'is_ranged': creature_info.is_ranged if creature_info else False,
                        'is_mage': creature_info.is_mage if creature_info else False,
                        'is_healer': creature_info.is_healer if creature_info else False,
                        'difficulty_level': creature_info.difficulty_level if creature_info else 0,
                        'max_health': creature_info.max_health if creature_info else 0,
                        'experience': creature_info.experience if creature_info else 0
                    }
                    
                    # Crear entrada en la base de datos
                    self.visual_database[monster_name.lower()] = VisualTargetingInfo(
                        monster_name=monster_name,
                        look_type=outfit['lookType'],
                        outfit=outfit,
                        corpse_info=corpse_info,
                        loot_info=loot_data,
                        recommended_strategy=strategy,
                        visual_indicators=visual_indicators
                    )
        
        logger.info(f"Base de datos visual creada: {len(self.visual_database)} monstruos")
    
    def _create_corpse_templates(self):
        """Crea templates para detección de cuerpos muertos."""
        logger.info("Creando templates de cuerpos muertos...")
        
        for corpse_id, corpse_info in self.assets_reader.corpse_items.items():
            if corpse_info.corpse_size > 0:  # Solo cuerpos que pueden contener loot
                self.corpse_templates[corpse_id] = {
                    'name': corpse_info.name,
                    'size': corpse_info.corpse_size,
                    'duration': corpse_info.duration,
                    'decay_to': corpse_info.decay_to,
                    'weight': corpse_info.weight,
                    'attributes': corpse_info.attributes
                }
        
        logger.info(f"Templates de cuerpos creados: {len(self.corpse_templates)}")
    
    def _create_loot_templates(self):
        """Crea templates para detección de loot."""
        logger.info("Creando templates de loot...")
        
        for monster_name, loot_info in self.assets_reader.loot_database.items():
            # Agrupar loot por rareza y tipo
            rare_items = [item for item in loot_info.items if item['chance'] <= 1000]
            valuable_items = [item for item in loot_info.items if item['chance'] <= 5000]
            
            self.loot_templates[monster_name] = {
                'total_items': loot_info.total_items,
                'rare_items': rare_items,
                'valuable_items': valuable_items,
                'estimated_value': self._estimate_loot_value(loot_info.items)
            }
        
        logger.info(f"Templates de loot creados: {len(self.loot_templates)}")
    
    def _estimate_loot_value(self, items: List[Dict]) -> int:
        """Estima el valor del loot basado en rareza y cantidad."""
        total_value = 0
        
        for item in items:
            chance = item.get('chance', 0)
            max_count = item.get('max_count', 1)
            
            # Valor base según rareza
            if chance <= 100:
                base_value = 1000  # Legendary
            elif chance <= 500:
                base_value = 500   # Epic
            elif chance <= 1000:
                base_value = 200   # Rare
            elif chance <= 5000:
                base_value = 50    # Uncommon
            else:
                base_value = 10    # Common
            
            # Ajustar por cantidad máxima
            adjusted_value = base_value * max_count
            
            # Ajustar por probabilidad
            expected_value = adjusted_value * (chance / 100000)
            
            total_value += int(expected_value)
        
        return total_value
    
    def get_visual_targeting_info(self, monster_name: str) -> Optional[VisualTargetingInfo]:
        """Obtiene información visual completa de un monstruo."""
        return self.visual_database.get(monster_name.lower())
    
    def identify_creature_by_outfit(self, look_type: int, outfit: Dict) -> Optional[str]:
        """Identifica una criatura por su outfit."""
        # Buscar coincidencia exacta de look_type
        for name, info in self.visual_database.items():
            if info.look_type == look_type:
                # Verificar si el outfit coincide
                if (info.outfit.get('lookHead') == outfit.get('lookHead') and
                    info.outfit.get('lookBody') == outfit.get('lookBody') and
                    info.outfit.get('lookLegs') == outfit.get('lookLegs') and
                    info.outfit.get('lookFeet') == outfit.get('lookFeet')):
                    return name
        
        return None
    
    def get_corpse_detection_info(self, corpse_id: int) -> Optional[Dict]:
        """Obtiene información para detección de corpse."""
        return self.corpse_templates.get(corpse_id)
    
    def get_loot_prioritization(self, monster_name: str) -> Dict:
        """Obtiene priorización de loot para un monstruo."""
        loot_template = self.loot_templates.get(monster_name.lower())
        
        if not loot_template:
            return {'priority': 'normal', 'value': 0, 'items': []}
        
        # Determinar prioridad basada en el valor estimado
        estimated_value = loot_template['estimated_value']
        
        if estimated_value >= 10000:
            priority = 'very_high'
        elif estimated_value >= 5000:
            priority = 'high'
        elif estimated_value >= 2000:
            priority = 'medium'
        else:
            priority = 'low'
        
        return {
            'priority': priority,
            'value': estimated_value,
            'rare_items': loot_template['rare_items'],
            'valuable_items': loot_template['valuable_items'],
            'total_items': loot_template['total_items']
        }
    
    def get_visual_indicators(self, monster_name: str) -> Dict:
        """Obtiene indicadores visuales para un monstruo."""
        info = self.get_visual_targeting_info(monster_name)
        
        if not info:
            return {}
        
        indicators = info.visual_indicators.copy()
        
        # Agregar indicadores adicionales
        indicators.update({
            'has_valuable_loot': info.loot_info.get('rare_items', 0) > 0,
            'corpse_size': info.corpse_info.get('size', 0),
            'corpse_duration': info.corpse_info.get('duration', 0),
            'recommended_attack_mode': info.recommended_strategy.get('mode', 'offensive'),
            'recommended_chase_mode': info.recommended_strategy.get('chase_mode', 'auto'),
            'threat_level': self._calculate_threat_level(indicators)
        })
        
        return indicators
    
    def _calculate_threat_level(self, indicators: Dict) -> str:
        """Calcula el nivel de amenaza basado en indicadores."""
        threat_score = 0
        
        # HP y experiencia
        if indicators.get('max_health', 0) >= 1000:
            threat_score += 3
        elif indicators.get('max_health', 0) >= 500:
            threat_score += 2
        elif indicators.get('max_health', 0) >= 200:
            threat_score += 1
        
        # Características peligrosas
        if indicators.get('is_mage', False):
            threat_score += 2
        if indicators.get('is_ranged', False):
            threat_score += 1
        if indicators.get('is_healer', False):
            threat_score += 1
        
        # Dificultad
        difficulty = indicators.get('difficulty_level', 0)
        threat_score += difficulty
        
        # Determinar nivel
        if threat_score >= 8:
            return 'extreme'
        elif threat_score >= 6:
            return 'high'
        elif threat_score >= 4:
            return 'medium'
        elif threat_score >= 2:
            return 'low'
        else:
            return 'minimal'
    
    def get_area_visual_analysis(self, detected_creatures: List[str]) -> Dict:
        """Realiza análisis visual del área."""
        analysis = {
            'total_creatures': len(detected_creatures),
            'threats': [],
            'valuable_targets': [],
            'recommended_strategy': 'balanced',
            'area_loot_value': 0,
            'visual_indicators': {}
        }
        
        total_threat = 0
        total_loot_value = 0
        
        for creature_name in detected_creatures:
            visual_info = self.get_visual_targeting_info(creature_name)
            
            if visual_info:
                indicators = self.get_visual_indicators(creature_name)
                loot_info = self.get_loot_prioritization(creature_name)
                
                # Agregar a amenazas
                if indicators['threat_level'] in ['high', 'extreme']:
                    analysis['threats'].append({
                        'name': creature_name,
                        'threat_level': indicators['threat_level'],
                        'is_mage': indicators['is_mage'],
                        'is_ranged': indicators['is_ranged']
                    })
                
                # Agregar objetivos valiosos
                if loot_info['priority'] in ['high', 'very_high']:
                    analysis['valuable_targets'].append({
                        'name': creature_name,
                        'loot_value': loot_info['value'],
                        'rare_items_count': len(loot_info['rare_items'])
                    })
                
                total_threat += self._threat_level_to_score(indicators['threat_level'])
                total_loot_value += loot_info['value']
                
                analysis['visual_indicators'][creature_name] = indicators
        
        # Calcular estrategia recomendada
        if total_threat >= 10:
            analysis['recommended_strategy'] = 'defensive'
        elif total_threat >= 5:
            analysis['recommended_strategy'] = 'balanced'
        else:
            analysis['recommended_strategy'] = 'offensive'
        
        analysis['area_loot_value'] = total_loot_value
        analysis['total_threat_score'] = total_threat
        
        return analysis
    
    def _threat_level_to_score(self, threat_level: str) -> int:
        """Convierte nivel de amenaza a puntaje."""
        scores = {
            'minimal': 0,
            'low': 1,
            'medium': 2,
            'high': 3,
            'extreme': 4
        }
        return scores.get(threat_level, 0)
    
    def save_visual_database(self, output_path: str):
        """Guarda la base de datos visual."""
        data = {
            "version": "1.0",
            "total_creatures": len(self.visual_database),
            "total_corpses": len(self.corpse_templates),
            "total_loot_templates": len(self.loot_templates),
            "visual_database": {name: asdict(info) for name, info in self.visual_database.items()},
            "corpse_templates": self.corpse_templates,
            "loot_templates": self.loot_templates
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Base de datos visual guardada en: {output_path}")
    
    def load_visual_database(self, input_path: str) -> bool:
        """Carga la base de datos visual."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruir objetos
            self.visual_database = {}
            for name, info_data in data.get("visual_database", {}).items():
                self.visual_database[name] = VisualTargetingInfo(**info_data)
            
            self.corpse_templates = data.get("corpse_templates", {})
            self.loot_templates = data.get("loot_templates", {})
            
            logger.info(f"Base de datos visual cargada: {len(self.visual_database)} criaturas")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando base de datos visual: {e}")
            return False

class VisualTargetingIntegrator:
    """Integrador del sistema visual con el targeting engine."""
    
    def __init__(self, targeting_engine: TargetingEngineV2):
        self.targeting_engine = targeting_engine
        self.visual_system = VisualTargetingSystem()
        
        # Inicializar sistema
        if self.visual_system.initialize_system():
            logger.info("Sistema de targeting visual inicializado")
        else:
            logger.error("Error inicializando sistema visual")
    
    def enhance_targeting_with_visuals(self):
        """Mejora el targeting con información visual."""
        # Agregar callbacks visuales al engine
        original_process_frame = self.targeting_engine.process_frame
        
        def enhanced_process_frame(frame):
            # Procesamiento original
            result = original_process_frame(frame)
            
            # Análisis visual adicional
            self._process_visual_analysis(frame)
            
            return result
        
        self.targeting_engine.process_frame = enhanced_process_frame
    
    def _process_visual_analysis(self, frame):
        """Procesa análisis visual del frame."""
        try:
            # Obtener criaturas detectadas
            if hasattr(self.targeting_engine, 'creature_tracker'):
                creatures = self.targeting_engine.creature_tracker.get_creatures()
                creature_names = [c.name for c in creatures]
                
                if creature_names:
                    # Análisis visual del área
                    visual_analysis = self.visual_system.get_area_visual_analysis(creature_names)
                    
                    # Actualizar estrategia si es necesario
                    current_strategy = getattr(self.targeting_engine, '_current_strategy', 'balanced')
                    recommended_strategy = visual_analysis['recommended_strategy']
                    
                    if current_strategy != recommended_strategy:
                        logger.info(f"Cambiando estrategia: {current_strategy} -> {recommended_strategy}")
                        self.targeting_engine._current_strategy = recommended_strategy
        
        except Exception as e:
            logger.error(f"Error en análisis visual: {e}")
    
    def get_visual_target_info(self, monster_name: str) -> Optional[Dict]:
        """Obtiene información visual de un target."""
        visual_info = self.visual_system.get_visual_targeting_info(monster_name)
        
        if visual_info:
            return {
                'monster_name': visual_info.monster_name,
                'outfit': visual_info.outfit,
                'corpse': visual_info.corpse_info,
                'loot': visual_info.loot_info,
                'strategy': visual_info.recommended_strategy,
                'indicators': visual_info.visual_indicators
            }
        
        return None
    
    def get_corpse_detection_template(self, corpse_id: int) -> Optional[Dict]:
        """Obtiene template para detección de corpse."""
        return self.visual_system.get_corpse_detection_info(corpse_id)

def main():
    """Función principal para probar el sistema visual."""
    print("=== SISTEMA DE TARGETING VISUAL ===\n")
    
    # Crear sistema visual
    visual_system = VisualTargetingSystem()
    
    # Inicializar
    if not visual_system.initialize_system():
        print("Error inicializando sistema visual")
        return
    
    # Guardar base de datos
    visual_system.save_visual_database("visual_targeting_database.json")
    
    # Probar análisis visual
    test_creatures = ["Dragon", "Demon", "Amazon", "Orc"]
    
    print("\n=== ANÁLISIS VISUAL DE CRIATURAS ===")
    
    for creature in test_creatures:
        info = visual_system.get_visual_targeting_info(creature)
        
        if info:
            print(f"\n[CREATURE] {creature}:")
            print(f"  Look Type: {info.look_type}")
            print(f"  Outfit: {info.outfit}")
            
            if info.corpse_info:
                print(f"  Corpse: {info.corpse_info['name']} (Size: {info.corpse_info['size']})")
            
            if info.loot_info:
                print(f"  Loot: {info.loot_info['total_items']} items, {info.loot_info['rare_items']} raros")
            
            indicators = visual_system.get_visual_indicators(creature)
            print(f"  Indicadores: {indicators}")
    
    # Probar análisis de área
    area_creatures = ["Dragon", "Dragon Lord", "Demon", "Amazon"]
    area_analysis = visual_system.get_area_visual_analysis(area_creatures)
    
    print(f"\n=== ANÁLISIS DE ÁREA ===")
    print(f"  Criaturas: {area_analysis['total_creatures']}")
    print(f"  Amenazas: {len(area_analysis['threats'])}")
    print(f"  Objetivos valiosos: {len(area_analysis['valuable_targets'])}")
    print(f"  Estrategia recomendada: {area_analysis['recommended_strategy']}")
    print(f"  Valor total del loot: {area_analysis['area_loot_value']}")
    
    print(f"\n=== ESTADÍSTICAS ===")
    print(f"  Base de datos visual: {len(visual_system.visual_database)} criaturas")
    print(f"  Templates de corpses: {len(visual_system.corpse_templates)}")
    print(f"  Templates de loot: {len(visual_system.loot_templates)}")
    
    print(f"\n[SUCCESS] Sistema de targeting visual funcionando correctamente")

if __name__ == "__main__":
    main()
