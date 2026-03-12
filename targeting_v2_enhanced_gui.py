#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeting_v2_enhanced_gui.py - GUI mejorada para el Targeting V2 con inteligencia artificial
Muestra información detallada de criaturas y análisis inteligente.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Dict, List, Optional
import json
from targeting_engine_v2 import TargetingEngineV2
from intelligent_targeting import IntelligentTargeting
import threading

class TargetingV2EnhancedGUI:
    """GUI mejorada para el targeting V2 con inteligencia artificial."""
    
    def __init__(self, parent, config, targeting_engine_v2):
        self.parent = parent
        self.config = config
        self.engine = targeting_engine_v2
        
        # Variables para la GUI
        self.selected_creature = None
        self.creature_search_results = []
        
        # Crear frame principal
        self.create_main_frame()
        
        # Inicializar datos
        self.load_initial_data()
    
    def create_main_frame(self):
        """Crea el frame principal con pestañas."""
        # Frame con scroll para todo el contenido
        self.main_frame = ctk.CTkScrollableFrame(
            self.parent, 
            label_text="🎯 TARGETING V2 - INTELIGENCIA ARTIFICIAL",
            fg_color="#1a2733"
        )
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Crear pestañas
        self.create_status_tab()
        self.create_creature_database_tab()
        self.create_intelligent_profiles_tab()
        self.create_area_analysis_tab()
        self.create_manual_config_tab()
        
        # Botones de acción
        self.create_action_buttons()
    
    def create_status_tab(self):
        """Crea la pestaña de estado en tiempo real."""
        self.status_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.status_frame, text="📊 Estado en Tiempo Real")
        
        # Frame de estado del target
        target_frame = ctk.CTkFrame(self.status_frame, fg_color="#0f1923")
        target_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            target_frame, 
            text="🎯 TARGET ACTUAL", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Información del target
        self.target_info_frame = ctk.CTkFrame(target_frame, fg_color="transparent")
        self.target_info_frame.pack(fill="x", padx=10, pady=5)
        
        # Labels dinámicos para información del target
        self.target_labels = {}
        target_info_fields = [
            ("name", "Nombre: --"),
            ("health", "HP: --"),
            ("experience", "Experiencia: --"),
            ("class", "Clase: --"),
            ("difficulty", "Dificultad: --"),
            ("strategy", "Estrategia: --"),
            ("weaknesses", "Debilidades: --"),
            ("immunities", "Inmunidades: --")
        ]
        
        for field, default_text in target_info_fields:
            frame = ctk.CTkFrame(self.target_info_frame, fg_color="transparent")
            frame.pack(fill="x", pady=2)
            
            label = ctk.CTkLabel(frame, text=default_text, font=ctk.CTkFont(size=12))
            label.pack(anchor="w")
            self.target_labels[field] = label
        
        # Frame de estado general
        general_frame = ctk.CTkFrame(self.status_frame, fg_color="#0f1923")
        general_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            general_frame, 
            text="📈 ESTADO GENERAL", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Indicadores generales
        self.general_info_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        self.general_info_frame.pack(fill="x", padx=10, pady=5)
        
        self.general_labels = {}
        general_info_fields = [
            ("state", "Estado: --"),
            ("monsters", "Criaturas: --"),
            ("threat_level", "Nivel Amenaza: --"),
            ("priority_target", "Target Prioritario: --"),
            ("recommended_spells", "Spells Recomendados: --"),
            ("database_status", "Base de Datos: --")
        ]
        
        for field, default_text in general_info_fields:
            frame = ctk.CTkFrame(self.general_info_frame, fg_color="transparent")
            frame.pack(fill="x", pady=2)
            
            label = ctk.CTkLabel(frame, text=default_text, font=ctk.CTkFont(size=12))
            label.pack(anchor="w")
            self.general_labels[field] = label
        
        # Botón de actualización
        ctk.CTkButton(
            general_frame,
            text="🔄 Actualizar Estado",
            command=self.update_status_display,
            width=200
        ).pack(pady=10)
    
    def create_creature_database_tab(self):
        """Crea la pestaña de base de datos de criaturas."""
        self.db_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.db_frame, text="📚 Base de Datos")
        
        # Frame de búsqueda
        search_frame = ctk.CTkFrame(self.db_frame, fg_color="#0f1923")
        search_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            search_frame, 
            text="🔍 BÚSQUEDA DE CRIATURAS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Input de búsqueda
        search_input_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        search_input_frame.pack(fill="x", padx=10, pady=5)
        
        self.search_entry = ctk.CTkEntry(
            search_input_frame, 
            placeholder_text="Buscar criatura (ej: dragon, orc, demon)",
            width=400
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(
            search_input_frame,
            text="🔍 Buscar",
            command=self.search_creatures,
            width=100
        ).pack(side="right")
        
        # Bind Enter key
        self.search_entry.bind('<Return>', lambda e: self.search_creatures())
        
        # Frame de resultados
        results_frame = ctk.CTkFrame(self.db_frame, fg_color="#0f1923")
        results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            results_frame, 
            text="📋 RESULTADOS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Treeview para resultados
        self.results_tree = ttk.Treeview(
            results_frame,
            columns=("name", "health", "exp", "class", "difficulty", "ranged", "mage"),
            show="headings",
            height=15
        )
        
        # Configurar columnas
        self.results_tree.heading("name", text="Nombre")
        self.results_tree.heading("health", text="HP")
        self.results_tree.heading("exp", text="Exp")
        self.results_tree.heading("class", text="Clase")
        self.results_tree.heading("difficulty", text="Dif.")
        self.results_tree.heading("ranged", text="Ranged")
        self.results_tree.heading("mage", text="Mage")
        
        # Anchos de columna
        self.results_tree.column("name", width=200)
        self.results_tree.column("health", width=80)
        self.results_tree.column("exp", width=80)
        self.results_tree.column("class", width=120)
        self.results_tree.column("difficulty", width=50)
        self.results_tree.column("ranged", width=80)
        self.results_tree.column("mage", width=60)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=5)
        
        # Bind double click
        self.results_tree.bind('<Double-1>', self.on_creature_double_click)
        
        # Frame de detalles
        details_frame = ctk.CTkFrame(self.db_frame, fg_color="#0f1923")
        details_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            details_frame, 
            text="📄 DETALLES DE CRIATURA", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.creature_details_text = ctk.CTkTextbox(details_frame, height=150)
        self.creature_details_text.pack(fill="x", padx=10, pady=5)
        self.creature_details_text.configure(state="disabled")
    
    def create_intelligent_profiles_tab(self):
        """Crea la pestaña de perfiles inteligentes."""
        self.profiles_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.profiles_frame, text="🧠 Perfiles Inteligentes")
        
        # Frame de estadísticas
        stats_frame = ctk.CTkFrame(self.profiles_frame, fg_color="#0f1923")
        stats_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            stats_frame, 
            text="📊 ESTADÍSTICAS DE PERFILES", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.stats_labels = {}
        stats_info = [
            ("total_creatures", "Total Criaturas: --"),
            ("auto_profiles", "Perfiles Automáticos: --"),
            ("manual_profiles", "Perfiles Manuales: --"),
            ("database_loaded", "Base de Datos: --")
        ]
        
        for key, text in stats_info:
            label = ctk.CTkLabel(stats_frame, text=text, font=ctk.CTkFont(size=12))
            label.pack(anchor="w", padx=10, pady=2)
            self.stats_labels[key] = label
        
        # Frame de gestión de perfiles
        management_frame = ctk.CTkFrame(self.profiles_frame, fg_color="#0f1923")
        management_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            management_frame, 
            text="⚙️ GESTIÓN DE PERFILES", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Botones de gestión
        buttons_frame = ctk.CTkFrame(management_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="📥 Exportar Perfiles a Config",
            command=self.export_profiles,
            width=200
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="📤 Importar Perfiles Manuales",
            command=self.import_profiles,
            width=200
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="🔄 Recargar Base de Datos",
            command=self.reload_database,
            width=200
        ).pack(side="left", padx=5)
        
        # Frame de información
        info_frame = ctk.CTkFrame(management_frame, fg_color="#27AE60")
        info_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text="ℹ️ INFORMACIÓN:\n"
                 "• Los perfiles automáticos se generan basados en las características reales de las criaturas\n"
                 "• Los perfiles manuales tienen prioridad sobre los automáticos\n"
                 "• Puedes personalizar cualquier perfil manualmente\n"
                 "• El sistema usa lazy loading para cargar solo las criaturas necesarias\n"
                 "• La base de datos completa contiene 1429 criaturas con información detallada",
            font=ctk.CTkFont(size=11),
            text_color="white",
            justify="left"
        ).pack(padx=10, pady=10)
        
        # Etiqueta de estado dinámico
        self.info_label = ctk.CTkLabel(
            info_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="yellow"
        )
        self.info_label.pack(padx=10, pady=(0, 5))
    
    def create_area_analysis_tab(self):
        """Crea la pestaña de análisis de área."""
        self.area_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.area_frame, text="🗺️ Análisis de Área")
        
        # Frame principal
        main_area_frame = ctk.CTkFrame(self.area_frame, fg_color="#0f1923")
        main_area_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            main_area_frame, 
            text="🗺️ ANÁLISIS DE ÁREA EN TIEMPO REAL", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Frame de análisis actual
        current_frame = ctk.CTkFrame(main_area_frame, fg_color="transparent")
        current_frame.pack(fill="x", padx=10, pady=10)
        
        self.area_labels = {}
        area_info = [
            ("total_creatures", "Total Criaturas: --"),
            ("known_creatures", "Criaturas Conocidas: --"),
            ("unknown_creatures", "Criaturas Desconocidas: --"),
            ("threat_level", "Nivel de Amenaza: --"),
            ("priority_target", "Target Prioritario: --"),
            ("recommended_spells", "Spells Recomendados: --")
        ]
        
        for key, text in area_info:
            label = ctk.CTkLabel(current_frame, text=text, font=ctk.CTkFont(size=12))
            label.pack(anchor="w", pady=2)
            self.area_labels[key] = label
        
        # Frame de criaturas peligrosas
        dangerous_frame = ctk.CTkFrame(main_area_frame, fg_color="#E74C3C")
        dangerous_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            dangerous_frame,
            text="⚠️ CRIATURAS PELIGROSAS DETECTADAS",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white"
        ).pack(pady=5)
        
        self.dangerous_text = ctk.CTkTextbox(dangerous_frame, height=100)
        self.dangerous_text.pack(fill="x", padx=10, pady=5)
        self.dangerous_text.configure(state="disabled")
        
        # Botón de actualización
        ctk.CTkButton(
            main_area_frame,
            text="🔄 Actualizar Análisis",
            command=self.update_area_analysis,
            width=200
        ).pack(pady=10)
    
    def create_manual_config_tab(self):
        """Crea la pestaña de configuración manual."""
        self.manual_frame = ctk.CTkFrame(self.notebook)
        self.notebook.add(self.manual_frame, text="⚙️ Configuración Manual")
        
        # Frame de configuración global
        global_frame = ctk.CTkFrame(self.manual_frame, fg_color="#0f1923")
        global_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            global_frame, 
            text="⚙️ CONFIGURACIÓN GLOBAL", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Switches principales
        switches_frame = ctk.CTkFrame(global_frame, fg_color="transparent")
        switches_frame.pack(fill="x", padx=10, pady=5)
        
        self.enabled_var = tk.BooleanVar(value=self.config.get("targeting", {}).get("enabled", False))
        self.enabled_cb = ctk.CTkSwitch(
            switches_frame, 
            text="Targeting habilitado",
            variable=self.enabled_var,
            command=self.on_config_changed
        )
        self.enabled_cb.pack(anchor="w", pady=2)
        
        self.auto_attack_var = tk.BooleanVar(value=self.config.get("targeting", {}).get("auto_attack", True))
        self.auto_attack_cb = ctk.CTkSwitch(
            switches_frame, 
            text="Auto-ataque",
            variable=self.auto_attack_var,
            command=self.on_config_changed
        )
        self.auto_attack_cb.pack(anchor="w", pady=2)
        
        # Frame de lista de criaturas
        list_frame = ctk.CTkFrame(self.manual_frame, fg_color="#0f1923")
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            list_frame, 
            text="👾 LISTA DE CRIATURAS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Input para añadir criaturas
        input_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=5)
        
        self.creature_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Nombre de criatura para atacar",
            width=300
        )
        self.creature_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(
            input_frame,
            text="➕ Añadir",
            command=self.add_creature_to_list,
            width=100
        ).pack(side="right")
        
        # Lista de criaturas
        self.creatures_listbox = tk.Listbox(list_frame, height=10)
        self.creatures_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Botones de lista
        list_buttons_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_buttons_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            list_buttons_frame,
            text="🗑️ Quitar",
            command=self.remove_creature_from_list,
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            list_buttons_frame,
            text="💾 Guardar Config",
            command=self.save_config,
            width=120
        ).pack(side="right", padx=5)
    
    def create_action_buttons(self):
        """Crea los botones de acción principales."""
        buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="🧪 Testear Targeting",
            command=self.test_targeting,
            fg_color="#9B59B6",
            hover_color="#8E44AD",
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="🔄 Actualizar Todo",
            command=self.update_all,
            fg_color="#3498DB",
            hover_color="#2980B9",
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="📊 Ver Diagnóstico",
            command=self.show_diagnosis,
            fg_color="#E67E22",
            hover_color="#D35400",
            width=150
        ).pack(side="left", padx=5)
    
    def load_initial_data(self):
        """Carga los datos iniciales."""
        # Actualizar estadísticas
        self.update_profile_stats()
        
        # Cargar lista de criaturas
        self.load_creatures_list()
        
        # Iniciar actualización automática
        self.start_auto_update()
    
    def update_profile_stats(self):
        """Actualiza las estadísticas de perfiles."""
        db_info = self.engine.get_creature_database_info()
        
        mode = db_info.get('mode', 'unknown')
        if mode == 'lazy_loading':
            status_text = f"Base de Datos: Lazy Loading ({db_info['total_creatures']} criaturas)"
            message = db_info.get('message', '')
        else:
            status_text = f"Base de Datos: Completa ({db_info['total_creatures']} criaturas)"
            message = ''
        
        self.stats_labels["total_creatures"].configure(
            text=f"Total Criaturas: {db_info['total_creatures']}"
        )
        self.stats_labels["auto_profiles"].configure(
            text=f"Perfiles Automáticos: {db_info['auto_profiles']}"
        )
        self.stats_labels["manual_profiles"].configure(
            text=f"Perfiles Manuales: {db_info['manual_profiles']}"
        )
        self.stats_labels["database_loaded"].configure(text=status_text)
        
        # Mostrar mensaje informativo si está en lazy loading
        if message and hasattr(self, 'info_label'):
            self.info_label.configure(text=message)
    
    def load_creatures_list(self):
        """Carga la lista de criaturas desde la configuración."""
        attack_list = self.config.get("targeting", {}).get("attack_list", [])
        
        self.creatures_listbox.delete(0, tk.END)
        for creature in attack_list:
            self.creatures_listbox.insert(tk.END, creature)
    
    def search_creatures(self):
        """Busca criaturas en la base de datos."""
        query = self.search_entry.get().strip()
        if not query:
            return
        
        # Limpiar resultados anteriores
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Buscar criaturas
        results = self.engine.search_creatures(query)
        
        # Agregar resultados al treeview
        for result in results:
            self.results_tree.insert("", "end", values=(
                result['name'],
                result['health'],
                result['experience'],
                result['class'],
                result['difficulty'],
                "Sí" if result['is_ranged'] else "No",
                "Sí" if result['is_mage'] else "No"
            ))
        
        self.creature_search_results = results
    
    def on_creature_double_click(self, event):
        """Maneja doble clic en una criatura de los resultados."""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = self.results_tree.item(selection[0])
        creature_name = item['values'][0]
        
        # Obtener análisis completo
        analysis = self.engine.get_target_analysis(creature_name)
        
        if analysis:
            # Mostrar detalles
            details = f"📋 ANÁLISIS DE {creature_name.upper()}\n\n"
            
            # Información básica
            if analysis['creature_info']:
                info = analysis['creature_info']
                details += f"📊 INFORMACIÓN BÁSICA:\n"
                details += f"  HP: {info.health}\n"
                details += f"  Experiencia: {info.experience}\n"
                details += f"  Clase: {info.class_type}\n"
                details += f"  Dificultad: {info.difficulty}\n"
                details += f"  Ranged: {'Sí' if info.is_ranged else 'No'}\n"
                details += f"  Mage: {'Sí' if info.is_mage else 'No'}\n"
                details += f"  Healer: {'Sí' if info.is_healer else 'No'}\n\n"
            
            # Estrategia
            strategy = analysis['strategy']
            details += f"⚔️ ESTRATEGIA RECOMENDADA:\n"
            details += f"  Modo: {strategy['mode']}\n"
            details += f"  Distancia: {strategy['distance']}\n"
            details += f"  Chase Mode: {strategy['chase_mode']}\n"
            details += f"  Razón: {strategy['reason']}\n\n"
            
            # Debilidades
            if analysis['weaknesses']:
                details += f"🎯 DEBILIDADES:\n"
                for element, percent in analysis['weaknesses'].items():
                    details += f"  {element}: +{percent*100:.0f}% daño\n"
                details += "\n"
            
            # Inmunidades
            if analysis['immunities']:
                details += f"🛡️ INMUNIDADES:\n"
                for immunity in analysis['immunities']:
                    details += f"  {immunity}\n"
            
            # Mostrar en el textbox
            self.creature_details_text.configure(state="normal")
            self.creature_details_text.delete("1.0", tk.END)
            self.creature_details_text.insert("1.0", details)
            self.creature_details_text.configure(state="disabled")
    
    def update_status_display(self):
        """Actualiza la visualización del estado."""
        try:
            # Obtener estado del engine
            status = self.engine.get_status()
            
            # Actualizar información del target
            target_info = status.get('current_creature_info', {})
            self.target_labels["name"].configure(text=f"Nombre: {target_info.get('name', '--')}")
            self.target_labels["health"].configure(text=f"HP: {target_info.get('health', '--')}")
            self.target_labels["experience"].configure(text=f"Experiencia: {target_info.get('experience', '--')}")
            self.target_labels["class"].configure(text=f"Clase: {target_info.get('class', '--')}")
            self.target_labels["difficulty"].configure(text=f"Dificultad: {target_info.get('difficulty', '--')}")
            
            # Obtener análisis del target actual
            if status.get('current_target'):
                analysis = self.engine.get_target_analysis(status['current_target'])
                if analysis:
                    strategy = analysis['strategy']
                    self.target_labels["strategy"].configure(
                        text=f"Estrategia: {strategy['mode']} ({strategy['reason']})"
                    )
                    
                    # Debilidades
                    weaknesses = analysis['weaknesses']
                    if weaknesses:
                        weakness_text = ", ".join([f"{elem}+{p*100:.0f}%" for elem, p in weaknesses.items()])
                        self.target_labels["weaknesses"].configure(text=f"Debilidades: {weakness_text}")
                    else:
                        self.target_labels["weaknesses"].configure(text="Debilidades: Ninguna conocida")
                    
                    # Inmunidades
                    immunities = analysis['immunities']
                    if immunities:
                        self.target_labels["immunities"].configure(text=f"Inmunidades: {', '.join(immunities)}")
                    else:
                        self.target_labels["immunities"].configure(text="Inmunidades: Ninguna conocida")
            
            # Actualizar estado general
            self.general_labels["state"].configure(text=f"Estado: {status.get('state', '--')}")
            self.general_labels["monsters"].configure(text=f"Criaturas: {status.get('monster_count', 0)}")
            
            # Análisis de área
            area_analysis = status.get('area_analysis')
            if area_analysis:
                self.general_labels["threat_level"].configure(
                    text=f"Nivel Amenaza: {area_analysis.get('threat_level', '--').upper()}"
                )
                self.general_labels["priority_target"].configure(
                    text=f"Target Prioritario: {area_analysis.get('highest_priority', '--')}"
                )
                
                spells = area_analysis.get('recommended_spells', [])
                self.general_labels["recommended_spells"].configure(
                    text=f"Spells Recomendados: {', '.join(spells) if spells else 'Ninguno'}"
                )
            
            # Estado de la base de datos
            db_info = self.engine.get_creature_database_info()
            db_status = f"Activa ({db_info['total_creatures']} criaturas)" if db_info['loaded'] else "No disponible"
            self.general_labels["database_status"].configure(text=f"Base de Datos: {db_status}")
            
        except Exception as e:
            print(f"Error actualizando estado: {e}")
    
    def update_area_analysis(self):
        """Actualiza el análisis de área."""
        try:
            status = self.engine.get_status()
            area_analysis = status.get('area_analysis')
            
            if area_analysis:
                self.area_labels["total_creatures"].configure(
                    text=f"Total Criaturas: {area_analysis.get('total_creatures', 0)}"
                )
                self.area_labels["known_creatures"].configure(
                    text=f"Criaturas Conocidas: {area_analysis.get('known_creatures', 0)}"
                )
                self.area_labels["unknown_creatures"].configure(
                    text=f"Criaturas Desconocidas: {area_analysis.get('unknown_creatures', 0)}"
                )
                self.area_labels["threat_level"].configure(
                    text=f"Nivel de Amenaza: {area_analysis.get('threat_level', '--').upper()}"
                )
                self.area_labels["priority_target"].configure(
                    text=f"Target Prioritario: {area_analysis.get('highest_priority', '--')}"
                )
                
                spells = area_analysis.get('recommended_spells', [])
                self.area_labels["recommended_spells"].configure(
                    text=f"Spells Recomendados: {', '.join(spells) if spells else 'Ninguno'}"
                )
                
                # Actualizar criaturas peligrosas
                dangerous = area_analysis.get('dangerous_creatures', [])
                if dangerous:
                    danger_text = "⚠️ CRIATURAS PELIGROSAS:\n\n"
                    for creature in dangerous:
                        danger_text += f"• {creature['name']}: {creature['reason']}\n"
                    
                    self.dangerous_text.configure(state="normal")
                    self.dangerous_text.delete("1.0", tk.END)
                    self.dangerous_text.insert("1.0", danger_text)
                    self.dangerous_text.configure(state="disabled")
                else:
                    self.dangerous_text.configure(state="normal")
                    self.dangerous_text.delete("1.0", tk.END)
                    self.dangerous_text.insert("1.0", "✅ No hay criaturas peligrosas detectadas")
                    self.dangerous_text.configure(state="disabled")
        
        except Exception as e:
            print(f"Error actualizando análisis de área: {e}")
    
    def add_creature_to_list(self):
        """Añade una criatura a la lista de ataque."""
        creature = self.creature_entry.get().strip()
        if creature:
            self.creatures_listbox.insert(tk.END, creature)
            self.creature_entry.delete(0, tk.END)
    
    def remove_creature_from_list(self):
        """Quita una criatura de la lista de ataque."""
        selection = self.creatures_listbox.curselection()
        if selection:
            self.creatures_listbox.delete(selection[0])
    
    def on_config_changed(self):
        """Maneja cambios en la configuración."""
        # Aquí podrías agregar lógica para guardar automáticamente
        pass
    
    def save_config(self):
        """Guarda la configuración."""
        try:
            # Obtener lista de criaturas
            creatures = list(self.creatures_listbox.get(0, tk.END))
            
            # Actualizar configuración
            if "targeting" not in self.config:
                self.config["targeting"] = {}
            
            self.config["targeting"]["enabled"] = self.enabled_var.get()
            self.config["targeting"]["auto_attack"] = self.auto_attack_var.get()
            self.config["targeting"]["attack_list"] = creatures
            
            # Guardar a archivo
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            messagebox.showinfo("Éxito", "Configuración guardada correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando configuración: {e}")
    
    def export_profiles(self):
        """Exporta perfiles inteligentes a la configuración."""
        if self.engine.export_intelligent_profiles():
            messagebox.showinfo("Éxito", "Perfiles exportados correctamente")
        else:
            messagebox.showerror("Error", "Error exportando perfiles")
    
    def import_profiles(self):
        """Importa perfiles manuales desde la configuración."""
        if self.engine.import_manual_profiles():
            self.update_profile_stats()
            messagebox.showinfo("Éxito", "Perfiles importados correctamente")
        else:
            messagebox.showerror("Error", "Error importando perfiles")
    
    def reload_database(self):
        """Recarga la base de datos de criaturas con opciones."""
        # Crear ventana de diálogo
        dialog = tk.Toplevel(self.parent)
        dialog.title("Opciones de Recarga")
        dialog.geometry("400x300")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Frame principal
        main_frame = ctk.CTkFrame(dialog, fg_color="#1a2733")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            main_frame,
            text="🔄 OPCIONES DE RECARGA",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Información actual
        db_info = self.engine.get_creature_database_info()
        info_text = f"Modo actual: {db_info.get('mode', 'unknown')}\n"
        info_text += f"Criaturas cargadas: {db_info['total_creatures']}"
        
        ctk.CTkLabel(
            main_frame,
            text=info_text,
            font=ctk.CTkFont(size=12)
        ).pack(pady=5)
        
        # Opciones
        options_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        options_frame.pack(fill="x", padx=10, pady=10)
        
        def lazy_reload():
            """Recargar solo criaturas seleccionadas."""
            attack_list = list(self.creatures_listbox.get(0, tk.END))
            if attack_list:
                self.engine.intelligent_targeting.lazy_loaded_creatures.clear()
                success = self.engine.intelligent_targeting.load_creatures_on_demand(attack_list)
                if success:
                    messagebox.showinfo("Éxito", f"Cargadas {len(attack_list)} criaturas bajo demanda")
                    self.update_profile_stats()
                else:
                    messagebox.showerror("Error", "Error cargando criaturas bajo demanda")
            else:
                messagebox.showwarning("Advertencia", "No hay criaturas en la lista de ataque")
            dialog.destroy()
        
        def full_reload():
            """Cargar base de datos completa."""
            success = self.engine.intelligent_targeting.load_full_database()
            if success:
                messagebox.showinfo("Éxito", "Base de datos completa cargada")
                self.update_profile_stats()
            else:
                messagebox.showerror("Error", "Error cargando base de datos completa")
            dialog.destroy()
        
        def cancel():
            dialog.destroy()
        
        # Botones
        ctk.CTkButton(
            options_frame,
            text="📦 Cargar Solo Criaturas Seleccionadas",
            command=lazy_reload,
            fg_color="#3498DB",
            hover_color="#2980B9",
            width=350
        ).pack(pady=5)
        
        ctk.CTkButton(
            options_frame,
            text="🗄️ Cargar Base de Datos Completa",
            command=full_reload,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            width=350
        ).pack(pady=5)
        
        ctk.CTkButton(
            options_frame,
            text="❌ Cancelar",
            command=cancel,
            fg_color="#95A5A6",
            hover_color="#7F8C8D",
            width=350
        ).pack(pady=5)
    
    def test_targeting(self):
        """Inicia una prueba del targeting."""
        messagebox.showinfo("Test", "Iniciando prueba de targeting...\n"
                                "Revisa la consola para ver los logs")
    
    def update_all(self):
        """Actualiza toda la información."""
        self.update_status_display()
        self.update_area_analysis()
        self.update_profile_stats()
    
    def show_diagnosis(self):
        """Muestra diagnóstico completo."""
        # Aquí podrías abrir una ventana con el diagnóstico
        messagebox.showinfo("Diagnóstico", "Ejecuta diagnose_targeting_v2.py para diagnóstico completo")
    
    def start_auto_update(self):
        """Inicia actualización automática cada 2 segundos."""
        def auto_update():
            try:
                self.update_status_display()
                self.update_area_analysis()
            except:
                pass
            finally:
                self.parent.after(2000, auto_update)
        
        # Iniciar después de 1 segundo
        self.parent.after(1000, auto_update)
