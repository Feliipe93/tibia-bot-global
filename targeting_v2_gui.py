#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targeting_v2_gui.py - GUI completa para el Targeting V2
Muestra y configura todas las funcionalidades avanzadas del targeting.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Dict, List, Optional
import json


class TargetingV2GUI:
    """GUI completa para el sistema de targeting V2."""
    
    def __init__(self, parent, config, targeting_engine):
        self.parent = parent
        self.config = config
        self.targeting_engine = targeting_engine
        
        # Variables para la GUI
        self.creature_profiles = {}
        self.current_creature = None
        
        # Crear frame principal
        self.create_main_frame()
        
        # Cargar configuración existente
        self.load_configuration()
    
    def create_main_frame(self):
        """Crea el frame principal de la GUI."""
        # Frame con scroll para todo el contenido
        self.main_frame = ctk.CTkScrollableFrame(
            self.parent, 
            label_text="⚔️ TARGETING V2 - Sistema Avanzado",
            fg_color="#1a2733"
        )
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Sección de estado
        self.create_status_section()
        
        # Sección de configuración global
        self.create_global_config_section()
        
        # Sección de criaturas
        self.create_creatures_section()
        
        # Sección de perfiles
        self.create_profiles_section()
        
        # Botones de acción
        self.create_action_buttons()
    
    def create_status_section(self):
        """Crea la sección de estado del targeting."""
        status_frame = ctk.CTkFrame(self.main_frame, fg_color="#0f1923")
        status_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            status_frame, 
            text="📊 ESTADO ACTUAL", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame para indicadores
        indicators_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        indicators_frame.pack(fill="x", padx=10, pady=5)
        
        # Target actual
        self.target_label = ctk.CTkLabel(
            indicators_frame, 
            text="Target: Ninguno",
            font=ctk.CTkFont(size=12)
        )
        self.target_label.pack(side="left", padx=10)
        
        # HP del target
        self.hp_label = ctk.CTkLabel(
            indicators_frame, 
            text="HP: --%",
            font=ctk.CTkFont(size=12)
        )
        self.hp_label.pack(side="left", padx=10)
        
        # Modo actual
        self.mode_label = ctk.CTkLabel(
            indicators_frame, 
            text="Modo: Stand",
            font=ctk.CTkFont(size=12)
        )
        self.mode_label.pack(side="left", padx=10)
        
        # Criaturas cercanas
        self.creatures_label = ctk.CTkLabel(
            indicators_frame, 
            text="Criaturas: 0",
            font=ctk.CTkFont(size=12)
        )
        self.creatures_label.pack(side="left", padx=10)
    
    def create_global_config_section(self):
        """Crea la sección de configuración global."""
        global_frame = ctk.CTkFrame(self.main_frame, fg_color="#0f1923")
        global_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            global_frame, 
            text="⚙️ CONFIGURACIÓN GLOBAL", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame para configuraciones
        config_frame = ctk.CTkFrame(global_frame, fg_color="transparent")
        config_frame.pack(fill="x", padx=10, pady=5)
        
        # Habilitar targeting
        self.enabled_var = tk.BooleanVar(value=self.config.get("targeting", {}).get("enabled", False))
        self.enabled_cb = ctk.CTkSwitch(
            config_frame, 
            text="Targeting habilitado",
            variable=self.enabled_var,
            command=self.on_enabled_changed
        )
        self.enabled_cb.pack(anchor="w", pady=2)
        
        # Auto-ataque
        self.auto_attack_var = tk.BooleanVar(value=self.config.get("targeting", {}).get("auto_attack", True))
        self.auto_attack_cb = ctk.CTkSwitch(
            config_frame, 
            text="Auto-ataque",
            variable=self.auto_attack_var,
            command=self.on_auto_attack_changed
        )
        self.auto_attack_cb.pack(anchor="w", pady=2)
        
        # Chase monsters
        self.chase_monsters_var = tk.BooleanVar(value=self.config.get("targeting", {}).get("chase_monsters", True))
        self.chase_monsters_cb = ctk.CTkSwitch(
            config_frame, 
            text="Perseguir monstruos",
            variable=self.chase_monsters_var,
            command=self.on_chase_monsters_changed
        )
        self.chase_monsters_cb.pack(anchor="w", pady=2)
        
        # Frame para delays
        delays_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        delays_frame.pack(fill="x", pady=5)
        
        # Attack delay
        ctk.CTkLabel(delays_frame, text="Delay ataque:").pack(side="left", padx=(0, 5))
        self.attack_delay_var = tk.StringVar(value=str(self.config.get("targeting", {}).get("attack_delay", 0.5)))
        self.attack_delay_entry = ctk.CTkEntry(
            delays_frame, 
            textvariable=self.attack_delay_var,
            width=80
        )
        self.attack_delay_entry.pack(side="left", padx=5)
        ctk.CTkLabel(delays_frame, text="seg").pack(side="left")
        
        # Re-attack delay
        ctk.CTkLabel(delays_frame, text="Delay re-ataque:").pack(side="left", padx=(20, 5))
        self.re_attack_delay_var = tk.StringVar(value=str(self.config.get("targeting", {}).get("re_attack_delay", 0.6)))
        self.re_attack_delay_entry = ctk.CTkEntry(
            delays_frame, 
            textvariable=self.re_attack_delay_var,
            width=80
        )
        self.re_attack_delay_entry.pack(side="left", padx=5)
        ctk.CTkLabel(delays_frame, text="seg").pack(side="left")
        
        # Frame para hotkeys
        hotkeys_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        hotkeys_frame.pack(fill="x", pady=5)
        
        # Chase key
        ctk.CTkLabel(hotkeys_frame, text="Chase key:").pack(side="left", padx=(0, 5))
        self.chase_key_var = tk.StringVar(value=self.config.get("targeting", {}).get("chase_key", ""))
        self.chase_key_entry = ctk.CTkEntry(
            hotkeys_frame, 
            textvariable=self.chase_key_var,
            width=100
        )
        self.chase_key_entry.pack(side="left", padx=5)
        
        # Stand key
        ctk.CTkLabel(hotkeys_frame, text="Stand key:").pack(side="left", padx=(20, 5))
        self.stand_key_var = tk.StringVar(value=self.config.get("targeting", {}).get("stand_key", ""))
        self.stand_key_entry = ctk.CTkEntry(
            hotkeys_frame, 
            textvariable=self.stand_key_var,
            width=100
        )
        self.stand_key_entry.pack(side="left", padx=5)
    
    def create_creatures_section(self):
        """Crea la sección de lista de criaturas."""
        creatures_frame = ctk.CTkFrame(self.main_frame, fg_color="#0f1923")
        creatures_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            creatures_frame, 
            text="👾 LISTA DE CRIATURAS", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame para listas
        lists_frame = ctk.CTkFrame(creatures_frame, fg_color="transparent")
        lists_frame.pack(fill="x", padx=10, pady=5)
        
        # Columna izquierda - Attack list
        left_frame = ctk.CTkFrame(lists_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(left_frame, text="Criaturas a atacar:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.attack_listbox = tk.Listbox(left_frame, height=6)
        self.attack_listbox.pack(fill="both", expand=True, pady=2)
        
        # Botones para attack list
        attack_buttons_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        attack_buttons_frame.pack(fill="x")
        
        ctk.CTkButton(
            attack_buttons_frame, 
            text="Añadir", 
            command=self.add_to_attack_list,
            width=80
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            attack_buttons_frame, 
            text="Quitar", 
            command=self.remove_from_attack_list,
            width=80
        ).pack(side="left", padx=2)
        
        # Entry para añadir criatura
        self.creature_entry = ctk.CTkEntry(left_frame, placeholder_text="Nombre de criatura")
        self.creature_entry.pack(fill="x", pady=2)
        
        # Columna derecha - Ignore list
        right_frame = ctk.CTkFrame(lists_frame, fg_color="transparent")
        right_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        ctk.CTkLabel(right_frame, text="Criaturas a ignorar:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.ignore_listbox = tk.Listbox(right_frame, height=6)
        self.ignore_listbox.pack(fill="both", expand=True, pady=2)
        
        # Botones para ignore list
        ignore_buttons_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        ignore_buttons_frame.pack(fill="x")
        
        ctk.CTkButton(
            ignore_buttons_frame, 
            text="Añadir", 
            command=self.add_to_ignore_list,
            width=80
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            ignore_buttons_frame, 
            text="Quitar", 
            command=self.remove_from_ignore_list,
            width=80
        ).pack(side="left", padx=2)
        
        # Entry para añadir criatura a ignorar
        self.ignore_entry = ctk.CTkEntry(right_frame, placeholder_text="Nombre de criatura")
        self.ignore_entry.pack(fill="x", pady=2)
    
    def create_profiles_section(self):
        """Crea la sección de perfiles por criatura."""
        profiles_frame = ctk.CTkFrame(self.main_frame, fg_color="#0f1923")
        profiles_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(
            profiles_frame, 
            text="📋 PERFILES POR CRIATURA", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Frame principal para perfiles
        profiles_main_frame = ctk.CTkFrame(profiles_frame, fg_color="transparent")
        profiles_main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Frame izquierdo - Lista de criaturas con perfiles
        left_profile_frame = ctk.CTkFrame(profiles_main_frame, fg_color="transparent")
        left_profile_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(
            left_profile_frame, 
            text="Criaturas con perfil:", 
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")
        
        self.creature_profile_listbox = tk.Listbox(left_profile_frame, height=8)
        self.creature_profile_listbox.pack(fill="both", expand=True, pady=2)
        self.creature_profile_listbox.bind('<<ListboxSelect>>', self.on_creature_selected)
        
        # Botones para perfiles
        profile_buttons_frame = ctk.CTkFrame(left_profile_frame, fg_color="transparent")
        profile_buttons_frame.pack(fill="x")
        
        ctk.CTkButton(
            profile_buttons_frame, 
            text="Nuevo Perfil", 
            command=self.create_new_profile,
            width=100
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            profile_buttons_frame, 
            text="Eliminar Perfil", 
            command=self.delete_profile,
            width=100
        ).pack(side="left", padx=2)
        
        # Frame derecho - Configuración del perfil
        right_profile_frame = ctk.CTkFrame(profiles_main_frame, fg_color="#0f1923")
        right_profile_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        ctk.CTkLabel(
            right_profile_frame, 
            text="CONFIGURACIÓN DEL PERFIL", 
            font=ctk.CTkFont(weight="bold")
        ).pack(pady=5)
        
        # Notebook para pestañas de configuración
        self.profile_notebook = ttk.Notebook(right_profile_frame)
        self.profile_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Crear pestañas
        self.create_basic_tab()
        self.create_hp_thresholds_tab()
        self.create_spells_tab()
        self.create_advanced_tab()
    
    def create_basic_tab(self):
        """Crea la pestaña de configuración básica."""
        self.basic_frame = ctk.CTkFrame(self.profile_notebook)
        self.profile_notebook.add(self.basic_frame, text="Básico")
        
        # Modo de ataque
        mode_frame = ctk.CTkFrame(self.basic_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(mode_frame, text="Modo de ataque:").pack(anchor="w")
        self.attack_mode_var = tk.StringVar(value="offensive")
        self.attack_mode_combo = ctk.CTkComboBox(
            mode_frame, 
            values=["offensive", "balanced", "defensive"],
            variable=self.attack_mode_var
        )
        self.attack_mode_combo.pack(fill="x", pady=2)
        
        # Modo de chase
        chase_frame = ctk.CTkFrame(self.basic_frame, fg_color="transparent")
        chase_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(chase_frame, text="Modo de persecución:").pack(anchor="w")
        self.chase_mode_var = tk.StringVar(value="auto")
        self.chase_mode_combo = ctk.CTkComboBox(
            chase_frame, 
            values=["auto", "chase", "stand"],
            variable=self.chase_mode_var
        )
        self.chase_mode_combo.pack(fill="x", pady=2)
        
        # Prioridad
        priority_frame = ctk.CTkFrame(self.basic_frame, fg_color="transparent")
        priority_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(priority_frame, text="Prioridad:").pack(anchor="w")
        self.priority_var = tk.StringVar(value="50")
        self.priority_entry = ctk.CTkEntry(priority_frame, textvariable=self.priority_var)
        self.priority_entry.pack(fill="x", pady=2)
        
        # Ranged
        self.is_ranged_var = tk.BooleanVar(value=False)
        self.is_ranged_cb = ctk.CTkSwitch(
            self.basic_frame, 
            text="Monstruo a distancia (ranged)",
            variable=self.is_ranged_var
        )
        self.is_ranged_cb.pack(anchor="w", padx=10, pady=5)
        
        # Huye al HP
        flee_frame = ctk.CTkFrame(self.basic_frame, fg_color="transparent")
        flee_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(flee_frame, text="Huye al HP (%):").pack(anchor="w")
        self.flees_at_hp_var = tk.StringVar(value="0")
        self.flees_at_hp_entry = ctk.CTkEntry(flee_frame, textvariable=self.flees_at_hp_var)
        self.flees_at_hp_entry.pack(fill="x", pady=2)
    
    def create_hp_thresholds_tab(self):
        """Crea la pestaña de umbrales de HP."""
        self.hp_frame = ctk.CTkFrame(self.profile_notebook)
        self.profile_notebook.add(self.hp_frame, text="HP Thresholds")
        
        # Información
        info_frame = ctk.CTkFrame(self.hp_frame, fg_color="#27AE60")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            info_frame, 
            text="💡 Configura cuándo cambiar entre chase/stand según el HP de la criatura",
            font=ctk.CTkFont(size=11),
            text_color="white"
        ).pack(padx=10, pady=5)
        
        # HP threshold para chase
        chase_threshold_frame = ctk.CTkFrame(self.hp_frame, fg_color="transparent")
        chase_threshold_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            chase_threshold_frame, 
            text="Cambiar a CHASE cuando HP ≤ (%):",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")
        self.hp_threshold_chase_var = tk.StringVar(value="30")
        self.hp_threshold_chase_entry = ctk.CTkEntry(
            chase_threshold_frame, 
            textvariable=self.hp_threshold_chase_var
        )
        self.hp_threshold_chase_entry.pack(fill="x", pady=2)
        
        # HP threshold para stand
        stand_threshold_frame = ctk.CTkFrame(self.hp_frame, fg_color="transparent")
        stand_threshold_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            stand_threshold_frame, 
            text="Cambiar a STAND cuando HP ≥ (%):",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w")
        self.hp_threshold_stand_var = tk.StringVar(value="80")
        self.hp_threshold_stand_entry = ctk.CTkEntry(
            stand_threshold_frame, 
            textvariable=self.hp_threshold_stand_var
        )
        self.hp_threshold_stand_entry.pack(fill="x", pady=2)
        
        # Preview de comportamiento
        preview_frame = ctk.CTkFrame(self.hp_frame, fg_color="#0f1923")
        preview_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            preview_frame, 
            text="🎯 Comportamiento esperado:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", pady=5)
        
        self.behavior_preview_label = ctk.CTkLabel(
            preview_frame, 
            text="HP > 80%: Stand mode\n80% ≥ HP > 30%: Mantener modo actual\nHP ≤ 30%: Chase mode",
            font=ctk.CTkFont(size=10),
            text_color="#95A5A6"
        )
        self.behavior_preview_label.pack(anchor="w", padx=10)
    
    def create_spells_tab(self):
        """Crea la pestaña de configuración de spells."""
        self.spells_frame = ctk.CTkFrame(self.profile_notebook)
        self.profile_notebook.add(self.spells_frame, text="Spells")
        
        # Información
        info_frame = ctk.CTkFrame(self.spells_frame, fg_color="#3498DB")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            info_frame, 
            text="🔮 Configura diferentes spells según el número de criaturas cercanas",
            font=ctk.CTkFont(size=11),
            text_color="white"
        ).pack(padx=10, pady=5)
        
        # Frame para spells por cantidad
        spells_config_frame = ctk.CTkFrame(self.spells_frame, fg_color="transparent")
        spells_config_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 1 criatura
        spell1_frame = ctk.CTkFrame(spells_config_frame, fg_color="transparent")
        spell1_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(spell1_frame, text="1 criatura:", width=100).pack(side="left")
        self.spell1_var = tk.StringVar(value="")
        self.spell1_entry = ctk.CTkEntry(spell1_frame, textvariable=self.spell1_var)
        self.spell1_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 2 criaturas
        spell2_frame = ctk.CTkFrame(spells_config_frame, fg_color="transparent")
        spell2_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(spell2_frame, text="2 criaturas:", width=100).pack(side="left")
        self.spell2_var = tk.StringVar(value="")
        self.spell2_entry = ctk.CTkEntry(spell2_frame, textvariable=self.spell2_var)
        self.spell2_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 3 criaturas
        spell3_frame = ctk.CTkFrame(spells_config_frame, fg_color="transparent")
        spell3_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(spell3_frame, text="3+ criaturas:", width=100).pack(side="left")
        self.spell3_var = tk.StringVar(value="")
        self.spell3_entry = ctk.CTkEntry(spell3_frame, textvariable=self.spell3_var)
        self.spell3_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Default
        spell_default_frame = ctk.CTkFrame(spells_config_frame, fg_color="transparent")
        spell_default_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(spell_default_frame, text="Por defecto:", width=100).pack(side="left")
        self.spell_default_var = tk.StringVar(value="")
        self.spell_default_entry = ctk.CTkEntry(spell_default_frame, textvariable=self.spell_default_var)
        self.spell_default_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Spell cooldown
        cooldown_frame = ctk.CTkFrame(self.spells_frame, fg_color="transparent")
        cooldown_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(cooldown_frame, text="Cooldown entre spells (segundos):").pack(anchor="w")
        self.spell_cooldown_var = tk.StringVar(value="1.0")
        self.spell_cooldown_entry = ctk.CTkEntry(cooldown_frame, textvariable=self.spell_cooldown_var)
        self.spell_cooldown_entry.pack(fill="x", pady=2)
    
    def create_advanced_tab(self):
        """Crea la pestaña de configuración avanzada."""
        self.advanced_frame = ctk.CTkFrame(self.profile_notebook)
        self.profile_notebook.add(self.advanced_frame, text="Avanzado")
        
        # Opciones adicionales
        self.use_chase_on_flee_var = tk.BooleanVar(value=True)
        self.use_chase_on_flee_cb = ctk.CTkSwitch(
            self.advanced_frame, 
            text="Perseguir si la criatura huye",
            variable=self.use_chase_on_flee_var
        )
        self.use_chase_on_flee_cb.pack(anchor="w", padx=10, pady=5)
        
        # Información adicional
        info_frame = ctk.CTkFrame(self.advanced_frame, fg_color="#95A5A6")
        info_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            info_frame, 
            text="ℹ️ Configuraciones avanzadas para comportamiento específico\n"
                 "al enfrentar criaturas con diferentes patrones de ataque.",
            font=ctk.CTkFont(size=10),
            text_color="white",
            justify="left"
        ).pack(padx=10, pady=5)
    
    def create_action_buttons(self):
        """Crea los botones de acción."""
        buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=5, pady=10)
        
        # Botones principales
        main_buttons_frame = ctk.CTkFrame(buttons_frame, fg_color="transparent")
        main_buttons_frame.pack(fill="x")
        
        ctk.CTkButton(
            main_buttons_frame, 
            text="💾 Guardar Configuración", 
            command=self.save_configuration,
            fg_color="#27AE60",
            hover_color="#229954"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            main_buttons_frame, 
            text="🔄 Recargar", 
            command=self.load_configuration,
            fg_color="#3498DB",
            hover_color="#2980B9"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            main_buttons_frame, 
            text="🧪 Test Targeting", 
            command=self.test_targeting,
            fg_color="#9B59B6",
            hover_color="#8E44AD"
        ).pack(side="left", padx=5)
        
        # Botón de reset
        ctk.CTkButton(
            main_buttons_frame, 
            text="🗑️ Resetear Todo", 
            command=self.reset_all,
            fg_color="#E74C3C",
            hover_color="#C0392B"
        ).pack(side="right", padx=5)
    
    # Métodos para manejo de eventos
    def on_enabled_changed(self):
        """Maneja el cambio del switch de targeting habilitado."""
        enabled = self.enabled_var.get()
        if self.targeting_engine:
            if enabled:
                self.targeting_engine.start()
            else:
                self.targeting_engine.stop()
    
    def on_auto_attack_changed(self):
        """Maneja el cambio del switch de auto-ataque."""
        # Actualizar configuración
        if "targeting" not in self.config:
            self.config["targeting"] = {}
        self.config["targeting"]["auto_attack"] = self.auto_attack_var.get()
    
    def on_chase_monsters_changed(self):
        """Maneja el cambio del switch de chase monsters."""
        # Actualizar configuración
        if "targeting" not in self.config:
            self.config["targeting"] = {}
        self.config["targeting"]["chase_monsters"] = self.chase_monsters_var.get()
    
    def add_to_attack_list(self):
        """Añade una criatura a la lista de ataque."""
        creature = self.creature_entry.get().strip()
        if creature:
            self.attack_listbox.insert(tk.END, creature)
            self.creature_entry.delete(0, tk.END)
    
    def remove_from_attack_list(self):
        """Quita una criatura de la lista de ataque."""
        selection = self.attack_listbox.curselection()
        if selection:
            self.attack_listbox.delete(selection[0])
    
    def add_to_ignore_list(self):
        """Añade una criatura a la lista de ignorar."""
        creature = self.ignore_entry.get().strip()
        if creature:
            self.ignore_listbox.insert(tk.END, creature)
            self.ignore_entry.delete(0, tk.END)
    
    def remove_from_ignore_list(self):
        """Quita una criatura de la lista de ignorar."""
        selection = self.ignore_listbox.curselection()
        if selection:
            self.ignore_listbox.delete(selection[0])
    
    def on_creature_selected(self, event):
        """Maneja la selección de una criatura en la lista de perfiles."""
        selection = self.creature_profile_listbox.curselection()
        if selection:
            creature_name = self.creature_profile_listbox.get(selection[0])
            self.current_creature = creature_name
            self.load_profile_to_gui(creature_name)
    
    def create_new_profile(self):
        """Crea un nuevo perfil para una criatura."""
        # Diálogo para ingresar nombre
        dialog = tk.Toplevel(self.parent)
        dialog.title("Nuevo Perfil")
        dialog.geometry("300x100")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Nombre de la criatura:").pack(pady=10)
        name_entry = ctk.CTkEntry(dialog, width=200)
        name_entry.pack(pady=5)
        name_entry.focus()
        
        def create_profile():
            name = name_entry.get().strip()
            if name:
                self.creature_profiles[name] = self.get_default_profile()
                self.creature_profile_listbox.insert(tk.END, name)
                self.save_configuration()
                dialog.destroy()
        
        ctk.CTkButton(dialog, text="Crear", command=create_profile).pack(pady=10)
        
        # Bind Enter key
        name_entry.bind('<Return>', lambda e: create_profile())
    
    def delete_profile(self):
        """Elimina el perfil actual."""
        if self.current_creature and self.current_creature in self.creature_profiles:
            if messagebox.askyesno("Confirmar", f"¿Eliminar perfil de '{self.current_creature}'?"):
                del self.creature_profiles[self.current_creature]
                
                # Remover de la lista
                items = list(self.creature_profile_listbox.get(0, tk.END))
                if self.current_creature in items:
                    index = items.index(self.current_creature)
                    self.creature_profile_listbox.delete(index)
                
                self.current_creature = None
                self.clear_profile_fields()
                self.save_configuration()
    
    def get_default_profile(self):
        """Retorna un perfil por defecto."""
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
                "1": [],
                "2": [],
                "3": [],
                "default": []
            },
            "spell_cooldown": 1.0
        }
    
    def load_profile_to_gui(self, creature_name):
        """Carga la configuración del perfil a la GUI."""
        profile = self.creature_profiles.get(creature_name, {})
        
        # Cargar configuración básica
        self.attack_mode_var.set(profile.get("attack_mode", "offensive"))
        self.chase_mode_var.set(profile.get("chase_mode", "auto"))
        self.priority_var.set(str(profile.get("priority", 50)))
        self.is_ranged_var.set(profile.get("is_ranged", False))
        self.flees_at_hp_var.set(str(profile.get("flees_at_hp", 0)))
        
        # Cargar umbrales de HP
        self.hp_threshold_chase_var.set(str(int(profile.get("hp_threshold_chase", 0) * 100)))
        self.hp_threshold_stand_var.set(str(int(profile.get("hp_threshold_stand", 0) * 100)))
        
        # Cargar spells
        spells = profile.get("spells_by_count", {})
        self.spell1_var.set(", ".join(spells.get("1", [])))
        self.spell2_var.set(", ".join(spells.get("2", [])))
        self.spell3_var.set(", ".join(spells.get("3", [])))
        self.spell_default_var.set(", ".join(spells.get("default", [])))
        
        self.spell_cooldown_var.set(str(profile.get("spell_cooldown", 1.0)))
        
        # Cargar configuraciones avanzadas
        self.use_chase_on_flee_var.set(profile.get("use_chase_on_flee", True))
        
        # Actualizar preview
        self.update_behavior_preview()
    
    def clear_profile_fields(self):
        """Limpia los campos del perfil."""
        self.attack_mode_var.set("offensive")
        self.chase_mode_var.set("auto")
        self.priority_var.set("50")
        self.is_ranged_var.set(False)
        self.flees_at_hp_var.set("0")
        
        self.hp_threshold_chase_var.set("0")
        self.hp_threshold_stand_var.set("0")
        
        self.spell1_var.set("")
        self.spell2_var.set("")
        self.spell3_var.set("")
        self.spell_default_var.set("")
        self.spell_cooldown_var.set("1.0")
        
        self.use_chase_on_flee_var.set(True)
    
    def update_behavior_preview(self):
        """Actualiza el preview del comportamiento."""
        try:
            chase_threshold = float(self.hp_threshold_chase_var.get())
            stand_threshold = float(self.hp_threshold_stand_var.get())
            
            if chase_threshold > 0 and stand_threshold > 0:
                if chase_threshold < stand_threshold:
                    preview = f"HP > {stand_threshold:.0f}%: Stand mode\n"
                    preview += f"{stand_threshold:.0f}% ≥ HP > {chase_threshold:.0f}%: Mantener modo actual\n"
                    preview += f"HP ≤ {chase_threshold:.0f}%: Chase mode"
                else:
                    preview = "⚠️ Los umbrales están invertidos"
            else:
                preview = "Sin umbrales configurados"
            
            self.behavior_preview_label.configure(text=preview)
        except ValueError:
            self.behavior_preview_label.configure(text="⚠️ Valores inválidos")
    
    def save_configuration(self):
        """Guarda toda la configuración."""
        try:
            # Guardar configuración global
            if "targeting" not in self.config:
                self.config["targeting"] = {}
            
            self.config["targeting"]["enabled"] = self.enabled_var.get()
            self.config["targeting"]["auto_attack"] = self.auto_attack_var.get()
            self.config["targeting"]["chase_monsters"] = self.chase_monsters_var.get()
            self.config["targeting"]["attack_delay"] = float(self.attack_delay_var.get())
            self.config["targeting"]["re_attack_delay"] = float(self.re_attack_delay_var.get())
            self.config["targeting"]["chase_key"] = self.chase_key_var.get()
            self.config["targeting"]["stand_key"] = self.stand_key_var.get()
            
            # Guardar listas
            self.config["targeting"]["attack_list"] = list(self.attack_listbox.get(0, tk.END))
            self.config["targeting"]["ignore_list"] = list(self.ignore_listbox.get(0, tk.END))
            
            # Guardar perfiles
            if self.current_creature:
                self.save_current_profile()
            
            self.config["targeting"]["creature_profiles"] = self.creature_profiles
            
            # Guardar a archivo
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            messagebox.showinfo("Éxito", "Configuración guardada correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando configuración: {e}")
    
    def save_current_profile(self):
        """Guarda el perfil actual."""
        if not self.current_creature:
            return
        
        # Parsear spells
        def parse_spells(spell_text):
            if not spell_text.strip():
                return []
            return [s.strip() for s in spell_text.split(",") if s.strip()]
        
        profile = {
            "chase_mode": self.chase_mode_var.get(),
            "attack_mode": self.attack_mode_var.get(),
            "flees_at_hp": float(self.flees_at_hp_var.get()) / 100,
            "is_ranged": self.is_ranged_var.get(),
            "priority": int(self.priority_var.get()),
            "use_chase_on_flee": self.use_chase_on_flee_var.get(),
            "hp_threshold_chase": float(self.hp_threshold_chase_var.get()) / 100,
            "hp_threshold_stand": float(self.hp_threshold_stand_var.get()) / 100,
            "spells_by_count": {
                "1": parse_spells(self.spell1_var.get()),
                "2": parse_spells(self.spell2_var.get()),
                "3": parse_spells(self.spell3_var.get()),
                "default": parse_spells(self.spell_default_var.get())
            },
            "spell_cooldown": float(self.spell_cooldown_var.get())
        }
        
        self.creature_profiles[self.current_creature] = profile
    
    def load_configuration(self):
        """Carga la configuración desde el archivo."""
        try:
            # Cargar listas
            attack_list = self.config.get("targeting", {}).get("attack_list", [])
            ignore_list = self.config.get("targeting", {}).get("ignore_list", [])
            
            self.attack_listbox.delete(0, tk.END)
            for creature in attack_list:
                self.attack_listbox.insert(tk.END, creature)
            
            self.ignore_listbox.delete(0, tk.END)
            for creature in ignore_list:
                self.ignore_listbox.insert(tk.END, creature)
            
            # Cargar perfiles
            self.creature_profiles = self.config.get("targeting", {}).get("creature_profiles", {})
            
            self.creature_profile_listbox.delete(0, tk.END)
            for creature_name in self.creature_profiles.keys():
                self.creature_profile_listbox.insert(tk.END, creature_name)
            
            messagebox.showinfo("Éxito", "Configuración recargada correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando configuración: {e}")
    
    def test_targeting(self):
        """Inicia una prueba del targeting."""
        if self.targeting_engine:
            if not self.enabled_var.get():
                messagebox.showwarning("Advertencia", "Activa el targeting primero")
                return
            
            messagebox.showinfo("Test", "Iniciando prueba de targeting...\n"
                                    "Revisa la consola para ver los logs")
    
    def reset_all(self):
        """Resetea toda la configuración."""
        if messagebox.askyesno("Confirmar", "¿Resetear toda la configuración del targeting?"):
            # Limpiar listas
            self.attack_listbox.delete(0, tk.END)
            self.ignore_listbox.delete(0, tk.END)
            self.creature_profile_listbox.delete(0, tk.END)
            
            # Resetear variables
            self.creature_profiles = {}
            self.current_creature = None
            self.clear_profile_fields()
            
            # Resetear configuración global
            self.enabled_var.set(False)
            self.auto_attack_var.set(True)
            self.chase_monsters_var.set(True)
            self.attack_delay_var.set("0.5")
            self.re_attack_delay_var.set("0.6")
            self.chase_key_var.set("")
            self.stand_key_var.set("")
            
            messagebox.showinfo("Reset", "Configuración reseteada")
    
    def update_status(self, target_name=None, hp_percentage=None, mode=None, creature_count=None):
        """Actualiza los indicadores de estado."""
        if target_name is not None:
            self.target_label.configure(text=f"Target: {target_name}")
        
        if hp_percentage is not None:
            self.hp_label.configure(text=f"HP: {hp_percentage:.0f}%")
        
        if mode is not None:
            self.mode_label.configure(text=f"Modo: {mode.title()}")
        
        if creature_count is not None:
            self.creatures_label.configure(text=f"Criaturas: {creature_count}")
    
    def get_current_configuration(self):
        """Retorna la configuración actual."""
        return {
            "enabled": self.enabled_var.get(),
            "auto_attack": self.auto_attack_var.get(),
            "chase_monsters": self.chase_monsters_var.get(),
            "attack_list": list(self.attack_listbox.get(0, tk.END)),
            "ignore_list": list(self.ignore_listbox.get(0, tk.END)),
            "creature_profiles": self.creature_profiles
        }
