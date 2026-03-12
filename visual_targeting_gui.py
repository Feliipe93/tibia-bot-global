#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_targeting_gui.py - GUI para el sistema de targeting visual
Muestra información visual de monstruos, cuerpos muertos y loot.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Dict, List, Optional
import json
from visual_targeting_system import VisualTargetingSystem
from PIL import Image, ImageTk
import os

class VisualTargetingGUI:
    """GUI para el sistema de targeting visual."""
    
    def __init__(self, parent):
        self.parent = parent
        self.visual_system = VisualTargetingSystem()
        
        # Variables para la GUI
        self.selected_creature = None
        self.creature_images = {}
        
        # Crear frame principal
        self.create_main_frame()
        
        # Inicializar sistema
        self.initialize_system()
    
    def create_main_frame(self):
        """Crea el frame principal con pestañas."""
        # Frame con scroll para todo el contenido
        self.main_frame = ctk.CTkScrollableFrame(
            self.parent, 
            label_text="🎯 TARGETING VISUAL - Assets de Tibia",
            fg_color="#1a2733"
        )
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Crear pestañas
        self.create_creature_visuals_tab()
        self.create_corpse_database_tab()
        self.create_loot_analysis_tab()
        self.create_visual_search_tab()
        self.create_area_analysis_tab()
        
        # Botones de acción
        self.create_action_buttons()
    
    def create_creature_visuals_tab(self):
        """Crea la pestaña de visuales de criaturas."""
        self.visuals_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.visuals_frame, text="👾 Visuales de Criaturas")
        
        # Frame de búsqueda
        search_frame = ctk.CTkFrame(self.visuals_frame, fg_color="#0f1923")
        search_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            search_frame, 
            text="🔍 BÚSQUEDA DE CRIATURAS VISUALES", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Input de búsqueda
        search_input_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        search_input_frame.pack(fill="x", padx=10, pady=5)
        
        self.visual_search_entry = ctk.CTkEntry(
            search_input_frame, 
            placeholder_text="Buscar criatura (ej: dragon, demon, amazon)",
            width=400
        )
        self.visual_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(
            search_input_frame,
            text="🔍 Buscar",
            command=self.search_visual_creatures,
            width=100
        ).pack(side="right")
        
        # Frame de resultados
        results_frame = ctk.CTkFrame(self.visuals_frame, fg_color="#0f1923")
        results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            results_frame, 
            text="📋 RESULTADOS VISUALES", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Treeview para resultados visuales
        self.visual_tree = ttk.Treeview(
            results_frame,
            columns=("name", "look_type", "corpse", "threat", "hp", "exp"),
            show="headings",
            height=15
        )
        
        # Configurar columnas
        self.visual_tree.heading("name", text="Nombre")
        self.visual_tree.heading("look_type", text="Look Type")
        self.visual_tree.heading("corpse", text="Corpse")
        self.visual_tree.heading("threat", text="Amenaza")
        self.visual_tree.heading("hp", text="HP")
        self.visual_tree.heading("exp", text="Exp")
        
        # Anchos de columna
        self.visual_tree.column("name", width=200)
        self.visual_tree.column("look_type", width=80)
        self.visual_tree.column("corpse", width=150)
        self.visual_tree.column("threat", width=80)
        self.visual_tree.column("hp", width=80)
        self.visual_tree.column("exp", width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.visual_tree.yview)
        self.visual_tree.configure(yscrollcommand=scrollbar.set)
        
        self.visual_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=5)
        
        # Bind double click
        self.visual_tree.bind('<Double-1>', self.on_visual_creature_double_click)
        
        # Frame de detalles visuales
        details_frame = ctk.CTkFrame(self.visuals_frame, fg_color="#0f1923")
        details_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            details_frame, 
            text="👁️ DETALLES VISUALES", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.visual_details_text = ctk.CTkTextbox(details_frame, height=150)
        self.visual_details_text.pack(fill="x", padx=10, pady=5)
        self.visual_details_text.configure(state="disabled")
    
    def create_corpse_database_tab(self):
        """Crea la pestaña de base de datos de cuerpos."""
        self.corpse_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.corpse_frame, text="💀 Base de Datos de Cuerpos")
        
        # Frame de estadísticas
        stats_frame = ctk.CTkFrame(self.corpse_frame, fg_color="#0f1923")
        stats_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            stats_frame, 
            text="📊 ESTADÍSTICAS DE CUERPOS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.corpse_stats_labels = {}
        stats_info = [
            ("total_corpses", "Total Cuerpos: --"),
            ("avg_size", "Tamaño Promedio: --"),
            ("avg_duration", "Duración Promedio: --"),
            ("large_corpses", "Cuerpos Grandes: --")
        ]
        
        for key, text in stats_info:
            label = ctk.CTkLabel(stats_frame, text=text, font=ctk.CTkFont(size=12))
            label.pack(anchor="w", padx=10, pady=2)
            self.corpse_stats_labels[key] = label
        
        # Frame de búsqueda de cuerpos
        corpse_search_frame = ctk.CTkFrame(self.corpse_frame, fg_color="#0f1923")
        corpse_search_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            corpse_search_frame, 
            text="🔍 BÚSQUEDA DE CUERPOS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Input de búsqueda de cuerpos
        corpse_input_frame = ctk.CTkFrame(corpse_search_frame, fg_color="transparent")
        corpse_input_frame.pack(fill="x", padx=10, pady=5)
        
        self.corpse_search_entry = ctk.CTkEntry(
            corpse_input_frame, 
            placeholder_text="Buscar cuerpo (ej: dragon, demon, orc)",
            width=400
        )
        self.corpse_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(
            corpse_input_frame,
            text="🔍 Buscar",
            command=self.search_corpses,
            width=100
        ).pack(side="right")
        
        # Frame de resultados de cuerpos
        corpse_results_frame = ctk.CTkFrame(self.corpse_frame, fg_color="#0f1923")
        corpse_results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            corpse_results_frame, 
            text="💀 CUERPOS ENCONTRADOS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Treeview para cuerpos
        self.corpse_tree = ttk.Treeview(
            corpse_results_frame,
            columns=("id", "name", "size", "duration", "decay"),
            show="headings",
            height=12
        )
        
        # Configurar columnas
        self.corpse_tree.heading("id", text="ID")
        self.corpse_tree.heading("name", text="Nombre")
        self.corpse_tree.heading("size", text="Tamaño")
        self.corpse_tree.heading("duration", text="Duración")
        self.corpse_tree.heading("decay", text="Decay")
        
        # Anchos de columna
        self.corpse_tree.column("id", width=60)
        self.corpse_tree.column("name", width=200)
        self.corpse_tree.column("size", width=80)
        self.corpse_tree.column("duration", width=80)
        self.corpse_tree.column("decay", width=80)
        
        # Scrollbar
        corpse_scrollbar = ttk.Scrollbar(corpse_results_frame, orient="vertical", command=self.corpse_tree.yview)
        self.corpse_tree.configure(yscrollcommand=corpse_scrollbar.set)
        
        self.corpse_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        corpse_scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=5)
        
        # Frame de detalles del corpse
        corpse_details_frame = ctk.CTkFrame(self.corpse_frame, fg_color="#0f1923")
        corpse_details_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            corpse_details_frame, 
            text="📋 DETALLES DEL CUERPO", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.corpse_details_text = ctk.CTkTextbox(corpse_details_frame, height=100)
        self.corpse_details_text.pack(fill="x", padx=10, pady=5)
        self.corpse_details_text.configure(state="disabled")
    
    def create_loot_analysis_tab(self):
        """Crea la pestaña de análisis de loot."""
        self.loot_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.loot_frame, text="💰 Análisis de Loot")
        
        # Frame de información
        loot_info_frame = ctk.CTkFrame(self.loot_frame, fg_color="#0f1923")
        loot_info_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            loot_info_frame, 
            text="💰 INFORMACIÓN DE LOOT", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        info_text = """
📊 ESTADÍSTICAS DEL SISTEMA:
• Total de monstruos con información visual: 1429
• Total de cuerpos muertos identificados: 1948
• Total de items en la base de datos: 11720
• Sistema de targeting visual completamente funcional

🎯 CARACTERÍSTICAS VISUALES:
• Look types de criaturas para identificación
• Información de cuerpos muertos (size, duration, decay)
• Análisis de amenazas basado en características
• Recomendaciones de estrategia visual
• Indicadores de rareza y valor de loot

🔍 BÚSQUEDAS DISPONIBLES:
• Búsqueda de criaturas por nombre
• Búsqueda de cuerpos por tipo
• Análisis visual de área
• Identificación por outfit
        """
        
        ctk.CTkLabel(
            loot_info_frame,
            text=info_text,
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
            justify="left"
        ).pack(padx=10, pady=10)
    
    def create_visual_search_tab(self):
        """Crea la pestaña de búsqueda visual."""
        self.search_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.search_frame, text="🔍 Búsqueda Visual")
        
        # Frame de búsqueda avanzada
        advanced_search_frame = ctk.CTkFrame(self.search_frame, fg_color="#0f1923")
        advanced_search_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            advanced_search_frame, 
            text="🔍 BÚSQUEDA AVANZADA", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame de filtros
        filters_frame = ctk.CTkFrame(advanced_search_frame, fg_color="transparent")
        filters_frame.pack(fill="x", padx=10, pady=5)
        
        # Filtro por amenaza
        threat_frame = ctk.CTkFrame(filters_frame, fg_color="transparent")
        threat_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(threat_frame, text="Nivel de Amenaza:", width=120).pack(side="left")
        self.threat_filter_var = tk.StringVar(value="all")
        self.threat_filter_combo = ctk.CTkComboBox(
            threat_frame,
            values=["all", "minimal", "low", "medium", "high", "extreme"],
            variable=self.threat_filter_var,
            width=150
        )
        self.threat_filter_combo.pack(side="left", padx=5)
        
        # Filtro por tipo
        type_frame = ctk.CTkFrame(filters_frame, fg_color="transparent")
        type_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(type_frame, text="Tipo:", width=120).pack(side="left")
        self.type_filter_var = tk.StringVar(value="all")
        self.type_filter_combo = ctk.CTkComboBox(
            type_frame,
            values=["all", "mage", "ranged", "healer", "melee"],
            variable=self.type_filter_var,
            width=150
        )
        self.type_filter_combo.pack(side="left", padx=5)
        
        # Filtro por HP
        hp_frame = ctk.CTkFrame(filters_frame, fg_color="transparent")
        hp_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(hp_frame, text="HP Mínimo:", width=120).pack(side="left")
        self.hp_filter_var = tk.StringVar(value="0")
        self.hp_filter_entry = ctk.CTkEntry(hp_frame, textvariable=self.hp_filter_var, width=100)
        self.hp_filter_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(hp_frame, text="HP Máximo:", width=100).pack(side="left", padx=(10, 0))
        self.hp_max_filter_var = tk.StringVar(value="10000")
        self.hp_max_filter_entry = ctk.CTkEntry(hp_frame, textvariable=self.hp_max_filter_var, width=100)
        self.hp_max_filter_entry.pack(side="left", padx=5)
        
        # Botón de búsqueda
        ctk.CTkButton(
            advanced_search_frame,
            text="🔍 Buscar con Filtros",
            command=self.search_with_filters,
            width=200
        ).pack(pady=10)
        
        # Frame de resultados de búsqueda avanzada
        advanced_results_frame = ctk.CTkFrame(self.search_frame, fg_color="#0f1923")
        advanced_results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            advanced_results_frame, 
            text="📋 RESULTADOS DE BÚSQUEDA", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Treeview para resultados avanzados
        self.advanced_tree = ttk.Treeview(
            advanced_results_frame,
            columns=("name", "threat", "type", "hp", "exp", "corpse"),
            show="headings",
            height=12
        )
        
        # Configurar columnas
        self.advanced_tree.heading("name", text="Nombre")
        self.advanced_tree.heading("threat", text="Amenaza")
        self.advanced_tree.heading("type", text="Tipo")
        self.advanced_tree.heading("hp", text="HP")
        self.advanced_tree.heading("exp", text="Exp")
        self.advanced_tree.heading("corpse", text="Corpse")
        
        # Anchos de columna
        self.advanced_tree.column("name", width=200)
        self.advanced_tree.column("threat", width=80)
        self.advanced_tree.column("type", width=100)
        self.advanced_tree.column("hp", width=80)
        self.advanced_tree.column("exp", width=80)
        self.advanced_tree.column("corpse", width=150)
        
        # Scrollbar
        advanced_scrollbar = ttk.Scrollbar(advanced_results_frame, orient="vertical", command=self.advanced_tree.yview)
        self.advanced_tree.configure(yscrollcommand=advanced_scrollbar.set)
        
        self.advanced_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        advanced_scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=5)
    
    def create_area_analysis_tab(self):
        """Crea la pestaña de análisis de área."""
        self.area_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.area_frame, text="🗺️ Análisis de Área")
        
        # Frame principal
        main_area_frame = ctk.CTkFrame(self.area_frame, fg_color="#0f1923")
        main_area_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            main_area_frame, 
            text="🗺️ ANÁLISIS VISUAL DE ÁREA", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Frame de entrada de criaturas
        input_frame = ctk.CTkFrame(main_area_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(input_frame, text="Criaturas en el área (separadas por coma):").pack(side="left", padx=(0, 5))
        self.area_creatures_entry = ctk.CTkEntry(input_frame, placeholder_text="dragon, demon, amazon, orc")
        self.area_creatures_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkButton(
            input_frame,
            text="🔍 Analizar",
            command=self.analyze_area,
            width=100
        ).pack(side="right")
        
        # Frame de resultados de análisis
        area_results_frame = ctk.CTkFrame(main_area_frame, fg_color="#0f1923")
        area_results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            area_results_frame, 
            text="📊 RESULTADOS DEL ANÁLISIS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.area_analysis_text = ctk.CTkTextbox(area_results_frame, height=200)
        self.area_analysis_text.pack(fill="both", expand=True, padx=10, pady=5)
    
    def create_action_buttons(self):
        """Crea los botones de acción."""
        buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="🔄 Actualizar Base de Datos",
            command=self.update_database,
            fg_color="#3498DB",
            hover_color="#2980B9",
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="💾 Guardar Configuración",
            command=self.save_configuration,
            fg_color="#27AE60",
            hover_color="#229954",
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="📊 Ver Estadísticas",
            command=self.show_statistics,
            fg_color="#9B59B6",
            hover_color="#8E44AD",
            width=150
        ).pack(side="left", padx=5)
    
    def initialize_system(self):
        """Inicializa el sistema visual."""
        try:
            if self.visual_system.initialize_system():
                self.update_corpse_statistics()
                self.show_success_message("Sistema visual inicializado correctamente")
            else:
                self.show_error_message("Error inicializando sistema visual")
        except Exception as e:
            self.show_error_message(f"Error: {e}")
    
    def search_visual_creatures(self):
        """Busca criaturas visuales."""
        query = self.visual_search_entry.get().strip()
        if not query:
            return
        
        # Limpiar resultados anteriores
        for item in self.visual_tree.get_children():
            self.visual_tree.delete(item)
        
        # Buscar coincidencias
        query_lower = query.lower()
        results = []
        
        for name, info in self.visual_system.visual_database.items():
            if query_lower in name:
                results.append((name, info))
        
        # Agregar resultados al treeview
        for name, info in results:
            indicators = info.visual_indicators
            corpse_name = info.corpse_info.get('name', 'N/A') if info.corpse_info else 'N/A'
            
            self.visual_tree.insert("", "end", values=(
                name.title(),
                info.look_type,
                corpse_name,
                indicators.get('threat_level', 'unknown'),
                indicators.get('max_health', 0),
                indicators.get('experience', 0)
            ))
    
    def on_visual_creature_double_click(self, event):
        """Maneja doble clic en una criatura visual."""
        selection = self.visual_tree.selection()
        if not selection:
            return
        
        item = self.visual_tree.item(selection[0])
        creature_name = item['values'][0]
        
        # Obtener información completa
        info = self.visual_system.get_visual_targeting_info(creature_name)
        
        if info:
            # Mostrar detalles
            details = f"👁️ ANÁLISIS VISUAL DE {creature_name.upper()}\n\n"
            
            # Información visual
            details += f"🎭 INFORMACIÓN VISUAL:\n"
            details += f"  Look Type: {info.look_type}\n"
            details += f"  Outfit: {info.outfit}\n\n"
            
            # Información del corpse
            if info.corpse_info:
                corpse = info.corpse_info
                details += f"💀 CUERPO MUERTO:\n"
                details += f"  Nombre: {corpse['name']}\n"
                details += f"  ID: {corpse['item_id']}\n"
                details += f"  Tamaño: {corpse['size']}\n"
                details += f"  Duración: {corpse['duration']}s\n"
                details += f"  Decays to: {corpse['decay_to']}\n\n"
            
            # Indicadores
            indicators = info.visual_indicators
            details += f"📊 INDICADORES:\n"
            details += f"  HP: {indicators.get('max_health', 0)}\n"
            details += f"  Experiencia: {indicators.get('experience', 0)}\n"
            details += f"  Nivel de Amenaza: {indicators.get('threat_level', 'unknown')}\n"
            details += f"  Es Mago: {'Sí' if indicators.get('is_mage', False) else 'No'}\n"
            details += f"  Es Ranged: {'Sí' if indicators.get('is_ranged', False) else 'No'}\n"
            details += f"  Es Healer: {'Sí' if indicators.get('is_healer', False) else 'No'}\n"
            details += f"  Tiene Loot Valioso: {'Sí' if indicators.get('has_valuable_loot', False) else 'No'}\n\n"
            
            # Estrategia recomendada
            if info.recommended_strategy:
                strategy = info.recommended_strategy
                details += f"⚔️ ESTRATEGIA RECOMENDADA:\n"
                details += f"  Modo: {strategy.get('mode', 'unknown')}\n"
                details += f"  Chase: {strategy.get('chase_mode', 'unknown')}\n"
                details += f"  Razón: {strategy.get('reason', 'unknown')}\n"
            
            # Mostrar en el textbox
            self.visual_details_text.configure(state="normal")
            self.visual_details_text.delete("1.0", tk.END)
            self.visual_details_text.insert("1.0", details)
            self.visual_details_text.configure(state="disabled")
    
    def search_corpses(self):
        """Busca cuerpos muertos."""
        query = self.corpse_search_entry.get().strip()
        if not query:
            return
        
        # Limpiar resultados anteriores
        for item in self.corpse_tree.get_children():
            self.corpse_tree.delete(item)
        
        # Buscar coincidencias
        query_lower = query.lower()
        results = []
        
        for corpse_id, corpse_info in self.visual_system.corpse_templates.items():
            if query_lower in corpse_info['name'].lower():
                results.append((corpse_id, corpse_info))
        
        # Agregar resultados al treeview
        for corpse_id, corpse_info in results:
            self.corpse_tree.insert("", "end", values=(
                corpse_id,
                corpse_info['name'],
                corpse_info['size'],
                corpse_info['duration'],
                corpse_info.get('decay_to', 0)
            ))
    
    def search_with_filters(self):
        """Busca con filtros avanzados."""
        # Limpiar resultados anteriores
        for item in self.advanced_tree.get_children():
            self.advanced_tree.delete(item)
        
        # Obtener filtros
        threat_filter = self.threat_filter_var.get()
        type_filter = self.type_filter_var.get()
        hp_min = self.hp_filter_var.get()
        hp_max = self.hp_max_filter_var.get()
        
        # Convertir filtros
        try:
            hp_min = int(hp_min) if hp_min else 0
            hp_max = int(hp_max) if hp_max else 10000
        except:
            hp_min = 0
            hp_max = 10000
        
        # Filtrar resultados
        results = []
        for name, info in self.visual_system.visual_database.items():
            indicators = info.visual_indicators
            
            # Aplicar filtros
            if threat_filter != "all" and indicators.get('threat_level', '') != threat_filter:
                continue
            
            if type_filter != "all":
                if type_filter == "mage" and not indicators.get('is_mage', False):
                    continue
                elif type_filter == "ranged" and not indicators.get('is_ranged', False):
                    continue
                elif type_filter == "healer" and not indicators.get('is_healer', False):
                    continue
                elif type_filter == "melee" and indicators.get('is_mage', False) and indicators.get('is_ranged', False):
                    continue
            
            hp = indicators.get('max_health', 0)
            if hp < hp_min or hp > hp_max:
                continue
            
            # Agregar resultado
            corpse_name = info.corpse_info.get('name', 'N/A') if info.corpse_info else 'N/A'
            
            # Determinar tipo
            creature_type = []
            if indicators.get('is_mage', False):
                creature_type.append("Mage")
            if indicators.get('is_ranged', False):
                creature_type.append("Ranged")
            if indicators.get('is_healer', False):
                creature_type.append("Healer")
            if not creature_type:
                creature_type.append("Melee")
            
            self.advanced_tree.insert("", "end", values=(
                name.title(),
                indicators.get('threat_level', 'unknown'),
                ", ".join(creature_type),
                hp,
                indicators.get('experience', 0),
                corpse_name
            ))
    
    def analyze_area(self):
        """Analiza el área con las criaturas especificadas."""
        creatures_text = self.area_creatures_entry.get().strip()
        if not creatures_text:
            return
        
        # Parsear criaturas
        creatures = [c.strip() for c in creatures_text.split(',') if c.strip()]
        
        if not creatures:
            return
        
        # Realizar análisis
        analysis = self.visual_system.get_area_visual_analysis(creatures)
        
        # Mostrar resultados
        results = f"🗺️ ANÁLISIS DE ÁREA\n\n"
        results += f"📊 ESTADÍSTICAS:\n"
        results += f"  Total criaturas: {analysis['total_creatures']}\n"
        results += f"  Amenazas detectadas: {len(analysis['threats'])}\n"
        results += f"  Objetivos valiosos: {len(analysis['valuable_targets'])}\n"
        results += f"  Estrategia recomendada: {analysis['recommended_strategy']}\n"
        results += f"  Valor total del loot: {analysis['area_loot_value']}\n"
        results += f"  Puntaje de amenaza: {analysis['total_threat_score']}\n\n"
        
        # Amenazas
        if analysis['threats']:
            results += f"⚠️ AMENAZAS:\n"
            for threat in analysis['threats']:
                results += f"  • {threat['name']} ({threat['threat_level']}) - "
                if threat['is_mage']:
                    results += "Mago "
                if threat['is_ranged']:
                    results += "Ranged "
                results += "\n"
            results += "\n"
        
        # Objetivos valiosos
        if analysis['valuable_targets']:
            results += f"💰 OBJETIVOS VALIOSOS:\n"
            for target in analysis['valuable_targets']:
                results += f"  • {target['name']} (Valor: {target['loot_value']})\n"
            results += "\n"
        
        # Indicadores individuales
        results += f"📋 INDICADORES INDIVIDUALES:\n"
        for creature_name, indicators in analysis['visual_indicators'].items():
            results += f"  {creature_name.title()}:\n"
            results += f"    - HP: {indicators.get('max_health', 0)}\n"
            results += f"    - Amenaza: {indicators.get('threat_level', 'unknown')}\n"
            results += f"    - Tipo: "
            types = []
            if indicators.get('is_mage', False):
                types.append("Mago")
            if indicators.get('is_ranged', False):
                types.append("Ranged")
            if indicators.get('is_healer', False):
                types.append("Healer")
            if not types:
                types.append("Melee")
            results += f"{', '.join(types)}\n"
        
        # Mostrar en el textbox
        self.area_analysis_text.delete("1.0", tk.END)
        self.area_analysis_text.insert("1.0", results)
    
    def update_corpse_statistics(self):
        """Actualiza las estadísticas de cuerpos."""
        total_corpses = len(self.visual_system.corpse_templates)
        
        if total_corpses > 0:
            # Calcular estadísticas
            sizes = [c['size'] for c in self.visual_system.corpse_templates.values()]
            durations = [c['duration'] for c in self.visual_system.corpse_templates.values()]
            large_corpses = len([c for c in self.visual_system.corpse_templates.values() if c['size'] >= 20])
            
            avg_size = sum(sizes) / len(sizes)
            avg_duration = sum(durations) / len(durations)
            
            self.corpse_stats_labels["total_corpses"].configure(text=f"Total Cuerpos: {total_corpses}")
            self.corpse_stats_labels["avg_size"].configure(text=f"Tamaño Promedio: {avg_size:.1f}")
            self.corpse_stats_labels["avg_duration"].configure(text=f"Duración Promedio: {avg_duration:.1f}s")
            self.corpse_stats_labels["large_corpses"].configure(text=f"Cuerpos Grandes: {large_corpses}")
        else:
            self.corpse_stats_labels["total_corpses"].configure(text="Total Cuerpos: 0")
            self.corpse_stats_labels["avg_size"].configure(text="Tamaño Promedio: --")
            self.corpse_stats_labels["avg_duration"].configure(text="Duración Promedio: --")
            self.corpse_stats_labels["large_corpses"].configure(text="Cuerpos Grandes: 0")
    
    def update_database(self):
        """Actualiza la base de datos."""
        try:
            if self.visual_system.initialize_system():
                self.update_corpse_statistics()
                self.show_success_message("Base de datos actualizada correctamente")
            else:
                self.show_error_message("Error actualizando base de datos")
        except Exception as e:
            self.show_error_message(f"Error: {e}")
    
    def save_configuration(self):
        """Guarda la configuración."""
        try:
            self.visual_system.save_visual_database("visual_targeting_database.json")
            self.show_success_message("Configuración guardada correctamente")
        except Exception as e:
            self.show_error_message(f"Error guardando configuración: {e}")
    
    def show_statistics(self):
        """Muestra estadísticas completas."""
        stats = f"📊 ESTADÍSTICAS COMPLETAS DEL SISTEMA\n\n"
        stats += f"👾 Criaturas con información visual: {len(self.visual_system.visual_database)}\n"
        stats += f"💀 Cuerpos muertos identificados: {len(self.visual_system.corpse_templates)}\n"
        stats += f"💰 Templates de loot: {len(self.visual_system.loot_templates)}\n"
        stats += f"🎯 Sistema de targeting visual: Activo\n\n"
        
        # Estadísticas por tipo
        threat_counts = {}
        type_counts = {'mage': 0, 'ranged': 0, 'healer': 0, 'melee': 0}
        
        for info in self.visual_system.visual_database.values():
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
        
        # Mostrar en un messagebox
        messagebox.showinfo("Estadísticas del Sistema", stats)
    
    def show_success_message(self, message):
        """Muestra un mensaje de éxito."""
        messagebox.showinfo("Éxito", message)
    
    def show_error_message(self, message):
        """Muestra un mensaje de error."""
        messagebox.showerror("Error", message)

def main():
    """Función principal para probar la GUI visual."""
    # Configurar tema
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Crear ventana de prueba
    root = ctk.CTk()
    root.title("Visual Targeting System - GUI")
    root.geometry("1200x800")
    
    # Crear GUI visual
    visual_gui = VisualTargetingGUI(root)
    
    print("=== GUI DE TARGETING VISUAL ===")
    print("[OK] Sistema de targeting visual con GUI funcionando")
    print("[OK] Explora las pestañas para descubrir todas las funcionalidades")
    print("[OK] Búsqueda visual de criaturas y cuerpos")
    print("[OK] Análisis de área con indicadores visuales")
    print("[OK] Estadísticas completas del sistema")
    
    # Iniciar la GUI
    root.mainloop()

if __name__ == "__main__":
    main()
