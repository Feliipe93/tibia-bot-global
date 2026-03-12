#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tibia_assets_reader.py - Sistema para leer assets de Tibia
Extrae información visual de monstruos, cuerpos muertos y loot desde archivos .dat y .xml
"""

import os
import xml.etree.ElementTree as ET
import struct
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ItemInfo:
    """Información de un item de Tibia."""
    id: int
    name: str
    article: str = ""
    description: str = ""
    weight: float = 0.0
    attributes: Dict = None
    is_container: bool = False
    is_corpse: bool = False
    corpse_size: int = 0
    decay_to: int = 0
    duration: int = 0
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}

@dataclass
class MonsterVisualInfo:
    """Información visual de un monstruo."""
    name: str
    look_type: int
    look_head: int
    look_body: int
    look_legs: int
    look_feet: int
    look_addons: int
    corpse_item_id: int
    corpse_name: str
    corpse_images: List[int] = None
    
    def __post_init__(self):
        if self.corpse_images is None:
            self.corpse_images = []

@dataclass
class LootInfo:
    """Información de loot de un monstruo."""
    monster_name: str
    items: List[Dict]
    total_items: int
    rare_items: List[Dict]
    common_items: List[Dict]

class TibiaAssetsReader:
    """Lector de assets de Tibia."""
    
    def __init__(self, tibia_files_path: str):
        self.tibia_files_path = tibia_files_path
        self.items_xml_path = os.path.join(tibia_files_path, "data", "items", "items.xml")
        self.appearances_dat_path = os.path.join(tibia_files_path, "data", "items", "appearances.dat")
        self.monster_files_path = os.path.join(tibia_files_path, "data", "monster")
        
        self.items: Dict[int, ItemInfo] = {}
        self.corpse_items: Dict[int, ItemInfo] = {}
        self.monster_visuals: Dict[str, MonsterVisualInfo] = {}
        self.loot_database: Dict[str, LootInfo] = {}
        
    def load_all_assets(self) -> bool:
        """Carga todos los assets."""
        logger.info("Cargando assets de Tibia...")
        
        success = True
        
        # 1. Cargar items desde XML
        if not self._load_items_xml():
            success = False
        
        # 2. Identificar cuerpos muertos
        self._identify_corpse_items()
        
        # 3. Cargar información visual de monstruos
        if not self._load_monster_visuals():
            success = False
        
        # 4. Extraer información de loot
        if not self._extract_loot_info():
            success = False
        
        logger.info(f"Assets cargados: {len(self.items)} items, {len(self.corpse_items)} cuerpos, {len(self.monster_visuals)} monstruos")
        
        return success
    
    def _load_items_xml(self) -> bool:
        """Carga items desde el archivo XML."""
        try:
            if not os.path.exists(self.items_xml_path):
                logger.error(f"No existe el archivo: {self.items_xml_path}")
                return False
            
            tree = ET.parse(self.items_xml_path)
            root = tree.getroot()
            
            for item_elem in root.findall("item"):
                item_info = self._parse_item_xml(item_elem)
                if item_info:
                    self.items[item_info.id] = item_info
            
            logger.info(f"Items cargados: {len(self.items)}")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando items XML: {e}")
            return False
    
    def _parse_item_xml(self, item_elem) -> Optional[ItemInfo]:
        """Parsea un elemento XML de item."""
        try:
            # ID y nombre
            item_id = int(item_elem.get("id"))
            name = item_elem.get("name", "")
            article = item_elem.get("article", "")
            
            # Atributos
            attributes = {}
            weight = 0.0
            is_container = False
            is_corpse = False
            corpse_size = 0
            decay_to = 0
            duration = 0
            description = ""
            
            for attr_elem in item_elem.findall("attribute"):
                key = attr_elem.get("key", "")
                value = attr_elem.get("value", "")
                
                attributes[key] = value
                
                # Atributos importantes
                if key == "weight":
                    try:
                        weight_val = float(value) if value else 0.0
                        weight = weight_val / 100.0  # Convertir de oz a kg
                    except:
                        pass
                elif key == "containersize":
                    is_container = True
                    try:
                        corpse_size = int(value) if value else 0
                    except:
                        pass
                elif key == "decayTo":
                    try:
                        decay_to = int(value) if value else 0
                    except:
                        pass
                elif key == "duration":
                    try:
                        duration = int(value) if value else 0
                    except:
                        pass
                elif key == "description":
                    description = value or ""
            
            # Detectar si es un cuerpo muerto
            is_corpse = ("corpse" in name.lower() or 
                        "dead " in name.lower() or 
                        "remains" in name.lower() or
                        is_container and decay_to > 0)
            
            return ItemInfo(
                id=item_id,
                name=name,
                article=article,
                description=description,
                weight=weight,
                attributes=attributes,
                is_container=is_container,
                is_corpse=is_corpse,
                corpse_size=corpse_size,
                decay_to=decay_to,
                duration=duration
            )
            
        except Exception as e:
            logger.warning(f"Error parseando item XML: {e}")
            return None
    
    def _identify_corpse_items(self):
        """Identifica y cataloga los items de cuerpos muertos."""
        self.corpse_items = {}
        
        for item_id, item_info in self.items.items():
            if item_info.is_corpse:
                self.corpse_items[item_id] = item_info
        
        logger.info(f"Cuerpos muertos identificados: {len(self.corpse_items)}")
    
    def _load_monster_visuals(self) -> bool:
        """Carga información visual de monstruos desde archivos .lua."""
        try:
            if not os.path.exists(self.monster_files_path):
                logger.error(f"No existe el directorio: {self.monster_files_path}")
                return False
            
            # Recorrer todos los archivos de monstruos
            for root, dirs, files in os.walk(self.monster_files_path):
                for file in files:
                    if file.endswith('.lua'):
                        file_path = os.path.join(root, file)
                        monster_info = self._parse_monster_lua(file_path)
                        if monster_info:
                            self.monster_visuals[monster_info.name.lower()] = monster_info
            
            logger.info(f"Visuales de monstruos cargados: {len(self.monster_visuals)}")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando visuales de monstruos: {e}")
            return False
    
    def _parse_monster_lua(self, file_path: str) -> Optional[MonsterVisualInfo]:
        """Parsea un archivo .lua de monstruo para extraer información visual."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Extraer nombre
            name_match = self._extract_lua_value(content, 'Game.createMonsterType')
            if not name_match:
                return None
            
            name = name_match.strip('"')
            
            # Extraer outfit
            outfit = self._extract_lua_outfit(content)
            if not outfit:
                return None
            
            look_type = outfit.get('lookType', 0)
            look_head = outfit.get('lookHead', 0)
            look_body = outfit.get('lookBody', 0)
            look_legs = outfit.get('lookLegs', 0)
            look_feet = outfit.get('lookFeet', 0)
            look_addons = outfit.get('lookAddons', 0)
            
            # Buscar corpse item
            corpse_item_id = self._find_corpse_for_monster(name, content)
            corpse_name = ""
            
            if corpse_item_id and corpse_item_id in self.corpse_items:
                corpse_name = self.corpse_items[corpse_item_id].name
            
            return MonsterVisualInfo(
                name=name,
                look_type=look_type,
                look_head=look_head,
                look_body=look_body,
                look_legs=look_legs,
                look_feet=look_feet,
                look_addons=look_addons,
                corpse_item_id=corpse_item_id,
                corpse_name=corpse_name
            )
            
        except Exception as e:
            logger.warning(f"Error parseando monstruo {file_path}: {e}")
            return None
    
    def _extract_lua_value(self, content: str, pattern: str) -> Optional[str]:
        """Extrae un valor de un archivo Lua."""
        import re
        
        if pattern == 'Game.createMonsterType':
            match = re.search(r'Game\.createMonsterType\("([^"]+)"\)', content)
            return match.group(1) if match else None
        
        return None
    
    def _extract_lua_outfit(self, content: str) -> Optional[Dict]:
        """Extrae el outfit de un monstruo."""
        import re
        
        # Buscar el bloque de outfit
        outfit_match = re.search(r'monster\.outfit\s*=\s*{([^}]+)}', content, re.DOTALL)
        if not outfit_match:
            return None
        
        outfit_str = outfit_match.group(1)
        outfit = {}
        
        # Extraer cada atributo
        patterns = {
            'lookType': r'lookType\s*=\s*(\d+)',
            'lookHead': r'lookHead\s*=\s*(\d+)',
            'lookBody': r'lookBody\s*=\s*(\d+)',
            'lookLegs': r'lookLegs\s*=\s*(\d+)',
            'lookFeet': r'lookFeet\s*=\s*(\d+)',
            'lookAddons': r'lookAddons\s*=\s*(\d+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, outfit_str)
            if match:
                outfit[key] = int(match.group(1))
        
        return outfit if outfit else None
    
    def _find_corpse_for_monster(self, monster_name: str, content: str) -> Optional[int]:
        """Busca el ID del corpse para un monstruo."""
        import re
        
        # Primero buscar corpse en el archivo del monstruo
        corpse_match = re.search(r'monster\.corpse\s*=\s*(\d+)', content)
        if corpse_match:
            return int(corpse_match.group(1))
        
        # Si no está, buscar por nombre en los corpse items
        monster_lower = monster_name.lower()
        
        # Buscar corpse con el nombre exacto del monstruo
        for corpse_id, corpse_info in self.corpse_items.items():
            corpse_name_lower = corpse_info.name.lower()
            
            # "dead monstername" o "monstername corpse"
            if (f"dead {monster_lower}" in corpse_name_lower or 
                f"{monster_lower} corpse" in corpse_name_lower or
                monster_lower in corpse_name_lower):
                return corpse_id
        
        # Búsqueda más flexible
        for corpse_id, corpse_info in self.corpse_items.items():
            corpse_name_lower = corpse_info.name.lower()
            
            # Si el nombre del monstruo está contenido en el corpse
            if monster_lower in corpse_name_lower and "corpse" in corpse_name_lower:
                return corpse_id
        
        return None
    
    def _extract_loot_info(self) -> bool:
        """Extrae información de loot desde archivos de monstruos."""
        try:
            if not os.path.exists(self.monster_files_path):
                logger.error(f"No existe el directorio: {self.monster_files_path}")
                return False
            
            # Recorrer todos los archivos de monstruos
            for root, dirs, files in os.walk(self.monster_files_path):
                for file in files:
                    if file.endswith('.lua'):
                        file_path = os.path.join(root, file)
                        loot_info = self._parse_monster_loot(file_path)
                        if loot_info:
                            self.loot_database[loot_info.monster_name.lower()] = loot_info
            
            logger.info(f"Loot cargado: {len(self.loot_database)} monstruos")
            return True
            
        except Exception as e:
            logger.error(f"Error extrayendo loot: {e}")
            return False
    
    def _parse_monster_loot(self, file_path: str) -> Optional[LootInfo]:
        """Parsea el loot de un monstruo."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Extraer nombre
            name_match = self._extract_lua_value(content, 'Game.createMonsterType')
            if not name_match:
                return None
            
            monster_name = name_match.strip('"')
            
            # Extraer loot
            loot_items = self._extract_lua_loot_items(content)
            
            if not loot_items:
                return None
            
            # Clasificar items
            rare_items = []
            common_items = []
            
            for item in loot_items:
                chance = item.get('chance', 0)
                if chance <= 1000:  # 10% o menos
                    rare_items.append(item)
                else:
                    common_items.append(item)
            
            return LootInfo(
                monster_name=monster_name,
                items=loot_items,
                total_items=len(loot_items),
                rare_items=rare_items,
                common_items=common_items
            )
            
        except Exception as e:
            logger.warning(f"Error parseando loot de {file_path}: {e}")
            return None
    
    def _extract_lua_loot_items(self, content: str) -> List[Dict]:
        """Extrae items de loot de un monstruo."""
        import re
        
        items = []
        
        # Buscar el bloque de loot
        loot_match = re.search(r'monster\.loot\s*=\s*{([^}]+)}', content, re.DOTALL)
        if not loot_match:
            return items
        
        loot_content = loot_match.group(1)
        
        # Extraer cada item
        item_pattern = r'{([^}]+)}'
        for item_match in re.finditer(item_pattern, loot_content):
            item_str = item_match.group(1)
            item = self._parse_loot_item(item_str)
            if item:
                items.append(item)
        
        return items
    
    def _parse_loot_item(self, item_str: str) -> Optional[Dict]:
        """Parsea un item de loot individual."""
        import re
        
        try:
            # Extraer valores
            name = self._extract_field_from_loot(item_str, "name")
            item_id = self._extract_field_from_loot(item_str, "id")
            chance = self._extract_field_from_loot(item_str, "chance", 0)
            max_count = self._extract_field_from_loot(item_str, "maxCount", 1)
            
            # Si no tiene nombre pero tiene ID, buscar en items
            if not name and item_id:
                item_id_int = int(item_id)
                if item_id_int in self.items:
                    name = self.items[item_id_int].name
            
            if not name:
                return None
            
            return {
                'name': name,
                'item_id': int(item_id) if item_id else None,
                'chance': int(chance),
                'max_count': int(max_count),
                'rarity': self._calculate_rarity(int(chance))
            }
            
        except Exception as e:
            logger.warning(f"Error parseando item loot: {e}")
            return None
    
    def _extract_field_from_loot(self, loot_str: str, field: str, default=None):
        """Extrae un campo específico de un item de loot."""
        import re
        
        pattern = rf'{field}\s*=\s*"?([^",\}}]+)"?'
        match = re.search(pattern, loot_str)
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
    
    def _calculate_rarity(self, chance: int) -> str:
        """Calcula la rareza de un item basado en su chance."""
        if chance <= 100:
            return "Legendary"
        elif chance <= 500:
            return "Epic"
        elif chance <= 1000:
            return "Rare"
        elif chance <= 5000:
            return "Uncommon"
        else:
            return "Common"
    
    def get_monster_visual_info(self, monster_name: str) -> Optional[MonsterVisualInfo]:
        """Obtiene información visual de un monstruo."""
        return self.monster_visuals.get(monster_name.lower())
    
    def get_loot_info(self, monster_name: str) -> Optional[LootInfo]:
        """Obtiene información de loot de un monstruo."""
        return self.loot_database.get(monster_name.lower())
    
    def get_corpse_info(self, corpse_id: int) -> Optional[ItemInfo]:
        """Obtiene información de un cuerpo muerto."""
        return self.corpse_items.get(corpse_id)
    
    def search_items(self, query: str) -> List[ItemInfo]:
        """Busca items por nombre."""
        query = query.lower()
        results = []
        
        for item in self.items.values():
            if query in item.name.lower():
                results.append(item)
        
        return results
    
    def search_corpses(self, query: str) -> List[ItemInfo]:
        """Busca cuerpos muertos por nombre."""
        query = query.lower()
        results = []
        
        for corpse in self.corpse_items.values():
            if query in corpse.name.lower():
                results.append(corpse)
        
        return results
    
    def get_monster_complete_info(self, monster_name: str) -> Optional[Dict]:
        """Obtiene información completa de un monstruo."""
        visual_info = self.get_monster_visual_info(monster_name)
        loot_info = self.get_loot_info(monster_name)
        
        if not visual_info and not loot_info:
            return None
        
        result = {
            'name': monster_name,
            'visual': asdict(visual_info) if visual_info else None,
            'loot': asdict(loot_info) if loot_info else None
        }
        
        # Agregar información del corpse si existe
        if visual_info and visual_info.corpse_item_id:
            corpse_info = self.get_corpse_info(visual_info.corpse_item_id)
            if corpse_info:
                result['corpse'] = asdict(corpse_info)
        
        return result
    
    def save_assets_database(self, output_path: str):
        """Guarda la base de datos de assets."""
        data = {
            "version": "1.0",
            "total_items": len(self.items),
            "total_corpses": len(self.corpse_items),
            "total_monsters": len(self.monster_visuals),
            "total_loot_entries": len(self.loot_database),
            "items": {str(item_id): asdict(item_info) for item_id, item_info in self.items.items()},
            "corpses": {str(corpse_id): asdict(corpse_info) for corpse_id, corpse_info in self.corpse_items.items()},
            "monster_visuals": {name: asdict(visual_info) for name, visual_info in self.monster_visuals.items()},
            "loot_database": {name: asdict(loot_info) for name, loot_info in self.loot_database.items()}
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Base de datos de assets guardada en: {output_path}")
    
    def load_assets_database(self, input_path: str) -> bool:
        """Carga la base de datos de assets desde un archivo JSON."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruir objetos
            self.items = {}
            for item_id, item_data in data.get("items", {}).items():
                self.items[int(item_id)] = ItemInfo(**item_data)
            
            self.corpse_items = {}
            for corpse_id, corpse_data in data.get("corpses", {}).items():
                self.corpse_items[int(corpse_id)] = ItemInfo(**corpse_data)
            
            self.monster_visuals = {}
            for name, visual_data in data.get("monster_visuals", {}).items():
                self.monster_visuals[name] = MonsterVisualInfo(**visual_data)
            
            self.loot_database = {}
            for name, loot_data in data.get("loot_database", {}).items():
                self.loot_database[name] = LootInfo(**loot_data)
            
            logger.info(f"Base de datos de assets cargada: {len(self.items)} items")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando base de datos de assets: {e}")
            return False

def main():
    """Función principal para probar el sistema."""
    tibia_files_path = "tibia_files_canary"
    output_path = "tibia_assets_database.json"
    
    print("=== SISTEMA DE ASSETS DE TIBIA ===\n")
    
    # Crear lector
    reader = TibiaAssetsReader(tibia_files_path)
    
    # Cargar todos los assets
    if not reader.load_all_assets():
        print("Error cargando assets")
        return
    
    # Guardar base de datos
    reader.save_assets_database(output_path)
    
    # Probar búsquedas
    print("\n=== PRUEBAS DE BÚSQUEDA ===")
    
    # Buscar monstruos
    test_monsters = ["Dragon", "Orc", "Demon", "Amazon"]
    
    for monster in test_monsters:
        info = reader.get_monster_complete_info(monster)
        if info:
            print(f"\n[INFO] {monster}:")
            
            if info['visual']:
                visual = info['visual']
                print(f"  Look Type: {visual['look_type']}")
                print(f"  Corpse ID: {visual['corpse_item_id']}")
                print(f"  Corpse Name: {visual['corpse_name']}")
            
            if info['loot']:
                loot = info['loot']
                print(f"  Loot Items: {loot['total_items']}")
                print(f"  Rare Items: {len(loot['rare_items'])}")
                if loot['items'][:3]:  # Mostrar primeros 3 items
                    for item in loot['items'][:3]:
                        print(f"    - {item['name']} (Chance: {item['chance']}, Rarity: {item['rarity']})")
            
            if info['corpse']:
                corpse = info['corpse']
                print(f"  Corpse Size: {corpse['corpse_size']}")
                print(f"  Duration: {corpse['duration']}s")
    
    # Buscar cuerpos
    print(f"\n[SEARCH] Busqueda de cuerpos 'dragon':")
    dragon_corpses = reader.search_corpses("dragon")
    for corpse in dragon_corpses[:5]:
        print(f"  - {corpse.name} (ID: {corpse.id}, Size: {corpse.corpse_size})")
    
    # Estadísticas
    print(f"\n[STATS] ESTADISTICAS:")
    print(f"  Total Items: {len(reader.items)}")
    print(f"  Total Corpses: {len(reader.corpse_items)}")
    print(f"  Monster Visuals: {len(reader.monster_visuals)}")
    print(f"  Loot Entries: {len(reader.loot_database)}")
    
    print(f"\n[SUCCESS] Base de datos guardada en: {output_path}")

if __name__ == "__main__":
    main()
