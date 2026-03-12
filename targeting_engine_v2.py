#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeting_engine_v2.py - Versión mejorada del targeting engine con inteligencia artificial
Integra la base de datos de criaturas para comportamiento adaptativo.
"""

from targeting.targeting_engine import TargetingEngine
from intelligent_targeting import IntelligentTargeting, TargetingIntegrator
import logging

logger = logging.getLogger(__name__)

class TargetingEngineV2(TargetingEngine):
    """Targeting Engine V2 con inteligencia artificial integrada."""
    
    def __init__(self):
        super().__init__()
        
        # Sistema inteligente
        self.intelligent_targeting = IntelligentTargeting()
        self.targeting_integrator = None
        
        # Estado extendido
        self.current_creature_info = None
        self.area_analysis = None
        self.last_creatures_detected = []
        
        # Callbacks extendidos
        self._setup_intelligent_callbacks()
    
    def _setup_intelligent_callbacks(self):
        """Configura callbacks inteligentes."""
        # Importar perfiles manuales existentes
        self.intelligent_targeting.import_manual_profiles()
        
        # Crear integrador
        self.targeting_integrator = TargetingIntegrator(self)
    
    def configure(self, config):
        """Configura el targeting con perfiles inteligentes."""
        # Configuración original
        super().configure(config)
        
        # Cargar criaturas seleccionadas bajo demanda
        attack_list = config.get("targeting", {}).get("attack_list", [])
        if attack_list and self.intelligent_targeting:
            logger.info(f"Cargando {len(attack_list)} criaturas bajo demanda...")
            self.intelligent_targeting.load_creatures_on_demand(attack_list)
        
        # Mejorar perfiles con inteligencia artificial
        if self.targeting_integrator:
            self.targeting_integrator._enhance_creature_profiles()
        
        logger.info("Targeting V2 configurado con carga bajo demanda")
    
    def process_frame(self, frame):
        """Procesa un frame con inteligencia artificial."""
        # Procesamiento original
        super().process_frame(frame)
        
        # Análisis inteligente adicional
        self._process_intelligent_analysis(frame)
    
    def _process_intelligent_analysis(self, frame):
        """Realiza análisis inteligente del frame."""
        try:
            # Obtener criaturas detectadas
            current_creatures = []
            if hasattr(self, 'creature_tracker'):
                current_creatures = [c.name for c in self.creature_tracker.get_creatures()]
            
            # Si hay nuevas criaturas, analizar el área
            if set(current_creatures) != set(self.last_creatures_detected):
                self.last_creatures_detected = current_creatures
                
                if current_creatures and self.targeting_integrator:
                    self.area_analysis = self.targeting_integrator.analyze_area(current_creatures)
                    
                    # Log del análisis
                    logger.info(f"Análisis de área: {self.area_analysis['total_creatures']} criaturas, "
                              f"amenaza: {self.area_analysis['threat_level']}")
                    
                    if self.area_analysis['dangerous_creatures']:
                        logger.warning(f"Criaturas peligrosas detectadas: "
                                     f"{[c['name'] for c in self.area_analysis['dangerous_creatures']]}")
            
            # Actualizar información del target actual
            if self.current_target and self.intelligent_targeting:
                self.intelligent_targeting.update_target_info(self.current_target)
                self.current_creature_info = self.intelligent_targeting.current_target_info
                
                # Aplicar estrategia inteligente
                self._apply_intelligent_strategy()
        
        except Exception as e:
            logger.error(f"Error en análisis inteligente: {e}")
    
    def _apply_intelligent_strategy(self):
        """Aplica la estrategia inteligente para el target actual."""
        if not self.current_target or not self.intelligent_targeting:
            return
        
        try:
            # Obtener estrategia recomendada
            strategy = self.intelligent_targeting.get_attack_strategy(self.current_target)
            
            # Aplicar modo de chase/stand basado en HP
            if self.current_creature_info and hasattr(self, 'hp_detector'):
                hp_info = self.hp_detector.process_frame(None)  # Usar último frame
                
                if hp_info and hp_info['hp_percentage'] is not None:
                    should_chase = self.intelligent_targeting.should_use_chase_mode(
                        self.current_target, 
                        hp_info['hp_percentage']
                    )
                    
                    if should_chase and self._current_chase_mode != "chase":
                        self._set_chase_mode()
                        logger.info(f"Modo chase activado (HP: {hp_info['hp_percentage']}%)")
                    elif not should_chase and self._current_chase_mode != "stand":
                        self._set_stand_mode()
                        logger.info(f"Modo stand activado (HP: {hp_info['hp_percentage']}%)")
            
            # Actualizar prioridad si es necesario
            recommended_priority = self.intelligent_targeting.get_target_priority(self.current_target)
            current_priority = self.creature_profiles.get(self.current_target.lower(), {}).get('priority', 50)
            
            if recommended_priority != current_priority:
                logger.info(f"Prioridad actualizada para {self.current_target}: {current_priority} -> {recommended_priority}")
        
        except Exception as e:
            logger.error(f"Error aplicando estrategia inteligente: {e}")
    
    def get_status(self):
        """Obtiene estado extendido con información inteligente."""
        status = super().get_status()
        
        # Agregar información inteligente
        status.update({
            'current_creature_info': {
                'name': self.current_creature_info.name if self.current_creature_info else None,
                'health': self.current_creature_info.max_health if self.current_creature_info else None,
                'experience': self.current_creature_info.experience if self.current_creature_info else None,
                'class': self.current_creature_info.class_type if self.current_creature_info else None,
                'difficulty': self.current_creature_info.difficulty_level if self.current_creature_info else None
            },
            'area_analysis': self.area_analysis,
            'intelligent_profiles_count': len(self.intelligent_targeting.auto_profiles),
            'manual_profiles_count': len(self.intelligent_targeting.manual_profiles)
        })
        
        return status
    
    def get_target_analysis(self, creature_name: str = None):
        """Obtiene análisis completo del target."""
        target_name = creature_name or self.current_target
        
        if not target_name or not self.targeting_integrator:
            return None
        
        return self.targeting_integrator.get_target_analysis(target_name)
    
    def get_recommended_spells(self, nearby_creatures: list = None):
        """Obtiene spells recomendados para la situación actual."""
        if not self.current_target or not self.intelligent_targeting:
            return []
        
        nearby = nearby_creatures or self.last_creatures_detected
        
        return self.intelligent_targeting.get_recommended_spells(self.current_target, nearby)
    
    def export_intelligent_profiles(self, config_path: str = "config.json"):
        """Exporta perfiles inteligentes a la configuración."""
        if self.intelligent_targeting:
            return self.intelligent_targeting.export_profiles_to_config(config_path)
        return False
    
    def import_manual_profiles(self, config_path: str = "config.json"):
        """Importa perfiles manuales desde la configuración."""
        if self.intelligent_targeting:
            return self.intelligent_targeting.import_manual_profiles(config_path)
        return False
    
    def get_creature_database_info(self):
        """Obtiene información sobre la base de datos de criaturas."""
        if not self.intelligent_targeting:
            return {
                'loaded': False,
                'total_creatures': 0,
                'message': 'Sistema inteligente no disponible'
            }
        
        # Información del sistema de lazy loading
        lazy_loaded = len(self.intelligent_targeting.lazy_loaded_creatures)
        auto_profiles = len(self.intelligent_targeting.auto_profiles)
        manual_profiles = len(self.intelligent_targeting.manual_profiles)
        
        if self.intelligent_targeting.database_loaded and self.intelligent_targeting.creature_db:
            # Si la BD completa está cargada
            db = self.intelligent_targeting.creature_db
            classes = {}
            difficulties = {}
            
            for creature in db.creatures.values():
                classes[creature.class_type] = classes.get(creature.class_type, 0) + 1
                difficulties[creature.difficulty_level] = difficulties.get(creature.difficulty_level, 0) + 1
            
            return {
                'loaded': True,
                'total_creatures': len(db.creatures),
                'classes': classes,
                'difficulties': difficulties,
                'auto_profiles': auto_profiles,
                'manual_profiles': manual_profiles,
                'database_path': self.intelligent_targeting.db_path,
                'lazy_loaded': lazy_loaded,
                'mode': 'full_database'
            }
        else:
            # Si está en modo lazy loading
            return {
                'loaded': True,
                'total_creatures': lazy_loaded,
                'auto_profiles': auto_profiles,
                'manual_profiles': manual_profiles,
                'database_path': self.intelligent_targeting.db_path,
                'lazy_loaded': lazy_loaded,
                'mode': 'lazy_loading',
                'message': f'Modo lazy loading - {lazy_loaded} criaturas cargadas bajo demanda'
            }
    
    def search_creatures(self, query: str) -> list:
        """Busca criaturas en la base de datos (con lazy loading)."""
        if not self.intelligent_targeting:
            return []
        
        results = self.intelligent_targeting.search_creatures_by_pattern(query, limit=10)
        
        return [
            {
                'name': creature.name,
                'description': creature.description,
                'health': creature.max_health,
                'experience': creature.experience,
                'class': creature.class_type,
                'difficulty': creature.difficulty_level,
                'is_ranged': creature.is_ranged,
                'is_mage': creature.is_mage,
                'locations': creature.locations[:3]  # Primeras 3 ubicaciones
            }
            for creature in results
        ]
    
    def set_manual_profile(self, creature_name: str, profile: dict):
        """Establece un perfil manual para una criatura."""
        if self.intelligent_targeting:
            self.intelligent_targeting.set_manual_profile(creature_name, profile)
            
            # Actualizar perfiles del engine
            if creature_name.lower() not in self.creature_profiles:
                self.creature_profiles[creature_name.lower()] = {}
            
            self.creature_profiles[creature_name.lower()].update(profile)
            
            logger.info(f"Perfil manual establecido para {creature_name}")
            return True
        
        return False

# Función de actualización para el healer_bot.py
def upgrade_targeting_to_v2():
    """Función para actualizar el healer_bot a targeting V2."""
    logger.info("Actualizando a Targeting Engine V2...")
    
    # Reemplazar el targeting engine
    from healer_bot import HealerBot
    
    # Guardar referencia al método original
    original_init = HealerBot.__init__
    
    def new_init(self, config, log):
        # Inicialización original
        original_init(self, config, log)
        
        # Reemplazar targeting engine con V2
        self.targeting_engine = TargetingEngineV2()
        logger.info("Targeting Engine V2 instalado")
    
    HealerBot.__init__ = new_init
    
    logger.info("Targeting Engine V2 actualizado exitosamente")

if __name__ == "__main__":
    # Pruebas del Targeting V2
    print("=== PRUEBAS TARGETING ENGINE V2 ===")
    
    # Crear engine V2
    engine = TargetingEngineV2()
    
    # Verificar base de datos
    db_info = engine.get_creature_database_info()
    print(f"Base de datos cargada: {db_info['loaded']}")
    print(f"Total criaturas: {db_info['total_creatures']}")
    
    # Buscar criaturas
    results = engine.search_creatures("dragon")
    print(f"\nResultados para 'dragon': {len(results)}")
    for result in results[:3]:
        print(f"  - {result['name']}: HP {result['health']}, Exp {result['experience']}, "
              f"Clase {result['class']}, Dificultad {result['difficulty']}")
    
    # Probar análisis
    analysis = engine.get_target_analysis("Demon")
    if analysis:
        print(f"\nAnálisis de Demon:")
        print(f"  Estrategia: {analysis['strategy']['mode']} ({analysis['strategy']['reason']})")
        print(f"  Debilidades: {analysis['weaknesses']}")
        print(f"  Inmunidades: {analysis['immunities']}")
    
    print("\nTargeting Engine V2 funcionando correctamente")
