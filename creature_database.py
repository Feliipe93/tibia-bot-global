#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
creature_database.py - Sistema completo de base de datos de criaturas
Lee todos los archivos .lua de Tibia y genera información completa para el targeting.
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CreatureAttack:
    """Representa un ataque de una criatura."""
    name: str
    interval: int
    chance: int
    min_damage: int
    max_damage: int
    attack_type: Optional[str] = None
    range: Optional[int] = None
    radius: Optional[int] = None
    target: Optional[bool] = None
    shoot_effect: Optional[str] = None

@dataclass
class CreatureLoot:
    """Representa un item de loot."""
    name: str
    chance: int
    max_count: Optional[int] = None
    item_id: Optional[int] = None

@dataclass
class CreatureInfo:
    """Información completa de una criatura."""
    name: str
    description: str
    experience: int
    health: int
    max_health: int
    speed: int
    race: str
    class_type: str
    target_distance: int
    run_health: int
    static_attack_chance: int
    attacks: List[CreatureAttack]
    loot: List[CreatureLoot]
    elements: Dict[str, int]
    immunities: Dict[str, bool]
    can_summon: bool
    is_ranged: bool
    is_mage: bool
    is_healer: bool
    difficulty_level: int  # 1-5 estrellas
    locations: List[str]

class CreatureDatabase:
    """Base de datos de criaturas de Tibia."""
    
    def __init__(self, tibia_files_path: str):
        self.tibia_files_path = tibia_files_path
        self.monster_data_path = os.path.join(tibia_files_path, "data", "monster")
        self.creatures: Dict[str, CreatureInfo] = {}
        self.creature_names: List[str] = []
        
    def load_all_creatures(self) -> bool:
        """Carga todas las criaturas desde los archivos .lua."""
        logger.info("Cargando base de datos de criaturas...")
        
        if not os.path.exists(self.monster_data_path):
            logger.error(f"No existe el path: {self.monster_data_path}")
            return False
        
        total_files = 0
        loaded_files = 0
        
        # Recorrer todos los directorios
        for root, dirs, files in os.walk(self.monster_data_path):
            for file in files:
                if file.endswith('.lua'):
                    total_files += 1
                    file_path = os.path.join(root, file)
                    
                    try:
                        creature = self._parse_creature_file(file_path)
                        if creature:
                            self.creatures[creature.name.lower()] = creature
                            self.creature_names.append(creature.name)
                            loaded_files += 1
                            
                    except Exception as e:
                        logger.warning(f"Error procesando {file}: {e}")
        
        logger.info(f"Procesados {loaded_files}/{total_files} archivos de criaturas")
        logger.info(f"Total criaturas cargadas: {len(self.creatures)}")
        
        return True
    
    def _parse_creature_file(self, file_path: str) -> Optional[CreatureInfo]:
        """Parsea un archivo .lua de criatura."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Extraer nombre de la criatura
            name_match = re.search(r'Game\.createMonsterType\("([^"]+)"\)', content)
            if not name_match:
                return None
            
            name = name_match.group(1)
            
            # Extraer información básica
            description = self._extract_string_field(content, "monster.description")
            experience = self._extract_number_field(content, "monster.experience", 0)
            health = self._extract_number_field(content, "monster.health", 0)
            max_health = self._extract_number_field(content, "monster.maxHealth", health)
            speed = self._extract_number_field(content, "monster.speed", 0)
            race = self._extract_string_field(content, "monster.race", "blood")
            
            # Extraer Bestiary
            bestiary_class = self._extract_bestiary_field(content, "class", "Unknown")
            locations = self._extract_bestiary_locations(content)
            stars = self._extract_bestiary_field(content, "Stars", 0)
            
            # Extraer flags
            target_distance = self._extract_flag_field(content, "targetDistance", 1)
            run_health = self._extract_flag_field(content, "runHealth", 0)
            static_attack_chance = self._extract_flag_field(content, "staticAttackChance", 90)
            
            # Extraer ataques
            attacks = self._extract_attacks(content)
            
            # Extraer loot
            loot = self._extract_loot(content)
            
            # Extraer elementos e inmunidades
            elements = self._extract_elements(content)
            immunities = self._extract_immunities(content)
            
            # Determinar características
            is_ranged = target_distance > 1 or any(atk.range and atk.range > 1 for atk in attacks)
            is_mage = any(atk.attack_type and atk.attack_type != "melee" for atk in attacks)
            is_healer = any("healing" in atk.name.lower() or "heal" in atk.name.lower() for atk in attacks)
            can_summon = "monster.summon" in content
            
            return CreatureInfo(
                name=name,
                description=description,
                experience=experience,
                health=health,
                max_health=max_health,
                speed=speed,
                race=race,
                class_type=bestiary_class,
                target_distance=target_distance,
                run_health=run_health,
                static_attack_chance=static_attack_chance,
                attacks=attacks,
                loot=loot,
                elements=elements,
                immunities=immunities,
                can_summon=can_summon,
                is_ranged=is_ranged,
                is_mage=is_mage,
                is_healer=is_healer,
                difficulty_level=int(stars),
                locations=locations
            )
            
        except Exception as e:
            logger.error(f"Error parseando {file_path}: {e}")
            return None
    
    def _extract_string_field(self, content: str, field: str, default: str = "") -> str:
        """Extrae un campo string del contenido."""
        pattern = rf'{field}\s*=\s*"([^"]+)"'
        match = re.search(pattern, content)
        return match.group(1) if match else default
    
    def _extract_number_field(self, content: str, field: str, default: int = 0) -> int:
        """Extrae un campo numérico del contenido."""
        pattern = rf'{field}\s*=\s*(\d+)'
        match = re.search(pattern, content)
        return int(match.group(1)) if match else default
    
    def _extract_bestiary_field(self, content: str, field: str, default: str = "") -> str:
        """Extrae un campo del Bestiary."""
        pattern = rf'{field}\s*=\s*"?([^",\n]+)"?'
        match = re.search(pattern, content)
        return match.group(1) if match else default
    
    def _extract_bestiary_locations(self, content: str) -> List[str]:
        """Extrae las ubicaciones del Bestiary."""
        pattern = r'Locations\s*=\s*"([^"]+)"'
        match = re.search(pattern, content)
        if match:
            locations_str = match.group(1)
            # Limpiar y dividir ubicaciones
            locations_str = locations_str.replace('\\z', '').replace('\\', '')
            return [loc.strip() for loc in locations_str.split(',') if loc.strip()]
        return []
    
    def _extract_flag_field(self, content: str, field: str, default: int = 0) -> int:
        """Extrae un campo de flags."""
        pattern = rf'{field}\s*=\s*(\d+)'
        match = re.search(pattern, content)
        return int(match.group(1)) if match else default
    
    def _extract_attacks(self, content: str) -> List[CreatureAttack]:
        """Extrae los ataques de una criatura."""
        attacks = []
        
        # Buscar el bloque de attacks
        attacks_match = re.search(r'monster\.attacks\s*=\s*{(.*?)}', content, re.DOTALL)
        if not attacks_match:
            return attacks
        
        attacks_content = attacks_match.group(1)
        
        # Extraer cada ataque
        attack_pattern = r'{([^}]+)}'
        for attack_match in re.finditer(attack_pattern, attacks_content):
            attack_str = attack_match.group(1)
            
            attack = self._parse_attack(attack_str)
            if attack:
                attacks.append(attack)
        
        return attacks
    
    def _parse_attack(self, attack_str: str) -> Optional[CreatureAttack]:
        """Parsea un ataque individual."""
        try:
            # Extraer valores básicos
            name = self._extract_field_from_attack(attack_str, "name", "melee")
            interval = self._extract_field_from_attack(attack_str, "interval", 2000)
            chance = self._extract_field_from_attack(attack_str, "chance", 100)
            min_damage = self._extract_field_from_attack(attack_str, "minDamage", 0)
            max_damage = self._extract_field_from_attack(attack_str, "maxDamage", 0)
            
            # Extraer valores opcionales
            attack_type = self._extract_field_from_attack(attack_str, "type")
            range_val = self._extract_field_from_attack(attack_str, "range")
            radius = self._extract_field_from_attack(attack_str, "radius")
            target = self._extract_field_from_attack(attack_str, "target")
            shoot_effect = self._extract_field_from_attack(attack_str, "shootEffect")
            
            return CreatureAttack(
                name=name,
                interval=interval,
                chance=chance,
                min_damage=min_damage,
                max_damage=max_damage,
                attack_type=attack_type,
                range=int(range_val) if range_val else None,
                radius=int(radius) if radius else None,
                target=bool(target) if target is not None else None,
                shoot_effect=shoot_effect
            )
            
        except Exception as e:
            logger.warning(f"Error parseando ataque: {e}")
            return None
    
    def _extract_field_from_attack(self, attack_str: str, field: str, default=None):
        """Extrae un campo específico de un ataque."""
        pattern = rf'{field}\s*=\s*"?([^",\}}]+)"?'
        match = re.search(pattern, attack_str)
        if match:
            value = match.group(1)
            # Intentar convertir a número
            try:
                if value.startswith('-') or value.isdigit():
                    return int(value)
                return value
            except ValueError:
                return value
        return default
    
    def _extract_loot(self, content: str) -> List[CreatureLoot]:
        """Extrae el loot de una criatura."""
        loot_items = []
        
        # Buscar el bloque de loot
        loot_match = re.search(r'monster\.loot\s*=\s*{(.*?)}', content, re.DOTALL)
        if not loot_match:
            return loot_items
        
        loot_content = loot_match.group(1)
        
        # Extraer cada item de loot
        item_pattern = r'{([^}]+)}'
        for item_match in re.finditer(item_pattern, loot_content):
            item_str = item_match.group(1)
            
            item = self._parse_loot_item(item_str)
            if item:
                loot_items.append(item)
        
        return loot_items
    
    def _parse_loot_item(self, item_str: str) -> Optional[CreatureLoot]:
        """Parsea un item de loot individual."""
        try:
            name = self._extract_field_from_attack(item_str, "name")
            item_id = self._extract_field_from_attack(item_str, "id")
            chance = self._extract_field_from_attack(item_str, "chance", 0)
            max_count = self._extract_field_from_attack(item_str, "maxCount")
            
            # Si no tiene nombre pero tiene ID, usar el ID
            if not name and item_id:
                name = f"Item {item_id}"
            
            if not name:
                return None
            
            return CreatureLoot(
                name=name,
                chance=int(chance),
                max_count=int(max_count) if max_count else None,
                item_id=int(item_id) if item_id else None
            )
            
        except Exception as e:
            logger.warning(f"Error parseando loot item: {e}")
            return None
    
    def _extract_elements(self, content: str) -> Dict[str, int]:
        """Extrae las resistencias a elementos."""
        elements = {}
        
        # Buscar el bloque de elements
        elements_match = re.search(r'monster\.elements\s*=\s*{(.*?)}', content, re.DOTALL)
        if not elements_match:
            return elements
        
        elements_content = elements_match.group(1)
        
        # Extraer cada elemento
        element_pattern = r'{type\s*=\s*([^,]+),\s*percent\s*=\s*([^}]+)}'
        for elem_match in re.finditer(element_pattern, elements_content):
            elem_type = elem_match.group(1).strip()
            percent = elem_match.group(2).strip()
            
            try:
                elements[elem_type] = int(percent)
            except ValueError:
                continue
        
        return elements
    
    def _extract_immunities(self, content: str) -> Dict[str, bool]:
        """Extrae las inmunidades."""
        immunities = {}
        
        # Buscar el bloque de immunities
        immunities_match = re.search(r'monster\.immunities\s*=\s*{(.*?)}', content, re.DOTALL)
        if not immunities_match:
            return immunities
        
        immunities_content = immunities_match.group(1)
        
        # Extraer cada inmunidad
        immunity_pattern = r'{type\s*=\s*"([^"]+)",\s*condition\s*=\s*([^}]+)}'
        for imm_match in re.finditer(immunity_pattern, immunities_content):
            imm_type = imm_match.group(1)
            condition = imm_match.group(2).strip()
            
            immunities[imm_type] = condition.lower() == "true"
        
        return immunities
    
    def get_creature(self, name: str) -> Optional[CreatureInfo]:
        """Obtiene información de una criatura por nombre."""
        return self.creatures.get(name.lower())
    
    def search_creatures(self, query: str) -> List[CreatureInfo]:
        """Busca criaturas por nombre parcial."""
        query = query.lower()
        results = []
        
        for creature in self.creatures.values():
            if query in creature.name.lower():
                results.append(creature)
        
        return results
    
    def get_creatures_by_class(self, class_type: str) -> List[CreatureInfo]:
        """Obtiene criaturas por clase."""
        return [c for c in self.creatures.values() if c.class_type == class_type]
    
    def get_creatures_by_difficulty(self, min_level: int, max_level: int = None) -> List[CreatureInfo]:
        """Obtiene criaturas por nivel de dificultad."""
        if max_level is None:
            max_level = min_level
        
        return [c for c in self.creatures.values() 
                if min_level <= c.difficulty_level <= max_level]
    
    def save_database(self, output_path: str):
        """Guarda la base de datos en formato JSON."""
        data = {
            "version": "1.0",
            "total_creatures": len(self.creatures),
            "creature_names": self.creature_names,
            "creatures": {name: asdict(creature) for name, creature in self.creatures.items()}
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Base de datos guardada en: {output_path}")
    
    def load_database(self, input_path: str) -> bool:
        """Carga la base de datos desde un archivo JSON."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.creature_names = data.get("creature_names", [])
            
            # Reconstruir objetos CreatureInfo
            self.creatures = {}
            for name, creature_data in data.get("creatures", {}).items():
                # Convertir ataques
                attacks = []
                for atk_data in creature_data.get("attacks", []):
                    attacks.append(CreatureAttack(**atk_data))
                
                # Convertir loot
                loot = []
                for loot_data in creature_data.get("loot", []):
                    loot.append(CreatureLoot(**loot_data))
                
                creature_data["attacks"] = attacks
                creature_data["loot"] = loot
                self.creatures[name] = CreatureInfo(**creature_data)
            
            logger.info(f"Base de datos cargada: {len(self.creatures)} criaturas")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando base de datos: {e}")
            return False
    
    def generate_targeting_profiles(self) -> Dict[str, Dict]:
        """Genera perfiles automáticos para el targeting basados en las características."""
        profiles = {}
        
        for creature in self.creatures.values():
            profile = self._generate_creature_profile(creature)
            profiles[creature.name] = profile
        
        return profiles
    
    def _generate_creature_profile(self, creature: CreatureInfo) -> Dict:
        """Genera un perfil de targeting para una criatura específica."""
        
        # Determinar modo de ataque basado en características
        if creature.is_mage:
            attack_mode = "defensive"  # Mantener distancia de magos
        elif creature.is_ranged:
            attack_mode = "balanced"   # Equilibrado para ranged
        else:
            attack_mode = "offensive"  # Ofensivo para melee
        
        # Determinar modo de chase
        if creature.run_health > 0 and creature.run_health < creature.max_health * 0.3:
            chase_mode = "chase"  # Criatura huye fácilmente
        elif creature.is_ranged:
            chase_mode = "stand"   # Mantener distancia de ranged
        else:
            chase_mode = "auto"    # Automático
        
        # Determinar umbrales de HP
        if creature.max_health >= 1000:
            hp_threshold_chase = 0.3  # Criaturas fuertes
            hp_threshold_stand = 0.7
        elif creature.max_health >= 500:
            hp_threshold_chase = 0.2
            hp_threshold_stand = 0.6
        else:
            hp_threshold_chase = 0.1  # Criaturas débiles
            hp_threshold_stand = 0.5
        
        # Determinar spells basados en ataques de la criatura
        spells_by_count = self._generate_spells_for_creature(creature)
        
        # Prioridad basada en experiencia y dificultad
        priority = creature.experience + (creature.difficulty_level * 100)
        
        return {
            "chase_mode": chase_mode,
            "attack_mode": attack_mode,
            "flees_at_hp": creature.run_health / creature.max_health if creature.run_health > 0 else 0.0,
            "is_ranged": creature.is_ranged,
            "priority": priority,
            "use_chase_on_flee": creature.run_health > 0,
            "hp_threshold_chase": hp_threshold_chase,
            "hp_threshold_stand": hp_threshold_stand,
            "spells_by_count": spells_by_count,
            "spell_cooldown": 2.0 if creature.is_mage else 1.5,
            "auto_generated": True,
            "source_data": {
                "experience": creature.experience,
                "health": creature.max_health,
                "class": creature.class_type,
                "difficulty": creature.difficulty_level,
                "is_mage": creature.is_mage,
                "is_ranged": creature.is_ranged,
                "is_healer": creature.is_healer
            }
        }
    
    def _generate_spells_for_creature(self, creature: CreatureInfo) -> Dict[str, List[str]]:
        """Genera configuración de spells basada en las características de la criatura."""
        
        # Spells base según tipo de criatura
        if creature.is_mage:
            # Contra magos usar spells de alto daño
            return {
                "1": ["exori", "exori gran"],
                "2": ["exori mas", "exori gran", "exori"],
                "3": ["exori gran", "exori mas", "exori", "utori mort"],
                "default": ["exori"]
            }
        elif creature.is_ranged:
            # Contra ranged usar spells de distancia
            return {
                "1": ["exori con"],
                "2": ["exori gran con", "exori con"],
                "3": ["exori mas con", "exori gran con", "exori con"],
                "default": ["exori con"]
            }
        elif creature.is_healer:
            # Contra healers usar spells de muerte
            return {
                "1": ["exori mort"],
                "2": ["exori gran mort", "exori mort"],
                "3": ["exori mas mort", "exori gran mort", "exori mort"],
                "default": ["exori mort"]
            }
        else:
            # Criaturas melee normales
            return {
                "1": ["exori"],
                "2": ["exori gran", "exori"],
                "3": ["exori mas", "exori gran", "exori"],
                "default": ["exori"]
            }

