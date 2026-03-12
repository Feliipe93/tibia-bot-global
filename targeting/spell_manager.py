#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spell_manager.py - Gestor de spells para targeting.
Maneja el lanzamiento de spells basado en el número de criaturas cercanas.
"""

import time
from typing import Dict, List, Optional, Tuple

import numpy as np


class SpellManager:
    """
    Gestor de spells para el sistema de targeting.
    Permite configurar spells diferentes según el número de criaturas.
    """
    
    def __init__(self):
        self.spells_by_count: Dict[int, List[str]] = {
            1: [],  # 1 criatura
            2: [],  # 2 criaturas
            3: [],  # 3+ criaturas
        }
        self.default_spells: List[str] = []
        
        # Cooldowns por spell
        self.spell_cooldowns: Dict[str, float] = {}
        self.last_cast_times: Dict[str, float] = {}
        
        # Callback para enviar teclas
        self.key_callback: Optional[callable] = None
        
        # Callback para logging
        self.log_callback: Optional[callable] = None
        
    def set_key_callback(self, callback: callable):
        """Establece el callback para enviar teclas."""
        self.key_callback = callback
        
    def set_log_callback(self, callback: callable):
        """Establece el callback para logging."""
        self.log_callback = callback
        
    def configure_spells(self, creature_name: str, spells_config: Dict):
        """
        Configura los spells para una criatura específica.
        
        Args:
            creature_name: Nombre de la criatura
            spells_config: Configuración de spells desde el perfil
        """
        if 'spells_by_count' in spells_config:
            spells_by_count = spells_config['spells_by_count']
            
            # Spells para 1 criatura
            if 1 in spells_by_count:
                self.spells_by_count[1] = spells_by_count[1]
                
            # Spells para 2 criaturas
            if 2 in spells_by_count:
                self.spells_by_count[2] = spells_by_count[2]
                
            # Spells para 3+ criaturas
            if 3 in spells_by_count:
                self.spells_by_count[3] = spells_by_count[3]
                
            # Spells por defecto
            if 'default' in spells_by_count:
                self.default_spells = spells_by_count['default']
                
        # Configurar cooldowns
        if 'spell_cooldown' in spells_config:
            cooldown = spells_config['spell_cooldown']
            # Aplicar mismo cooldown a todos los spells de esta criatura
            for count_spells in self.spells_by_count.values():
                for spell in count_spells:
                    self.spell_cooldowns[spell] = cooldown
            for spell in self.default_spells:
                self.spell_cooldowns[spell] = cooldown
                
    def get_spells_for_count(self, creature_count: int) -> List[str]:
        """
        Obtiene la lista de spells para un número específico de criaturas.
        """
        if creature_count in self.spells_by_count:
            return self.spells_by_count[creature_count]
        elif creature_count >= 3:
            return self.spells_by_count.get(3, self.default_spells)
        else:
            return self.default_spells
            
    def can_cast_spell(self, spell: str) -> bool:
        """
        Verifica si un spell puede ser lanzado (cooldown).
        """
        if spell not in self.spell_cooldowns:
            return True
            
        current_time = time.time()
        last_cast = self.last_cast_times.get(spell, 0.0)
        cooldown = self.spell_cooldowns[spell]
        
        return (current_time - last_cast) >= cooldown
        
    def cast_spell(self, spell: str) -> bool:
        """
        Lanza un spell.
        
        Args:
            spell: El spell a lanzar (hotkey)
            
        Returns:
            True si se lanzó correctamente, False si no
        """
        if not self.key_callback:
            if self.log_callback:
                self.log_callback("⚠ Sin callback de teclas - no se puede lanzar spell")
            return False
            
        if not self.can_cast_spell(spell):
            return False
            
        try:
            # Enviar tecla
            result = self.key_callback(spell)
            
            if result:
                # Actualizar tiempo de último lanzamiento
                self.last_cast_times[spell] = time.time()
                
                if self.log_callback:
                    self.log_callback(f"🔮 Spell lanzado: {spell}")
                    
                return True
            else:
                if self.log_callback:
                    self.log_callback(f"⚠ Falló lanzamiento de spell: {spell}")
                return False
                
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"❌ Error lanzando spell {spell}: {e}")
            return False
            
    def process_spells_for_creature(self, creature_name: str, nearby_creatures: List[str]) -> bool:
        """
        Procesa los spells para una criatura basándose en el número de criaturas cercanas.
        
        Args:
            creature_name: Nombre de la criatura objetivo
            nearby_creatures: Lista de criaturas cercanas (incluyendo el objetivo)
            
        Returns:
            True si se lanzó al menos un spell, False si no
        """
        creature_count = len(nearby_creatures)
        spells = self.get_spells_for_count(creature_count)
        
        if not spells:
            return False
            
        spells_cast = False
        
        for spell in spells:
            if self.cast_spell(spell):
                spells_cast = True
                # Pequeña pausa entre spells
                time.sleep(0.1)
                
        return spells_cast
        
    def get_spell_status(self) -> Dict:
        """
        Obtiene el estado actual de los spells.
        """
        current_time = time.time()
        status = {}
        
        for spell, cooldown in self.spell_cooldowns.items():
            last_cast = self.last_cast_times.get(spell, 0.0)
            time_remaining = max(0, cooldown - (current_time - last_cast))
            
            status[spell] = {
                'cooldown': cooldown,
                'last_cast': last_cast,
                'time_remaining': time_remaining,
                'ready': time_remaining <= 0
            }
            
        return status
        
    def reset_cooldowns(self):
        """Resetea todos los cooldowns de spells."""
        self.last_cast_times.clear()
        
        if self.log_callback:
            self.log_callback("🔄 Cooldowns de spells reseteados")
