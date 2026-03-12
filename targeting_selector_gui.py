#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeting_selector_gui.py - GUI para selección de criaturas para targeting V2
Permite elegir qué monstruos atacar y cuáles ignorar con toda la información visual disponible.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Dict, List, Optional
import json
from auto_targeting_system import AutoTargetingSystem
from intelligent_targeting import IntelligentTargeting
from visual_targeting_system import VisualTargetingSystem
import logging

logger = logging.getLogger(__name__)

class TargetingSelectorGUI:
    """GUI para selección de criaturas para targeting V2."""
    
    def __init__(self, parent, targeting_engine_v2):
        self.parent = parent
        self.targeting_engine = targeting_engine_v2
        
        # Sistema automático
        self.auto_system = AutoTargetingSystem()
        
        # Variables para la GUI
        self.available_creatures = []
        self.selected_creatures = []
        self.ignored_creatures = []
        self.creature_details = {}
        
        # Crear frame principal
        self.create_main_frame()
        
        # Inicializar sistema
        self.initialize_system()
    
    def create_main_frame(self):
        """Crea el frame principal."""
        # Frame principal
        self.main_frame = ctk.CTkFrame(
            self.parent, 
            fg_color="#1a2733"
        )
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Frame de título
        title_frame = ctk.CTkFrame(self.main_frame, fg_color="#0f1923")
        title_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            title_frame,
            text="🎯 SELECCIÓN DE CRIATURAS PARA TARGETING V2",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        info_text = """
📋 INSTRUCCIONES:
• El sistema detecta automáticamente todas las criaturas disponibles
• Puedes elegir qué criaturas atacar y cuáles ignorar
• La prioridad se calcula automáticamente según experiencia, HP y dificultad
• Toda la información visual está disponible para ayudar en la decisión
• La configuración se guarda y se puede exportar al config.json principal
        """
        
        ctk.CTkLabel(
            title_frame,
            text=info_text,
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
            justify="left"
        ).pack(padx=10, pady=5)
        
        # Frame de selección con columnas
        selection_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        selection_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Columna izquierda - Criaturas disponibles
        left_frame = ctk.CTkFrame(selection_frame, fg_color="#0f1923")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(
            left_frame,
            text="👾️ CRIATURAS DISPONIBLES",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame de búsqueda y filtros
        search_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Búsqueda
        search_input_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        search_input_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(
            search_input_frame,
            text="🔍 Buscar:",
            width=80
        ).pack(side="left", padx=(0, 5))
        
        self.search_entry = ctk.CTkEntry(
            search_input_frame,
            placeholder_text="Buscar criatura...",
            width=200
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        
        self.search_entry.bind('<Return>', lambda e: self.search_creatures())
        
        ctk.CTkButton(
            search_input_frame,
            text="🔍",
            command=self.search_creatures,
            width=40
        ).pack(side="right")
        
        # Filtros rápidos
        filters_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        filters_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(
            filters_frame,
            text="🔍 Filtros:",
            width=80
        ).pack(side="left", padx=(0, 5))
        
        self.filter_combo = ctk.CTkComboBox(
            filters_frame,
            values=["Todos", "Alta Prioridad", "Media Prioridad", "Baja Prioridad", "Magos", "Ranged", "Melee"],
            width=150
        )
        self.filter_combo.set("Todos")
        self.filter_combo.pack(side="left", padx=5)
        
        # Frame de lista de criaturas
        list_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Treeview para criaturas disponibles
        self.available_tree = ttk.Treeview(
            list_frame,
            columns=("name", "priority", "hp", "exp", "type", "threat"),
            show="headings",
            height=20
        )
        
        # Configurar columnas
        self.available_tree.heading("name", text="Criatura")
        self.available_tree.heading("priority", text="Prioridad")
        self.available_tree.heading("hp", text="HP")
        self.available_tree.heading("exp", text="Exp")
        self.available_tree.heading("type", text="Tipo")
        self.available_tree.heading("threat", text="Amenaza")
        
        # Anchos de columna
        self.available_tree.column("name", width=150)
        self.available_tree.column("priority", width=80)
        self.available_tree.column("hp", width=60)
        self.available_tree.column("exp", width=60)
        self.available_tree.column("type", width=80)
        self.available_tree.column("threat", width=80)
        
        # Scrollbar
        scrollbar1 = ttk.Scrollbar(list_frame, orient="vertical", command=self.available_tree.yview)
        self.available_tree.configure(yscrollcommand=scrollbar1.set)
        
        self.available_tree.pack(side="left", fill="both", expand=True, padx=(0, 0), pady=5)
        scrollbar1.pack(side="right", fill="y", padx=(0, 5), pady=5)
        
        # Botones de selección rápida
        quick_select_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        quick_select_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            quick_select_frame,
            text="👆 Seleccionar Todos",
            command=self.select_all_creatures,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            quick_select_frame,
            text="👎 Seleccionar Ninguno",
            command=self.clear_selection,
            width=120
        ).pack(side="left", padx=5)
        
        # Columna central - Criaturas seleccionadas
        center_frame = ctk.CTkFrame(selection_frame, fg_color="#0f1923")
        center_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(
            center_frame,
            text="🎯 CRIATURAS SELECCIONADAS",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame de botones de acción
        action_frame = ctk.CTkFrame(center_frame, fg_color="transparent")
        action_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            action_frame,
            text="➡️ Agregar a Seleccionados",
            command=self.add_to_selected,
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            action_frame,
            text="➖️ Quitar de Seleccionados",
            command=self.remove_from_selected,
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            action_frame,
            text="🔄 Limpiar Selección",
            command=self.clear_selection,
            width=120
        ).pack(side="left", padx=5)
        
        # Frame de lista de criaturas seleccionadas
        selected_list_frame = ctk.CTkFrame(center_frame, fg_color="transparent")
        selected_list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Treeview para criaturas seleccionadas
        self.selected_tree = ttk.Treeview(
            selected_list_frame,
            columns=("name", "priority", "hp", "exp", "type", "threat"),
            show="headings",
            height=20
        )
        
        # Configurar columnas
        self.selected_tree.heading("name", text="Criatura")
        self.selected_tree.heading("priority", text="Prioridad")
        self.selected_tree.heading("hp", text="HP")
        self.selected_tree.heading("exp", text="Exp")
        self.selected_tree.heading("type", text="Tipo")
        self.selected_tree.heading("threat", text="Amenaza")
        
        # Anchos de columna
        self.selected_tree.column("name", width=150)
        self.selected_tree.column("priority", width=80)
        self.selected_tree.column("hp", width=60)
        self.selected_tree.column("exp", width=60)
        self.selected_tree.column("type", width=80)
        self.selected_tree.column("threat", width=80)
        
        # Scrollbar
        scrollbar2 = ttk.Scrollbar(selected_list_frame, orient="vertical", command=self.selected_tree.yview)
        self.selected_tree.configure(yscrollcommand=scrollbar2.set)
        
        self.selected_tree.pack(side="left", fill="both", expand=True, padx=(0, 0), pady=5)
        scrollbar2.pack(side="right", fill="y", padx=(0, 5), pady=5)
        
        # Columna derecha - Criaturas ignoradas
        right_frame = ctk.CTkFrame(selection_frame, fg_color="#0f1923")
        right_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(
            right_frame,
            text="🚫 CRIATURAS IGNORADAS",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame de búsqueda de ignorados
        ignore_search_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        ignore_search_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            ignore_search_frame,
            text="🔍 Buscar:",
            width=80
        ).pack(side="left", padx=(0, 5))
        
        self.ignore_search_entry = ctk.CTkEntry(
            ignore_search_frame,
            placeholder_text="Buscar criatura...",
            width=200
        )
        self.ignore_search_entry.pack(side="left", fill="x", expand=True)
        
        self.ignore_search_entry.bind('<Return>', lambda e: self.search_ignored_creatures())
        
        ctk.CTkButton(
            ignore_search_frame,
            text="🔍",
            command=self.search_ignored_creatures,
            width=40
        ).pack(side="right")
        
        # Frame de lista de criaturas ignoradas
        ignored_list_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        ignored_list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Treeview para criaturas ignoradas
        self.ignored_tree = ttk.Treeview(
            ignored_list_frame,
            columns=("name", "reason", "priority", "hp", "exp"),
            show="headings",
            height=20
        )
        
        # Configurar columnas
        self.ignored_tree.heading("name", text="Criatura")
        self.ignored_tree.heading("reason", text="Razón")
        self.ignored_tree.heading("priority", text="Prioridad")
        self.ignored_tree.heading("hp", text="HP")
        self.ignored_tree.heading("exp", text="Exp")
        
        # Anchos de columna
        self.ignored_tree.column("name", width=150)
        self.ignored_tree.column("reason", width=200)
        self.ignored_tree.column("priority", width=80)
        self.ignored_tree.column("hp", width=60)
        self.ignored_tree.column("exp", width=60)
        
        # Scrollbar
        scrollbar3 = ttk.Scrollbar(ignored_list_frame, orient="vertical", command=self.ignored_tree.yview)
        self.ignored_tree.configure(yscrollcommand=scrollbar3.set)
        
        self.ignored_tree.pack(side="left", fill="both", expand=True, padx=(0, 0), pady=5)
        scrollbar3.pack(side="right", fill="y", padx=(0, 5), pady=5)
        
        # Frame de botones de acción para ignorados
        ignore_action_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        ignore_action_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            ignore_action_frame,
            text="➡️ Agregar a Ignorados",
            command=self.add_to_ignored,
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            ignore_action_frame,
            text="➖️ Quitar de Ignorados",
            command=self.remove_from_ignored,
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            ignore_action_frame,
            text="🔄 Limpiar Ignorados",
            command=self.clear_ignored,
            width=120
        ).pack(side="left", padx=5)
        
        # Frame de detalles
        details_frame = ctk.CTkFrame(self.main_frame, fg_color="#0f1923")
        details_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            details_frame,
            text="📋 DETALLES DE LA CRIATURA",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.details_text = ctk.CTkTextbox(details_frame, height=120)
        self.details_text.pack(fill="x", padx=10, pady=5)
        self.details_text.configure(state="disabled")
        
        # Frame de estadísticas
        stats_frame = ctk.CTkFrame(self.main_frame, fg_color="#0f1923")
        stats_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            stats_frame,
            text="📊 ESTADÍSTICAS",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.stats_labels = {}
        
        stats_info = [
            ("total_creatures", "Total Criaturas: --"),
            ("selected_creatures", "Seleccionados: --"),
            ("ignored_creatures", "Ignorados: --"),
            ("avg_priority", "Prioridad Promedio: --"),
            ("high_priority", "Alta Prioridad: --"),
            ("mage_count", "Magos: --"),
            ("ranged_count", "Ranged: --")
        ]
        
        for key, text in stats_info:
            label = ctk.CTkLabel(stats_frame, text=text, font=ctk.CTkFont(size=12))
            label.pack(anchor="w", padx=10, pady=2)
            self.stats_labels[key] = label
        
        # Frame de botones principales
        buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="💾 Aplicar Selección",
            command=self.apply_selection,
            fg_color="#27AE60",
            hover_color="#229954",
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="🔄 Recargar Sistema",
            command=self.reload_system,
            fg_color="#3498DB",
            hover_color="#2980B9",
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="💾 Guardar Configuración",
            command=self.save_configuration,
            fg_color="#9B59B6",
            hover_color="#8E44AD",
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="📊 Ver Estadísticas",
            command=self.show_statistics,
            fg_color="#E67E22",
            hover_color="#D35400",
            width=150
        ).pack(side="left", padx=5)
        
        # Bind doble click en las listas
        self.available_tree.bind('<Double-1>', self.on_available_double_click)
        self.selected_tree.bind('<Double-1>', self.on_selected_double_click)
        self.ignored_tree.bind('<Double-1>', self.on_ignored_double_click)
    
    def add_to_ignored(self, creature_name: str = None):
        """Agrega una criatura a la lista de ignorados."""
        if creature_name is None:
            # Obtener selección del treeview disponible
            selection = self.available_tree.selection()
            if not selection:
                return
            
            item = self.available_tree.item(selection[0])
            creature_name = item['values'][0]
        
        if creature_name not in self.ignored_creatures:
            self.ignored_creatures.append(creature_name)
            self.add_creature_to_ignored_tree(creature_name)
            
            # Remover de disponibles si está allí
            items = self.available_tree.get_children()
            for item in items:
                if item['values'][0].lower() == creature_name.lower():
                    self.available_tree.delete(item)
                    break
            
            # Actualizar estadísticas
            self.update_statistics()
    
    def add_creature_to_ignored_tree(self, creature_name: str):
        """Agrega una criatura al treeview de ignorados."""
        # Obtener información
        priority = self.auto_system.get_creature_priority(creature_name)
        
        creature_info = self.auto_system.creature_db.get_creature_info(creature_name)
        
        hp = creature_info.max_health if creature_info else 0
        exp = creature_info.experience if creature_info else 0
        
        # Agregar al treeview
        self.ignored_tree.insert("", "end", values=(
            creature_name.title(),
            "Manualmente ignorado",
            f"{priority:.1f}",
            hp,
            exp
        ))
    
    def remove_from_ignored(self):
        """Quita criaturas ignoradas."""
        selection = self.ignored_tree.selection()
        if selection:
            item = self.ignored_tree.item(selection[0])
            creature_name = item['values'][0]
            
            # Remover de ignorados
            if creature_name in self.ignored_creatures:
                self.ignored_creatures.remove(creature_name)
            
            # Agregar de vuelta a disponibles
            self.add_creature_to_available(creature_name)
            
            # Actualizar estadísticas
            self.update_statistics()
    
    def clear_ignored(self):
        """Limpia la lista de ignorados."""
        self.ignored_creatures.clear()
        
        # Limpiar treeview
        for item in self.ignored_tree.get_children():
            self.ignored_tree.delete(item)
        
        # Actualizar estadísticas
        self.update_statistics()
    
    def initialize_system(self):
        """Inicializa el sistema y carga criaturas."""
        try:
            # Inicializar sistema automático
            if not self.auto_system.initialize():
                self.show_error("Error", "No se pudo inicializar el sistema automático")
                return
            
            # Cargar criaturas disponibles
            self.load_available_creatures()
            
            # Actualizar estadísticas
            self.update_statistics()
            
            # Mostrar mensaje de éxito
            self.show_success("Sistema inicializado correctamente")
            
        except Exception as e:
            self.show_error("Error", f"Error inicializando: {e}")
    
    def load_available_creatures(self):
        """Carga las criaturas disponibles en el sistema."""
        try:
            # Obtener criaturas del sistema automático
            auto_creatures = self.auto_system.auto_detected_creatures
            self.available_creatures = list(auto_creatures)
            
            # Limpiar treeview
            for item in self.available_tree.get_children():
                self.available_tree.delete(item)
            
            # Agregar criaturas al treeview
            for creature_name in self.available_creatures:
                self.add_creature_to_available(creature_name)
            
            logger.info(f"Criaturas cargadas: {len(self.available_creatures)}")
            
        except Exception as e:
            logger.error(f"Error cargando criaturas: {e}")
    
    def add_creature_to_available(self, creature_name: str):
        """Agrega una criatura a la lista de disponibles."""
        # Obtener información de la criatura
        priority = self.auto_system.get_creature_priority(creature_name)
        
        # Obtener información visual
        visual_info = self.auto_system.visual_system.get_visual_targeting_info(creature_name)
        creature_info = self.auto_system.creature_db.get_creature_info(creature_name)
        
        # Determinar tipo y amenaza
        creature_type = "Melee"
        threat_level = "low"
        
        if visual_info:
            indicators = visual_info.visual_indicators
            if indicators.get('is_mage', False):
                creature_type = "Mage"
            elif indicators.get('is_ranged', False):
                creature_type = "Ranged"
            elif indicators.get('is_healer', False):
                creature_type = "Healer"
            
            threat_level = indicators.get('threat_level', 'low')
        
        hp = creature_info.max_health if creature_info else 0
        exp = creature_info.experience if creature_info else 0
        
        # Agregar al treeview
        self.available_tree.insert("", "end", values=(
            creature_name.title(),
            f"{priority:.1f}",
            hp,
            exp,
            creature_type,
            threat_level.title()
        ))
    
    def search_creatures(self):
        """Busca criaturas en la lista disponible."""
        query = self.search_entry.get().strip().lower()
        if not query:
            return
        
        # Limpiar resultados anteriores
        for item in self.available_tree.get_children():
            self.available_tree.delete(item)
        
        # Buscar coincidencias
        for creature_name in self.available_creatures:
            if query in creature_name.lower():
                self.add_creature_to_available(creature_name)
    
    def search_ignored_creatures(self):
        """Busca criaturas en la lista de ignorados."""
        query = self.ignore_search_entry.get().strip().lower()
        if not query:
            return
        
        # Limpiar resultados anteriores
        for item in self.ignored_tree.get_children():
            self.ignored_tree.delete(item)
        
        # Buscar coincidencias
        for creature_name in self.available_creatures:
            if query in creature_name.lower() and creature_name not in self.selected_creatures:
                # Agregar a ignorados con razón
                self.ignored_tree.insert("", "end", values=(
                    creature_name.title(),
                    "Manualmente ignorado",
                    f"{self.auto_system.get_creature_priority(creature_name):.1f}",
                    self.auto_system.get_creature_info(creature_name).max_health if self.auto_system.creature_db.get_creature_info(creature_name) else 0,
                    self.auto_system.get_creature_info(creature_name).experience if self.auto_system.creature_db.get_creature_info(creature_name) else 0
                ))
    
    def on_available_double_click(self, event):
        """Maneja doble clic en criaturas disponibles."""
        selection = self.available_tree.selection()
        if selection:
            item = self.available_tree.item(selection[0])
            creature_name = item['values'][0]
            self.add_to_selected(creature_name)
    
    def on_selected_double_click(self, event):
        """Maneja doble clic en criaturas seleccionadas."""
        selection = self.selected_tree.selection()
        if selection:
            item = self.selected_tree.item(selection[0])
            creature_name = item['values'][0]
            self.show_creature_details(creature_name)
    
    def on_ignored_double_click(self, event):
        """Maneja doble clic en criaturas ignoradas."""
        selection = self.ignored_tree.selection()
        if selection:
            item = self.ignored_tree.item(selection[0])
            creature_name = item['values'][0]
            self.show_creature_details(creature_name)
    
    def add_to_selected(self, creature_name: str):
        """Agrega una criatura a la lista de seleccionados."""
        if creature_name not in self.selected_creatures:
            self.selected_creatures.append(creature_name)
            self.add_creature_to_selected_tree(creature_name)
            
            # Remover de disponibles si está allí
            items = self.available_tree.get_children()
            for item in items:
                if item['values'][0].lower() == creature_name.lower():
                    self.available_tree.delete(item)
                    break
            
            # Actualizar estadísticas
            self.update_statistics()
    
    def add_creature_to_selected_tree(self, creature_name: str):
        """Agrega una criatura al treeview de seleccionados."""
        # Obtener información
        priority = self.auto_system.get_creature_priority(creature_name)
        
        visual_info = self.auto_system.visual_system.get_visual_targeting_info(creature_name)
        creature_info = self.auto_system.creature_db.get_creature_info(creature_name)
        
        # Determinar tipo y amenaza
        creature_type = "Melee"
        threat_level = "low"
        
        if visual_info:
            indicators = visual_info.visual_indicators
            if indicators.get('is_mage', False):
                creature_type = "Mage"
            elif indicators.get('is_ranged', False):
                creature_type = "Ranged"
            elif indicators.get('is_healer', False):
                creature_type = "Healer"
            
            threat_level = indicators.get('threat_level', 'low')
        
        hp = creature_info.max_health if creature_info else 0
        exp = creature_info.experience if creature_info else 0
        
        # Agregar al treeview
        self.selected_tree.insert("", "end", values=(
            creature_name.title(),
            f"{priority:.1f}",
            hp,
            exp,
            creature_type,
            threat_level.title()
        ))
    
    def remove_from_selected(self):
        """Quita criaturas seleccionadas."""
        selection = self.selected_tree.selection()
        if selection:
            item = self.selected_tree.item(selection[0])
            creature_name = item['values'][0]
            
            # Remover de seleccionados
            if creature_name in self.selected_creatures:
                self.selected_creatures.remove(creature_name)
            
            # Agregar de vuelta a disponibles
            self.add_creature_to_available(creature_name)
            
            # Actualizar estadísticas
            self.update_statistics()
    
    def remove_from_ignored(self):
        """Quita criaturas ignoradas."""
        selection = self.ignored_tree.selection()
        if selection:
            item = self.ignored_tree.item(selection[0])
            creature_name = item['values'][0]
            
            # Remover de ignorados
            if creature_name in self.ignored_creatures:
                self.ignored_creatures.remove(creature_name)
            
            # Agregar de vuelta a disponibles
            self.add_creature_to_available(creature_name)
            
            # Actualizar estadísticas
            self.update_statistics()
    
    def clear_selection(self):
        """Limpia la selección actual."""
        self.selected_creatures.clear()
        
        # Limpiar treeview
        for item in self.selected_tree.get_children():
            self.selected_tree.delete(item)
        
        # Actualizar estadísticas
        self.update_statistics()
    
    def clear_ignored(self):
        """Limpia la lista de ignorados."""
        self.ignored_creatures.clear()
        
        # Limpiar treeview
        for item in self.ignored_tree.get_children():
            self.ignored_tree.delete(item)
        
        # Actualizar estadísticas
        self.update_statistics()
    
    def select_all_creatures(self):
        """Selecciona todas las criaturas disponibles."""
        # Limpiar selección actual
        self.clear_selection()
        
        # Seleccionar todas las criaturas disponibles
        for creature_name in self.available_creatures:
            if creature_name not in self.selected_creatures:
                self.add_to_selected(creature_name)
        
        # Actualizar estadísticas
        self.update_statistics()
    
    def show_creature_details(self, creature_name: str):
        """Muestra detalles de una criatura."""
        try:
            # Obtener información completa
            visual_info = self.auto_system.visual_system.get_visual_targeting_info(creature_name)
            creature_info = self.auto_system.creature_db.get_creature_info(creature_name)
            
            if not visual_info and not creature_info:
                return
            
            # Construir detalles
            details = f"📋 DETALLES DE {creature_name.upper()}\n\n"
            
            # Información básica
            if creature_info:
                details += f"📊 INFORMACIÓN BÁSICA:\n"
                details += f"  HP: {creature_info.max_health}\n"
                details += f"  Experiencia: {creature_info.experience}\n"
                details += f"  Clase: {creature_info.class_type}\n"
                details += f"  Dificultad: {creature_info.difficulty_level}\n\n"
            
            # Información visual
            if visual_info:
                details += f"🎭 INFORMACIÓN VISUAL:\n"
                outfit = visual_info.outfit
                details += f"  Look Type: {visual_info.look_type}\n"
                
                if visual_info.corpse_info:
                    corpse = visual_info.corpse_info
                    details += f"  Corpse: {corpse['name']}\n"
                    details += f"  Tamaño: {corpse['size']}\n"
                    details += f"  Duración: {corpse['duration']}s\n"
                
                indicators = visual_info.visual_indicators
                details += f"  Es Mago: {'Sí' if indicators.get('is_mage', False) else 'No'}\n"
                details += f"  Es Ranged: {'Sí' if indicators.get('is_ranged', False) else 'No'}\n"
                details += f" Nivel Amenaza: {indicators.get('threat_level', 'unknown')}\n\n"
            
            # Estrategia recomendada
            if visual_info.recommended_strategy:
                strategy = visual_info.recommended_strategy
                details += f"⚔️ ESTRATEGIA RECOMENDADA:\n"
                details += f"  Modo: {strategy.get('mode', 'unknown')}\n"
                details += f"  Chase: {strategy.get('chase_mode', 'unknown')}\n"
                details += f"  Razón: {strategy.get('reason', 'unknown')}\n"
            
            # Loot
            if visual_info.loot_info:
                loot = visual_info.loot_info
                details += f"💰 LOOT:\n"
                details += f"  Items totales: {loot.get('total_items', 0)}\n"
                details += f"  Items raros: {loot.get('rare_items', 0)}\n\n"
            
            # Amenazas
            indicators = visual_info.visual_indicators
            threat_level = indicators.get('threat_level', 'unknown')
            if threat_level in ['high', 'extreme']:
                details += f"⚠️ PELIGROSA: {threat_level.upper()}\n"
            
            # Mostrar en el textbox
            self.details_text.configure(state="normal")
            self.details_text.delete("1.0", tk.END)
            self.details_text.insert("1.0", details)
            self.details_text.configure(state="disabled")
            
        except Exception as e:
            logger.error(f"Error mostrando detalles: {e}")
    
    def apply_selection(self):
        """Aplica la selección al targeting engine."""
        try:
            # Actualizar lista de ataque en el sistema automático
            self.auto_system.auto_config["targeting"]["attack_list"] = self.selected_creatures
            
            # Actualizar lista de ignorados
            self.auto_system.auto_config["targeting"]["ignore_list"] = self.ignored_creatures
            
            # Reconfigurar targeting engine
            if self.targeting_engine:
                self.targeting_engine.configure(self.auto_config["targeting"])
            
            # Guardar configuración
            self.save_configuration()
            
            self.show_success("Selección aplicada correctamente")
            
        except Exception as e:
            self.show_error(f"Error aplicando selección: {e}")
    
    def reload_system(self):
        """Recarga el sistema."""
        try:
            # Reinicializar sistema
            self.auto_system = AutoTargetingSystem()
            
            # Inicializar
            if self.auto_system.initialize():
                # Cargar criaturas
                self.load_available_creatures()
                
                # Limpiar selecciones
                self.clear_selection()
                self.clear_ignored()
                
                # Actualizar estadísticas
                self.update_statistics()
                
                self.show_success("Sistema recargado correctamente")
            else:
                self.show_error("Error recargando sistema")
                
        except Exception as e:
            self.show_error(f"Error recargando sistema: {e}")
    
    def save_configuration(self):
        """Guarda la configuración actual."""
        try:
            # Guardar configuración del sistema automático
            self.auto_system.save_configuration()
            
            # Exportar a config principal
            self.auto_system.export_to_standard_config()
            
            self.show_success("Configuración guardada correctamente")
            
        except Exception as e:
            self.show_error(f"Error guardando configuración: {e}")
    
    def update_statistics(self):
        """Actualiza las estadísticas en la GUI."""
        try:
            total_creatures = len(self.available_creatures)
            selected_creatures = len(self.selected_creatures)
            ignored_creatures = len(self.ignored_creatures)
            
            # Calcular estadísticas
            if selected_creatures > 0:
                priorities = [self.auto_system.get_creature_priority(c) for c in selected_creatures]
                avg_priority = sum(priorities) / len(priorities)
                high_priority = len([p for p in priorities if p >= 200])
            else:
                avg_priority = 0
                high_priority = 0
            
            if self.available_creatures > 0:
                mage_count = 0
                ranged_count = 0
                for creature_name in self.available_creatures:
                    visual_info = self.auto_system.visual_system.get_visual_targeting_info(creature_name)
                    if visual_info:
                        indicators = visual_info.visual_indicators
                        if indicators.get('is_mage', False):
                            mage_count += 1
                        if indicators.get('is_ranged', False):
                            ranged_count += 1
                
                avg_priority = sum([self.auto_system.get_creature_priority(c) for c in self.available_creatures]) / len(self.available_creatures)
            
            # Actualizar labels
            self.stats_labels["total_creatures"].configure(text=f"Total Criaturas: {total_creatures}")
            self.stats_labels["selected_creatures"].configure(text=f"Seleccionados: {selected_creatures}")
            self.stats_labels["ignored_creatures"].configure(text=f"Ignorados: {ignored_creatures}")
            self.stats_labels["avg_priority"].configure(text=f"Prioridad Promedio: {avg_priority:.1f}")
            self.stats_labels["high_priority"].configure(text=f"Alta Prioridad: {high_priority}")
            self.stats_labels["mage_count"].configure(text=f"Magos: {mage_count}")
            self.stats_labels["ranged_count"].configure(text=f"Ranged: {ranged_count}")
            
        except Exception as e:
            logger.error(f"Error actualizando estadísticas: {e}")
    
    def show_success(self, message: str):
        """Muestra un mensaje de éxito."""
        messagebox.showinfo("Éxito", message)
    
    def show_error(self, title_or_message: str, message: str = None):
        """Muestra un mensaje de error."""
        if message is None:
            # Solo se pasó un argumento, es el mensaje
            messagebox.showerror("Error", title_or_message)
        else:
            # Se pasaron dos argumentos, título y mensaje
            messagebox.showerror(title_or_message, message)
    
    def show_statistics(self):
        """Muestra estadísticas completas."""
        try:
            stats = f"📊 ESTADÍSTICAS COMPLETAS DEL SISTEMA\n\n"
            stats += f"👾 Criaturas con información visual: {len(self.auto_system.visual_database)}\n"
            stats += f"💀 Cuerpos muertos identificados: {len(self.auto_system.corpse_templates)}\n"
            stats += f"💰 Templates de loot: {len(self.auto_system.loot_templates)}\n"
            stats += f"🎯 Sistema de targeting visual: Activo\n\n"
            
            # Estadísticas por tipo
            threat_counts = {}
            type_counts = {'mage': 0, 'ranged': 0, 'healer': 0, 'melee': 0}
            
            for info in self.auto_system.visual_database.values():
                indicators = info.visual_indicators
                
                # Contar por amenaza
                threat = indicators.get('threat_level', 'unknown')
                threat_counts[threat] = threat_counts.get(threat, 0) + 1
                
                # Contar por tipo
                if indicators.get('is_mage', False):
                    type_counts['mage'] += 1
                if indicators.get('is_ranged', False):
                    type_counts['ranged'] += 1
                if indicators.get('is_healer', False):
                    type_counts['healer'] += 1
                if not (indicators.get('is_mage', False) or indicators.get('is_ranged', False) or indicators.get('is_healer', False)):
                    type_counts['melee'] += 1
            
            stats += f"📈 DISTRIBUCIÓN POR AMENAZA:\n"
            for threat, count in sorted(threat_counts.items()):
                stats += f"  {threat.title()}: {count}\n"
            
            stats += f"\n📈 DISTRIBUCIÓN POR TIPO:\n"
            for type_name, count in type_counts.items():
                stats += f"  {type_name.title()}: {count}\n"
            
            # Estadísticas de selección
            stats += f"\n🎯 ESTADÍSTICAS DE SELECCIÓN:\n"
            stats += f"  Criaturas seleccionadas: {len(self.selected_creatures)}\n"
            stats += f"  Criaturas ignoradas: {len(self.ignored_creatures)}\n"
            stats += f"  Criaturas disponibles: {len(self.available_creatures)}\n"
            
            # Mostrar en un messagebox
            messagebox.showinfo("Estadísticas del Sistema", stats)
            
        except Exception as e:
            self.show_error(f"Error mostrando estadísticas: {e}")
    
    def get_selected_creatures(self) -> List[str]:
        """Obtiene la lista de criaturas seleccionadas."""
        return self.selected_creatures.copy()
    
    def get_ignored_creatures(self) -> List[str]:
        """Obtiene la lista de criaturas ignoradas."""
        return self.ignored_creatures.copy()

def main():
    """Función principal para probar la GUI de selección."""
    # Configurar tema
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Crear ventana de prueba
    root = ctk.CTk()
    root.title("Targeting V2 - Selector de Criaturas")
    root.geometry("1200x800")
    
    # Crear GUI de selección
    # Nota: Esto debería integrarse con el targeting engine V2 existente
    from targeting_engine_v2 import TargetingEngineV2
    from config import Config
    
    # Crear un targeting engine de prueba
    targeting_engine = TargetingEngineV2()
    
    # Crear GUI de selección
    selector_gui = TargetingSelectorGUI(root, targeting_engine)
    
    print("=== GUI DE SELECCIÓN DE TARGETING V2 ===")
    print("[OK] Sistema de selección de criaturas funcionando")
    print("[OK] Explora las pestañas para seleccionar qué atacar")
    print("[OK] Toda la información visual está disponible")
    print("[OK] La configuración se guarda automáticamente")
    
    # Iniciar la GUI
    root.mainloop()

if __name__ == "__main__":
    main()