def main():
    """Función principal para generar la base de datos."""
    tibia_files_path = "tibia_files_canary"
    output_path = "creature_database.json"
    profiles_path = "auto_targeting_profiles.json"
    
    # Crear base de datos
    db = CreatureDatabase(tibia_files_path)
    
    # Cargar todas las criaturas
    if not db.load_all_creatures():
        print("Error cargando criaturas")
        return
    
    # Guardar base de datos
    db.save_database(output_path)
    
    # Generar perfiles automáticos
    profiles = db.generate_targeting_profiles()
    
    # Guardar perfiles
    with open(profiles_path, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== RESUMEN ===")
    print(f"Total criaturas: {len(db.creatures)}")
    print(f"Perfiles generados: {len(profiles)}")
    print(f"Base de datos guardada en: {output_path}")
    print(f"Perfiles guardados en: {profiles_path}")
    
    # Mostrar algunas estadísticas
    classes = {}
    difficulties = {}
    
    for creature in db.creatures.values():
        classes[creature.class_type] = classes.get(creature.class_type, 0) + 1
        difficulties[creature.difficulty_level] = difficulties.get(creature.difficulty_level, 0) + 1
    
    print(f"\n=== DISTRIBUCIÓN POR CLASE ===")
    for class_type, count in sorted(classes.items()):
        print(f"{class_type}: {count}")
    
    print(f"\n=== DISTRIBUCIÓN POR DIFICULTAD ===")
    for level, count in sorted(difficulties.items()):
        print(f"Nivel {level}: {count}")

if __name__ == "__main__":
    main()
