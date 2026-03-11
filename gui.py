"""
gui.py - Interfaz gráfica completa con customtkinter.
Contiene las 4 secciones principales + pestaña de Ayuda.
"""

import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np
import cv2
import keyboard

from config import Config
from logger import BotLogger
from healer_bot import HealerBot
from window_finder import find_tibia_windows
from key_sender import KeySender
from simple_walking import SimpleWalkRecorder, DIRECTION_ARROWS

# Tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Colores para niveles de log
LOG_COLORS = {
    "DEBUG": "#888888",
    "INFO": "#00CC66",
    "WARNING": "#FFAA00",
    "ERROR": "#FF3333",
    "CRITICAL": "#FF0000",
}

AVAILABLE_KEYS = KeySender.get_available_keys()


class TibiaHealerGUI(ctk.CTk):
    """Ventana principal del Tibia Auto Healer."""

    def __init__(self):
        super().__init__()

        # ----------------------------------------------------------
        # Inicialización de componentes
        # ----------------------------------------------------------
        self.config = Config()
        self.log = BotLogger(level=self.config.log_level)
        self.bot = HealerBot(self.config, self.log)

        # Conectar callbacks
        self.bot.set_status_callback(self._schedule_status_update)
        self.log.set_gui_callback(self._log_callback)

        # Estado GUI
        self._hotkey_registered = False
        self._exit_hotkey_registered = False
        self._update_job = None
        self._rule_frames: List[ctk.CTkFrame] = []
        self._log_queue: queue.Queue = queue.Queue()
        self._gui_ready = False

        # Listas de ventanas para dropdowns
        self._tibia_windows: List[Dict] = []

        # Simple Walking recorder
        self.walk_recorder = SimpleWalkRecorder()
        self.walk_recorder.set_log_callback(self._sw_log)
        self.walk_recorder.set_on_step_recorded(self._sw_on_step_recorded)
        self.walk_recorder.set_on_playback_step(self._sw_on_playback_step)
        self.walk_recorder.set_on_cycle_complete(self._sw_on_cycle_complete)

        # ----------------------------------------------------------
        # Configuración de la ventana principal
        # ----------------------------------------------------------
        self.title("⚔️ Tibia Auto Healer")
        self.geometry("800x720")  # Reducido más para asegurar espacio
        self.minsize(700, 620)    # Reducido mínimo
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ----------------------------------------------------------
        # Layout principal con pestañas verticales y scroll
        # ----------------------------------------------------------
        # Frame principal para contener todo
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        
        # Frame izquierdo para las pestañas verticales
        tabs_frame = ctk.CTkFrame(main_frame, width=200)
        tabs_frame.pack(side="left", fill="y", padx=(0, 5))
        tabs_frame.pack_propagate(False)
        
        # Scrollable frame para las pestañas
        self.tabs_scroll = ctk.CTkScrollableFrame(tabs_frame, fg_color="transparent")
        self.tabs_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Frame derecho para el contenido
        self.content_frame = ctk.CTkFrame(main_frame)
        self.content_frame.pack(side="right", fill="both", expand=True, padx=(0, 8), pady=8)
        
        # Crear pestañas verticales
        self.tab_buttons = {}
        self.tab_contents = {}
        self.current_tab = None
        
        # Lista de pestañas con sus iconos (orden reorganizado)
        tabs_data = [
            ("main", "🏠 Principal"),
            ("config", "⚙️ Configuración"),
            ("conditions", "🩺 Condiciones"),
            ("windows", "🪟 Ventanas"),
            ("targeting", "⚔️ Targeting"),
            ("looter", "💰 Looter"),
            ("simple_walking", "🚶 Simple Walking"),
            ("cavebot", "🗺️ Cavebot"),
            ("screenview", "🖥️ Screen View"),
            ("test", "🧪 Test"),
            ("logs", "📋 Logs"),
            ("help", "❓ Ayuda")
        ]
        
        for tab_id, tab_name in tabs_data:
            # Botón de pestaña
            btn = ctk.CTkButton(
                self.tabs_scroll,
                text=tab_name,
                width=180,
                height=40,
                command=lambda tid=tab_id: self._switch_tab(tid)
            )
            btn.pack(fill="x", pady=2)
            self.tab_buttons[tab_id] = btn
            
            # Frame de contenido (oculto inicialmente)
            content = ctk.CTkFrame(self.content_frame)
            self.tab_contents[tab_id] = content
        
        # Separador y botón para agregar pestañas
        separator = ctk.CTkFrame(self.tabs_scroll, height=2)
        separator.pack(fill="x", pady=(10, 5))
        
        add_tab_btn = ctk.CTkButton(
            self.tabs_scroll,
            text="➕ Agregar Pestaña",
            width=180,
            height=40,
            fg_color=("#27AE60", "#229954"),
            hover_color=("#229954", "#1E8449"),
            command=self._show_add_tab_dialog
        )
        add_tab_btn.pack(fill="x", pady=2)
        
        # Seleccionar primera pestaña por defecto
        self._switch_tab("main")
        
        # Asignar tabs a variables para compatibilidad con código existente
        self.tab_main = self.tab_contents["main"]
        self.tab_config = self.tab_contents["config"]
        self.tab_conditions = self.tab_contents["conditions"]
        self.tab_windows = self.tab_contents["windows"]
        self.tab_targeting = self.tab_contents["targeting"]
        self.tab_looter = self.tab_contents["looter"]
        self.tab_cavebot = self.tab_contents["cavebot"]
        self.tab_screenview = self.tab_contents["screenview"]
        self.tab_test = self.tab_contents["test"]
        self.tab_logs = self.tab_contents["logs"]
        self.tab_help = self.tab_contents["help"]
        self.tab_simple_walking = self.tab_contents["simple_walking"]

        # Construir cada sección
        self._build_main_tab()
        self._build_simple_walking_tab()
        self._build_test_tab()
        self._build_config_tab()
        self._build_conditions_tab()
        self._build_windows_tab()
        self._build_cavebot_tab()
        self._build_targeting_tab()
        self._build_looter_tab()
        self._build_screenview_tab()
        self._build_logs_tab()
        self._build_help_tab()

        # ----------------------------------------------------------
        # Panel de Logs (siempre visible abajo)
        # ----------------------------------------------------------
        self._build_log_panel()

        # ----------------------------------------------------------
        # Inicialización post-build
        # ----------------------------------------------------------
        self._refresh_windows()
        self._auto_connect_obs()
        self.bot.start()
        self._register_hotkeys()
        self._start_status_loop()

        self._gui_ready = True
        self._configure_module_log_tags()
        self._configure_sw_log_tags()
        self._drain_log_queue()

        # Conectar el walk recorder al key_sender del bot
        self.walk_recorder.set_send_key_callback(
            lambda key: self.bot.key_sender.send_key(key)
        )
        
        # Conectar las funciones de test al mismo callback que Simple Walker
        self._test_send_key_callback = lambda key: self.bot.key_sender.send_key(key)

        self.log.ok("GUI iniciada correctamente")

    def _switch_tab(self, tab_id: str):
        """Cambia a la pestaña especificada."""
        if self.current_tab == tab_id:
            return
            
        # Ocultar contenido actual
        if self.current_tab and self.current_tab in self.tab_contents:
            self.tab_contents[self.current_tab].pack_forget()
            # Restaurar color del botón
            self.tab_buttons[self.current_tab].configure(
                fg_color=("gray75", "gray25"),
                hover_color=("gray60", "gray40")
            )
        
        # Mostrar nuevo contenido
        if tab_id in self.tab_contents:
            self.tab_contents[tab_id].pack(fill="both", expand=True, padx=3, pady=3)
            # Resaltar botón activo
            self.tab_buttons[tab_id].configure(
                fg_color=("#1f538d", "#1a4d8c"),
                hover_color=("#2e6da4", "#286090")
            )
            self.current_tab = tab_id

    def add_new_tab(self, tab_id: str, tab_name: str):
        """Agrega una nueva pestaña dinámicamente."""
        if tab_id in self.tab_buttons:
            return  # Ya existe
            
        # Crear botón
        btn = ctk.CTkButton(
            self.tabs_scroll,
            text=tab_name,
            width=180,
            height=40,
            command=lambda tid=tab_id: self._switch_tab(tid)
        )
        btn.pack(fill="x", pady=2)
        self.tab_buttons[tab_id] = btn
        
        # Crear frame de contenido
        content = ctk.CTkFrame(self.content_frame)
        self.tab_contents[tab_id] = content
        
        # Asignar a variable dinámica
        setattr(self, f"tab_{tab_id}", content)

    def _show_add_tab_dialog(self):
        """Muestra un diálogo para agregar una nueva pestaña."""
        dialog = ctk.CTkInputDialog(
            text="Nombre de la nueva pestaña:",
            title="Agregar Nueva Pestaña"
        )
        
        tab_name = dialog.get_input()
        if tab_name and tab_name.strip():
            # Generar ID válido desde el nombre
            tab_id = tab_name.strip().lower().replace(" ", "_").replace("ñ", "n")
            tab_id = "".join(c for c in tab_id if c.isalnum() or c == "_")
            
            if not tab_id:
                messagebox.showerror("Error", "Nombre inválido")
                return
                
            # Agregar la pestaña
            self.add_new_tab(tab_id, tab_name.strip())
            self.log.ok(f"Nueva pestaña agregada: {tab_name}")
            
            # Cambiar a la nueva pestaña
            self._switch_tab(tab_id)

    def _auto_connect_obs(self):
        """Intenta conectar automáticamente a OBS si hay config guardada."""
        if self.config.obs_host:
            success = self.bot.connect_obs()
            if success:
                self.lbl_obs_status.configure(
                    text=f"Estado: Conectado — {self.bot.obs_version}",
                    text_color="#2ECC71",
                )
                self._refresh_obs_sources()
            else:
                self.lbl_obs_status.configure(
                    text="Estado: Auto-conexión fallida (conéctate manualmente)",
                    text_color="#FFAA00",
                )

    # ==================================================================
    # TAB: Principal (Estado del bot)
    # ==================================================================
    def _build_main_tab(self):
        tab = self.tab_main

        # --- Header ---
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 3))

        ctk.CTkLabel(
            header,
            text="⚔️ TIBIA AUTO HEALER",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        self.btn_toggle = ctk.CTkButton(
            header,
            text="▶ ACTIVAR",
            width=130,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2ECC71",
            hover_color="#27AE60",
            command=self._toggle_bot,
        )
        self.btn_toggle.pack(side="right")

        # --- Estado ---
        status_frame = ctk.CTkFrame(tab)
        status_frame.pack(fill="x", padx=8, pady=3)

        self.lbl_status = ctk.CTkLabel(
            status_frame,
            text="Estado: ○ INACTIVO",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#FFAA00",
        )
        self.lbl_status.pack(anchor="w", padx=12, pady=(8, 3))

        # --- Barras HP/MP ---
        bars_frame = ctk.CTkFrame(tab)
        bars_frame.pack(fill="x", padx=8, pady=3)

        # HP
        hp_row = ctk.CTkFrame(bars_frame, fg_color="transparent")
        hp_row.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(hp_row, text="HP:", font=ctk.CTkFont(size=13, weight="bold"), width=30).pack(side="left")
        self.hp_bar = ctk.CTkProgressBar(hp_row, height=20, width=280)
        self.hp_bar.pack(side="left", padx=(4, 8))
        self.hp_bar.set(0)
        self.lbl_hp = ctk.CTkLabel(hp_row, text="N/A", font=ctk.CTkFont(size=13), width=100)
        self.lbl_hp.pack(side="left")

        # MP
        mp_row = ctk.CTkFrame(bars_frame, fg_color="transparent")
        mp_row.pack(fill="x", padx=12, pady=(2, 8))
        ctk.CTkLabel(mp_row, text="MP:", font=ctk.CTkFont(size=13, weight="bold"), width=30).pack(side="left")
        self.mp_bar = ctk.CTkProgressBar(mp_row, height=20, width=280, progress_color="#3498DB")
        self.mp_bar.pack(side="left", padx=(4, 8))
        self.mp_bar.set(0)
        self.lbl_mp = ctk.CTkLabel(mp_row, text="N/A", font=ctk.CTkFont(size=13), width=100)
        self.lbl_mp.pack(side="left")

        # --- Info conexión ---
        info_frame = ctk.CTkFrame(tab)
        info_frame.pack(fill="x", padx=8, pady=3)

        self.lbl_tibia_status = ctk.CTkLabel(
            info_frame, text="Tibia: No conectado", font=ctk.CTkFont(size=11)
        )
        self.lbl_tibia_status.pack(anchor="w", padx=12, pady=(6, 2))

        self.lbl_obs_status = ctk.CTkLabel(
            info_frame, text="OBS: No conectado", font=ctk.CTkFont(size=11)
        )
        self.lbl_obs_status.pack(anchor="w", padx=12, pady=(2, 6))

        self.lbl_fps = ctk.CTkLabel(
            info_frame, text="Capturas/seg: 0.0", font=ctk.CTkFont(size=11)
        )
        self.lbl_fps.pack(anchor="w", padx=12, pady=(2, 2))

        self.lbl_heals = ctk.CTkLabel(
            info_frame, text="Curaciones: 0", font=ctk.CTkFont(size=11)
        )
        self.lbl_heals.pack(anchor="w", padx=12, pady=(2, 2))

        # --- Indicador de calibración v3.1 ---
        self.lbl_calibration = ctk.CTkLabel(
            info_frame,
            text="🎯 Calibración: Pendiente",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FFAA00",
        )
        self.lbl_calibration.pack(anchor="w", padx=12, pady=(2, 2))

        # --- Indicador de módulos activos ---
        self.lbl_modules_status = ctk.CTkLabel(
            info_frame,
            text="📦 Módulos: —",
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
        )
        self.lbl_modules_status.pack(anchor="w", padx=12, pady=(2, 6))

# ==================================================================
# TAB: Configuración de curación
# ==================================================================
    def _build_config_tab(self):
        tab = self.tab_config

        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(tab, label_text="REGLAS DE CURACIÓN")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # --- Reglas de HP ---
        self.rules_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.rules_container.pack(fill="x", padx=4, pady=3)

        self._rebuild_rules_ui()

        # Botones agregar/quitar
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=4, pady=3)

        ctk.CTkButton(
            btn_row, text="+ Agregar regla", width=140, command=self._add_rule
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btn_row,
            text="- Quitar última",
            width=140,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=self._remove_last_rule,
        ).pack(side="left", padx=4)

        # --- Curación de Mana ---
        mana_frame = ctk.CTkFrame(scroll)
        mana_frame.pack(fill="x", padx=4, pady=(10, 3))
        ctk.CTkLabel(mana_frame, text="CURACIÓN DE MANA", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(6, 3)
        )

        # Checkbox para activar mana healing
        self.mana_enabled_var = ctk.BooleanVar(value=self.config.mana_heal.get("enabled", False))
        mana_enable_row = ctk.CTkFrame(mana_frame, fg_color="transparent")
        mana_enable_row.pack(fill="x", padx=8, pady=3)
        ctk.CTkCheckBox(
            mana_enable_row, text="Activar curación de mana", 
            variable=self.mana_enabled_var, command=self._save_mana_config
        ).pack(side="left")

        # Frame para las reglas de mana (dinámico como HP)
        self.mana_rules_frame = ctk.CTkFrame(mana_frame, fg_color="transparent")
        self.mana_rules_frame.pack(fill="x", padx=8, pady=3)
        
        # Botones para agregar/eliminar reglas de mana
        mana_buttons_row = ctk.CTkFrame(mana_frame, fg_color="transparent")
        mana_buttons_row.pack(fill="x", padx=8, pady=3)
        
        ctk.CTkButton(
            mana_buttons_row, text="Agregar Condición", 
            command=self._add_mana_rule, width=120
        ).pack(side="left", padx=(0, 8))
        
        ctk.CTkButton(
            mana_buttons_row, text="Eliminar Última", 
            command=self._remove_last_mana_rule, width=120
        ).pack(side="left")

        # Variables para las reglas de mana (dinámicas)
        self._mana_rule_vars: List[Tuple[ctk.StringVar, ctk.StringVar, ctk.StringVar, ctk.StringVar]] = []
        self._mana_rule_frames: List[ctk.CTkFrame] = []
        
        # Construir UI inicial de reglas de mana
        self._rebuild_mana_rules_ui()

        # --- Parámetros ---
        params_frame = ctk.CTkFrame(scroll)
        params_frame.pack(fill="x", padx=4, pady=(10, 3))
        ctk.CTkLabel(params_frame, text="PARÁMETROS", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(6, 3)
        )

        # Cooldown
        p_row1 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row1.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(p_row1, text="Cooldown entre curaciones (seg):").pack(side="left")
        self.cooldown_var = ctk.StringVar(value=str(self.config.cooldown))
        ctk.CTkEntry(p_row1, textvariable=self.cooldown_var, width=70).pack(side="left", padx=4)

        # Intervalo
        p_row2 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row2.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(p_row2, text="Intervalo de chequeo (seg):").pack(side="left")
        self.interval_var = ctk.StringVar(value=str(self.config.check_interval))
        ctk.CTkEntry(p_row2, textvariable=self.interval_var, width=70).pack(side="left", padx=4)

        # Hotkeys
        p_row3 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row3.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(p_row3, text="Tecla Activar/Desactivar:").pack(side="left")
        self.toggle_key_var = ctk.StringVar(value=self.config.hotkey_toggle)
        ctk.CTkOptionMenu(
            p_row3, variable=self.toggle_key_var, values=AVAILABLE_KEYS, width=80
        ).pack(side="left", padx=4)

        p_row4 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row4.pack(fill="x", padx=8, pady=(3, 8))
        ctk.CTkLabel(p_row4, text="Tecla Salir:").pack(side="left")
        self.exit_key_var = ctk.StringVar(value=self.config.hotkey_exit)
        ctk.CTkOptionMenu(
            p_row4, variable=self.exit_key_var, values=AVAILABLE_KEYS, width=80
        ).pack(side="left", padx=4)

        # Botón guardar
        ctk.CTkButton(
            scroll,
            text="💾 Guardar Configuración",
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save_all_config,
        ).pack(fill="x", padx=4, pady=10)

    def _rebuild_rules_ui(self):
        """Reconstruye los widgets de reglas de HP."""
        for frame in self._rule_frames:
            frame.destroy()
        self._rule_frames.clear()

        self._rule_vars = []

        for i, level in enumerate(self.config.heal_levels):
            frame = ctk.CTkFrame(self.rules_container)
            frame.pack(fill="x", pady=3)

            ctk.CTkLabel(frame, text=f"Nivel {i + 1}:", width=60).pack(side="left", padx=(8, 4))
            ctk.CTkLabel(frame, text="HP <").pack(side="left")

            thresh_var = ctk.StringVar(value=str(int(level["threshold"] * 100)))
            ctk.CTkEntry(frame, textvariable=thresh_var, width=50).pack(side="left", padx=3)
            ctk.CTkLabel(frame, text="% → Tecla:").pack(side="left")

            key_var = ctk.StringVar(value=level.get("key", "F1"))
            ctk.CTkOptionMenu(
                frame, variable=key_var, values=AVAILABLE_KEYS, width=80
            ).pack(side="left", padx=4)

            ctk.CTkLabel(frame, text="Desc:").pack(side="left")
            desc_var = ctk.StringVar(value=level.get("description", ""))
            ctk.CTkEntry(frame, textvariable=desc_var, width=110).pack(side="left", padx=4)

            self._rule_vars.append((thresh_var, key_var, desc_var))
            self._rule_frames.append(frame)

    def _add_rule(self):
        self.config.add_heal_level(0.50, "F1", "Nueva regla")
        self._rebuild_rules_ui()

    def _remove_last_rule(self):
        levels = self.config.heal_levels
        if len(levels) > 0:
            self.config.remove_heal_level(len(levels) - 1)
            self._rebuild_rules_ui()

    def _add_mana_rule(self):
        """Agrega una nueva regla de mana."""
        new_level = {
            "threshold": 0.50,
            "comparison": "<=",
            "key": "F3",
            "description": "Mana Potion",
        }
        self.config.add_mana_level(new_level)
        self._rebuild_mana_rules_ui()

    def _remove_last_mana_rule(self):
        """Elimina la última regla de mana."""
        levels = self.config.get_mana_levels()
        if len(levels) > 0:
            self.config.remove_mana_level(len(levels) - 1)
            self._rebuild_mana_rules_ui()

    def _rebuild_mana_rules_ui(self):
        """Reconstruye la UI de las reglas de mana."""
        # Limpiar widgets existentes
        for frame in self._mana_rule_frames:
            frame.destroy()
        self._mana_rule_frames.clear()
        self._mana_rule_vars.clear()

        # Crear widgets para cada nivel
        mana_levels = self.config.get_mana_levels()
        for i, level in enumerate(mana_levels):
            frame = ctk.CTkFrame(self.mana_rules_frame, fg_color="transparent")
            frame.pack(fill="x", pady=2)
            self._mana_rule_frames.append(frame)

            # Dropdown de comparación
            comp_var = ctk.StringVar(value=level.get("comparison", "<="))
            ctk.CTkOptionMenu(
                frame, variable=comp_var, values=["<", "<="], width=50
            ).pack(side="left", padx=(0, 4))

            # Threshold
            thresh_var = ctk.StringVar(value=str(int(level.get("threshold", 0.50) * 100)))
            ctk.CTkEntry(frame, textvariable=thresh_var, width=50).pack(side="left", padx=3)
            ctk.CTkLabel(frame, text="% →").pack(side="left", padx=(0, 4))

            # Key
            key_var = ctk.StringVar(value=level.get("key", "F3"))
            ctk.CTkOptionMenu(
                frame, variable=key_var, values=AVAILABLE_KEYS, width=80
            ).pack(side="left", padx=4)

            # Description
            desc_var = ctk.StringVar(value=level.get("description", "Mana Potion"))
            ctk.CTkEntry(frame, textvariable=desc_var, width=150).pack(side="left", padx=4)

            # Guardar variables
            self._mana_rule_vars.append((comp_var, thresh_var, key_var, desc_var))

    def _save_mana_config(self):
        """Guarda la configuración de mana desde la UI."""
        # Guardar enabled
        current_mana = self.config.mana_heal.copy()
        current_mana["enabled"] = self.mana_enabled_var.get()
        
        # Guardar niveles desde las variables
        new_levels = []
        for comp_var, thresh_var, key_var, desc_var in self._mana_rule_vars:
            try:
                thresh = int(thresh_var.get()) / 100.0
            except ValueError:
                thresh = 0.50
            
            new_levels.append({
                "threshold": max(0.01, min(1.0, thresh)),
                "comparison": comp_var.get(),
                "key": key_var.get(),
                "description": desc_var.get(),
            })
        
        # Ordenar de mayor a menor threshold
        new_levels.sort(key=lambda x: x["threshold"], reverse=True)
        current_mana["levels"] = new_levels
        
        self.config.mana_heal = current_mana

    def _save_all_config(self):
        """Guarda toda la configuración desde los widgets de la GUI."""
        # Reglas de HP
        new_levels = []
        for thresh_var, key_var, desc_var in self._rule_vars:
            try:
                t = int(thresh_var.get()) / 100.0
            except ValueError:
                t = 0.50
            new_levels.append({
                "threshold": max(0.01, min(1.0, t)),
                "key": key_var.get(),
                "description": desc_var.get(),
            })
        new_levels.sort(key=lambda x: x["threshold"], reverse=True)
        self.config.heal_levels = new_levels

        # Mana
        self._save_mana_config()

        # Parámetros
        try:
            self.config.cooldown = float(self.cooldown_var.get())
        except ValueError:
            pass
        try:
            self.config.check_interval = float(self.interval_var.get())
        except ValueError:
            pass

        # Hotkeys
        old_toggle = self.config.hotkey_toggle
        old_exit = self.config.hotkey_exit
        self.config.hotkey_toggle = self.toggle_key_var.get()
        self.config.hotkey_exit = self.exit_key_var.get()

        # Re-registrar hotkeys si cambiaron
        if old_toggle != self.config.hotkey_toggle or old_exit != self.config.hotkey_exit:
            self._unregister_hotkeys()
            self._register_hotkeys()

        # Guardar en disco
        self.config.save()
        self._rebuild_rules_ui()
        self._rebuild_mana_rules_ui()
        self.log.ok("Configuración guardada exitosamente")

    # ==================================================================
    # TAB: Condiciones (sistema de estado)
    # ==================================================================
    def _build_conditions_tab(self):
        tab = self.tab_conditions
        
        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(tab, label_text="🩺 CONDICIONES — Auto Haste, Paralyze, Poison")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # === Activador principal ===
        main_frame = ctk.CTkFrame(scroll)
        main_frame.pack(fill="x", padx=5, pady=5)
        
        # Enable/Disable principal
        self.conditions_enabled_var = ctk.BooleanVar(value=self.config.conditions.get("enabled", False))
        ctk.CTkCheckBox(
            main_frame,
            text="🩺 Activar Sistema de Condiciones",
            variable=self.conditions_enabled_var,
            command=self._on_conditions_toggle
        ).pack(anchor="w", padx=10, pady=5)
        
        # Botón de recalibración
        ctk.CTkButton(
            main_frame,
            text="🔄 Recalibrar Barras",
            width=150,
            command=self._force_conditions_calibration
        ).pack(anchor="w", padx=10, pady=2)
        
        # === Configuración individual ===
        # Frame para controles dinámicos
        self.conditions_frame = ctk.CTkFrame(scroll)
        self.conditions_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            self.conditions_frame, text="⚙️ Configuración Individual", 
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10, pady=(5, 10))
        
        # Contenedor scrollable para todas las condiciones
        self.conditions_scroll_frame = ctk.CTkScrollableFrame(self.conditions_frame)
        self.conditions_scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Generar dinámicamente los controles para cada condición
        self._build_conditions_controls()
        
        # Separador visual
        separator = ctk.CTkFrame(self.conditions_scroll_frame)
        separator.pack(fill="x", padx=5, pady=10)
        
        # Botones de acción
        actions_frame = ctk.CTkFrame(self.conditions_frame)
        actions_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(
            actions_frame, text="🔄 Recalibrar Todo", width=150,
            command=self._force_conditions_calibration
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            actions_frame, text="💾 Guardar Configuración", width=150,
            command=self._save_all_conditions_config
        ).pack(side="left", padx=5)
        
        # === Información ===
        info_frame = ctk.CTkFrame(scroll)
        info_frame.pack(fill="x", padx=5, pady=10)
        
        info_text = (
            "📋 SISTEMA DE CONDICIONES\n\n"
            "Este sistema detecta automáticamente estados como:\n"
            "• 🏃 Haste - Ausencia de lentitud\n"
            "• ⚡ Paralyze - Parálisis del personaje\n"
            "• ☠️ Poison - Personaje envenenado\n\n"
            "El bot monitorea la barra de condiciones (debajo de la barra de mana) "
            "y activa los hechizos configurados cuando detecta alguna condición.\n\n"
            "💡 La calibración es automática y se adapta a cambios en los paneles del juego."
        )
        
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=11),
            justify="left",
            text_color="#CCCCCC"
        ).pack(anchor="w", padx=10, pady=5)

    # ==================================================================
    # TAB: Ventanas
    # ==================================================================
    def _build_windows_tab(self):
        tab = self.tab_windows

        scroll = ctk.CTkScrollableFrame(tab, label_text="CONEXIONES")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # === OBS WebSocket ===
        obs_frame = ctk.CTkFrame(scroll)
        obs_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(
            obs_frame, text="🔌 OBS WebSocket", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(8, 4))

        # Host y Puerto
        conn_row = ctk.CTkFrame(obs_frame, fg_color="transparent")
        conn_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(conn_row, text="Host:").pack(side="left")
        self.obs_host_var = ctk.StringVar(value=self.config.obs_host)
        ctk.CTkEntry(conn_row, textvariable=self.obs_host_var, width=140).pack(side="left", padx=(3, 10))
        ctk.CTkLabel(conn_row, text="Puerto:").pack(side="left")
        self.obs_port_var = ctk.StringVar(value=str(self.config.obs_port))
        ctk.CTkEntry(conn_row, textvariable=self.obs_port_var, width=70).pack(side="left", padx=3)

        # Password
        pass_row = ctk.CTkFrame(obs_frame, fg_color="transparent")
        pass_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(pass_row, text="Contraseña:").pack(side="left")
        self.obs_pass_var = ctk.StringVar(value=self.config.obs_password)
        ctk.CTkEntry(pass_row, textvariable=self.obs_pass_var, width=200, show="*").pack(side="left", padx=3)

        # Botones conectar/desconectar
        btn_row_obs = ctk.CTkFrame(obs_frame, fg_color="transparent")
        btn_row_obs.pack(fill="x", padx=10, pady=5)

        self.btn_obs_connect = ctk.CTkButton(
            btn_row_obs,
            text="🔗 Conectar",
            width=140,
            fg_color="#2ECC71",
            hover_color="#27AE60",
            command=self._connect_obs,
        )
        self.btn_obs_connect.pack(side="left", padx=5)

        self.btn_obs_disconnect = ctk.CTkButton(
            btn_row_obs,
            text="⛓️‍💥 Desconectar",
            width=140,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=self._disconnect_obs,
        )
        self.btn_obs_disconnect.pack(side="left", padx=5)

        self.lbl_obs_status = ctk.CTkLabel(
            obs_frame, text="Estado: No conectado", font=ctk.CTkFont(size=12),
            text_color="#E74C3C",
        )
        self.lbl_obs_status.pack(anchor="w", padx=10, pady=(2, 4))

        # Fuente OBS
        source_frame = ctk.CTkFrame(obs_frame, fg_color="transparent")
        source_frame.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(source_frame, text="Fuente OBS:").pack(side="left")

        self.obs_source_var = ctk.StringVar(value=self.config.obs_source_name or "(seleccionar)")
        self.obs_source_combo = ctk.CTkOptionMenu(
            source_frame,
            variable=self.obs_source_var,
            values=["(conectar primero)"],
            width=300,
            command=self._on_obs_source_selected,
        )
        self.obs_source_combo.pack(side="left", padx=5)

        ctk.CTkButton(
            source_frame, text="🔄", width=35, command=self._refresh_obs_sources
        ).pack(side="left", padx=3)

        self.lbl_obs_source_info = ctk.CTkLabel(
            obs_frame, text="", font=ctk.CTkFont(size=11)
        )
        self.lbl_obs_source_info.pack(anchor="w", padx=10, pady=(2, 8))

        # === Tibia Window ===
        tibia_frame = ctk.CTkFrame(scroll)
        tibia_frame.pack(fill="x", padx=5, pady=(15, 5))
        ctk.CTkLabel(
            tibia_frame, text="🎮 Cliente Tibia", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(8, 4))

        self.tibia_combo_var = ctk.StringVar(value="(ninguno)")
        self.tibia_combo = ctk.CTkOptionMenu(
            tibia_frame,
            variable=self.tibia_combo_var,
            values=["(ninguno)"],
            width=450,
            command=self._on_tibia_selected,
        )
        self.tibia_combo.pack(fill="x", padx=10, pady=3)

        self.lbl_tibia_info = ctk.CTkLabel(
            tibia_frame, text="HWND: — | Tamaño: —", font=ctk.CTkFont(size=11)
        )
        self.lbl_tibia_info.pack(anchor="w", padx=10, pady=(2, 4))

        ctk.CTkButton(
            tibia_frame, text="🔄 Refrescar ventanas Tibia", command=self._refresh_windows
        ).pack(fill="x", padx=10, pady=(2, 8))

        # === Acciones ===
        actions_frame = ctk.CTkFrame(scroll)
        actions_frame.pack(fill="x", padx=5, pady=(15, 5))

        ctk.CTkButton(
            actions_frame,
            text="📸 Tomar captura de prueba",
            command=self._take_test_capture,
        ).pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            actions_frame,
            text="🔬 Mostrar análisis de barras",
            command=self._show_bar_analysis,
        ).pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            actions_frame,
            text="🎯 Recalibrar barras",
            command=self._run_calibration,
        ).pack(fill="x", padx=10, pady=5)

        # Preview
        self.preview_label = ctk.CTkLabel(
            scroll, text="", width=500, height=300
        )
        self.preview_label.pack(padx=5, pady=10)

    def _connect_obs(self):
        """Conecta a OBS WebSocket con los parámetros de la GUI."""
        host = self.obs_host_var.get().strip() or "localhost"
        try:
            port = int(self.obs_port_var.get().strip())
        except ValueError:
            port = 4455
        password = self.obs_pass_var.get()
        source = self.obs_source_var.get()
        if source in ("(conectar primero)", "(seleccionar)"):
            source = ""

        success = self.bot.connect_obs(
            host=host, port=port, password=password, source_name=source
        )
        if success:
            self.lbl_obs_status.configure(
                text=f"Estado: Conectado — {self.bot.obs_version}",
                text_color="#2ECC71",
            )
            self._refresh_obs_sources()
        else:
            self.lbl_obs_status.configure(
                text=f"Estado: Error — {self.bot.capture.last_error}",
                text_color="#E74C3C",
            )

    def _disconnect_obs(self):
        """Desconecta de OBS WebSocket."""
        self.bot.disconnect_obs()
        self.lbl_obs_status.configure(
            text="Estado: No conectado", text_color="#E74C3C"
        )
        self.obs_source_combo.configure(values=["(conectar primero)"])
        self.obs_source_var.set("(conectar primero)")

    # Mapa de tipos OBS → nombre amigable para el dropdown
    OBS_KIND_LABELS: Dict[str, str] = {
        "game_capture": "🎮 Juego",
        "window_capture": "🪟 Ventana",
        "monitor_capture": "🖥️ Monitor",
        "dshow_input": "📹 Cámara",
        "image_source": "🖼️ Imagen",
        "ffmpeg_source": "🎞️ Media",
        "vlc_source": "🎞️ VLC",
        "browser_source": "🌐 Navegador",
        "text_gdiplus": "📝 Texto",
        "text_ft2_source": "📝 Texto",
        "color_source": "🎨 Color",
        "color_source_v3": "🎨 Color",
        "ndi_source": "📡 NDI",
    }

    def _refresh_obs_sources(self):
        """Refresca la lista de fuentes de VIDEO disponibles en OBS."""
        if not self.bot.projector_connected and not self.bot.capture.is_connected:
            return

        # Solo fuentes de video (excluye audio automáticamente)
        sources = self.bot.get_obs_sources()
        scenes = self.bot.get_obs_scenes()

        # Mapeo nombre limpio → nombre display
        self._obs_source_map: Dict[str, str] = {}  # display_name → clean_name

        all_display_names = []

        # Fuentes de video con etiqueta de tipo
        for s in sources:
            name = s.get("name", "")
            kind = s.get("kind", "")
            label = self.OBS_KIND_LABELS.get(kind, f"📦 {kind}")
            display = f"{label} | {name}"
            all_display_names.append(display)
            self._obs_source_map[display] = name

        # Escenas (todas pueden hacer screenshot)
        for scene in scenes:
            if scene:
                display = f"🎬 Escena | {scene}"
                all_display_names.append(display)
                self._obs_source_map[display] = scene

        if all_display_names:
            self.obs_source_combo.configure(values=all_display_names)
            # Si hay fuente guardada, seleccionarla
            saved = self.config.obs_source_name
            found = False
            if saved:
                for display_name, clean_name in self._obs_source_map.items():
                    if clean_name == saved:
                        self.obs_source_var.set(display_name)
                        found = True
                        break
            if not found:
                self.obs_source_var.set(all_display_names[0])
            self._on_obs_source_selected(self.obs_source_var.get())
            n_src = len(sources)
            n_sce = len(scenes)
            self.lbl_obs_source_info.configure(
                text=f"{n_src} fuentes de video + {n_sce} escenas (audio excluido)"
            )
        else:
            self.obs_source_combo.configure(values=["(sin fuentes de video)"])
            self.obs_source_var.set("(sin fuentes de video)")

    def _on_obs_source_selected(self, display_name: str):
        """Cuando el usuario selecciona una fuente OBS."""
        if display_name in (
            "(conectar primero)", "(sin fuentes)",
            "(seleccionar)", "(sin fuentes de video)",
        ):
            return
        # Buscar nombre real en el mapa
        source_map = getattr(self, "_obs_source_map", {})
        clean_name = source_map.get(display_name, display_name)
        self.bot.set_obs_source(clean_name)

    def _refresh_windows(self):
        """Refresca las listas de ventanas de Tibia."""
        self._tibia_windows = find_tibia_windows()

        # Actualizar combo Tibia
        tibia_titles = [w["title"] for w in self._tibia_windows]
        if tibia_titles:
            self.tibia_combo.configure(values=tibia_titles)
            # Si hay una guardada, seleccionarla
            saved = self.config.get("tibia_window_title", "")
            found = False
            for t in tibia_titles:
                if saved and saved.lower() in t.lower():
                    self.tibia_combo_var.set(t)
                    found = True
                    break
            if not found:
                self.tibia_combo_var.set(tibia_titles[0])
            self._on_tibia_selected(self.tibia_combo_var.get())
        else:
            self.tibia_combo.configure(values=["(ninguno)"])
            self.tibia_combo_var.set("(ninguno)")
            self.lbl_tibia_info.configure(text="HWND: — | Tamaño: —")

        self.bot.detect_windows()
        self.log.info(f"Ventanas Tibia encontradas: {len(self._tibia_windows)}")

    def _on_tibia_selected(self, title: str):
        for w in self._tibia_windows:
            if w["title"] == title:
                self.bot.set_tibia_window(w["hwnd"], w["title"])
                self.lbl_tibia_info.configure(
                    text=f"HWND: 0x{w['hwnd']:08X} | Tamaño: {w['width']}x{w['height']}"
                )
                return

    def _take_test_capture(self):
        img = self.bot.take_test_capture()
        if img is not None:
            self._show_preview(img, "Captura de prueba")
        else:
            messagebox.showwarning(
                "Sin captura",
                "No se pudo tomar captura.\n\n"
                "Verifica que:\n"
                "1. OBS esté abierto y el WebSocket activo\n"
                "2. Estés conectado (botón 'Conectar')\n"
                "3. Hayas seleccionado una fuente válida",
            )

    def _show_bar_analysis(self):
        img = self.bot.generate_analysis_image()
        if img is not None:
            self._show_preview(img, "Análisis de barras")
        else:
            messagebox.showwarning(
                "Sin análisis",
                "No se pudo generar el análisis. ¿Está el proyector OBS abierto?",
            )

    def _run_calibration(self):
        result = self.bot.run_calibration()
        if result.get("hp_row") is not None:
            messagebox.showinfo(
                "Calibración",
                f"✅ Calibración exitosa:\n"
                f"- Barra HP en fila: {result['hp_row']}\n"
                f"- Barra MP en fila: {result.get('mp_row', 'N/A')}\n"
                f"- Ancho máximo: {result['bar_max_width']}px",
            )
        else:
            messagebox.showwarning(
                "Calibración",
                "No se encontraron barras.\n"
                "Asegúrate de que el proyector OBS muestre Tibia.",
            )

    def _show_preview(self, img: np.ndarray, title: str = ""):
        """Muestra una imagen en el preview del tab de ventanas."""
        # Redimensionar para la preview
        max_w, max_h = 500, 300
        h, w = img.shape[:2]
        scale = min(max_w / w, max_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(img, (new_w, new_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))

        self.preview_label.configure(image=ctk_img, text="")
        self.preview_label._ctk_image = ctk_img  # evitar garbage collection

    # ==================================================================
    # TAB: Cavebot (v2.0)
    # ==================================================================
    def _build_cavebot_tab(self):
        tab = self.tab_cavebot
        scroll = ctk.CTkScrollableFrame(tab, label_text="🗺️ CAVEBOT — Navegación por Waypoints")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Habilitar ---
        enable_frame = ctk.CTkFrame(scroll)
        enable_frame.pack(fill="x", padx=5, pady=5)

        self.cb_cavebot_enabled = ctk.CTkSwitch(
            enable_frame, text="Cavebot habilitado",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._toggle_cavebot,
        )
        self.cb_cavebot_enabled.pack(anchor="w", padx=15, pady=10)

        # --- Ruta ---
        route_frame = ctk.CTkFrame(scroll)
        route_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(route_frame, text="RUTA", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        route_btns = ctk.CTkFrame(route_frame, fg_color="transparent")
        route_btns.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(route_btns, text="📂 Cargar Ruta", width=130, command=self._load_route).pack(side="left", padx=3)
        ctk.CTkButton(route_btns, text="💾 Guardar Ruta", width=130, command=self._save_route).pack(side="left", padx=3)
        ctk.CTkButton(route_btns, text="🗑️ Limpiar", width=100, fg_color="#E74C3C", command=self._clear_route).pack(side="left", padx=3)

        self.lbl_route_name = ctk.CTkLabel(route_frame, text="Ruta: (ninguna cargada)", font=ctk.CTkFont(size=12))
        self.lbl_route_name.pack(anchor="w", padx=15, pady=(0, 8))

        # --- Lista de Waypoints ---
        wp_frame = ctk.CTkFrame(scroll)
        wp_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(wp_frame, text="WAYPOINTS", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self.wp_listbox = ctk.CTkTextbox(wp_frame, height=200, font=ctk.CTkFont(family="Consolas", size=11))
        self.wp_listbox.pack(fill="x", padx=10, pady=5)
        self.wp_listbox.insert("1.0", "(Sin waypoints)")
        self.wp_listbox.configure(state="disabled")

        # --- Agregar waypoint manual ---
        add_frame = ctk.CTkFrame(scroll)
        add_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(add_frame, text="AGREGAR WAYPOINT", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        # Tipo de waypoint
        type_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        type_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(type_row, text="Tipo:", width=80).pack(side="left")

        wp_types = [
            "WALK", "ROPE", "SHOVEL", "LADDER", "DOOR", "STAIRS",
            "STAND", "SINGLE_MOVE", "PICK", "MACHETE", "SEWER",
            "RIGHT_CLICK_USE", "NPC_TALK", "DEPOSIT_GOLD",
            "DEPOSIT_ITEMS", "TRAVEL", "BUY_BACKPACK",
            "DROP_FLASKS", "REFILL_CHECKER", "REFILL", "LABEL",
        ]
        self.cb_wp_type = ctk.CTkComboBox(type_row, values=wp_types, width=180)
        self.cb_wp_type.set("WALK")
        self.cb_wp_type.pack(side="left", padx=5)

        # Coordenadas
        coord_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        coord_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(coord_row, text="X:", width=25).pack(side="left")
        self.entry_wp_x = ctk.CTkEntry(coord_row, width=60)
        self.entry_wp_x.insert(0, "0")
        self.entry_wp_x.pack(side="left", padx=(3, 10))
        ctk.CTkLabel(coord_row, text="Y:", width=25).pack(side="left")
        self.entry_wp_y = ctk.CTkEntry(coord_row, width=60)
        self.entry_wp_y.insert(0, "0")
        self.entry_wp_y.pack(side="left", padx=(3, 10))
        ctk.CTkLabel(coord_row, text="Z:", width=25).pack(side="left")
        self.entry_wp_z = ctk.CTkEntry(coord_row, width=40)
        self.entry_wp_z.insert(0, "7")
        self.entry_wp_z.pack(side="left", padx=3)

        # Label / opciones
        opt_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        opt_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(opt_row, text="Etiqueta:", width=70).pack(side="left")
        self.entry_wp_label = ctk.CTkEntry(opt_row, width=150, placeholder_text="nombre del wp")
        self.entry_wp_label.pack(side="left", padx=(3, 10))
        ctk.CTkLabel(opt_row, text="Ciudad/NPC:", width=90).pack(side="left")
        self.entry_wp_option = ctk.CTkEntry(opt_row, width=150, placeholder_text="Thais, Venore...")
        self.entry_wp_option.pack(side="left", padx=3)

        add_btn_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        add_btn_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(
            add_btn_row, text="+ Agregar WP", width=140,
            fg_color="#2ECC71", hover_color="#27AE60",
            command=self._add_waypoint_manual,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            add_btn_row, text="- Quitar Último", width=140,
            fg_color="#E74C3C", hover_color="#C0392B",
            command=self._remove_last_waypoint,
        ).pack(side="left", padx=3)

        # --- Hotkeys de herramientas ---
        tools_frame = ctk.CTkFrame(scroll)
        tools_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(tools_frame, text="HOTKEYS DE HERRAMIENTAS", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            tools_frame,
            text="Configura las teclas que el bot usará para Rope/Shovel/Pick/Machete",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack(anchor="w", padx=10, pady=(0, 5))

        hotkeys_cfg = self.config.hotkeys
        self._hotkey_vars: Dict[str, ctk.StringVar] = {}

        tool_keys = [
            ("rope", "🪢 Rope:"),
            ("shovel", "⛏️ Shovel:"),
            ("pick", "🔨 Pick:"),
            ("machete", "🗡️ Machete:"),
            ("food", "🍖 Food:"),
            ("light", "💡 Light:"),
        ]

        for key_id, label in tool_keys:
            row = ctk.CTkFrame(tools_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(row, text=label, width=120, anchor="w").pack(side="left")
            var = ctk.StringVar(value=hotkeys_cfg.get(key_id, ""))
            ctk.CTkOptionMenu(
                row, variable=var, values=[""] + AVAILABLE_KEYS, width=90,
            ).pack(side="left", padx=5)
            self._hotkey_vars[key_id] = var

        # --- Configuración ---
        cfg_frame = ctk.CTkFrame(scroll)
        cfg_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(cfg_frame, text="CONFIGURACIÓN", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        row1 = ctk.CTkFrame(cfg_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row1, text="Modo caminata:", width=120).pack(side="left")
        self.cb_walk_mode = ctk.CTkComboBox(row1, values=["click", "arrow"], width=120)
        self.cb_walk_mode.set(self.config.cavebot.get("walk_mode", "click"))
        self.cb_walk_mode.pack(side="left", padx=5)

        self.cb_cyclic = ctk.CTkSwitch(cfg_frame, text="Ruta cíclica")
        self.cb_cyclic.pack(anchor="w", padx=15, pady=5)
        if self.config.cavebot.get("cyclic", True):
            self.cb_cyclic.select()

        # NPC config
        npc_frame = ctk.CTkFrame(scroll)
        npc_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(npc_frame, text="NPC INTERACCIÓN", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        npc_cfg = self.config.npc
        npc_row1 = ctk.CTkFrame(npc_frame, fg_color="transparent")
        npc_row1.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(npc_row1, text="Delay entre pasos (seg):", width=180).pack(side="left")
        self.entry_npc_step_delay = ctk.CTkEntry(npc_row1, width=60)
        self.entry_npc_step_delay.insert(0, str(npc_cfg.get("step_delay", 0.8)))
        self.entry_npc_step_delay.pack(side="left", padx=5)

        npc_row2 = ctk.CTkFrame(npc_frame, fg_color="transparent")
        npc_row2.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(npc_row2, text="Delay al hablar (seg):", width=180).pack(side="left")
        self.entry_npc_say_delay = ctk.CTkEntry(npc_row2, width=60)
        self.entry_npc_say_delay.insert(0, str(npc_cfg.get("say_delay", 1.0)))
        self.entry_npc_say_delay.pack(side="left", padx=5)

        # --- Guardar cavebot ---
        ctk.CTkButton(
            scroll,
            text="💾 Guardar Config Cavebot",
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_cavebot_config,
        ).pack(fill="x", padx=5, pady=8)

        # --- Estado ---
        state_frame = ctk.CTkFrame(scroll)
        state_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(state_frame, text="ESTADO", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self.lbl_cavebot_state = ctk.CTkLabel(state_frame, text="Estado: idle | WP: 0/0 | Pasos: 0", font=ctk.CTkFont(size=12))
        self.lbl_cavebot_state.pack(anchor="w", padx=15, pady=(0, 10))

        # --- Log del Cavebot ---
        log_frame_cb = ctk.CTkFrame(scroll)
        log_frame_cb.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(log_frame_cb, text="📋 LOG CAVEBOT", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        self.log_cavebot = ctk.CTkTextbox(log_frame_cb, height=120, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_cavebot.pack(fill="x", padx=10, pady=(2, 8))
        self.log_cavebot.configure(state="disabled")

        # --- Botón Calibrar ---
        ctk.CTkButton(
            scroll, text="🎯 Calibrar Regiones del Juego", height=36,
            font=ctk.CTkFont(weight="bold"), fg_color="#8E44AD", hover_color="#7D3C98",
            command=self._force_recalibrate,
        ).pack(fill="x", padx=5, pady=5)

    def _save_cavebot_config(self):
        """Guarda toda la configuración del cavebot desde la GUI."""
        # Cavebot
        cavebot = self.config.cavebot
        cavebot["walk_mode"] = self.cb_walk_mode.get()
        cavebot["cyclic"] = bool(self.cb_cyclic.get())
        self.config.cavebot = cavebot

        # Hotkeys
        hotkeys = self.config.hotkeys
        for key_id, var in self._hotkey_vars.items():
            hotkeys[key_id] = var.get()
        self.config.hotkeys = hotkeys

        # NPC
        npc = self.config.npc
        try:
            npc["step_delay"] = float(self.entry_npc_step_delay.get())
        except ValueError:
            pass
        try:
            npc["say_delay"] = float(self.entry_npc_say_delay.get())
        except ValueError:
            pass
        self.config.npc = npc

        self.config.save()
        # Re-configure engine with new settings
        self.bot.cavebot_engine.configure(cavebot)
        self.log.ok("Configuración del Cavebot guardada")

    def _add_waypoint_manual(self):
        """Agrega un waypoint desde los campos de la GUI."""
        wp_type = self.cb_wp_type.get().lower()
        label = self.entry_wp_label.get().strip()

        # Usar el label como nombre de marca (o tipo por defecto)
        mark_name = label if label else wp_type

        # Agregar al engine
        self.bot.cavebot_engine.add_waypoint(mark_name, wp_type)
        self._refresh_waypoint_list()

    def _remove_last_waypoint(self):
        """Elimina el último waypoint."""
        self.bot.cavebot_engine.remove_last_waypoint()
        self._refresh_waypoint_list()

    def _toggle_cavebot(self):
        enabled = self.cb_cavebot_enabled.get()
        self.config.cavebot_enabled = bool(enabled)
        self.config.save()
        # Wire to dispatcher + engine
        if enabled:
            self.bot.dispatcher.enable_module("cavebot")
            self.bot.cavebot_engine.start()
        else:
            self.bot.dispatcher.disable_module("cavebot")
            self.bot.cavebot_engine.stop()
        self.log.info(f"Cavebot {'habilitado' if enabled else 'deshabilitado'}")

    def _load_route(self):
        path = filedialog.askopenfilename(
            title="Cargar ruta",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            initialdir="routes",
        )
        if path:
            success = self.bot.cavebot_engine.load_route(path)
            if success:
                self.lbl_route_name.configure(text=f"Ruta: {os.path.basename(path)}")
                self._refresh_waypoint_list()
            else:
                self.log.warning(f"Error cargando ruta: {path}")

    def _save_route(self):
        path = filedialog.asksaveasfilename(
            title="Guardar ruta",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialdir="routes",
        )
        if path:
            self.bot.cavebot_engine.save_route(path)

    def _clear_route(self):
        self.bot.cavebot_engine.clear_route()
        self.wp_listbox.configure(state="normal")
        self.wp_listbox.delete("1.0", "end")
        self.wp_listbox.insert("1.0", "(Sin waypoints)")
        self.wp_listbox.configure(state="disabled")
        self.lbl_route_name.configure(text="Ruta: (ninguna cargada)")

    def _refresh_waypoint_list(self):
        """Actualiza el textbox de waypoints desde el engine."""
        wps = self.bot.cavebot_engine.waypoints
        self.wp_listbox.configure(state="normal")
        self.wp_listbox.delete("1.0", "end")
        if not wps:
            self.wp_listbox.insert("1.0", "(Sin waypoints)")
        else:
            for i, wp in enumerate(wps):
                prefix = "→ " if wp.status else "  "
                line = f"{prefix}#{i}: {wp.wp_type:12s} [{wp.mark}]\n"
                self.wp_listbox.insert("end", line)
        self.wp_listbox.configure(state="disabled")

    def _force_recalibrate(self):
        """Fuerza recalibración de regiones del juego."""
        self.log.info("Forzando recalibración de regiones...")
        success = self.bot.force_recalibrate()
        if success:
            self.log.ok("Recalibración exitosa")
        else:
            self.log.error("Recalibración fallida - verificar captura OBS")

    # ==================================================================
    # TAB: Targeting (v2.1)
    # ==================================================================
    def _build_targeting_tab(self):
        tab = self.tab_targeting
        scroll = ctk.CTkScrollableFrame(tab, label_text="⚔️ TARGETING — Ataque Automático")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Habilitar ---
        enable_frame = ctk.CTkFrame(scroll)
        enable_frame.pack(fill="x", padx=5, pady=5)

        self.cb_targeting_enabled = ctk.CTkSwitch(
            enable_frame, text="Targeting habilitado",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._toggle_targeting,
        )
        self.cb_targeting_enabled.pack(anchor="w", padx=15, pady=10)

        # --- Recordatorio ---
        tip_frame = ctk.CTkFrame(enable_frame, fg_color="#1a2733", border_width=1, border_color="#27AE60")
        tip_frame.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(
            tip_frame,
            text=(
                "💡 Recuerda:\n"
                "• Escribe los monstruos a atacar en la lista de abajo (ej: Cave Rat).\n"
                "• Presiona 'Calibrar' antes de activar el Targeting.\n"
                "• El Targeting detectará criaturas y atacará automáticamente.\n"
                "• Si una criatura huye y desaparece, se soltará el target tras ~1.5s.\n"
                "• Activa el Looter en su pestaña para recoger el loot después de kills."
            ),
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
            justify="left",
        ).pack(anchor="w", padx=10, pady=6)

        # --- Modo de ataque ---
        mode_frame = ctk.CTkFrame(scroll)
        mode_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(mode_frame, text="MODO DE ATAQUE", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        row1 = ctk.CTkFrame(mode_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row1, text="Modo:", width=100).pack(side="left")
        self.cb_attack_mode = ctk.CTkComboBox(row1, values=["offensive", "balanced", "defensive"], width=150)
        self.cb_attack_mode.set(self.config.targeting.get("attack_mode", "offensive"))
        self.cb_attack_mode.pack(side="left", padx=5)

        row2 = ctk.CTkFrame(mode_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row2, text="Prioridad:", width=100).pack(side="left")
        self.cb_target_priority = ctk.CTkComboBox(row2, values=["closest", "lowest_hp", "highest_hp", "dangerous"], width=150)
        self.cb_target_priority.set(self.config.targeting.get("target_priority", "closest"))
        self.cb_target_priority.pack(side="left", padx=5)

        self.cb_auto_attack = ctk.CTkSwitch(mode_frame, text="Auto-ataque")
        self.cb_auto_attack.pack(anchor="w", padx=15, pady=3)
        if self.config.targeting.get("auto_attack", True):
            self.cb_auto_attack.select()

        self.cb_chase = ctk.CTkSwitch(mode_frame, text="Perseguir monstruos (global)")
        self.cb_chase.pack(anchor="w", padx=15, pady=(3, 4))
        if self.config.targeting.get("chase_monsters", True):
            self.cb_chase.select()

        # --- Chase/Stand auto-detección (v3.2) ---
        ctk.CTkLabel(
            mode_frame,
            text="🎯 Chase/Stand: Auto-detección por iconos de Tibia\n"
                 "   El bot detecta automáticamente los iconos de Chase (persona\n"
                 "   corriendo verde) y Stand (persona parada roja) en la UI\n"
                 "   de Tibia y clickea para cambiar de modo según el perfil\n"
                 "   de cada criatura. No necesitas configurar hotkeys.",
            font=ctk.CTkFont(size=11), text_color="#2ECC71",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(3, 8))

        # --- Listas de criaturas ---
        lists_frame = ctk.CTkFrame(scroll)
        lists_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(lists_frame, text="LISTAS DE CRIATURAS", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            lists_frame,
            text="Escribe nombres separados por coma. Ej: Rat, Cyclops, Dragon Lord",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack(anchor="w", padx=10, pady=(0, 5))

        # Attack list
        atk_row = ctk.CTkFrame(lists_frame, fg_color="transparent")
        atk_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(atk_row, text="✅ Atacar:", width=90, anchor="w",
                      text_color="#2ECC71", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.entry_attack_list = ctk.CTkEntry(atk_row, width=400,
                                               placeholder_text="Rat, Rotworm, Cyclops...")
        self.entry_attack_list.pack(side="left", padx=5)
        attack_str = ", ".join(self.config.attack_list)
        if attack_str:
            self.entry_attack_list.insert(0, attack_str)

        # Ignore list
        ign_row = ctk.CTkFrame(lists_frame, fg_color="transparent")
        ign_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(ign_row, text="🚫 Ignorar:", width=90, anchor="w",
                      text_color="#E74C3C", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.entry_ignore_list = ctk.CTkEntry(ign_row, width=400,
                                               placeholder_text="Deer, Rabbit, Bug...")
        self.entry_ignore_list.pack(side="left", padx=5)
        ignore_str = ", ".join(self.config.ignore_list)
        if ignore_str:
            self.entry_ignore_list.insert(0, ignore_str)

        # Priority list
        pri_row = ctk.CTkFrame(lists_frame, fg_color="transparent")
        pri_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(pri_row, text="⭐ Prioridad:", width=90, anchor="w",
                      text_color="#F39C12", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.entry_priority_list = ctk.CTkEntry(pri_row, width=400,
                                                 placeholder_text="Dragon Lord, Demon...")
        self.entry_priority_list.pack(side="left", padx=5)
        priority_str = ", ".join(self.config.priority_list)
        if priority_str:
            self.entry_priority_list.insert(0, priority_str)

        # Info skulls
        ctk.CTkLabel(
            lists_frame,
            text="💀 Detección de skulls: Automática (HSV color analysis). No atacará jugadores sin skull.",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack(anchor="w", padx=10, pady=(5, 8))

        # --- Templates de criaturas ---
        tpl_frame = ctk.CTkFrame(scroll)
        tpl_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(tpl_frame, text="📸 TEMPLATES DE CRIATURAS",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        # Label que muestra templates disponibles
        self.lbl_templates_info = ctk.CTkLabel(
            tpl_frame,
            text="Cargando...",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
            justify="left",
        )
        self.lbl_templates_info.pack(anchor="w", padx=10, pady=(0, 5))
        self._update_templates_info()

        # Botones de captura
        btn_row = ctk.CTkFrame(tpl_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            btn_row, text="📸 Capturar Templates desde OBS",
            width=250, fg_color="#2980B9", hover_color="#3498DB",
            command=self._capture_templates_from_obs,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_row, text="🔄 Actualizar Lista",
            width=140,
            command=self._update_templates_info,
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            tpl_frame,
            text="📸 Capturar: Toma un frame de OBS, detecta los nombres en la Battle List\n"
                 "   y los guarda como templates PNG automáticamente.\n"
                 "   Asegúrate de tener criaturas visibles en la Battle List antes de capturar.",
            font=ctk.CTkFont(size=10), text_color="#777777",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # --- Perfiles por criatura ---
        profile_frame = ctk.CTkFrame(scroll)
        profile_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(profile_frame, text="🎯 PERFILES POR CRIATURA",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            profile_frame,
            text=(
                "Configura comportamiento individual por criatura.\n"
                "Ejemplo: Rotworm=chase (melee que huye), Amazon=stand (ranged).\n"
                "Auto = usa la configuración global de arriba."
            ),
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 5))

        # Creature profile list (scrollable)
        self._creature_profile_widgets: List[Dict] = []
        self._profile_container = ctk.CTkFrame(profile_frame, fg_color="transparent")
        self._profile_container.pack(fill="x", padx=10, pady=2)

        # Load existing profiles
        existing_profiles = self.config.targeting.get("creature_profiles", {})
        for name, prof in existing_profiles.items():
            self._add_creature_profile_row(name, prof)

        # Add new creature profile button
        add_profile_row = ctk.CTkFrame(profile_frame, fg_color="transparent")
        add_profile_row.pack(fill="x", padx=10, pady=5)
        self.entry_new_profile_name = ctk.CTkEntry(
            add_profile_row, width=150,
            placeholder_text="Nombre criatura..."
        )
        self.entry_new_profile_name.pack(side="left", padx=5)
        ctk.CTkButton(
            add_profile_row, text="➕ Agregar Perfil", width=140,
            command=self._add_new_creature_profile,
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            profile_frame,
            text="Chase: perseguir criatura (melee/huye) | Stand: quedarse quieto (ranged)\n"
                 "Auto: usa config global | Prioridad: mayor número = atacar primero",
            font=ctk.CTkFont(size=10), text_color="#777777",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(2, 8))

        # --- Hechizos ---
        spell_frame = ctk.CTkFrame(scroll)
        spell_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(spell_frame, text="ROTACIÓN DE HECHIZOS", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self.cb_use_aoe = ctk.CTkSwitch(spell_frame, text="Usar hechizos AOE")
        self.cb_use_aoe.pack(anchor="w", padx=15, pady=3)
        if self.config.targeting.get("use_aoe", True):
            self.cb_use_aoe.select()

        row_aoe = ctk.CTkFrame(spell_frame, fg_color="transparent")
        row_aoe.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_aoe, text="Mín. monstruos AOE:", width=160).pack(side="left")
        self.entry_aoe_min = ctk.CTkEntry(row_aoe, width=60)
        self.entry_aoe_min.insert(0, str(self.config.targeting.get("aoe_min_monsters", 3)))
        self.entry_aoe_min.pack(side="left", padx=5)

        preset_row = ctk.CTkFrame(spell_frame, fg_color="transparent")
        preset_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(preset_row, text="Preset:", width=60).pack(side="left")
        ctk.CTkButton(preset_row, text="🗡️ Knight", width=90, command=lambda: self._load_spell_preset("knight")).pack(side="left", padx=2)
        ctk.CTkButton(preset_row, text="🔮 Sorcerer", width=90, command=lambda: self._load_spell_preset("sorcerer")).pack(side="left", padx=2)
        ctk.CTkButton(preset_row, text="🏹 Paladin", width=90, command=lambda: self._load_spell_preset("paladin")).pack(side="left", padx=2)
        ctk.CTkButton(preset_row, text="🌿 Druid", width=90, command=lambda: self._load_spell_preset("druid")).pack(side="left", padx=2)

        self.spell_list_text = ctk.CTkTextbox(spell_frame, height=100, font=ctk.CTkFont(family="Consolas", size=11))
        self.spell_list_text.pack(fill="x", padx=10, pady=(3, 8))
        self.spell_list_text.insert("1.0", "(Sin hechizos configurados)")
        self.spell_list_text.configure(state="disabled")

        # --- Guardar targeting ---
        ctk.CTkButton(
            scroll,
            text="💾 Guardar Config Targeting",
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_targeting_config,
        ).pack(fill="x", padx=5, pady=8)

        # --- Estado ---
        state_frame = ctk.CTkFrame(scroll)
        state_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(state_frame, text="ESTADO", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self.lbl_targeting_state = ctk.CTkLabel(
            state_frame,
            text="Estado: idle | Target: — | Kills: 0 | Casts: 0",
            font=ctk.CTkFont(size=12),
        )
        self.lbl_targeting_state.pack(anchor="w", padx=15, pady=(0, 10))

        # --- Log del Targeting ---
        log_frame_tg = ctk.CTkFrame(scroll)
        log_frame_tg.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(log_frame_tg, text="📋 LOG TARGETING", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        self.log_targeting = ctk.CTkTextbox(log_frame_tg, height=120, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_targeting.pack(fill="x", padx=10, pady=(2, 8))
        self.log_targeting.configure(state="disabled")

    # --- Creature profile helpers ---
    def _add_creature_profile_row(self, name: str = "", profile: dict = None):
        """Agrega una fila de perfil de criatura al editor."""
        if profile is None:
            profile = {}

        row = ctk.CTkFrame(self._profile_container, fg_color="#1a2733",
                           border_width=1, border_color="#2C3E50")
        row.pack(fill="x", pady=2)

        # Nombre
        name_entry = ctk.CTkEntry(row, width=120, placeholder_text="Nombre")
        name_entry.pack(side="left", padx=4, pady=4)
        if name:
            name_entry.insert(0, name)

        # Chase mode
        ctk.CTkLabel(row, text="Chase:", width=45,
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 0))
        chase_var = ctk.StringVar(value=profile.get("chase_mode", "auto"))
        chase_cb = ctk.CTkComboBox(row, variable=chase_var,
                                    values=["auto", "chase", "stand"], width=85)
        chase_cb.pack(side="left", padx=2)

        # Priority
        ctk.CTkLabel(row, text="Prio:", width=35,
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 0))
        prio_entry = ctk.CTkEntry(row, width=40)
        prio_entry.pack(side="left", padx=2)
        prio_entry.insert(0, str(profile.get("priority", 0)))

        # Flees checkbox
        flees_var = ctk.BooleanVar(value=profile.get("use_chase_on_flee", True))
        flees_cb = ctk.CTkCheckBox(row, text="Huye", variable=flees_var,
                                    width=55, font=ctk.CTkFont(size=11))
        flees_cb.pack(side="left", padx=4)

        # Ranged checkbox
        ranged_var = ctk.BooleanVar(value=profile.get("is_ranged", False))
        ranged_cb = ctk.CTkCheckBox(row, text="Ranged", variable=ranged_var,
                                     width=70, font=ctk.CTkFont(size=11))
        ranged_cb.pack(side="left", padx=4)

        # Delete button
        widget_data = {
            "row": row,
            "name_entry": name_entry,
            "chase_var": chase_var,
            "prio_entry": prio_entry,
            "flees_var": flees_var,
            "ranged_var": ranged_var,
        }
        ctk.CTkButton(
            row, text="🗑️", width=32, height=28, fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=lambda w=widget_data: self._remove_creature_profile(w),
        ).pack(side="right", padx=4, pady=4)

        self._creature_profile_widgets.append(widget_data)

    def _add_new_creature_profile(self):
        """Agrega un nuevo perfil de criatura desde el campo de texto."""
        name = self.entry_new_profile_name.get().strip()
        if not name:
            return
        # Verificar si ya existe
        for w in self._creature_profile_widgets:
            if w["name_entry"].get().strip().lower() == name.lower():
                self.log.warning(f"Perfil '{name}' ya existe")
                return
        self._add_creature_profile_row(name, {"chase_mode": "auto", "priority": 0})
        self.entry_new_profile_name.delete(0, "end")

    def _remove_creature_profile(self, widget_data: dict):
        """Elimina una fila de perfil de criatura."""
        widget_data["row"].destroy()
        if widget_data in self._creature_profile_widgets:
            self._creature_profile_widgets.remove(widget_data)

    def _save_targeting_config(self):
        """Guarda toda la configuración de targeting desde la GUI."""
        targeting = self.config.targeting

        targeting["attack_mode"] = self.cb_attack_mode.get()
        targeting["target_priority"] = self.cb_target_priority.get()
        targeting["auto_attack"] = bool(self.cb_auto_attack.get())
        targeting["chase_monsters"] = bool(self.cb_chase.get())
        targeting["use_aoe"] = bool(self.cb_use_aoe.get())
        try:
            targeting["aoe_min_monsters"] = int(self.entry_aoe_min.get())
        except ValueError:
            pass

        # Chase/Stand — ahora auto-detectado por iconos, no hotkeys
        # Mantener valores vacíos para compatibilidad
        targeting["chase_key"] = ""
        targeting["stand_key"] = ""

        # Listas de criaturas
        def parse_list(text: str) -> list:
            return [s.strip() for s in text.split(",") if s.strip()]

        targeting["attack_list"] = parse_list(self.entry_attack_list.get())
        targeting["ignore_list"] = parse_list(self.entry_ignore_list.get())
        targeting["priority_list"] = parse_list(self.entry_priority_list.get())

        # Creature profiles
        creature_profiles = {}
        for w in self._creature_profile_widgets:
            name = w["name_entry"].get().strip()
            if not name:
                continue
            try:
                prio = int(w["prio_entry"].get())
            except ValueError:
                prio = 0
            creature_profiles[name] = {
                "chase_mode": w["chase_var"].get(),
                "priority": prio,
                "use_chase_on_flee": w["flees_var"].get(),
                "is_ranged": w["ranged_var"].get(),
                "attack_mode": "auto",
                "flees_at_hp": 0.0,
            }
        targeting["creature_profiles"] = creature_profiles

        self.config.targeting = targeting
        self.config.save()
        # Re-configure engine with new settings
        self.bot.targeting_engine.configure(targeting)
        self.log.ok(f"Configuración de Targeting guardada ({len(creature_profiles)} perfiles)")

    def _toggle_targeting(self):
        enabled = self.cb_targeting_enabled.get()
        self.config.targeting_enabled = bool(enabled)
        self.config.save()
        # Wire to dispatcher + engine
        if enabled:
            # Aplicar la configuración actual de la GUI antes de activar
            self._save_targeting_config()
            self.bot.dispatcher.enable_module("targeting")
            self.bot.targeting_engine.start()
        else:
            self.bot.dispatcher.disable_module("targeting")
            self.bot.targeting_engine.stop()
        self.log.info(f"Targeting {'habilitado' if enabled else 'deshabilitado'}")

    # ------------------------------------------------------------------
    # Templates de criaturas
    # ------------------------------------------------------------------
    def _update_templates_info(self):
        """Actualiza el label con info de templates disponibles vs necesarios."""
        names_dir = os.path.join("images", "Targets", "Names")

        # Templates disponibles en disco
        available = {}
        if os.path.isdir(names_dir):
            for fname in os.listdir(names_dir):
                if fname.endswith(".png"):
                    raw = fname.replace(".png", "")
                    # CamelCase → display name  (e.g. "CaveRat" → "Cave Rat")
                    display = ""
                    for i, ch in enumerate(raw):
                        if ch.isupper() and i > 0 and raw[i - 1].islower():
                            display += " "
                        display += ch
                    available[display] = fname

        # Listas del usuario
        attack_names = [n.strip() for n in self.entry_attack_list.get().split(",") if n.strip()]
        ignore_names = [n.strip() for n in self.entry_ignore_list.get().split(",") if n.strip()]
        priority_names = [n.strip() for n in self.entry_priority_list.get().split(",") if n.strip()]
        all_needed = set(attack_names + ignore_names + priority_names)

        lines = []
        # Mostrar estado de las necesarias
        if all_needed:
            for name in sorted(all_needed):
                if name in available:
                    lines.append(f"  ✅ {name}  ({available[name]})")
                else:
                    camel = name.replace(" ", "")
                    lines.append(f"  ❌ {name}  (falta {camel}.png)")

        # Mostrar extras disponibles
        extras = sorted(set(available.keys()) - all_needed)
        if extras:
            lines.append("")
            lines.append("Otros templates disponibles:")
            for name in extras:
                lines.append(f"  📦 {name}")

        if not lines:
            lines.append("No hay templates ni criaturas configuradas.")

        total_available = len(available)
        total_needed = len(all_needed)
        found = sum(1 for n in all_needed if n in available)
        header = f"Templates: {total_available} disponibles | Necesarios: {found}/{total_needed}\n"

        self.lbl_templates_info.configure(
            text=header + "\n".join(lines),
            text_color="#55FF55" if found == total_needed and total_needed > 0 else "#FFAA55",
        )

    def _capture_templates_from_obs(self):
        """Captura un frame de OBS, detecta nombres en la Battle List y los guarda como templates."""
        # Validaciones
        if not self.bot.capture.is_connected:
            messagebox.showerror("Error", "No hay conexión a OBS.\nConéctate primero en la pestaña Principal.")
            return

        cal = self.bot.calibrator
        if cal.battle_region is None:
            messagebox.showerror(
                "Error",
                "La Battle List no está calibrada.\n"
                "Ejecuta la calibración primero (pestaña Principal).",
            )
            return

        # Capturar frame
        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame de OBS.")
            return

        # Recortar Battle List ROI
        bx1, by1, bx2, by2 = cal.battle_region
        h_frame, w_frame = frame.shape[:2]
        # Clamp
        bx1 = max(0, min(bx1, w_frame - 1))
        by1 = max(0, min(by1, h_frame - 1))
        bx2 = max(bx1 + 1, min(bx2, w_frame))
        by2 = max(by1 + 1, min(by2, h_frame))
        battle_roi = frame[by1:by2, bx1:bx2]

        if battle_roi.size == 0:
            messagebox.showerror("Error", "La región de Battle List está vacía.")
            return

        # Convertir a gris para detectar texto
        gray = cv2.cvtColor(battle_roi, cv2.COLOR_BGR2GRAY)

        # En la battle list, los nombres de criaturas son texto claro sobre fondo oscuro.
        # El texto tiene un gris ~180-255 y el fondo ~20-60.
        # Umbralizar para aislar texto brillante
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # Encontrar filas con texto (proyección horizontal)
        row_sums = np.sum(thresh, axis=1)
        # Normalizar: una fila con texto tendrá sum > 0
        text_rows = row_sums > (thresh.shape[1] * 255 * 0.02)  # al menos 2% de píxeles blancos

        # Detectar segmentos continuos de filas con texto
        segments = []
        in_segment = False
        start = 0
        for i, has_text in enumerate(text_rows):
            if has_text and not in_segment:
                start = i
                in_segment = True
            elif not has_text and in_segment:
                segments.append((start, i))
                in_segment = False
        if in_segment:
            segments.append((start, len(text_rows)))

        # Filtrar segmentos por altura razonable para nombres (6-16px)
        name_segments = []
        for y_start, y_end in segments:
            height = y_end - y_start
            if 5 <= height <= 18:
                name_segments.append((y_start, y_end))

        if not name_segments:
            messagebox.showinfo(
                "Sin resultados",
                "No se detectaron nombres de criaturas en la Battle List.\n\n"
                "Asegúrate de que:\n"
                "1. Hay criaturas visibles en la Battle List\n"
                "2. La calibración es correcta\n"
                "3. OBS está capturando el juego",
            )
            return

        # Para cada segmento detectado, recortar el nombre y pedir al usuario que lo nombre
        names_dir = os.path.join("images", "Targets", "Names")
        os.makedirs(names_dir, exist_ok=True)
        saved_count = 0

        # Lanzar en un hilo para no bloquear — pero los dialogs deben estar en main thread
        # Así que lo hacemos secuencialmente
        for idx, (y_start, y_end) in enumerate(name_segments):
            # Recortar el nombre: toda la anchura de la ROI, pero luego ajustar horizontalmente
            name_row = gray[y_start:y_end, :]
            _, name_thresh = cv2.threshold(name_row, 150, 255, cv2.THRESH_BINARY)

            # Encontrar los límites horizontales del texto
            col_sums = np.sum(name_thresh, axis=0)
            text_cols = np.where(col_sums > 0)[0]
            if len(text_cols) == 0:
                continue

            x_start = max(0, text_cols[0] - 1)
            x_end = min(name_row.shape[1], text_cols[-1] + 2)

            # Recortar solo el texto
            name_crop = gray[y_start:y_end, x_start:x_end]

            if name_crop.size == 0:
                continue

            # Mostrar preview ampliado
            preview_scale = 6
            preview = cv2.resize(
                name_crop,
                (name_crop.shape[1] * preview_scale, name_crop.shape[0] * preview_scale),
                interpolation=cv2.INTER_NEAREST,
            )

            # Guardar preview temporal para mostrar en diálogo
            preview_path = os.path.join("debug", f"_tpl_preview_{idx}.png")
            os.makedirs("debug", exist_ok=True)
            cv2.imwrite(preview_path, preview)

            # Crear diálogo con preview
            result = self._show_template_name_dialog(
                preview_path, name_crop, idx + 1, len(name_segments)
            )

            # Limpiar preview
            try:
                os.remove(preview_path)
            except OSError:
                pass

            if result is None:
                # Usuario canceló — salir del loop
                break
            if result == "":
                # Usuario dejó vacío — skip
                continue

            # Guardar template con nombre CamelCase
            camel_name = result.strip().replace(" ", "")
            save_path = os.path.join(names_dir, f"{camel_name}.png")

            # Verificar si ya existe
            if os.path.exists(save_path):
                overwrite = messagebox.askyesno(
                    "Template existente",
                    f"Ya existe '{camel_name}.png'.\n¿Deseas sobrescribirlo?",
                )
                if not overwrite:
                    continue

            cv2.imwrite(save_path, name_crop)
            saved_count += 1
            self.log.ok(f"Template guardado: {camel_name}.png ({name_crop.shape[1]}x{name_crop.shape[0]}px)")

        # Recargar templates en el engine
        if saved_count > 0:
            try:
                attack_list = [n.strip() for n in self.entry_attack_list.get().split(",") if n.strip()]
                self.bot.targeting_engine.battle_reader.load_monster_templates(attack_list)
                self.log.ok(f"✅ {saved_count} template(s) guardado(s) y recargado(s)")
            except Exception as e:
                self.log.warn(f"Templates guardados pero error al recargar: {e}")

        # Actualizar info
        self._update_templates_info()

        if saved_count == 0:
            messagebox.showinfo("Info", "No se guardaron templates nuevos.")
        else:
            messagebox.showinfo(
                "Listo",
                f"Se guardaron {saved_count} template(s).\n"
                "Los templates se recargaron automáticamente.",
            )

    def _show_template_name_dialog(
        self, preview_path: str, crop: np.ndarray, current: int, total: int
    ) -> Optional[str]:
        """Muestra un diálogo para que el usuario nombre un template detectado.

        Returns:
            str con el nombre, "" para skip, None para cancelar todo.
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Nombrar Template ({current}/{total})")
        dialog.geometry("500x350")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_force()

        result_var = {"value": None}  # mutable container

        # Info
        ctk.CTkLabel(
            dialog,
            text=f"Template detectado {current} de {total}",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            dialog,
            text=f"Tamaño: {crop.shape[1]}×{crop.shape[0]} px",
            font=ctk.CTkFont(size=11),
            text_color="#AAAAAA",
        ).pack()

        # Preview de la imagen
        try:
            pil_img = Image.open(preview_path)
            # Escalar para que sea visible
            max_w = 450
            if pil_img.width > max_w:
                ratio = max_w / pil_img.width
                pil_img = pil_img.resize(
                    (int(pil_img.width * ratio), int(pil_img.height * ratio)),
                    Image.NEAREST,
                )
            tk_img = ImageTk.PhotoImage(pil_img)
            img_label = ctk.CTkLabel(dialog, text="", image=tk_img)
            img_label.image = tk_img  # keep reference
            img_label.pack(pady=10)
        except Exception:
            ctk.CTkLabel(dialog, text="(Vista previa no disponible)").pack(pady=10)

        # Entry para el nombre
        ctk.CTkLabel(
            dialog,
            text="Nombre de la criatura (ej: Swamp Troll, Cave Rat):",
            font=ctk.CTkFont(size=12),
        ).pack(padx=20, anchor="w")

        name_entry = ctk.CTkEntry(dialog, width=350, placeholder_text="Nombre de la criatura...")
        name_entry.pack(padx=20, pady=5)
        name_entry.focus()

        # Botones
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)

        def on_save():
            result_var["value"] = name_entry.get()
            dialog.destroy()

        def on_skip():
            result_var["value"] = ""
            dialog.destroy()

        def on_cancel():
            result_var["value"] = None
            dialog.destroy()

        def on_enter(event=None):
            on_save()

        name_entry.bind("<Return>", on_enter)

        ctk.CTkButton(
            btn_frame, text="💾 Guardar", width=120,
            fg_color="#27AE60", hover_color="#2ECC71",
            command=on_save,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="⏭ Saltar", width=100,
            fg_color="#7F8C8D", hover_color="#95A5A6",
            command=on_skip,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="❌ Cancelar", width=100,
            fg_color="#C0392B", hover_color="#E74C3C",
            command=on_cancel,
        ).pack(side="left", padx=5)

        # Manejar cierre de ventana
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        # Esperar a que se cierre el diálogo
        dialog.wait_window()
        return result_var["value"]

    def _load_spell_preset(self, vocation: str):
        self.log.info(f"Cargando preset de hechizos: {vocation}")
        preset_map = {
            "knight": "Exori Gran [F1], Exori [F2], Exori Mas [F3]",
            "sorcerer": "Exori Vis [F1], Exori Gran Vis [F2], Exevo Vis Hur [F3]",
            "paladin": "Exori San [F1], Exori Gran Con [F2], Exevo Mas San [F3]",
            "druid": "Exori Tera [F1], Exori Gran Tera [F2], Exevo Tera Hur [F3]",
        }
        text = preset_map.get(vocation, "")
        self.spell_list_text.configure(state="normal")
        self.spell_list_text.delete("1.0", "end")
        self.spell_list_text.insert("1.0", text)
        self.spell_list_text.configure(state="disabled")

    # ==================================================================
    # TAB: Looter (v3)
    # ==================================================================
    def _build_looter_tab(self):
        tab = self.tab_looter
        scroll = ctk.CTkScrollableFrame(tab, label_text="💰 LOOTER — Looteo Automático Inteligente")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Habilitar ---
        enable_frame = ctk.CTkFrame(scroll)
        enable_frame.pack(fill="x", padx=5, pady=5)

        self.cb_looter_enabled = ctk.CTkSwitch(
            enable_frame, text="Looter habilitado",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._toggle_looter,
        )
        self.cb_looter_enabled.pack(anchor="w", padx=15, pady=10)

        # --- Guía rápida ---
        guide_frame = ctk.CTkFrame(scroll, fg_color="#1a2733", border_width=1, border_color="#2980B9")
        guide_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(
            guide_frame,
            text="📖 GUÍA RÁPIDA — Cómo configurar el Looter",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#3498DB",
        ).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            guide_frame,
            text=(
                "1️⃣  Tipo de cuenta: Selecciona Premium o Free Account.\n"
                "     • Premium: el cliente de Tibia organiza todo — solo necesita el click.\n"
                "     • Free: todo va a la primera BP. (Futuro: organización manual).\n"
                "\n"
                "2️⃣  Método de looteo: Pon left_click si en Tibia tienes Loot: Left,\n"
                "     o right_click si tienes Loot: Right (Options → General → Loot).\n"
                "\n"
                "3️⃣  Max SQMs: Usa 9 para clickear TODOS los cuadros incl. centro.\n"
                "     El cadáver puede caer en cualquier SQM (como TibiaAuto12).\n"
                "\n"
                "4️⃣  Lootear siempre (ON): Lootea inmediatamente tras cada kill.\n"
                "     El targeting NO se pausa — el loot es rápido (~0.5s).\n"
                "\n"
                "💡 Recuerda: Primero activa el Targeting con tus monstruos,\n"
                "   luego activa el Looter. Lootea entre kills automáticamente."
            ),
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#BDC3C7",
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # --- Método de looteo ---
        method_frame = ctk.CTkFrame(scroll)
        method_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(method_frame, text="MÉTODO DE LOOTEO",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            method_frame,
            text="Elige el mismo método que tienes en Options → General → Loot de Tibia",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack(anchor="w", padx=10, pady=(0, 5))

        row1 = ctk.CTkFrame(method_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row1, text="Método:", width=80).pack(side="left")
        self.cb_loot_method = ctk.CTkComboBox(
            row1,
            values=["left_click", "right_click", "shift_right_click"],
            width=170,
        )
        loot_m = self.config.looter.get("loot_method", "left_click")
        if loot_m not in ("left_click", "right_click", "shift_right_click"):
            loot_m = "left_click"
        self.cb_loot_method.set(loot_m)
        self.cb_loot_method.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="← shift_right_click = Quick Loot (recomendado)",
                      font=ctk.CTkFont(size=11), text_color="#888888").pack(side="left", padx=8)

        # --- Tipo de cuenta (Premium / Free) ---
        account_frame = ctk.CTkFrame(method_frame, fg_color="transparent")
        account_frame.pack(fill="x", padx=10, pady=(5, 3))

        ctk.CTkLabel(account_frame, text="Tipo de cuenta:",
                      font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))

        self._account_type_var = ctk.StringVar(
            value=self.config.looter.get("account_type",
                  "free" if self.config.looter.get("free_account", False) else "premium")
        )

        premium_row = ctk.CTkFrame(account_frame, fg_color="transparent")
        premium_row.pack(fill="x")
        self.rb_premium = ctk.CTkRadioButton(
            premium_row, text="⭐ Premium Account",
            variable=self._account_type_var, value="premium",
            command=self._on_account_type_changed,
            font=ctk.CTkFont(size=12),
        )
        self.rb_premium.pack(side="left")
        ctk.CTkLabel(premium_row,
                      text="El cliente organiza TODO el loot automáticamente. Solo necesita el click.",
                      font=ctk.CTkFont(size=10), text_color="#2ECC71").pack(side="left", padx=10)

        free_row = ctk.CTkFrame(account_frame, fg_color="transparent")
        free_row.pack(fill="x", pady=(3, 0))
        self.rb_free = ctk.CTkRadioButton(
            free_row, text="🆓 Free Account",
            variable=self._account_type_var, value="free",
            command=self._on_account_type_changed,
            font=ctk.CTkFont(size=12),
        )
        self.rb_free.pack(side="left")
        ctk.CTkLabel(free_row,
                      text="Sin Quick Loot. Todo va a BP principal. (Futuro: organización manual)",
                      font=ctk.CTkFont(size=10), text_color="#F39C12").pack(side="left", padx=10)

        # Cooldown
        row_cd = ctk.CTkFrame(method_frame, fg_color="transparent")
        row_cd.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_cd, text="Cooldown (s):", width=100).pack(side="left")
        self.entry_loot_cooldown = ctk.CTkEntry(row_cd, width=60)
        self.entry_loot_cooldown.insert(0, str(self.config.looter.get("loot_cooldown", 0.3)))
        self.entry_loot_cooldown.pack(side="left", padx=5)
        ctk.CTkLabel(row_cd, text="Espera entre looteos",
                      font=ctk.CTkFont(size=11), text_color="#888888").pack(side="left", padx=8)

        # Max SQMs por kill
        row_sqm = ctk.CTkFrame(method_frame, fg_color="transparent")
        row_sqm.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_sqm, text="SQMs por kill:", width=100).pack(side="left")
        self.entry_max_loot_sqms = ctk.CTkEntry(row_sqm, width=60)
        self.entry_max_loot_sqms.insert(0, str(self.config.looter.get("max_loot_sqms", 9)))
        self.entry_max_loot_sqms.pack(side="left", padx=5)
        ctk.CTkLabel(row_sqm, text="Cuántos SQMs clickear por cuerpo (1-9, 9=todos incl. centro)",
                      font=ctk.CTkFont(size=11), text_color="#888888").pack(side="left", padx=8)

        # --- Modo de detección de cadáveres ---
        detect_mode_frame = ctk.CTkFrame(scroll, border_width=1, border_color="#3498DB")
        detect_mode_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(detect_mode_frame, text="🔍 MODO DE DETECCIÓN DE CADÁVERES",
                      font=ctk.CTkFont(weight="bold"),
                      text_color="#3498DB").pack(anchor="w", padx=10, pady=(8, 4))

        self._loot_mode_var = ctk.StringVar(
            value=self.config.looter.get("loot_mode", "basic")
        )

        basic_row = ctk.CTkFrame(detect_mode_frame, fg_color="transparent")
        basic_row.pack(fill="x", padx=10, pady=2)
        self.rb_loot_basic = ctk.CTkRadioButton(
            basic_row, text="📦 Método Básico (SQMs ciegos)",
            variable=self._loot_mode_var, value="basic",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.rb_loot_basic.pack(side="left")
        ctk.CTkLabel(basic_row,
                      text="Clickea los 9 SQMs alrededor del player tras cada kill. Siempre funciona.",
                      font=ctk.CTkFont(size=10), text_color="#2ECC71").pack(side="left", padx=10)

        adv_row = ctk.CTkFrame(detect_mode_frame, fg_color="transparent")
        adv_row.pack(fill="x", padx=10, pady=2)
        self.rb_loot_advanced = ctk.CTkRadioButton(
            adv_row, text="🎯 Método Avanzado (Sprite del cadáver)",
            variable=self._loot_mode_var, value="advanced",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.rb_loot_advanced.pack(side="left")
        ctk.CTkLabel(adv_row,
                      text="Busca la imagen del cadáver en pantalla → click preciso. Requiere captura de sprite.",
                      font=ctk.CTkFont(size=10), text_color="#F39C12").pack(side="left", padx=10)

        ctk.CTkLabel(
            detect_mode_frame,
            text=(
                "💡 Básico: No requiere configuración extra. Lootea clickeando todos los cuadros.\n"
                "💡 Avanzado: Necesitas capturar el sprite del cadáver de cada criatura (sección abajo).\n"
                "    Si no hay sprite para una criatura, el avanzado usa SQMs ciegos como fallback."
            ),
            font=ctk.CTkFont(size=10), text_color="#888888",
            justify="left",
        ).pack(anchor="w", padx=12, pady=(4, 10))

        # --- Estrategia de looteo ---
        strat_frame = ctk.CTkFrame(scroll)
        strat_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(strat_frame, text="⚔️ ESTRATEGIA DE LOOTEO",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            strat_frame,
            text="Estilo TibiaAuto12: lootea inmediatamente tras cada kill.\n"
                 "NO pausa el targeting — el loot es rápido (~0.5s).",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack(anchor="w", padx=10, pady=(0, 5))

        self.cb_always_loot = ctk.CTkSwitch(
            strat_frame,
            text="Lootear siempre (recomendado ON = como TibiaAuto12)",
        )
        self.cb_always_loot.pack(anchor="w", padx=15, pady=3)
        if self.config.looter.get("always_loot", True):
            self.cb_always_loot.select()

        row_thresh = ctk.CTkFrame(strat_frame, fg_color="transparent")
        row_thresh.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_thresh, text="Threshold criaturas:", width=150).pack(side="left")
        self.entry_loot_threshold = ctk.CTkEntry(row_thresh, width=60)
        self.entry_loot_threshold.insert(0, str(self.config.looter.get("loot_threshold", 0)))
        self.entry_loot_threshold.pack(side="left", padx=5)
        ctk.CTkLabel(
            row_thresh,
            text="← Solo lootear si criaturas en pantalla ≤ este número",
            font=ctk.CTkFont(size=11), text_color="#888888",
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            strat_frame,
            text="Si 'Lootear siempre' está OFF, usa el threshold:\n"
                 "threshold=0 → solo lootea cuando NO hay criaturas\n"
                 "threshold=2 → lootea si hay ≤2 criaturas\n"
                 "RECOMENDADO: dejar 'Lootear siempre' ON",
            font=ctk.CTkFont(size=11), text_color="#777777",
        ).pack(anchor="w", padx=15, pady=(3, 8))

        # --- Drop items no deseados ---
        drop_frame = ctk.CTkFrame(scroll)
        drop_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(drop_frame, text="🗑️ DROP ITEMS NO DESEADOS",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            drop_frame,
            text="Items que se tirarán al piso automáticamente después de lootear.\n"
                 "(⚠ Requiere detección de inventario — próxima versión)",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack(anchor="w", padx=10, pady=(0, 5))

        self.cb_drop_enabled = ctk.CTkSwitch(
            drop_frame,
            text="Habilitar drop de items",
        )
        self.cb_drop_enabled.pack(anchor="w", padx=15, pady=3)
        if self.config.looter.get("drop_enabled", False):
            self.cb_drop_enabled.select()

        drop_row = ctk.CTkFrame(drop_frame, fg_color="transparent")
        drop_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(drop_row, text="Items a tirar:", width=100).pack(side="left")
        self.entry_drop_items = ctk.CTkEntry(drop_row, width=400,
                                              placeholder_text="Bone, Torch, Meat, Cheese...")
        self.entry_drop_items.pack(side="left", padx=5)
        drop_items_str = self.config.looter.get("drop_items", "")
        if isinstance(drop_items_str, list):
            drop_items_str = ", ".join(drop_items_str)
        if drop_items_str:
            self.entry_drop_items.insert(0, drop_items_str)

        ctk.CTkFrame(drop_frame, fg_color="transparent", height=8).pack()

        # --- Filtro de items ---
        filter_frame = ctk.CTkFrame(scroll)
        filter_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(filter_frame, text="FILTRO DE ITEMS",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        item_filter = self.config.looter.get("item_filter", {})

        self.cb_pick_gold = ctk.CTkSwitch(filter_frame, text="Recoger Gold Coins")
        self.cb_pick_gold.pack(anchor="w", padx=15, pady=2)
        if item_filter.get("pick_gold", True):
            self.cb_pick_gold.select()

        self.cb_pick_equipment = ctk.CTkSwitch(filter_frame, text="Recoger Equipamiento")
        self.cb_pick_equipment.pack(anchor="w", padx=15, pady=2)
        if item_filter.get("pick_equipment", True):
            self.cb_pick_equipment.select()

        self.cb_pick_valuables = ctk.CTkSwitch(filter_frame, text="Recoger items valiosos (auto GameData)")
        self.cb_pick_valuables.pack(anchor="w", padx=15, pady=2)
        if item_filter.get("pick_valuables", True):
            self.cb_pick_valuables.select()

        self.cb_pick_creature_products = ctk.CTkSwitch(filter_frame, text="Recoger creature products")
        self.cb_pick_creature_products.pack(anchor="w", padx=15, pady=2)
        if item_filter.get("pick_creature_products", False):
            self.cb_pick_creature_products.select()

        self.cb_pick_unknown = ctk.CTkSwitch(filter_frame, text="Recoger items desconocidos")
        self.cb_pick_unknown.pack(anchor="w", padx=15, pady=2)
        if item_filter.get("pick_unknown_items", False):
            self.cb_pick_unknown.select()

        val_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        val_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(val_row, text="Valor mínimo de item (gp):").pack(side="left")
        self.entry_min_value = ctk.CTkEntry(val_row, width=80)
        self.entry_min_value.insert(0, str(item_filter.get("min_item_value", 0)))
        self.entry_min_value.pack(side="left", padx=5)

        # --- Backpack Routing ---
        bp_frame = ctk.CTkFrame(scroll)
        bp_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(bp_frame, text="BACKPACK ROUTING",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            bp_frame,
            text="Asigna cada categoría a un índice de backpack (0=primera, 1=segunda, ...)",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack(anchor="w", padx=10, pady=(0, 5))

        bp_routing = self.config.backpack_routing
        cat_routes = bp_routing.get("category_routes", {})
        bp_values = ["0", "1", "2", "3", "4", "5"]
        self._bp_route_vars: Dict[str, ctk.StringVar] = {}

        categories = [
            ("gold", "💰 Oro"),
            ("valuable", "💎 Valiosos"),
            ("equipment", "🛡️ Equipamiento"),
            ("potion", "🧪 Pociones"),
            ("rune", "📜 Runas"),
            ("food", "🍖 Comida"),
            ("creature_product", "🦴 Creature Products"),
        ]

        for cat_key, cat_label in categories:
            row = ctk.CTkFrame(bp_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(row, text=cat_label, width=180, anchor="w").pack(side="left")
            var = ctk.StringVar(value=str(cat_routes.get(cat_key, 0)))
            ctk.CTkComboBox(row, variable=var, values=bp_values, width=70).pack(side="left", padx=5)
            self._bp_route_vars[cat_key] = var

        ctk.CTkFrame(bp_frame, fg_color="transparent", height=8).pack()

        # --- Guardar looter config ---
        ctk.CTkButton(
            scroll,
            text="💾 Guardar Config Looter",
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_looter_config,
        ).pack(fill="x", padx=5, pady=8)

        # --- 📸 Herramientas Visuales de Calibración ---
        visual_frame = ctk.CTkFrame(scroll, border_width=1, border_color="#E67E22")
        visual_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(visual_frame, text="📸 CALIBRACIÓN VISUAL — Verificar SQMs y Detección",
                      font=ctk.CTkFont(weight="bold"),
                      text_color="#E67E22").pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            visual_frame,
            text=(
                "Herramientas para verificar que el bot sabe DÓNDE clickear.\n"
                "Captura la pantalla del juego y muestra un overlay con los SQMs marcados.\n"
                "También puedes probar la detección de cadáveres si hay un cuerpo visible."
            ),
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Botones en fila
        vis_btn_row = ctk.CTkFrame(visual_frame, fg_color="transparent")
        vis_btn_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            vis_btn_row, text="🎯 Ver SQMs del Looter",
            width=200, fg_color="#2980B9", hover_color="#3498DB",
            command=self._preview_loot_sqms,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            vis_btn_row, text="🧪 Test Manual Loot",
            width=180, fg_color="#E74C3C", hover_color="#C0392B",
            command=self._test_manual_loot,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            vis_btn_row, text="💀 Probar Detección Cadáveres",
            width=220, fg_color="#8E44AD", hover_color="#9B59B6",
            command=self._preview_corpse_detection,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            vis_btn_row, text="🔧 Capturar Piso/Suelo",
            width=180, fg_color="#27AE60", hover_color="#2ECC71",
            command=self._capture_floor_reference,
        ).pack(side="left", padx=5)

        # Segunda fila: captura de cadáveres
        vis_btn_row2 = ctk.CTkFrame(visual_frame, fg_color="transparent")
        vis_btn_row2.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            vis_btn_row2, text="📸 Capturar Template de Cadáver",
            width=260, fg_color="#E67E22", hover_color="#F39C12",
            command=self._capture_corpse_template,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            vis_btn_row2, text="🔄 Actualizar Templates",
            width=180,
            command=self._update_corpse_templates_info,
        ).pack(side="left", padx=5)

        # Label de templates de cadáveres
        self.lbl_corpse_templates_info = ctk.CTkLabel(
            visual_frame,
            text="Cargando templates de cadáveres...",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
            justify="left",
        )
        self.lbl_corpse_templates_info.pack(anchor="w", padx=10, pady=(5, 5))
        self._update_corpse_templates_info()

        # Info de calibración actual
        self.lbl_loot_calibration = ctk.CTkLabel(
            visual_frame,
            text="⚠ Sin calibrar — presiona 'Calibrar' en la pestaña Principal primero",
            font=ctk.CTkFont(size=11), text_color="#F39C12",
            justify="left",
        )
        self.lbl_loot_calibration.pack(anchor="w", padx=10, pady=(0, 8))

        ctk.CTkLabel(
            visual_frame,
            text=(
                "💡 CÓMO FUNCIONA EL LOOT (v11):\n"
                "  1. PRIORIDAD: Detección por sprite del cadáver (template matching)\n"
                "     → El bot busca la FOTO del cuerpo muerto en el game screen\n"
                "     → Clickea exactamente donde encontró el cadáver\n"
                "  2. FALLBACK: SQMs ciegos (siempre funciona)\n"
                "     → Clickea los 5 SQMs alrededor del personaje (center + cardinales)\n\n"
                "  💎 Captura fotos de los CADÁVERES para que el bot los detecte"
            ),
            font=ctk.CTkFont(size=10), text_color="#777777",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

        # --- 💀 Captura de Sprites de Cadáveres ---
        tracker_frame = ctk.CTkFrame(scroll, border_width=1, border_color="#E74C3C")
        tracker_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(tracker_frame, text="💀 CORPSE SPRITES — Captura de Cadáveres (v11)",
                      font=ctk.CTkFont(weight="bold"),
                      text_color="#E74C3C").pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            tracker_frame,
            text=(
                "Captura una foto del CADÁVER de la criatura (32×32px) para que el\n"
                "bot pueda encontrarlo en el game screen después de matarla.\n"
                "Sin sprites, el bot usa SQMs ciegos (5 clicks alrededor tuyo).\n"
                "CON sprites, el bot clickea EXACTAMENTE sobre el cuerpo muerto.\n\n"
                "🖱️ Mata una criatura, luego captura la foto del cuerpo en el suelo.\n"
                "📷 Se guarda en images/Looter/Corpses/"
            ),
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Botones del corpse sprite
        tracker_btn_row = ctk.CTkFrame(tracker_frame, fg_color="transparent")
        tracker_btn_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            tracker_btn_row, text="💀 Capturar Sprite de Cadáver",
            width=260, fg_color="#E74C3C", hover_color="#C0392B",
            command=self._capture_corpse_sprite,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            tracker_btn_row, text="🔄 Ver Sprites Cargados",
            width=180,
            command=self._update_sprites_info,
        ).pack(side="left", padx=5)

        # Label de sprites cargados
        self.lbl_sprites_info = ctk.CTkLabel(
            tracker_frame,
            text="Cargando sprites...",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
            justify="left",
        )
        self.lbl_sprites_info.pack(anchor="w", padx=10, pady=(5, 5))
        self._update_sprites_info()

        # Estado del detector
        self.lbl_tracker_status = ctk.CTkLabel(
            tracker_frame,
            text="Detector: Sin sprites cargados",
            font=ctk.CTkFont(size=11), text_color="#F39C12",
            justify="left",
        )
        self.lbl_tracker_status.pack(anchor="w", padx=10, pady=(0, 8))

        # --- Estado ---
        state_frame = ctk.CTkFrame(scroll)
        state_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(state_frame, text="ESTADO",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self.lbl_looter_state = ctk.CTkLabel(
            state_frame,
            text="Estado: idle | Pendientes: 0 | Looteados: 0",
            font=ctk.CTkFont(size=12),
        )
        self.lbl_looter_state.pack(anchor="w", padx=15, pady=(0, 10))

        # --- Log del Looter ---
        log_frame_lt = ctk.CTkFrame(scroll)
        log_frame_lt.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(log_frame_lt, text="📋 LOG LOOTER",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        self.log_looter = ctk.CTkTextbox(log_frame_lt, height=120,
                                          font=ctk.CTkFont(family="Consolas", size=11))
        self.log_looter.pack(fill="x", padx=10, pady=(2, 8))
        self.log_looter.configure(state="disabled")

    def _save_looter_config(self):
        """Guarda toda la configuración del looter desde la GUI."""
        looter = self.config.looter

        # Método de looteo
        looter["loot_method"] = self.cb_loot_method.get()
        looter["account_type"] = self._account_type_var.get()
        # Compatibilidad: mantener free_account bool para backwards compat
        looter["free_account"] = (self._account_type_var.get() == "free")
        try:
            looter["loot_cooldown"] = float(self.entry_loot_cooldown.get())
        except ValueError:
            looter["loot_cooldown"] = 0.3
        try:
            looter["max_loot_sqms"] = int(self.entry_max_loot_sqms.get())
        except ValueError:
            looter["max_loot_sqms"] = 9

        # Modo de detección (básico / avanzado)
        looter["loot_mode"] = self._loot_mode_var.get()

        # Estrategia kill-first
        looter["always_loot"] = bool(self.cb_always_loot.get())
        try:
            looter["loot_threshold"] = int(self.entry_loot_threshold.get())
        except ValueError:
            looter["loot_threshold"] = 0

        # Drop items
        looter["drop_enabled"] = bool(self.cb_drop_enabled.get())
        looter["drop_items"] = self.entry_drop_items.get()

        # Filtro
        item_filter = looter.setdefault("item_filter", {})
        item_filter["pick_gold"] = bool(self.cb_pick_gold.get())
        item_filter["pick_equipment"] = bool(self.cb_pick_equipment.get())
        item_filter["pick_valuables"] = bool(self.cb_pick_valuables.get())
        item_filter["pick_creature_products"] = bool(self.cb_pick_creature_products.get())
        item_filter["pick_unknown_items"] = bool(self.cb_pick_unknown.get())
        try:
            item_filter["min_item_value"] = int(self.entry_min_value.get())
        except ValueError:
            item_filter["min_item_value"] = 0

        # Backpack routing
        cat_routes = {}
        for cat_key, var in self._bp_route_vars.items():
            try:
                cat_routes[cat_key] = int(var.get())
            except ValueError:
                cat_routes[cat_key] = 0
        looter.setdefault("backpack_routing", {})["category_routes"] = cat_routes

        self.config.looter = looter
        self.config.save()
        # Re-configure engine with new settings
        self.bot.looter_engine.configure(looter)
        self.log.ok("Configuración del Looter guardada")

    def _toggle_looter(self):
        enabled = self.cb_looter_enabled.get()
        self.config.looter_enabled = bool(enabled)
        # Wire to dispatcher + engine
        if enabled:
            # Aplicar configuración actual de la GUI y activar
            self._save_looter_config()
            self.bot.dispatcher.enable_module("looter")
            self.bot.looter_engine.start()
        else:
            self.bot.dispatcher.disable_module("looter")
            self.bot.looter_engine.stop()
            self.config.save()
        self.log.info(f"Looter {'habilitado' if enabled else 'deshabilitado'}")

    def _on_account_type_changed(self):
        """Callback cuando cambian los radio buttons Premium/Free."""
        acct = self._account_type_var.get()
        is_free = (acct == "free")

        # Habilitar/deshabilitar secciones según tipo de cuenta
        # Free Account: mostrar opciones de organización (futuro)
        # Premium: ocultar esas opciones (el cliente lo hace todo)

        # Actualizar tooltips/labels dinámicamente
        if is_free:
            self.log.info("Cuenta FREE seleccionada — loot va a BP principal")
        else:
            self.log.info("Cuenta PREMIUM seleccionada — el cliente organiza el loot")

    # ------------------------------------------------------------------
    # Herramientas visuales del Looter
    # ------------------------------------------------------------------
    def _preview_loot_sqms(self):
        """Captura frame de OBS y dibuja los 9 SQMs del looter como overlay."""
        if not self.bot.capture.is_connected:
            messagebox.showerror("Error", "No hay conexión a OBS.\nConéctate primero.")
            return

        cal = self.bot.calibrator
        if cal.game_region is None or cal.player_center is None:
            messagebox.showerror(
                "Error",
                "El Game Window no está calibrado.\n"
                "Presiona 'Calibrar' en la pestaña Principal.",
            )
            return

        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame de OBS.")
            return

        debug_img = frame.copy()
        gx1, gy1, gx2, gy2 = cal.game_region
        px, py = cal.player_center
        sqm_w, sqm_h = cal.sqm_size

        # Dibujar borde del game window
        cv2.rectangle(debug_img, (gx1, gy1), (gx2, gy2), (0, 255, 255), 2)
        cv2.putText(debug_img, "Game Window", (gx1 + 5, gy1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Dibujar los 9 SQMs
        sqm_labels = ["SW", "S", "SE", "W", "CENTER", "E", "NW", "N", "NE"]
        sqm_offsets = [
            (-1, 1), (0, 1), (1, 1),
            (-1, 0), (0, 0), (1, 0),
            (-1, -1), (0, -1), (1, -1),
        ]

        for i, (dx, dy) in enumerate(sqm_offsets):
            cx = px + dx * sqm_w
            cy = py + dy * sqm_h
            x1 = cx - sqm_w // 2
            y1 = cy - sqm_h // 2
            x2 = x1 + sqm_w
            y2 = y1 + sqm_h

            if i == 4:  # CENTER = player
                color = (0, 0, 255)  # Rojo
                thick = 3
            else:
                color = (0, 255, 0)  # Verde
                thick = 2

            cv2.rectangle(debug_img, (x1, y1), (x2, y2), color, thick)
            # Número del SQM
            cv2.putText(debug_img, f"{i+1}", (cx - 5, cy - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            # Label
            cv2.putText(debug_img, sqm_labels[i], (cx - 10, cy + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        # Player center marker
        cv2.drawMarker(debug_img, (px, py), (0, 0, 255), cv2.MARKER_CROSS, 20, 3)
        cv2.putText(debug_img, "PLAYER", (px - 25, py - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Info text
        info = f"SQM: {sqm_w}x{sqm_h}px | Center: ({px},{py}) | Game: ({gx1},{gy1})-({gx2},{gy2})"
        cv2.putText(debug_img, info, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # Guardar y mostrar
        os.makedirs("debug", exist_ok=True)
        path = os.path.join("debug", "loot_sqms_preview.png")
        cv2.imwrite(path, debug_img)

        # Mostrar en ventana
        self._show_preview_window(
            "🎯 SQMs del Looter — Verificación Visual",
            path,
            f"Los 9 SQMs verdes son donde el Looter clickeará.\n"
            f"El rojo (CENTER) es donde está tu personaje.\n"
            f"SQM size: {sqm_w}×{sqm_h}px | Player: ({px}, {py})\n\n"
            f"Si los cuadros NO coinciden con los tiles del juego,\n"
            f"la calibración del Game Window está incorrecta.",
        )

        # Actualizar label de calibración
        self.lbl_loot_calibration.configure(
            text=f"✅ Calibrado: SQM={sqm_w}×{sqm_h}px, Center=({px},{py}), "
                 f"Game=({gx1},{gy1})-({gx2},{gy2})",
            text_color="#55FF55",
        )

    def _preview_corpse_detection(self):
        """Captura frame y ejecuta el corpse_detector, mostrando qué detectó."""
        if not self.bot.capture.is_connected:
            messagebox.showerror("Error", "No hay conexión a OBS.\nConéctate primero.")
            return

        cal = self.bot.calibrator
        if cal.game_region is None:
            messagebox.showerror(
                "Error",
                "El Game Window no está calibrado.\n"
                "Presiona 'Calibrar' en la pestaña Principal.",
            )
            return

        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame de OBS.")
            return

        detector = self.bot.looter_engine.corpse_detector

        # Asegurar que tiene la configuración
        if detector._game_region is None:
            gx1, gy1, gx2, gy2 = cal.game_region
            detector.set_game_region(gx1, gy1, gx2, gy2)
        if cal.player_center:
            detector.set_player_center(*cal.player_center)
        if cal.sqm_size:
            detector.set_sqm_size(*cal.sqm_size)

        # Ejecutar detección
        corpses = detector.detect_corpses(frame)

        # Generar overlay de debug
        debug_img = detector.get_debug_overlay(frame)

        # Además dibujar las máscaras HSV como miniatura
        gx1, gy1, gx2, gy2 = cal.game_region
        game_roi = frame[gy1:gy2, gx1:gx2]
        hsv = cv2.cvtColor(game_roi, cv2.COLOR_BGR2HSV)

        # Máscara de aura (blanco + amarillo)
        mask_w = cv2.inRange(hsv, detector.aura_white_lower, detector.aura_white_upper)
        mask_y = cv2.inRange(hsv, detector.aura_yellow_lower, detector.aura_yellow_upper)
        aura_mask = cv2.bitwise_or(mask_w, mask_y)

        # Máscara de sangre
        mask_r1 = cv2.inRange(hsv, detector.blood_red_lower1, detector.blood_red_upper1)
        mask_r2 = cv2.inRange(hsv, detector.blood_red_lower2, detector.blood_red_upper2)
        mask_g = cv2.inRange(hsv, detector.blood_green_lower, detector.blood_green_upper)
        blood_mask = cv2.bitwise_or(cv2.bitwise_or(mask_r1, mask_r2), mask_g)

        # Guardar imágenes
        os.makedirs("debug", exist_ok=True)
        cv2.imwrite(os.path.join("debug", "corpse_detection_overlay.png"), debug_img)
        cv2.imwrite(os.path.join("debug", "corpse_aura_mask.png"), aura_mask)
        cv2.imwrite(os.path.join("debug", "corpse_blood_mask.png"), blood_mask)
        cv2.imwrite(os.path.join("debug", "corpse_game_roi.png"), game_roi)

        n = len(corpses)
        path = os.path.join("debug", "corpse_detection_overlay.png")
        self._show_preview_window(
            f"💀 Detección de Cadáveres — {n} encontrado(s)",
            path,
            f"Cadáveres detectados: {n}\n"
            f"{'Posiciones: ' + str(corpses) if corpses else 'No se detectaron cadáveres.'}\n\n"
            f"Imágenes guardadas en debug/:\n"
            f"  • corpse_detection_overlay.png — Frame con overlay\n"
            f"  • corpse_aura_mask.png — Máscara de aura (blanco/amarillo)\n"
            f"  • corpse_blood_mask.png — Máscara de sangre (rojo/verde)\n"
            f"  • corpse_game_roi.png — Game window recortado\n\n"
            f"💡 Si hay un cadáver visible y NO lo detectó:\n"
            f"  1. Revisa corpse_aura_mask.png — ¿se ve el aura?\n"
            f"  2. Si NO se ve, los umbrales HSV necesitan ajuste\n"
            f"  3. Si detecta MUCHO ruido, los umbrales son muy amplios\n"
            f"  4. El fallback ciego (9 SQMs) SIEMPRE funciona como respaldo",
        )

    def _capture_floor_reference(self):
        """Captura una imagen de referencia del suelo/piso para futura diferenciación."""
        if not self.bot.capture.is_connected:
            messagebox.showerror("Error", "No hay conexión a OBS.\nConéctate primero.")
            return

        cal = self.bot.calibrator
        if cal.game_region is None or cal.player_center is None:
            messagebox.showerror(
                "Error",
                "El Game Window no está calibrado.\n"
                "Presiona 'Calibrar' en la pestaña Principal.",
            )
            return

        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame de OBS.")
            return

        px, py = cal.player_center
        sqm_w, sqm_h = cal.sqm_size

        # Capturar un SQM de piso limpio (el que está debajo del player)
        # En la mayoría de situaciones, el player está parado en piso normal
        x1 = px - sqm_w // 2
        y1 = py - sqm_h // 2
        x2 = x1 + sqm_w
        y2 = y1 + sqm_h

        h_f, w_f = frame.shape[:2]
        x1 = max(0, min(x1, w_f - 1))
        y1 = max(0, min(y1, h_f - 1))
        x2 = max(x1 + 1, min(x2, w_f))
        y2 = max(y1 + 1, min(y2, h_f))

        floor_tile = frame[y1:y2, x1:x2]

        # Guardar
        os.makedirs(os.path.join("images", "Looter"), exist_ok=True)
        save_path = os.path.join("images", "Looter", "floor_reference.png")
        cv2.imwrite(save_path, floor_tile)

        # También guardar los 8 SQMs vecinos como referencia
        sqm_offsets = [
            ("N", 0, -1), ("S", 0, 1), ("E", 1, 0), ("W", -1, 0),
            ("NE", 1, -1), ("NW", -1, -1), ("SE", 1, 1), ("SW", -1, 1),
        ]
        saved_tiles = 1
        for label, dx, dy in sqm_offsets:
            sx = px + dx * sqm_w - sqm_w // 2
            sy = py + dy * sqm_h - sqm_h // 2
            sx2 = sx + sqm_w
            sy2 = sy + sqm_h
            sx = max(0, min(sx, w_f - 1))
            sy = max(0, min(sy, h_f - 1))
            sx2 = max(sx + 1, min(sx2, w_f))
            sy2 = max(sy + 1, min(sy2, h_f))
            tile = frame[sy:sy2, sx:sx2]
            tile_path = os.path.join("images", "Looter", f"floor_{label}.png")
            cv2.imwrite(tile_path, tile)
            saved_tiles += 1

        # Preview compuesto
        debug_img = frame.copy()
        for dx, dy in [(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]:
            sx = px + dx * sqm_w - sqm_w // 2
            sy = py + dy * sqm_h - sqm_h // 2
            color = (0, 255, 255) if (dx, dy) == (0, 0) else (255, 200, 0)
            cv2.rectangle(debug_img, (sx, sy), (sx + sqm_w, sy + sqm_h), color, 2)

        os.makedirs("debug", exist_ok=True)
        preview_path = os.path.join("debug", "floor_capture_preview.png")
        cv2.imwrite(preview_path, debug_img)

        self._show_preview_window(
            "🔧 Referencia de Suelo Capturada",
            preview_path,
            f"Se capturaron {saved_tiles} tiles de referencia del suelo.\n"
            f"Guardados en images/Looter/\n"
            f"  • floor_reference.png — Tile central (bajo el player)\n"
            f"  • floor_N.png, floor_S.png, etc. — Tiles vecinos\n\n"
            f"Tile size: {sqm_w}×{sqm_h}px\n\n"
            f"💡 PARA QUÉ SIRVE:\n"
            f"  Estas imágenes permiten al detector comparar el suelo\n"
            f"  'limpio' vs un SQM con cadáver/items encima.\n"
            f"  → Captura en un área SIN cadáveres para obtener\n"
            f"     una buena referencia del piso.",
        )
        self.log.ok(f"Referencia de suelo capturada: {saved_tiles} tiles en images/Looter/")

    def _update_corpse_templates_info(self):
        """Actualiza el label con info de templates de cadáveres disponibles."""
        corpse_dir = os.path.join("corpse_loot")
        templates = {}
        if os.path.isdir(corpse_dir):
            for fname in os.listdir(corpse_dir):
                if fname.endswith(".png"):
                    raw = fname.replace(".png", "")
                    # snake_case → display
                    if "_" in raw:
                        display = " ".join(w.capitalize() for w in raw.split("_"))
                    else:
                        display = ""
                        for i, ch in enumerate(raw):
                            if ch.isupper() and i > 0 and raw[i - 1].islower():
                                display += " "
                            display += ch
                    img = cv2.imread(os.path.join(corpse_dir, fname))
                    if img is not None:
                        templates[display] = (img.shape[1], img.shape[0], fname)

        if not templates:
            self.lbl_corpse_templates_info.configure(
                text="❌ No hay templates de cadáveres.\n"
                     "   Usa '📸 Capturar Template de Cadáver' para agregar.",
                text_color="#FF6666",
            )
            return

        lines = [f"Templates de cadáveres: {len(templates)} disponibles"]
        for name, (w, h, fname) in sorted(templates.items()):
            lines.append(f"  💀 {name} — {w}×{h}px ({fname})")

        self.lbl_corpse_templates_info.configure(
            text="\n".join(lines),
            text_color="#55FF55",
        )

    def _capture_corpse_template(self):
        """Captura frame de OBS y abre ventana de selección drag para recortar cadáver."""
        if not self.bot.capture.is_connected:
            messagebox.showerror("Error", "No hay conexión a OBS.\nConéctate primero.")
            return

        cal = self.bot.calibrator
        if cal.game_region is None or cal.player_center is None:
            messagebox.showerror(
                "Error",
                "El Game Window no está calibrado.\n"
                "Presiona 'Calibrar' en la pestaña Principal.",
            )
            return

        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame de OBS.")
            return

        # Recortar game window para mostrar solo el área de juego
        gx1, gy1, gx2, gy2 = cal.game_region
        h_f, w_f = frame.shape[:2]
        gx1 = max(0, min(gx1, w_f - 1))
        gy1 = max(0, min(gy1, h_f - 1))
        gx2 = max(gx1 + 1, min(gx2, w_f))
        gy2 = max(gy1 + 1, min(gy2, h_f))
        game_roi = frame[gy1:gy2, gx1:gx2]

        # Abrir ventana de selección con drag
        self._open_drag_select_window(game_roi, frame, (gx1, gy1))

    def _open_drag_select_window(
        self,
        game_roi: np.ndarray,
        full_frame: np.ndarray,
        roi_offset: Tuple[int, int],
    ):
        """
        Abre una ventana donde el usuario puede dibujar un rectángulo
        sobre el game window para seleccionar el sprite del cadáver.
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("📸 Seleccionar Cadáver — Dibuja un rectángulo sobre el cuerpo")
        dialog.focus_force()
        dialog.grab_set()

        # Estado de la selección
        state = {
            "start_x": 0, "start_y": 0,
            "end_x": 0, "end_y": 0,
            "dragging": False,
            "rect_id": None,
            "selection_done": False,
        }

        # Convertir imagen para tkinter
        roi_rgb = cv2.cvtColor(game_roi, cv2.COLOR_BGR2RGB)
        roi_h, roi_w = roi_rgb.shape[:2]

        # Calcular escala para que quepa en pantalla
        max_display_w, max_display_h = 1000, 650
        scale = min(max_display_w / roi_w, max_display_h / roi_h, 1.0)
        display_w = int(roi_w * scale)
        display_h = int(roi_h * scale)

        if scale < 1.0:
            display_rgb = cv2.resize(roi_rgb, (display_w, display_h), interpolation=cv2.INTER_AREA)
        else:
            display_rgb = roi_rgb.copy()

        dialog.geometry(f"{display_w + 20}x{display_h + 200}")

        # Instrucciones
        ctk.CTkLabel(
            dialog,
            text="🖱️ Haz clic y arrastra para seleccionar el cadáver/sprite.\n"
                 "El rectángulo se dibujará en amarillo. Luego haz clic en 'Guardar'.",
            font=ctk.CTkFont(size=12),
            text_color="#F1C40F",
        ).pack(padx=10, pady=(8, 4))

        # Info de escala
        sqm_w, sqm_h = self.bot.calibrator.sqm_size
        ctk.CTkLabel(
            dialog,
            text=f"SQM: {sqm_w}×{sqm_h}px | Escala display: {scale:.2f}x | "
                 f"Game Window: {roi_w}×{roi_h}px",
            font=ctk.CTkFont(size=10), text_color="#888888",
        ).pack(padx=10, pady=(0, 4))

        # Canvas con la imagen
        pil_img = Image.fromarray(display_rgb)
        tk_img = ImageTk.PhotoImage(pil_img)

        canvas = tk.Canvas(dialog, width=display_w, height=display_h,
                           bg="black", cursor="crosshair")
        canvas.pack(padx=10, pady=5)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas._tk_img = tk_img  # keep reference

        # Dibujar grid de SQMs para referencia
        px_local = self.bot.calibrator.player_center[0] - roi_offset[0]
        py_local = self.bot.calibrator.player_center[1] - roi_offset[1]
        for dx in range(-7, 8):
            for dy in range(-5, 6):
                sx = int((px_local + dx * sqm_w - sqm_w / 2) * scale)
                sy = int((py_local + dy * sqm_h - sqm_h / 2) * scale)
                ex = int((px_local + dx * sqm_w + sqm_w / 2) * scale)
                ey = int((py_local + dy * sqm_h + sqm_h / 2) * scale)
                color = "#FF0000" if dx == 0 and dy == 0 else "#333333"
                canvas.create_rectangle(sx, sy, ex, ey, outline=color, width=1)

        # Label de selección
        lbl_sel = ctk.CTkLabel(
            dialog, text="Selección: (ninguna)",
            font=ctk.CTkFont(size=11),
        )
        lbl_sel.pack(pady=2)

        # Eventos de mouse
        def on_press(event):
            state["start_x"] = event.x
            state["start_y"] = event.y
            state["dragging"] = True
            if state["rect_id"]:
                canvas.delete(state["rect_id"])

        def on_drag(event):
            if not state["dragging"]:
                return
            state["end_x"] = event.x
            state["end_y"] = event.y
            if state["rect_id"]:
                canvas.delete(state["rect_id"])
            state["rect_id"] = canvas.create_rectangle(
                state["start_x"], state["start_y"],
                state["end_x"], state["end_y"],
                outline="#FFFF00", width=2,
            )
            # Calcular tamaño real (sin escala)
            real_w = abs(state["end_x"] - state["start_x"]) / scale
            real_h = abs(state["end_y"] - state["start_y"]) / scale
            lbl_sel.configure(text=f"Selección: {real_w:.0f}×{real_h:.0f}px (real)")

        def on_release(event):
            state["dragging"] = False
            state["end_x"] = event.x
            state["end_y"] = event.y
            state["selection_done"] = True

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        # Botones
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=8)

        def on_save():
            if not state["selection_done"]:
                messagebox.showwarning("Aviso", "Primero dibuja un rectángulo sobre el cadáver.")
                return

            # Convertir coordenadas de display a coordenadas reales de la ROI
            x1 = int(min(state["start_x"], state["end_x"]) / scale)
            y1 = int(min(state["start_y"], state["end_y"]) / scale)
            x2 = int(max(state["start_x"], state["end_x"]) / scale)
            y2 = int(max(state["start_y"], state["end_y"]) / scale)

            # Clamp
            x1 = max(0, min(x1, roi_w - 1))
            y1 = max(0, min(y1, roi_h - 1))
            x2 = max(x1 + 1, min(x2, roi_w))
            y2 = max(y1 + 1, min(y2, roi_h))

            crop = game_roi[y1:y2, x1:x2]
            if crop.size == 0:
                messagebox.showerror("Error", "La selección está vacía.")
                return

            # Pedir nombre de la criatura
            name = self._ask_corpse_name(crop)
            if name is None or name.strip() == "":
                return

            # Guardar
            corpse_dir = "corpse_loot"
            os.makedirs(corpse_dir, exist_ok=True)

            # Nombre de archivo: snake_case
            file_name = name.strip().lower().replace(" ", "_")
            save_path = os.path.join(corpse_dir, f"{file_name}.png")

            if os.path.exists(save_path):
                overwrite = messagebox.askyesno(
                    "Template existente",
                    f"Ya existe '{file_name}.png'.\n¿Sobrescribir?",
                )
                if not overwrite:
                    return

            cv2.imwrite(save_path, crop)
            self.log.ok(
                f"Template de cadáver guardado: {file_name}.png "
                f"({crop.shape[1]}×{crop.shape[0]}px)"
            )

            # Recargar templates en el detector
            try:
                self.bot.looter_engine.corpse_template_detector.load_templates()
                self.log.ok("Templates de cadáveres recargados")
            except Exception as e:
                self.log.warn(f"Error recargando templates: {e}")

            self._update_corpse_templates_info()
            dialog.destroy()
            messagebox.showinfo(
                "Listo",
                f"Template guardado: {file_name}.png\n"
                f"Tamaño: {crop.shape[1]}×{crop.shape[0]}px\n\n"
                f"El detector lo usará automáticamente para buscar\n"
                f"cadáveres de {name.strip()} en el game window.",
            )

        ctk.CTkButton(
            btn_frame, text="💾 Guardar Template", width=180,
            fg_color="#27AE60", hover_color="#2ECC71",
            command=on_save,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="📸 Recapturar Frame", width=160,
            fg_color="#2980B9", hover_color="#3498DB",
            command=lambda: self._recapture_in_dialog(dialog, canvas, state, scale, lbl_sel, roi_offset),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="❌ Cancelar", width=120,
            fg_color="#C0392B", hover_color="#E74C3C",
            command=dialog.destroy,
        ).pack(side="left", padx=5)

    def _recapture_in_dialog(self, dialog, canvas, state, scale, lbl_sel, roi_offset):
        """Recaptura el frame de OBS sin cerrar la ventana de selección."""
        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame.")
            return

        cal = self.bot.calibrator
        gx1, gy1, gx2, gy2 = cal.game_region
        h_f, w_f = frame.shape[:2]
        gx1 = max(0, min(gx1, w_f - 1))
        gy1 = max(0, min(gy1, h_f - 1))
        gx2 = max(gx1 + 1, min(gx2, w_f))
        gy2 = max(gy1 + 1, min(gy2, h_f))
        game_roi = frame[gy1:gy2, gx1:gx2]

        roi_rgb = cv2.cvtColor(game_roi, cv2.COLOR_BGR2RGB)
        roi_h, roi_w = roi_rgb.shape[:2]
        display_w = int(roi_w * scale)
        display_h = int(roi_h * scale)

        if scale < 1.0:
            display_rgb = cv2.resize(roi_rgb, (display_w, display_h), interpolation=cv2.INTER_AREA)
        else:
            display_rgb = roi_rgb.copy()

        pil_img = Image.fromarray(display_rgb)
        tk_img = ImageTk.PhotoImage(pil_img)

        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas._tk_img = tk_img

        # Redibujar grid
        sqm_w, sqm_h = cal.sqm_size
        px_local = cal.player_center[0] - roi_offset[0]
        py_local = cal.player_center[1] - roi_offset[1]
        for dx in range(-7, 8):
            for dy in range(-5, 6):
                sx = int((px_local + dx * sqm_w - sqm_w / 2) * scale)
                sy = int((py_local + dy * sqm_h - sqm_h / 2) * scale)
                ex = int((px_local + dx * sqm_w + sqm_w / 2) * scale)
                ey = int((py_local + dy * sqm_h + sqm_h / 2) * scale)
                color = "#FF0000" if dx == 0 and dy == 0 else "#333333"
                canvas.create_rectangle(sx, sy, ex, ey, outline=color, width=1)

        state["rect_id"] = None
        state["selection_done"] = False
        lbl_sel.configure(text="Selección: (recapturado — dibuja de nuevo)")
        # Guardar referencia al nuevo game_roi para el save
        canvas._game_roi = game_roi
        self.log.info("Frame recapturado en ventana de selección")

    def _ask_corpse_name(self, crop: np.ndarray) -> Optional[str]:
        """Muestra diálogo para nombrar el template de cadáver."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nombrar Template de Cadáver")
        dialog.geometry("450x300")
        dialog.grab_set()
        dialog.focus_force()

        result = {"value": None}

        ctk.CTkLabel(
            dialog, text="Template capturado",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            dialog,
            text=f"Tamaño: {crop.shape[1]}×{crop.shape[0]}px",
            font=ctk.CTkFont(size=11), text_color="#AAAAAA",
        ).pack()

        # Preview
        try:
            preview = cv2.resize(crop, (crop.shape[1] * 4, crop.shape[0] * 4),
                                 interpolation=cv2.INTER_NEAREST)
            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(preview_rgb)
            max_w = 400
            if pil_img.width > max_w:
                ratio = max_w / pil_img.width
                pil_img = pil_img.resize(
                    (int(pil_img.width * ratio), int(pil_img.height * ratio)),
                    Image.NEAREST,
                )
            tk_img = ImageTk.PhotoImage(pil_img)
            img_label = ctk.CTkLabel(dialog, text="", image=tk_img)
            img_label.image = tk_img
            img_label.pack(pady=8)
        except Exception:
            ctk.CTkLabel(dialog, text="(Preview no disponible)").pack(pady=8)

        ctk.CTkLabel(
            dialog,
            text="Nombre de la criatura (ej: Swamp Troll, Cave Rat):",
            font=ctk.CTkFont(size=12),
        ).pack(padx=20, anchor="w")

        entry = ctk.CTkEntry(dialog, width=300, placeholder_text="Nombre de la criatura...")
        entry.pack(padx=20, pady=5)
        entry.focus()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        def on_save():
            result["value"] = entry.get()
            dialog.destroy()

        def on_cancel():
            result["value"] = None
            dialog.destroy()

        entry.bind("<Return>", lambda e: on_save())

        ctk.CTkButton(
            btn_frame, text="💾 Guardar", width=120,
            fg_color="#27AE60", hover_color="#2ECC71",
            command=on_save,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="❌ Cancelar", width=100,
            fg_color="#C0392B", hover_color="#E74C3C",
            command=on_cancel,
        ).pack(side="left", padx=5)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.wait_window()
        return result["value"]

    def _show_preview_window(self, title: str, image_path: str, description: str):
        """Muestra una ventana de preview con una imagen y descripción."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("900x700")
        dialog.focus_force()

        # Descripción arriba
        desc_frame = ctk.CTkFrame(dialog)
        desc_frame.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(
            desc_frame, text=description,
            font=ctk.CTkFont(family="Consolas", size=11),
            justify="left",
        ).pack(anchor="w", padx=10, pady=8)

        # Imagen
        try:
            pil_img = Image.open(image_path)
            # Escalar si es muy grande
            max_w, max_h = 860, 520
            ratio = min(max_w / pil_img.width, max_h / pil_img.height)
            if ratio < 1:
                new_w = int(pil_img.width * ratio)
                new_h = int(pil_img.height * ratio)
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

            tk_img = ImageTk.PhotoImage(pil_img)
            img_label = ctk.CTkLabel(dialog, text="", image=tk_img)
            img_label.image = tk_img
            img_label.pack(padx=10, pady=5)
        except Exception as e:
            ctk.CTkLabel(dialog, text=f"Error cargando imagen: {e}").pack(pady=20)

        # Botón cerrar
        ctk.CTkButton(
            dialog, text="Cerrar", width=120,
            command=dialog.destroy,
        ).pack(pady=10)

        # Botón abrir carpeta debug
        ctk.CTkButton(
            dialog, text="📁 Abrir carpeta debug/",
            width=180, fg_color="#7F8C8D",
            command=lambda: os.startfile(os.path.abspath("debug")),
        ).pack(pady=(0, 10))

    def _test_manual_loot(self):
        """Ejecuta una prueba manual del loot para verificar coordenadas."""
        if not self.bot.looter_engine.enabled:
            messagebox.showwarning(
                "Looter deshabilitado",
                "El Looter no está habilitado.\n"
                "Actívalo primero con el switch 'Looter habilitado'."
            )
            return

        # Obtener información de debug antes del test
        debug_info = self.bot.looter_engine.debug_coordinates()

        # Mostrar información previa
        info_text = (
            f"🧪 TEST MANUAL DE LOOT\n\n"
            f"SQMs disponibles: {debug_info['sqms_available']}\n"
            f"Usando SQMs fijos: {'SÍ' if debug_info['using_fixed_sqms'] else 'NO'}\n"
            f"Player center: {debug_info['player_center']}\n"
            f"SQM size: {debug_info['sqm_size']}\n"
            f"Max loot SQMs: {debug_info['max_loot_sqms']}\n\n"
            f"Coordenadas calculadas:\n"
        )

        for i, coord in enumerate(debug_info['calculated_loot_sqms']):
            info_text += f"  {i+1}. {coord}\n"

        info_text += (
            f"\n¿Ejecutar {len(debug_info['calculated_loot_sqms'])} clicks de prueba?\n\n"
            f"⚠ Asegúrate de que Tibia esté visible y el cursor\n"
            f"no interfiera con el área de juego."
        )

        # Confirmar ejecución
        if not messagebox.askyesno("Confirmar Test", info_text):
            return

        # Ejecutar test
        success = self.bot.looter_engine.test_loot_clicks("MANUAL_TEST")

        if success:
            self.log.info("🧪 Test manual de loot iniciado — revisa el log del Looter")
            messagebox.showinfo(
                "Test ejecutado",
                "Test de loot ejecutado correctamente.\n\n"
                "Revisa:\n"
                "• Los clicks se ejecutaron en las posiciones correctas\n"
                "• El log del Looter muestra las coordenadas usadas\n"
                "• No hay errores en el log principal\n\n"
                "Si los clicks van a posiciones incorrectas,\n"
                "recalibra presionando 'Calibrar' en la pestaña Principal."
            )
        else:
            messagebox.showerror(
                "Error en test",
                "No se pudo ejecutar el test de loot.\n"
                "Verifica que el looter esté correctamente configurado."
            )

    # ==================================================================
    # Corpse Sprite Detection - Captura de Sprites de Cadáveres (v11)
    # ==================================================================
    def _update_sprites_info(self):
        """Actualiza el label con info de sprites de cadáveres disponibles."""
        from looter.corpse_sprite_detector import CORPSE_SPRITES_DIR
        sprites = {}
        if os.path.isdir(CORPSE_SPRITES_DIR):
            for fname in os.listdir(CORPSE_SPRITES_DIR):
                if fname.lower().endswith(".png"):
                    base = fname.replace(".png", "").replace(".PNG", "")
                    # Separar variantes: "Rotworm_2" → "Rotworm"
                    parts = base.rsplit("_", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        display_name = parts[0]
                    else:
                        display_name = base
                    img = cv2.imread(os.path.join(CORPSE_SPRITES_DIR, fname))
                    if img is not None:
                        if display_name not in sprites:
                            sprites[display_name] = []
                        sprites[display_name].append(
                            (img.shape[1], img.shape[0], fname)
                        )

        if not sprites:
            self.lbl_sprites_info.configure(
                text="❌ No hay sprites de cadáveres capturados.\n"
                     "   Mata una criatura y usa '💀 Capturar Sprite de Cadáver'\n"
                     "   para que el bot pueda encontrar los cuerpos muertos.",
                text_color="#FF6666",
            )
            return

        total = sum(len(v) for v in sprites.values())
        lines = [f"✅ Sprites de cadáveres: {total} sprites de {len(sprites)} criaturas"]
        for name, variants in sorted(sprites.items()):
            for w, h, fname in variants:
                lines.append(f"  💀 {name} — {w}×{h}px ({fname})")

        self.lbl_sprites_info.configure(
            text="\n".join(lines),
            text_color="#55FF55",
        )

    def _capture_corpse_sprite(self):
        """
        Captura un sprite de cadáver desde el game screen.
        Abre ventana interactiva donde el usuario hace clic en el cuerpo
        muerto para capturar un recorte de 32x32 centrado en el punto de clic.
        """
        if not self.bot.capture.is_connected:
            messagebox.showerror("Error", "No hay conexión a OBS.\nConéctate primero.")
            return

        cal = self.bot.calibrator
        if cal.game_region is None or cal.player_center is None:
            messagebox.showerror(
                "Error",
                "El Game Window no está calibrado.\n"
                "Presiona 'Calibrar' en la pestaña Principal.",
            )
            return

        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame de OBS.")
            return

        # Recortar game window
        gx1, gy1, gx2, gy2 = cal.game_region
        h_f, w_f = frame.shape[:2]
        gx1 = max(0, min(gx1, w_f - 1))
        gy1 = max(0, min(gy1, h_f - 1))
        gx2 = max(gx1 + 1, min(gx2, w_f))
        gy2 = max(gy1 + 1, min(gy2, h_f))
        game_roi = frame[gy1:gy2, gx1:gx2]

        self._open_sprite_capture_window(game_roi, frame, (gx1, gy1))

    def _open_sprite_capture_window(
        self,
        game_roi: np.ndarray,
        full_frame: np.ndarray,
        roi_offset: Tuple[int, int],
    ):
        """
        Abre ventana donde el usuario hace clic en una criatura para
        capturar un sprite de 32×32 (o tamaño customizable).
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("💀 Capturar Sprite de Cadáver — Haz clic sobre el cuerpo")
        dialog.focus_force()
        dialog.grab_set()

        # Estado
        state = {
            "click_x": 0, "click_y": 0,
            "sprite_size": 32,
            "preview_id": None,
            "click_done": False,
        }

        # Convertir imagen para tkinter
        roi_rgb = cv2.cvtColor(game_roi, cv2.COLOR_BGR2RGB)
        roi_h, roi_w = roi_rgb.shape[:2]

        # Escala para display
        max_display_w, max_display_h = 1000, 650
        scale = min(max_display_w / roi_w, max_display_h / roi_h, 1.0)
        display_w = int(roi_w * scale)
        display_h = int(roi_h * scale)

        if scale < 1.0:
            display_rgb = cv2.resize(roi_rgb, (display_w, display_h),
                                      interpolation=cv2.INTER_AREA)
        else:
            display_rgb = roi_rgb.copy()

        dialog.geometry(f"{max(display_w + 40, 600)}x{min(display_h + 450, 900)}")
        dialog.resizable(True, True)
        dialog.minsize(500, 500)

        # Instrucciones
        ctk.CTkLabel(
            dialog,
            text=(
                "🖱️ Haz clic EXACTAMENTE sobre el CUERPO MUERTO de la criatura.\n"
                "Se recortará un cuadrado centrado en donde hagas clic.\n"
                "Puedes ajustar el tamaño del recorte abajo."
            ),
            font=ctk.CTkFont(size=12),
            text_color="#E74C3C",
        ).pack(padx=10, pady=(8, 4))

        # Controles de tamaño
        size_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        size_frame.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(size_frame, text="Tamaño del sprite:").pack(side="left", padx=5)
        size_var = ctk.StringVar(value="32")
        size_combo = ctk.CTkComboBox(
            size_frame, values=["24", "32", "48", "64"],
            variable=size_var, width=80,
        )
        size_combo.pack(side="left", padx=5)
        ctk.CTkLabel(size_frame, text="px",
                      font=ctk.CTkFont(size=11)).pack(side="left")

        def on_size_change(*_):
            try:
                state["sprite_size"] = int(size_var.get())
            except ValueError:
                state["sprite_size"] = 32
        size_var.trace_add("write", on_size_change)

        # Info
        sqm_w, sqm_h = self.bot.calibrator.sqm_size
        ctk.CTkLabel(
            dialog,
            text=f"SQM: {sqm_w}×{sqm_h}px | Escala: {scale:.2f}x | "
                 f"Game: {roi_w}×{roi_h}px | Default sprite: 32×32px",
            font=ctk.CTkFont(size=10), text_color="#888888",
        ).pack(padx=10, pady=(0, 4))

        # Canvas con imagen (sin expand para no robarse el espacio de los botones)
        pil_img = Image.fromarray(display_rgb)
        tk_img = ImageTk.PhotoImage(pil_img)

        canvas = tk.Canvas(dialog, width=display_w, height=display_h,
                           bg="black", cursor="crosshair")
        canvas.pack(padx=10, pady=5)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas._tk_img = tk_img

        # Grid de SQMs
        px_local = self.bot.calibrator.player_center[0] - roi_offset[0]
        py_local = self.bot.calibrator.player_center[1] - roi_offset[1]
        for dx in range(-4, 5):
            for dy in range(-3, 4):
                sx = int((px_local + dx * sqm_w - sqm_w / 2) * scale)
                sy = int((py_local + dy * sqm_h - sqm_h / 2) * scale)
                ex = int((px_local + dx * sqm_w + sqm_w / 2) * scale)
                ey = int((py_local + dy * sqm_h + sqm_h / 2) * scale)
                color = "#FF0000" if dx == 0 and dy == 0 else "#333333"
                canvas.create_rectangle(sx, sy, ex, ey, outline=color, width=1)

        # Label de preview de coordenadas
        lbl_preview = ctk.CTkLabel(
            dialog, text="👆 Haz clic en el cadáver de una criatura...",
            font=ctk.CTkFont(size=11),
        )
        lbl_preview.pack(padx=10, pady=2)

        # Preview del sprite capturado
        sprite_preview_label = ctk.CTkLabel(dialog, text="")
        sprite_preview_label.pack(pady=2)

        # ── Botones (siempre visibles al final) ──────────────
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(4, 10))

        def on_click(event):
            # Coordenadas reales en el ROI
            real_x = int(event.x / scale)
            real_y = int(event.y / scale)
            state["click_x"] = real_x
            state["click_y"] = real_y
            state["click_done"] = True

            size = state["sprite_size"]
            half = size // 2

            # Dibujar cuadrado de preview en el canvas
            if state["preview_id"]:
                canvas.delete(state["preview_id"])

            # Convertir a coords de display
            dx1 = int((real_x - half) * scale)
            dy1 = int((real_y - half) * scale)
            dx2 = int((real_x + half) * scale)
            dy2 = int((real_y + half) * scale)
            state["preview_id"] = canvas.create_rectangle(
                dx1, dy1, dx2, dy2, outline="#00FF00", width=2,
            )

            lbl_preview.configure(
                text=f"Sprite: ({real_x},{real_y}) — {size}×{size}px | "
                     f"Click 'Guardar' para guardar"
            )

            # Mostrar preview del sprite recortado
            x1c = max(0, real_x - half)
            y1c = max(0, real_y - half)
            x2c = min(roi_w, real_x + half)
            y2c = min(roi_h, real_y + half)
            crop = game_roi[y1c:y2c, x1c:x2c]
            if crop.size > 0:
                # Escalar para preview (×3)
                preview = cv2.resize(crop, (size * 3, size * 3),
                                      interpolation=cv2.INTER_NEAREST)
                preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
                pil_preview = Image.fromarray(preview_rgb)
                tk_preview = ImageTk.PhotoImage(pil_preview)
                sprite_preview_label.configure(image=tk_preview)
                sprite_preview_label._tk_img = tk_preview

        canvas.bind("<Button-1>", on_click)

        def on_save():
            if not state["click_done"]:
                messagebox.showwarning("Aviso",
                                        "Primero haz clic sobre la criatura.")
                return

            size = state["sprite_size"]
            half = size // 2
            real_x = state["click_x"]
            real_y = state["click_y"]

            x1 = max(0, real_x - half)
            y1 = max(0, real_y - half)
            x2 = min(roi_w, real_x + half)
            y2 = min(roi_h, real_y + half)

            crop = game_roi[y1:y2, x1:x2]
            if crop.size == 0:
                messagebox.showerror("Error", "La captura está vacía.")
                return

            # Pedir nombre de la criatura
            name = self._ask_sprite_name(crop)
            if name is None or name.strip() == "":
                return

            # Guardar como sprite de cadáver
            from looter.corpse_sprite_detector import CorpseSpriteDetector
            variant = CorpseSpriteDetector.get_next_variant_number(name.strip())
            save_path = CorpseSpriteDetector.save_corpse_sprite(
                crop, name.strip(), variant
            )

            self.log.ok(
                f"Sprite de cadáver guardado: {os.path.basename(save_path)} "
                f"({crop.shape[1]}×{crop.shape[0]}px)"
            )

            # Recargar sprites en el corpse sprite detector del looter
            try:
                self.bot.looter_engine.corpse_sprite_detector.load_templates()
                self.log.ok("Sprites de cadáveres recargados en el Looter")
            except Exception as e:
                self.log.warning(f"Error recargando sprites: {e}")

            self._update_sprites_info()
            dialog.destroy()
            messagebox.showinfo(
                "Listo",
                f"Sprite de cadáver guardado: {os.path.basename(save_path)}\n"
                f"Tamaño: {crop.shape[1]}×{crop.shape[0]}px\n\n"
                f"El Looter buscará este sprite en el game screen\n"
                f"después de matar un(a) '{name.strip()}'.\n"
                f"Cuando lo encuentre, clickeará exactamente\n"
                f"sobre el cadáver para lootear.",
            )

        ctk.CTkButton(
            btn_frame, text="💾 Guardar Sprite", width=180,
            fg_color="#27AE60", hover_color="#2ECC71",
            command=on_save,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="📸 Recapturar", width=160,
            fg_color="#2980B9", hover_color="#3498DB",
            command=lambda: self._recapture_sprite_dialog(
                dialog, canvas, state, scale, lbl_preview,
                sprite_preview_label, roi_offset
            ),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="❌ Cancelar", width=120,
            fg_color="#C0392B", hover_color="#E74C3C",
            command=dialog.destroy,
        ).pack(side="left", padx=5)

    def _recapture_sprite_dialog(self, dialog, canvas, state, scale,
                                   lbl_preview, sprite_preview_label,
                                   roi_offset):
        """Recaptura el frame sin cerrar la ventana de captura de sprites."""
        frame = self.bot.capture.capture_source()
        if frame is None:
            messagebox.showerror("Error", "No se pudo capturar frame.")
            return

        cal = self.bot.calibrator
        gx1, gy1, gx2, gy2 = cal.game_region
        h_f, w_f = frame.shape[:2]
        gx1 = max(0, min(gx1, w_f - 1))
        gy1 = max(0, min(gy1, h_f - 1))
        gx2 = max(gx1 + 1, min(gx2, w_f))
        gy2 = max(gy1 + 1, min(gy2, h_f))
        game_roi = frame[gy1:gy2, gx1:gx2]

        roi_rgb = cv2.cvtColor(game_roi, cv2.COLOR_BGR2RGB)
        roi_h, roi_w = roi_rgb.shape[:2]
        display_w = int(roi_w * scale)
        display_h = int(roi_h * scale)

        if scale < 1.0:
            display_rgb = cv2.resize(roi_rgb, (display_w, display_h),
                                      interpolation=cv2.INTER_AREA)
        else:
            display_rgb = roi_rgb.copy()

        pil_img = Image.fromarray(display_rgb)
        tk_img = ImageTk.PhotoImage(pil_img)

        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas._tk_img = tk_img
        canvas._game_roi = game_roi

        # Redibujar grid
        sqm_w, sqm_h = cal.sqm_size
        px_local = cal.player_center[0] - roi_offset[0]
        py_local = cal.player_center[1] - roi_offset[1]
        for dx in range(-4, 5):
            for dy in range(-3, 4):
                sx = int((px_local + dx * sqm_w - sqm_w / 2) * scale)
                sy = int((py_local + dy * sqm_h - sqm_h / 2) * scale)
                ex = int((px_local + dx * sqm_w + sqm_w / 2) * scale)
                ey = int((py_local + dy * sqm_h + sqm_h / 2) * scale)
                color = "#FF0000" if dx == 0 and dy == 0 else "#333333"
                canvas.create_rectangle(sx, sy, ex, ey, outline=color, width=1)

        state["preview_id"] = None
        state["click_done"] = False
        lbl_preview.configure(text="Recapturado — haz clic en el CUERPO MUERTO")

    def _ask_sprite_name(self, sprite: np.ndarray) -> Optional[str]:
        """Diálogo para pedir el nombre de la criatura del sprite capturado."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nombre de la Criatura")
        dialog.geometry("400x250")
        dialog.focus_force()
        dialog.grab_set()
        dialog.resizable(False, False)

        result = {"name": None}

        ctk.CTkLabel(
            dialog,
            text="Ingresa el nombre de la criatura:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(padx=20, pady=(15, 5))

        # Preview del sprite
        preview = cv2.resize(sprite, (64, 64), interpolation=cv2.INTER_NEAREST)
        preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        pil_preview = Image.fromarray(preview_rgb)
        tk_preview = ImageTk.PhotoImage(pil_preview)
        preview_label = ctk.CTkLabel(dialog, image=tk_preview, text="")
        preview_label.pack(pady=5)
        preview_label._tk_img = tk_preview

        ctk.CTkLabel(
            dialog,
            text="Ejemplo: Rotworm, Cave Rat, Swamp Troll",
            font=ctk.CTkFont(size=10), text_color="#888888",
        ).pack(padx=20, pady=(0, 5))

        entry = ctk.CTkEntry(dialog, width=300, placeholder_text="Nombre de la criatura...")
        entry.pack(padx=20, pady=5)
        entry.focus_set()

        def on_ok():
            result["name"] = entry.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        def on_enter(event):
            on_ok()

        entry.bind("<Return>", on_enter)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="✅ Guardar", width=120,
                        fg_color="#27AE60", command=on_ok).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="❌ Cancelar", width=120,
                        fg_color="#C0392B", command=on_cancel).pack(side="left", padx=5)

        dialog.wait_window()
        return result["name"]

    # ==================================================================
    # TAB: Simple Walking (grabador/reproductor de flechas)
    # ==================================================================
    def _build_simple_walking_tab(self):
        tab = self.tab_simple_walking

        # --- Header ---
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header,
            text="🚶 SIMPLE WALKING — Grabador de Ruta",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        # --- Botones de control ---
        ctrl_frame = ctk.CTkFrame(tab)
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        btn_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=8)

        self.btn_sw_record = ctk.CTkButton(
            btn_row,
            text="🔴 Grabar",
            width=160,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=self._sw_toggle_record,
        )
        self.btn_sw_record.pack(side="left", padx=(0, 10))

        self.btn_sw_play = ctk.CTkButton(
            btn_row,
            text="▶ Reproducir",
            width=160,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2ECC71",
            hover_color="#27AE60",
            command=self._sw_toggle_play,
        )
        self.btn_sw_play.pack(side="left", padx=(0, 10))

        self.btn_sw_clear = ctk.CTkButton(
            btn_row,
            text="🗑️ Limpiar",
            width=100,
            height=40,
            fg_color="#95A5A6",
            hover_color="#7F8C8D",
            command=self._sw_clear,
        )
        self.btn_sw_clear.pack(side="left", padx=(0, 10))

        # --- Guardar / Cargar ---
        file_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        file_row.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkButton(
            file_row, text="💾 Guardar ruta", width=130,
            fg_color="#3498DB", hover_color="#2980B9",
            command=self._sw_save,
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            file_row, text="📂 Cargar ruta", width=130,
            fg_color="#3498DB", hover_color="#2980B9",
            command=self._sw_load,
        ).pack(side="left", padx=(0, 10))

        # Estado
        self.lbl_sw_status = ctk.CTkLabel(
            file_row,
            text="Estado: Detenido | Pasos: 0 | Ciclos: 0",
            font=ctk.CTkFont(size=12),
            text_color="#FFAA00",
        )
        self.lbl_sw_status.pack(side="left", padx=10)

        # --- Waypoints grabados ---
        wp_frame = ctk.CTkFrame(tab)
        wp_frame.pack(fill="both", expand=True, padx=10, pady=(5, 2))

        ctk.CTkLabel(
            wp_frame,
            text="📍 Waypoints Grabados",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 4))

        self.sw_waypoints_text = ctk.CTkTextbox(
            wp_frame, height=160,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.sw_waypoints_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.sw_waypoints_text.configure(state="disabled")
        # Tags de color para resaltar waypoint activo
        self.sw_waypoints_text._textbox.tag_configure("active", background="#2E4053", foreground="#F1C40F")
        self.sw_waypoints_text._textbox.tag_configure("normal", foreground="#BDC3C7")
        self.sw_waypoints_text._textbox.tag_configure("header", foreground="#3498DB")

        # --- Logger mini ---
        log_frame = ctk.CTkFrame(tab)
        log_frame.pack(fill="x", padx=10, pady=(2, 8))

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=5, pady=(5, 2))

        ctk.CTkLabel(
            log_header,
            text="📋 Walking Log",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            log_header, text="Limpiar", width=60, height=24,
            command=self._sw_clear_log,
        ).pack(side="right", padx=3)

        self.sw_log_text = ctk.CTkTextbox(
            log_frame, height=120,
            font=ctk.CTkFont(family="Consolas", size=10),
        )
        self.sw_log_text.pack(fill="x", padx=5, pady=(2, 5))
        self.sw_log_text.configure(state="disabled")

    def _configure_sw_log_tags(self):
        """Configura tags de color para el log del simple walking."""
        try:
            self.sw_log_text._textbox.tag_configure("INFO", foreground="#00CC66")
            self.sw_log_text._textbox.tag_configure("WARNING", foreground="#FFAA00")
            self.sw_log_text._textbox.tag_configure("ERROR", foreground="#FF3333")
        except Exception:
            pass

    # --- Simple Walking: callbacks y acciones ---
    def _sw_log(self, msg: str):
        """Agrega mensaje al log del Simple Walking (thread-safe)."""
        try:
            self.after(0, self._sw_log_append, msg)
        except Exception:
            pass

    def _sw_log_append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        tag = "INFO"
        if "⚠️" in msg or "WARN" in msg:
            tag = "WARNING"
        elif "❌" in msg or "ERROR" in msg:
            tag = "ERROR"
        self.sw_log_text.configure(state="normal")
        self.sw_log_text._textbox.insert("end", f"[{ts}] {msg}\n", tag)
        # Limitar líneas
        count = int(self.sw_log_text._textbox.index("end-1c").split(".")[0])
        if count > 500:
            self.sw_log_text._textbox.delete("1.0", "100.0")
        self.sw_log_text._textbox.see("end")
        self.sw_log_text.configure(state="disabled")

    def _sw_on_step_recorded(self, step):
        """Callback cuando se graba un paso — actualiza la lista de waypoints."""
        try:
            self.after(0, self._sw_refresh_waypoints)
            self.after(0, self._sw_update_status)
        except Exception:
            pass

    def _sw_on_playback_step(self, index: int, cycle: int):
        """Callback en cada paso de reproducción — resalta waypoint activo."""
        try:
            self.after(0, self._sw_highlight_waypoint, index)
            self.after(0, self._sw_update_status)
        except Exception:
            pass

    def _sw_on_cycle_complete(self, cycle_number: int):
        """Callback al completar un ciclo."""
        try:
            self.after(0, self._sw_update_status)
        except Exception:
            pass

    def _sw_toggle_record(self):
        if self.walk_recorder.is_playing:
            self.walk_recorder.stop_playback()
            self._sw_update_play_btn(False)

        if self.walk_recorder.is_recording:
            self.walk_recorder.stop_recording()
            self.btn_sw_record.configure(
                text="🔴 Grabar", fg_color="#E74C3C", hover_color="#C0392B"
            )
        else:
            self.walk_recorder.start_recording()
            self.btn_sw_record.configure(
                text="⏹ Detener Grabación", fg_color="#F39C12", hover_color="#E67E22"
            )
        self._sw_update_status()

    def _sw_toggle_play(self):
        if self.walk_recorder.is_recording:
            self.walk_recorder.stop_recording()
            self.btn_sw_record.configure(
                text="🔴 Grabar", fg_color="#E74C3C", hover_color="#C0392B"
            )

        if self.walk_recorder.is_playing:
            self.walk_recorder.stop_playback()
            self._sw_update_play_btn(False)
        else:
            self.walk_recorder.start_playback()
            self._sw_update_play_btn(True)
        self._sw_update_status()

    def _sw_update_play_btn(self, playing: bool):
        if playing:
            self.btn_sw_play.configure(
                text="⏹ Detener", fg_color="#E74C3C", hover_color="#C0392B"
            )
        else:
            self.btn_sw_play.configure(
                text="▶ Reproducir", fg_color="#2ECC71", hover_color="#27AE60"
            )

    def _sw_clear(self):
        if self.walk_recorder.is_recording:
            self.walk_recorder.stop_recording()
            self.btn_sw_record.configure(
                text="🔴 Grabar", fg_color="#E74C3C", hover_color="#C0392B"
            )
        if self.walk_recorder.is_playing:
            self.walk_recorder.stop_playback()
            self._sw_update_play_btn(False)
        self.walk_recorder.clear()
        self._sw_refresh_waypoints()
        self._sw_update_status()

    def _sw_save(self):
        if not self.walk_recorder.steps:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialdir=os.path.join(os.path.dirname(__file__), "routes"),
            initialfile="walk_route.json",
        )
        if path:
            self.walk_recorder.save(path)

    def _sw_load(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")],
            initialdir=os.path.join(os.path.dirname(__file__), "routes"),
        )
        if path:
            self.walk_recorder.load(path)
            self._sw_refresh_waypoints()
            self._sw_update_status()

    def _sw_clear_log(self):
        self.sw_log_text.configure(state="normal")
        self.sw_log_text._textbox.delete("1.0", "end")
        self.sw_log_text.configure(state="disabled")

    def _sw_refresh_waypoints(self):
        """Reconstruye la lista visual de waypoints."""
        self.sw_waypoints_text.configure(state="normal")
        self.sw_waypoints_text._textbox.delete("1.0", "end")

        if not self.walk_recorder.steps:
            self.sw_waypoints_text._textbox.insert("1.0", "(sin pasos grabados)\n", "normal")
        else:
            self.sw_waypoints_text._textbox.insert(
                "end",
                f"{'#':<5} {'Dirección':<14} {'Delay (s)':<10}\n",
                "header",
            )
            self.sw_waypoints_text._textbox.insert("end", "─" * 32 + "\n", "header")
            for s in self.walk_recorder.steps:
                arrow = DIRECTION_ARROWS.get(s.direction, s.direction)
                line = f"{s.index + 1:<5} {arrow:<14} {s.delay:.2f}\n"
                self.sw_waypoints_text._textbox.insert("end", line, "normal")

        self.sw_waypoints_text._textbox.see("end")
        self.sw_waypoints_text.configure(state="disabled")

    def _sw_highlight_waypoint(self, index: int):
        """Resalta el waypoint activo en la lista."""
        self.sw_waypoints_text.configure(state="normal")
        tb = self.sw_waypoints_text._textbox
        # Quitar resaltado previo
        tb.tag_remove("active", "1.0", "end")
        # Las primeras 2 líneas son header; los waypoints empiezan en línea 3
        line_num = index + 3  # +2 header, +1 porque tkinter es 1-indexed
        total_lines = int(tb.index("end-1c").split(".")[0])
        if 1 <= line_num <= total_lines:
            tb.tag_add("active", f"{line_num}.0", f"{line_num}.end")
            tb.see(f"{line_num}.0")
        self.sw_waypoints_text.configure(state="disabled")

    def _sw_update_status(self):
        """Actualiza la etiqueta de estado del Simple Walking."""
        st = self.walk_recorder.get_status()
        if st["is_recording"]:
            state_txt = "🔴 Grabando"
            color = "#E74C3C"
        elif st["is_playing"]:
            state_txt = f"▶ Reproduciendo (WP {st['current_index'] + 1}/{st['total_steps']})"
            color = "#2ECC71"
        else:
            state_txt = "⏹ Detenido"
            color = "#FFAA00"

        self.lbl_sw_status.configure(
            text=f"Estado: {state_txt} | Pasos: {st['total_steps']} | Ciclos: {st['cycle_count']}",
            text_color=color,
        )

    # ==================================================================
    # TAB: Test (pruebas de flechas y funciones)
    # ==================================================================
    def _build_test_tab(self):
        tab = self.tab_test
        scroll = ctk.CTkScrollableFrame(tab, label_text="🧪 TEST — Pruebas de Funciones")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Flechas direccionales ---
        arrows_frame = ctk.CTkFrame(scroll)
        arrows_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(
            arrows_frame,
            text="🎮 Flechas Direccionales",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            arrows_frame,
            text="Presiona los botones para enviar flechas al cliente de Tibia",
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Cuadrícula de flechas (estilo D-pad)
        pad_frame = ctk.CTkFrame(arrows_frame, fg_color="transparent")
        pad_frame.pack(padx=10, pady=(0, 10))

        btn_size = 70
        btn_font = ctk.CTkFont(size=22, weight="bold")

        # Fila 1: UP centrado
        row1 = ctk.CTkFrame(pad_frame, fg_color="transparent")
        row1.pack()
        ctk.CTkFrame(row1, width=btn_size, height=1, fg_color="transparent").pack(side="left")
        ctk.CTkButton(
            row1, text="↑", width=btn_size, height=btn_size, font=btn_font,
            fg_color="#2C3E50", hover_color="#34495E",
            command=lambda: self._test_send_arrow("UP"),
        ).pack(side="left", padx=2, pady=2)
        ctk.CTkFrame(row1, width=btn_size, height=1, fg_color="transparent").pack(side="left")

        # Fila 2: LEFT, (espacio), RIGHT
        row2 = ctk.CTkFrame(pad_frame, fg_color="transparent")
        row2.pack()
        ctk.CTkButton(
            row2, text="←", width=btn_size, height=btn_size, font=btn_font,
            fg_color="#2C3E50", hover_color="#34495E",
            command=lambda: self._test_send_arrow("LEFT"),
        ).pack(side="left", padx=2, pady=2)
        ctk.CTkFrame(row2, width=btn_size, height=btn_size, fg_color="transparent").pack(side="left", padx=2, pady=2)
        ctk.CTkButton(
            row2, text="→", width=btn_size, height=btn_size, font=btn_font,
            fg_color="#2C3E50", hover_color="#34495E",
            command=lambda: self._test_send_arrow("RIGHT"),
        ).pack(side="left", padx=2, pady=2)

        # Fila 3: DOWN centrado
        row3 = ctk.CTkFrame(pad_frame, fg_color="transparent")
        row3.pack()
        ctk.CTkFrame(row3, width=btn_size, height=1, fg_color="transparent").pack(side="left")
        ctk.CTkButton(
            row3, text="↓", width=btn_size, height=btn_size, font=btn_font,
            fg_color="#2C3E50", hover_color="#34495E",
            command=lambda: self._test_send_arrow("DOWN"),
        ).pack(side="left", padx=2, pady=2)
        ctk.CTkFrame(row3, width=btn_size, height=1, fg_color="transparent").pack(side="left")

        # Resultado del test
        self.lbl_test_arrow_result = ctk.CTkLabel(
            arrows_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#95A5A6",
        )
        self.lbl_test_arrow_result.pack(anchor="w", padx=10, pady=(0, 8))

        # --- Teclas rápidas ---
        keys_frame = ctk.CTkFrame(scroll)
        keys_frame.pack(fill="x", padx=5, pady=(10, 5))

        ctk.CTkLabel(
            keys_frame,
            text="⌨️ Teclas de Función",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 4))

        fkeys_row = ctk.CTkFrame(keys_frame, fg_color="transparent")
        fkeys_row.pack(fill="x", padx=10, pady=(0, 8))

        for fk in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]:
            ctk.CTkButton(
                fkeys_row, text=fk, width=50, height=32,
                font=ctk.CTkFont(size=11),
                fg_color="#2C3E50", hover_color="#34495E",
                command=lambda k=fk: self._test_send_key(k),
            ).pack(side="left", padx=1, pady=2)

        # --- Teclas numéricas ---
        numkeys_frame = ctk.CTkFrame(scroll)
        numkeys_frame.pack(fill="x", padx=5, pady=(10, 5))

        ctk.CTkLabel(
            numkeys_frame,
            text="🔢 Teclas Numéricas (con Enter)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            numkeys_frame,
            text="Presiona para escribir número y enviar mensaje automáticamente",
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        numkeys_row = ctk.CTkFrame(numkeys_frame, fg_color="transparent")
        numkeys_row.pack(fill="x", padx=10, pady=(0, 8))

        for nk in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            ctk.CTkButton(
                numkeys_row, text=nk, width=45, height=32,
                font=ctk.CTkFont(size=11),
                fg_color="#2C3E50", hover_color="#34495E",
                command=lambda k=nk: self._test_send_number(k),
            ).pack(side="left", padx=1, pady=2)

        # --- Chat Functions ---
        chat_frame = ctk.CTkFrame(scroll)
        chat_frame.pack(fill="x", padx=5, pady=(10, 5))

        ctk.CTkLabel(
            chat_frame,
            text="💬 Chat Functions",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            chat_frame,
            text="Envía mensajes al chat local y canal NPC",
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Botones de chat
        chat_buttons_row = ctk.CTkFrame(chat_frame, fg_color="transparent")
        chat_buttons_row.pack(fill="x", padx=10, pady=(0, 8))

        # Botón para enviar "hi" automáticamente
        ctk.CTkButton(
            chat_buttons_row, text="👋 Enviar 'hi'", width=120, height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#27AE60", hover_color="#229954",
            command=self._send_hi_message,
        ).pack(side="left", padx=2, pady=2)

        # Botón para abrir canal NPC
        ctk.CTkButton(
            chat_buttons_row, text="📢 Abrir NPC", width=120, height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#3498DB", hover_color="#2980B9",
            command=self._open_npc_channel,
        ).pack(side="left", padx=2, pady=2)

        # Entrada de texto personalizado
        custom_msg_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        custom_msg_frame.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(
            custom_msg_frame,
            text="Mensaje personalizado:",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=(0, 5))

        msg_input_row = ctk.CTkFrame(custom_msg_frame, fg_color="transparent")
        msg_input_row.pack(fill="x", pady=(2, 0))

        self.custom_msg_entry = ctk.CTkEntry(
            msg_input_row, placeholder_text="Escribe tu mensaje aquí...",
            font=ctk.CTkFont(size=11), width=300
        )
        self.custom_msg_entry.pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            msg_input_row, text="📤 Enviar Local", width=100, height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#E67E22", hover_color="#D35400",
            command=self._send_custom_local,
        ).pack(side="left", padx=2, pady=2)

        ctk.CTkButton(
            msg_input_row, text="📤 Enviar NPC", width=100, height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#9B59B6", hover_color="#8E44AD",
            command=self._send_custom_npc,
        ).pack(side="left", padx=2, pady=2)

        # --- Test log ---
        test_log_frame = ctk.CTkFrame(scroll)
        test_log_frame.pack(fill="x", padx=5, pady=(10, 5))

        log_header = ctk.CTkFrame(test_log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=5, pady=(5, 2))

        ctk.CTkLabel(
            log_header,
            text="📋 Test Log",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            log_header, text="Limpiar", width=60, height=24,
            command=self._test_clear_log,
        ).pack(side="right", padx=3)

        self.test_log_text = ctk.CTkTextbox(
            test_log_frame, height=200,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.test_log_text.pack(fill="x", padx=5, pady=(2, 5))
        self.test_log_text.configure(state="disabled")
        self.test_log_text._textbox.tag_configure("OK", foreground="#00CC66")
        self.test_log_text._textbox.tag_configure("FAIL", foreground="#FF3333")
        self.test_log_text._textbox.tag_configure("INFO", foreground="#3498DB")

    # --- Test: helpers ---
    def _test_send_arrow(self, key_name: str):
        """Envía una flecha direccional al cliente de Tibia (igual que Simple Walker)."""
        if not self.bot.tibia_connected:
            self._test_log(f"⚠️ Tibia no conectado — no se puede enviar '{key_name}'", "FAIL")
            self.lbl_test_arrow_result.configure(
                text="⚠️ Tibia no conectado", text_color="#E74C3C"
            )
            return
        
        # Usar el MISMO callback que Simple Walker
        ok = self._test_send_key_callback(key_name)
        if ok:
            self._test_log(f"✅ Flecha '{key_name}' enviada (movimiento)", "OK")
            self.lbl_test_arrow_result.configure(
                text=f"✅ Moviendo: {key_name}", text_color="#2ECC71"
            )
        else:
            self._test_log(f"❌ Fallo al enviar flecha '{key_name}'", "FAIL")
            self.lbl_test_arrow_result.configure(
                text=f"❌ Fallo: {key_name}", text_color="#E74C3C"
            )

    def _test_send_number(self, number: str):
        """Envía un número y presiona Enter automáticamente."""
        if not self.bot.tibia_connected:
            self._test_log(f"⚠️ Tibia no conectado — no se puede enviar '{number}'", "FAIL")
            return
        
        # Enviar número + Enter usando el mismo callback
        ok1 = self._test_send_key_callback(number)
        time.sleep(0.05)  # Pequeña pausa entre teclas
        ok2 = self._test_send_key_callback("ENTER")
        
        if ok1 and ok2:
            self._test_log(f"✅ Número '{number}' + Enter enviados", "OK")
            self.lbl_test_arrow_result.configure(
                text=f"✅ Enviado: {number} + Enter", text_color="#2ECC71"
            )
        else:
            self._test_log(f"❌ Fallo al enviar número '{number}'", "FAIL")
            self.lbl_test_arrow_result.configure(
                text=f"❌ Fallo: {number}", text_color="#E74C3C"
            )

    def _test_send_key(self, key_name: str):
        """Envía una tecla al cliente de Tibia (igual que Simple Walker)."""
        if not self.bot.tibia_connected:
            self._test_log(f"⚠️ Tibia no conectado — no se puede enviar '{key_name}'", "FAIL")
            self.lbl_test_arrow_result.configure(
                text="⚠️ Tibia no conectado", text_color="#E74C3C"
            )
            return
        
        ok = self._test_send_key_callback(key_name)
        if ok:
            self._test_log(f"✅ Tecla '{key_name}' enviada correctamente", "OK")
            self.lbl_test_arrow_result.configure(
                text=f"✅ Enviado: {key_name}", text_color="#2ECC71"
            )
        else:
            self._test_log(f"❌ Fallo al enviar tecla '{key_name}'", "FAIL")
            self.lbl_test_arrow_result.configure(
                text=f"❌ Fallo: {key_name}", text_color="#E74C3C"
            )

    def _test_log(self, msg: str, tag: str = "INFO"):
        ts = time.strftime("%H:%M:%S")
        self.test_log_text.configure(state="normal")
        self.test_log_text._textbox.insert("end", f"[{ts}] {msg}\n", tag)
        self.test_log_text._textbox.see("end")
        self.test_log_text.configure(state="disabled")

    def _test_clear_log(self):
        self.test_log_text.configure(state="normal")
        self.test_log_text._textbox.delete("1.0", "end")
        self.test_log_text.configure(state="disabled")

    # --- Chat Functions ---
    def _is_local_channel_open(self) -> bool:
        """Detecta si el canal local está abierto usando OCR o color."""
        try:
            frame = self.bot.last_frame
            if frame is None:
                self._test_log("⚠️ No hay frame disponible para OCR", "FAIL")
                return False
            
            # Región donde aparece el nombre del canal
            chat_region = frame[500:550, 600:800]
            
            # Método 1: OCR
            if hasattr(self.bot, 'ocr_helper') and self.bot.ocr_helper.is_available:
                text = self.bot.ocr_helper.read_text(chat_region, preprocess=True)
                self._test_log(f"🔍 OCR detectó: '{text}'", "INFO")
                # Canal local no tiene texto específico, verificamos que no sea NPC/Guild/Party
                if not any(channel in text.lower() for channel in ["npc", "guild", "party", "trade"]):
                    return True
            
            # Método 2: Detección por color (local es blanco/verde)
            hsv = cv2.cvtColor(chat_region, cv2.COLOR_BGR2HSV)
            
            # Rango para texto de canal local (blanco/verde claro)
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 30, 255])
            
            mask = cv2.inRange(hsv, lower_white, upper_white)
            white_pixels = cv2.countNonZero(mask)
            
            if white_pixels > 30:
                self._test_log(f"🔍 Detección por color: {white_pixels} píxeles local", "INFO")
                return True
            
            self._test_log("🔍 Canal local no detectado", "INFO")
            return False
            
        except Exception as e:
            self._test_log(f"⚠️ Error en detección de canal local: {e}", "FAIL")
            return False

    def _switch_to_local_channel(self):
        """Cambia al canal local usando Previous/Next channel."""
        if not self.bot.tibia_connected:
            self._test_log("⚠️ Tibia no conectado", "FAIL")
            return
        
        # Si ya estamos en local, no hacer nada
        if self._is_local_channel_open():
            self._test_log("ℹ️ Ya estamos en canal local", "OK")
            return
        
        # Intentar cambiar de canal con Previous/Next
        # Generalmente Previous Channel (Ctrl+PageUp o similar) vuelve al local
        self._test_log("🔄 Intentando volver al canal local...", "INFO")
        
        # Método 1: Previous Channel (generalmente Ctrl+PageUp)
        ok1 = self._test_send_key_callback("CTRL+PGUP")
        time.sleep(0.2)
        
        if self._is_local_channel_open():
            self._test_log("✅ Canal local restaurado (Ctrl+PageUp)", "OK")
            return
        
        # Método 2: Intentar con PageUp solo
        ok2 = self._test_send_key_callback("PGUP")
        time.sleep(0.2)
        
        if self._is_local_channel_open():
            self._test_log("✅ Canal local restaurado (PageUp)", "OK")
            return
        
        # Método 3: Intentar varias veces Next Channel hasta llegar al local
        for i in range(5):  # Máximo 5 intentos
            self._test_send_key_callback("PGDN")  # Next Channel
            time.sleep(0.2)
            if self._is_local_channel_open():
                self._test_log(f"✅ Canal local encontrado después de {i+1} ciclos", "OK")
                return
        
        self._test_log("❌ No se pudo volver al canal local", "FAIL")

    def _send_hi_message(self):
        """Envía 'hi' al chat local automáticamente."""
        if not self.bot.tibia_connected:
            self._test_log("⚠️ Tibia no conectado — no se puede enviar 'hi'", "FAIL")
            return
        
        # Asegurarse de estar en canal local
        self._switch_to_local_channel()
        time.sleep(0.2)
        
        # Escribir "hi" y presionar Enter
        ok1 = self._test_send_key_callback("H")
        time.sleep(0.05)
        ok2 = self._test_send_key_callback("I")
        time.sleep(0.05)
        ok3 = self._test_send_key_callback("ENTER")
        
        if ok1 and ok2 and ok3:
            self._test_log("✅ Mensaje 'hi' enviado al chat local", "OK")
        else:
            self._test_log("❌ Fallo al enviar mensaje 'hi'", "FAIL")

    def _open_npc_channel(self):
        """Abre el canal de chat NPC usando Ctrl+O y click en NPCs/Open."""
        if not self.bot.tibia_connected:
            self._test_log("⚠️ Tibia no conectado — no se puede abrir canal NPC", "FAIL")
            return
        
        # Verificar target
        if self.bot.key_sender.hwnd != self.bot.tibia_hwnd:
            self.bot.key_sender.set_target(self.bot.tibia_hwnd)
        
        # Primero verificar si ya está abierto usando OCR
        if self._is_npc_channel_open():
            self._test_log("ℹ️ Canal NPC ya está abierto", "OK")
            return
        
        # Abrir ventana de canales con Ctrl+O
        ok1 = self.bot.key_sender.send_key("CTRL+O")
        time.sleep(0.3)  # Esperar que abra la ventana
        
        if not ok1:
            self._test_log("❌ Fallo al abrir ventana de canales (Ctrl+O)", "FAIL")
            return
        
        # Hacer click donde dice "NPCs" (posición aproximada)
        # Esta posición puede variar, necesitaríamos calibrarla
        npcs_x, npcs_y = 400, 200  # Posición estimada
        ok2 = self.bot.mouse_sender.click(npcs_x, npcs_y)
        time.sleep(0.2)
        
        if not ok2:
            self._test_log("❌ Fallo al hacer click en NPCs", "FAIL")
            return
        
        # Hacer click en "Open"
        open_x, open_y = 400, 250  # Posición estimada
        ok3 = self.bot.mouse_sender.click(open_x, open_y)
        time.sleep(0.3)
        
        if ok3:
            self._test_log("✅ Canal NPC abierto (Ctrl+O → NPCs → Open)", "OK")
        else:
            self._test_log("❌ Fallo al hacer click en Open", "FAIL")

    def _is_npc_channel_open(self) -> bool:
        """Detecta si el canal NPC ya está abierto usando OCR o detección de color."""
        try:
            # Tomar captura de la región del chat
            frame = self.bot.last_frame
            if frame is None:
                self._test_log("⚠️ No hay frame disponible para OCR", "FAIL")
                return False
            
            # Región donde aparece el nombre del canal (parte inferior derecha)
            # Estas coordenadas son aproximadas y necesitarían calibración
            chat_region = frame[500:550, 600:800]  # y:y+h, x:x+w
            
            # Método 1: Usar OCR si está disponible
            if hasattr(self.bot, 'ocr_helper') and self.bot.ocr_helper.is_available:
                text = self.bot.ocr_helper.read_text(chat_region, preprocess=True)
                self._test_log(f"🔍 OCR detectó: '{text}'", "INFO")
                if "npc" in text.lower():
                    return True
            
            # Método 2: Detección por color (fallback)
            # El canal NPC tiene un color característico (generalmente amarillo/naranja)
            # Buscar píxeles con el color del canal NPC
            hsv = cv2.cvtColor(chat_region, cv2.COLOR_BGR2HSV)
            
            # Rango de color para texto de canal NPC (amarillo/naranja)
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([30, 255, 255])
            
            mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            yellow_pixels = cv2.countNonZero(mask)
            
            if yellow_pixels > 50:  # Si hay suficientes píxeles amarillos
                self._test_log(f"🔍 Detección por color: {yellow_pixels} píxeles NPC", "INFO")
                return True
            
            self._test_log("🔍 Canal NPC no detectado", "INFO")
            return False
            
        except Exception as e:
            self._test_log(f"⚠️ Error en detección de canal NPC: {e}", "FAIL")
            return False

    def _send_custom_local(self):
        """Envía un mensaje personalizado al chat local."""
        if not self.bot.tibia_connected:
            self._test_log("⚠️ Tibia no conectado — no se puede enviar mensaje", "FAIL")
            return
        
        message = self.custom_msg_entry.get().strip()
        if not message:
            self._test_log("⚠️ Escribe un mensaje para enviar", "FAIL")
            return
        
        # Verificar target
        if self.bot.key_sender.hwnd != self.bot.tibia_hwnd:
            self.bot.key_sender.set_target(self.bot.tibia_hwnd)
        
        # Convertir mensaje a teclas (mayúsculas para letras)
        all_ok = True
        for char in message.upper():
            if char == ' ':
                ok = self._test_send_key_callback("SPACE")
            elif char in self.bot.key_sender.get_available_keys():
                ok = self._test_send_key_callback(char)
            else:
                continue  # Saltar caracteres no soportados
            
            if not ok:
                all_ok = False
                break
            time.sleep(0.03)  # Pequeña pausa entre caracteres
        
        # Enviar el mensaje con Enter
        if all_ok:
            ok_enter = self._test_send_key_callback("ENTER")
            if ok_enter:
                self._test_log(f"✅ Mensaje enviado al chat local: '{message}'", "OK")
            else:
                self._test_log(f"❌ Fallo al enviar Enter para: '{message}'", "FAIL")
        else:
            self._test_log(f"❌ Fallo al enviar mensaje: '{message}'", "FAIL")

    def _send_custom_npc(self):
        """Envía un mensaje personalizado al canal NPC y vuelve al local."""
        if not self.bot.tibia_connected:
            self._test_log("⚠️ Tibia no conectado — no se puede enviar mensaje NPC", "FAIL")
            return
        
        message = self.custom_msg_entry.get().strip()
        if not message:
            self._test_log("⚠️ Escribe un mensaje para enviar", "FAIL")
            return
        
        # Abrir canal NPC
        self._open_npc_channel()
        time.sleep(0.5)  # Esperar a que el canal se abra
        
        # Convertir mensaje a teclas y enviar
        all_ok = True
        for char in message.upper():
            if char == ' ':
                ok = self._test_send_key_callback("SPACE")
            elif char in self.bot.key_sender.get_available_keys():
                ok = self._test_send_key_callback(char)
            else:
                continue
            
            if not ok:
                all_ok = False
                break
            time.sleep(0.03)
        
        # Enviar con Enter
        if all_ok:
            ok_enter = self._test_send_key_callback("ENTER")
            if ok_enter:
                self._test_log(f"✅ Mensaje enviado al canal NPC: '{message}'", "OK")
                
                # Esperar un momento y volver al canal local
                time.sleep(0.5)
                self._switch_to_local_channel()
                
            else:
                self._test_log(f"❌ Fallo al enviar Enter NPC para: '{message}'", "FAIL")
        else:
            self._test_log(f"❌ Fallo al enviar mensaje NPC: '{message}'", "FAIL")

    # ==================================================================
    # TAB: Screen View (visualizador OBS en tiempo real)
    # ==================================================================
    def _build_screenview_tab(self):
        tab = self.tab_screenview

        # ── Controles superiores ──────────────────────────────────────────
        ctrl_frame = ctk.CTkFrame(tab, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            ctrl_frame,
            text="🖥️ Screen View — Frame OBS en tiempo real",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")

        # Toggle de actualización en vivo
        self._sv_live_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            ctrl_frame,
            text="▶ En vivo",
            variable=self._sv_live_var,
        ).pack(side="right", padx=8)

        # Botón captura única
        ctk.CTkButton(
            ctrl_frame, text="📸 Capturar", width=100,
            command=self._sv_capture_once,
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            ctrl_frame, text="🔄 Calibrar", width=100,
            command=self._sv_force_calibration,
        ).pack(side="right", padx=4)

        # ── Selector de overlay ───────────────────────────────────────────
        overlay_frame = ctk.CTkFrame(tab, fg_color="transparent")
        overlay_frame.pack(fill="x", padx=10, pady=(0, 4))

        ctk.CTkLabel(overlay_frame, text="Overlay:").pack(side="left")

        self._sv_overlay_var = ctk.StringVar(value="Ninguno")
        ctk.CTkOptionMenu(
            overlay_frame,
            variable=self._sv_overlay_var,
            values=["Ninguno", "Game Region", "Battle Region",
                    "SQMs", "Player Center", "Minimap", "Cavebot Waypoints",
                    "Targeting Criaturas", "Looter Items", "Conditions", "Todo"],
            width=180,
        ).pack(side="left", padx=6)

        # FPS del visor
        self._sv_fps_var = ctk.StringVar(value="Velocidad: 10 fps")
        ctk.CTkLabel(
            overlay_frame,
            textvariable=self._sv_fps_var,
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
        ).pack(side="right", padx=6)

        # ── Canvas / imagen principal ─────────────────────────────────────
        canvas_outer = ctk.CTkFrame(tab)
        canvas_outer.pack(fill="both", expand=True, padx=10, pady=(2, 4))

        self._sv_canvas = tk.Canvas(
            canvas_outer,
            bg="#1a1a1a",
            highlightthickness=0,
        )
        self._sv_canvas.pack(fill="both", expand=True)
        self._sv_imgtk = None   # referencia para evitar GC
        self._sv_frame_count = 0
        self._sv_last_fps_time = 0.0
        self._sv_displayed_fps = 0.0

        # ── Barra de info inferior ────────────────────────────────────────
        info_bar = ctk.CTkFrame(tab, fg_color="transparent")
        info_bar.pack(fill="x", padx=10, pady=(0, 6))

        self._sv_info_var = ctk.StringVar(
            value="Sin frame — conecta OBS y selecciona una fuente"
        )
        ctk.CTkLabel(
            info_bar,
            textvariable=self._sv_info_var,
            font=ctk.CTkFont(size=11),
            text_color="#95A5A6",
        ).pack(side="left")

        # ── Iniciar el loop de refresco ───────────────────────────────────
        self._sv_refresh_job = None
        self._sv_loop()

    def _sv_loop(self):
        """Loop de refresco del Screen View (~10 fps para video fluido)."""
        try:
            if self._sv_live_var.get():
                # Solo refrescar si la pestaña Screen View está visible
                if self.current_tab == "screenview":
                    self._sv_refresh()
        except Exception:
            pass
        # Programar siguiente tick (100 ms = ~10 fps para video fluido)
        self._sv_refresh_job = self.after(100, self._sv_loop)

    def _sv_capture_once(self):
        """Fuerza una captura inmediata aunque el live esté pausado."""
        self._sv_refresh()

    def _sv_force_calibration(self):
        """Fuerza una calibración completa del screen calibrator."""
        try:
            if self.bot.calibrator is None:
                self._sv_info_var.set("❌ Calibrator no disponible")
                return
            
            # Tomar frame actual
            frame = getattr(self.bot, "last_frame", None)
            if frame is None:
                self._sv_info_var.set("❌ Sin frame para calibrar")
                return
            
            # Forzar calibración
            success = self.bot.calibrator.calibrate_all(frame)
            if success:
                self._sv_info_var.set("✅ Calibración completada")
                self.log.ok("Screen View: Calibración forzada exitosa")
            else:
                self._sv_info_var.set("❌ Calibración falló")
                self.log.error("Screen View: La calibración forzada falló")
                
        except Exception as e:
            self._sv_info_var.set(f"❌ Error: {str(e)}")
            self.log.error(f"Screen View: Error en calibración: {e}")

    def _sv_refresh(self):
        """Obtiene el último frame del bot y lo muestra con overlay opcional."""
        import time as _time

        frame = getattr(self.bot, "last_frame", None)
        if frame is None:
            self._sv_info_var.set(
                "Sin frame — conecta OBS y selecciona una fuente"
            )
            return

        # Dibujar overlays antes de escalar (copia para no modificar el original)
        display = frame.copy()
        overlay = self._sv_overlay_var.get()

        if overlay != "Ninguno":
            try:
                cal = self.bot.calibrator
                
                # Verificar que el calibrator está inicializado
                if cal is None:
                    cv2.putText(display, "Calibrator not initialized", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                else:
                    # Game Region (screen_calibrator)
                    if overlay in ("Game Region", "Todo"):
                        gr = cal.game_region
                        if gr and len(gr) == 4:
                            x1, y1, x2, y2 = gr
                            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(display, "Game", (x1 + 4, y1 + 18),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)
                        else:
                            cv2.putText(display, "Game Region: Not calibrated", (10, 30),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                    # Battle Region
                    if overlay in ("Battle Region", "Todo"):
                        br = cal.battle_region
                        if br and len(br) == 4:
                            bx1, by1, bx2, by2 = br
                            cv2.rectangle(display, (bx1, by1), (bx2, by2),
                                          (0, 100, 255), 2)
                            cv2.putText(display, "Battle List",
                                        (bx1 + 4, by1 + 18),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.5, (0, 100, 255), 1)
                        else:
                            cv2.putText(display, "Battle Region: Not calibrated", (10, 55),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 100, 255), 1)

                # Player Center
                if overlay in ("Player Center", "Todo"):
                    pc = cal.player_center
                    if pc and len(pc) == 2:
                        cx, cy = pc
                        cv2.circle(display, (cx, cy), 10, (255, 255, 0), 2)
                        cv2.circle(display, (cx, cy), 3, (255, 255, 0), -1)
                        cv2.putText(display, "Player", (cx + 12, cy - 4),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.45, (255, 255, 0), 1)
                    else:
                        cv2.putText(display, "Player Center: Not calibrated", (10, 80),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                # SQMs (9 posiciones calibradas)
                if overlay in ("SQMs", "Todo"):
                    sqms = cal.sqms
                    if sqms and len(sqms) == 9:
                        for idx, (sx, sy) in enumerate(sqms):
                            if sx is not None and sy is not None:
                                # Centro = naranja, resto = cyan
                                color = (0, 200, 255) if idx != 4 else (0, 100, 255)
                                cv2.rectangle(
                                    display,
                                    (sx - 10, sy - 10), (sx + 10, sy + 10),
                                    color, 1,
                                )
                                cv2.putText(display, str(idx), (sx - 4, sy + 4),
                                            cv2.FONT_HERSHEY_SIMPLEX,
                                            0.35, color, 1)
                    else:
                        cv2.putText(display, "SQMs: Not calibrated", (10, 105),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

                # GSD region proporcional (si el looter la calculó)
                if overlay in ("Game Region", "Todo"):
                    try:
                        gsd = self.bot.looter_engine.game_screen_detector
                        if gsd._frame_w > 0:
                            gx1 = gsd._game_x1
                            gy1 = gsd._game_y1
                            gx2 = gsd._game_x2
                            gy2 = gsd._game_y2
                            cv2.rectangle(
                                display, (gx1, gy1), (gx2, gy2),
                                (255, 0, 200), 1,
                            )
                            label_src = ("Cal" if gsd._calibrator_region_set
                                         else "Prop")
                            cv2.putText(
                                display, f"GSD({label_src})",
                                (gx1 + 4, gy2 - 6),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.4, (255, 0, 200), 1,
                            )
                    except Exception:
                        pass

                # Minimap overlay
                if overlay in ("Minimap", "Todo"):
                    mr = cal.map_region
                    if mr and len(mr) == 4:
                        mx1, my1, mx2, my2 = mr
                        # Rectángulo del minimap
                        cv2.rectangle(display, (mx1, my1), (mx2, my2),
                                      (255, 200, 0), 2)
                        cv2.putText(display, "Minimap",
                                    (mx1 + 4, my1 - 6),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5, (255, 200, 0), 1)

                        # Centro del minimap (posición del jugador)
                        mcx = (mx1 + mx2) // 2
                        mcy = (my1 + my2) // 2
                        cv2.drawMarker(display, (mcx, mcy),
                                       (0, 255, 255), cv2.MARKER_CROSS,
                                       12, 2)
                        cv2.putText(display, "You",
                                    (mcx + 8, mcy - 6),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.35, (0, 255, 255), 1)
                    else:
                        cv2.putText(display, "Minimap: Not calibrated", (10, 130),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)

                    # Buscar marcas del cavebot en el minimap (solo si está calibrado)
                    if mr and len(mr) == 4:
                        try:
                            cb = self.bot.cavebot_engine
                            if cb.waypoints and cb._mark_templates:
                                minimap_roi = frame[my1:my2, mx1:mx2]
                                if minimap_roi.size > 0:
                                    mm_gray = cv2.cvtColor(
                                        minimap_roi, cv2.COLOR_BGR2GRAY
                                    )
                                    # Buscar TODAS las marcas usadas en la ruta
                                    seen_marks = set()
                                    for wp in cb.waypoints:
                                        seen_marks.add(wp.mark)
                                    for mark_name in seen_marks:
                                        tpl = cb._mark_templates.get(mark_name)
                                        if tpl is None:
                                            continue
                                        th, tw = tpl.shape[:2]
                                        if (mm_gray.shape[0] < th or
                                                mm_gray.shape[1] < tw):
                                            continue
                                        res = cv2.matchTemplate(
                                            mm_gray, tpl,
                                            cv2.TM_CCOEFF_NORMED
                                        )
                                        # Detectar múltiples coincidencias
                                        locs = np.where(res >= 0.70)
                                        found = set()
                                        for py, px in zip(*locs):
                                            # Agrupar detecciones cercanas
                                            key = (px // 8, py // 8)
                                            if key in found:
                                                continue
                                            found.add(key)
                                            ax = mx1 + px + tw // 2
                                            ay = my1 + py + th // 2
                                            # Es el waypoint actual?
                                            cur = cb._current_waypoint()
                                            is_cur = (
                                                cur is not None
                                                and cur.mark == mark_name
                                            )
                                            clr = (
                                                (0, 255, 0) if is_cur
                                                else (200, 150, 255)
                                            )
                                            cv2.circle(
                                                display, (ax, ay),
                                                6, clr, 2
                                            )
                                            cv2.putText(
                                                display, mark_name[:5],
                                                (ax + 7, ay + 4),
                                                cv2.FONT_HERSHEY_SIMPLEX,
                                                0.3, clr, 1,
                                            )
                        except Exception:
                            pass

                        # Mini-zoom del minimap (esquina inferior izquierda)
                        try:
                            mm_crop = frame[my1:my2, mx1:mx2]
                            if mm_crop.size > 0:
                                zoom = 2
                                zoomed = cv2.resize(
                                    mm_crop,
                                    (mm_crop.shape[1] * zoom,
                                     mm_crop.shape[0] * zoom),
                                    interpolation=cv2.INTER_NEAREST,
                                )
                                zh, zw = zoomed.shape[:2]
                                # Colocar en esquina inferior-izquierda
                                dh, dw = display.shape[:2]
                                zy = dh - zh - 10
                                zx = 10
                                if zy > 0 and zx + zw < dw:
                                    # Borde
                                    cv2.rectangle(
                                        display,
                                        (zx - 2, zy - 2),
                                        (zx + zw + 1, zy + zh + 1),
                                        (255, 200, 0), 1,
                                    )
                                    display[zy:zy + zh, zx:zx + zw] = zoomed
                                    cv2.putText(
                                        display, "Minimap x2",
                                        (zx + 4, zy - 6),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.4, (255, 200, 0), 1,
                                    )
                        except Exception:
                            pass

                # Cavebot Waypoints overlay
                if overlay in ("Cavebot Waypoints", "Todo"):
                    try:
                        cb = self.bot.cavebot_engine
                        if cb.waypoints:
                            # Dibujar waypoints actuales y siguientes
                            for i, wp in enumerate(cb.waypoints):
                                if hasattr(wp, 'x') and hasattr(wp, 'y'):
                                    # Convertir coordenadas del juego a pantalla
                                    cal = self.bot.calibrator
                                    if hasattr(cal, 'game_region') and cal.game_region:
                                        gx1, gy1, gx2, gy2 = cal.game_region
                                        # Approx conversion (esto puede necesitar ajuste)
                                        px = gx1 + int((wp.x / 15) * (gx2 - gx1))  # 15 = aprox ancho del mapa
                                        py = gy1 + int((wp.y / 15) * (gy2 - gy1))
                                        
                                        # Es el waypoint actual?
                                        is_current = (i == cb.current_wp_index if hasattr(cb, 'current_wp_index') else False)
                                        color = (0, 255, 0) if is_current else (255, 255, 0)
                                        
                                        cv2.circle(display, (px, py), 8, color, 2)
                                        cv2.putText(display, f"W{i+1}", (px + 10, py - 5),
                                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    except Exception:
                        pass

                # Targeting Criaturas overlay
                if overlay in ("Targeting Criaturas", "Todo"):
                    try:
                        targeting = self.bot.targeting_engine
                        if hasattr(targeting, 'detected_creatures'):
                            for creature in targeting.detected_creatures:
                                if hasattr(creature, 'rect') and hasattr(creature, 'name'):
                                    x, y, w, h = creature.rect
                                    # Dibujar rectángulo alrededor de la criatura
                                    cv2.rectangle(display, (x, y), (x + w, y + h), (255, 0, 255), 2)
                                    cv2.putText(display, creature.name[:8], (x, y - 5),
                                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
                    except Exception:
                        pass

                # Looter Items overlay
                if overlay in ("Looter Items", "Todo"):
                    try:
                        looter = self.bot.looter_engine
                        if hasattr(looter, 'detected_items'):
                            for item in looter.detected_items:
                                if hasattr(item, 'rect') and hasattr(item, 'name'):
                                    x, y, w, h = item.rect
                                    # Dibujar rectángulo alrededor del item
                                    cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 255), 2)
                                    cv2.putText(display, item.name[:6], (x, y - 5),
                                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
                    except Exception:
                        pass

                # Conditions overlay
                if overlay in ("Conditions", "Todo"):
                    try:
                        if hasattr(self.bot, 'condition_engine'):
                            debug_info = self.bot.condition_engine.get_debug_info(frame)
                            
                            # Dibujar barra de condiciones calibrada
                            if debug_info["calibrated"] and debug_info["bar_position"]:
                                pos = debug_info["bar_position"]
                                cv2.rectangle(display, 
                                          (pos["x1"]-5, pos["row"]-15),
                                          (pos["x2"]+5, pos["row"]+15),
                                          (255, 255, 0), 2)
                                cv2.putText(display, "Conditions Bar", 
                                          (pos["x1"], pos["row"]-20),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                            
                            # Dibujar detecciones activas con colores específicos
                            for condition_name, detected in debug_info["detections"].items():
                                if detected:
                                    # Obtener posición relativa para dibujar indicador
                                    if debug_info["bar_position"]:
                                        bar_y = debug_info["bar_position"]["row"]
                                        # Dibujar indicador a la derecha de la barra de condiciones
                                        indicator_x = debug_info["bar_position"]["x2"] + 10
                                        indicator_y = bar_y
                                        
                                        # Colores específicos para cada condición
                                        colors = {
                                            "haste": (0, 255, 0),      # Verde
                                            "paralyze": (255, 0, 255),    # Rojo
                                            "poison": (0, 0, 255),       # Azul
                                            "burning": (0, 165, 255),     # Naranja
                                            "curse": (128, 0, 128),     # Gris
                                            "hunger": (255, 165, 0),      # Amarillo oscuro
                                            "manashield": (255, 0, 255),     # Rojo
                                            "pz_zone": (255, 255, 255),   # Blanco
                                            "haste_medivia": (0, 255, 0),      # Verde
                                            "haste_otclient": (0, 255, 0),      # Verde
                                            "haste_otclientNewer": (0, 255, 0),      # Verde
                                            "haste_tibia-old": (0, 255, 0),      # Verde
                                            "haste_wearedragons": (0, 255, 0),      # Verde
                                            "paralyze_otclientNewer": (255, 0, 255),    # Rojo
                                            "poison_likeretro": (0, 0, 255),       # Azul
                                            "poison_medivia": (0, 0, 255),       # Azul
                                            "poison_otclientNewer": (0, 0, 255),       # Azul
                                            "poison_realera": (0, 0, 255),       # Azul
                                            "manashield_new": (255, 0, 255),     # Rojo
                                            "manashield_otclient": (255, 0, 255),     # Rojo
                                            "manashield_otclientNewer": (255, 0, 255),     # Rojo
                                            "hungry_lunos": (255, 165, 0),      # Amarillo oscuro
                                            "hungry_medivia": (255, 165, 0),      # Amarillo oscuro
                                            "hungry_nostalgic": (255, 165, 0),      # Amarillo oscuro
                                            "pz_zone_medivia": (255, 255, 255),   # Blanco
                                            "pz_zone_nostalgic": (255, 255, 255),   # Blanco
                                            "pz_zone_otclient": (255, 255, 255),   # Blanco
                                            "pz_zone_otclientv8": (255, 255, 255),   # Blanco
                                            "pz_zone_revolution": (255, 255, 255),   # Blanco
                                        }
                                        color = colors.get(condition_name, (128, 128, 128))
                                        
                                        cv2.circle(display, (indicator_x, indicator_y), 8, color, -1)
                                        cv2.putText(display, condition_name[:3].upper(),
                                                  (indicator_x - 15, indicator_y + 3),
                                                  cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    except Exception:
                        pass

            except Exception:
                pass

        # ── Escalar al tamaño del canvas ──────────────────────────────────
        cw = self._sv_canvas.winfo_width()
        ch = self._sv_canvas.winfo_height()
        if cw < 10 or ch < 10:
            # Canvas aún no tiene tamaño real (primer render)
            self.after(100, self._sv_refresh)
            return

        fh, fw = display.shape[:2]
        scale = min(cw / fw, ch / fh)
        nw = int(fw * scale)
        nh = int(fh * scale)
        resized = cv2.resize(display, (nw, nh),
                             interpolation=cv2.INTER_LINEAR)

        # BGR → RGB → PIL → ImageTk
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(image=pil_img)

        # Dibujar en canvas centrado
        self._sv_imgtk = imgtk   # evitar GC
        x_off = (cw - nw) // 2
        y_off = (ch - nh) // 2
        self._sv_canvas.delete("all")
        self._sv_canvas.create_image(x_off, y_off, anchor="nw", image=imgtk)

        # ── Actualizar info bar ───────────────────────────────────────────
        self._sv_frame_count += 1
        now = _time.time()
        if self._sv_last_fps_time == 0:
            self._sv_last_fps_time = now
        elapsed = now - self._sv_last_fps_time
        if elapsed >= 2.0:
            self._sv_displayed_fps = self._sv_frame_count / elapsed
            self._sv_frame_count = 0
            self._sv_last_fps_time = now

        obs_src = getattr(self.bot.capture, "source_name", "?") or "?"
        try:
            gsd_ready = "✅" if self.bot.looter_engine.game_screen_detector.is_ready() else "⏳"
        except Exception:
            gsd_ready = "?"
        cal_ok = "✅" if self.bot.calibrator.calibrated else "⏳"
        self._sv_info_var.set(
            f"Frame: {fw}×{fh}px → Vista: {nw}×{nh}px | "
            f"Fuente OBS: {obs_src} | "
            f"Cal: {cal_ok} | GSD: {gsd_ready} | "
            f"{self._sv_displayed_fps:.1f} fps vis."
        )

    # ==================================================================
    # TAB: Ayuda
    # ==================================================================
    def _build_help_tab(self):
        tab = self.tab_help
        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        help_text = """
╔══════════════════════════════════════════════════════════════╗
║                CONFIGURACIÓN INICIAL                        ║
║                (hacer UNA sola vez)                          ║
╚══════════════════════════════════════════════════════════════╝

1. Abre OBS Studio

2. Crea una fuente "Captura de juego" y selecciona client.exe (Tibia)

3. En OBS → Herramientas → Configuración del servidor WebSocket
   → Habilitar servidor WebSocket (puerto 4455 por defecto)

4. Abre Tibia y juega normalmente con Tibia en primer plano

5. Ejecuta este bot → pestaña "Ventanas":
   a) Haz clic en "Conectar" para conectar a OBS WebSocket
   b) Selecciona la fuente "Captura de juego" del dropdown
   c) Selecciona la ventana de Tibia

6. Configura tus teclas de curación en la pestaña "Configuración"

7. Presiona F9 (o la tecla configurada) para activar el auto-healer

╔══════════════════════════════════════════════════════════════╗
║                ¿POR QUÉ OBS WEBSOCKET?                      ║
╚══════════════════════════════════════════════════════════════╝

• OBS captura Tibia a nivel de GPU (BattleEye lo permite porque
  es software legítimo)

• El bot obtiene los frames directamente de la memoria de OBS
  vía WebSocket (GetSourceScreenshot)

• Funciona con Tibia en PRIMER PLANO — no necesitas que el
  proyector sea visible ni esté abierto

• El bot envía teclas directamente al proceso de Tibia via
  Windows API (PostMessage) — sin necesitar foco

╔══════════════════════════════════════════════════════════════╗
║                SOLUCIÓN DE PROBLEMAS                        ║
╚══════════════════════════════════════════════════════════════╝

❌ "Error al conectar a OBS"
   → Verifica que OBS esté abierto
   → Verifica que WebSocket esté habilitado en OBS:
     Herramientas → Configuración del servidor WebSocket
   → Verifica host (localhost) y puerto (4455)
   → Si pusiste contraseña en OBS, ingrésala aquí

❌ "Pantalla negra detectada"
   → La fuente en OBS no está capturando. Verifica que
     "Captura de juego" muestre Tibia en OBS.

❌ "Ventana de Tibia no encontrada"
   → Asegúrate de que Tibia esté abierto. La ventana se
     llama "Tibia - NombreDePersonaje".

❌ "HP/MP siempre muestra N/A"
   → Usa "Recalibrar barras" en la pestaña Ventanas.
   → Verifica con "Mostrar análisis de barras" que se vean
     las barras de colores.

❌ "Las teclas no llegan a Tibia"
   → Verifica que el HWND de Tibia sea correcto.
   → Asegúrate de que la tecla configurada tenga una acción
     asignada en Tibia (hotkey del juego).

╔══════════════════════════════════════════════════════════════╗
║                TECLAS RÁPIDAS                                ║
╚══════════════════════════════════════════════════════════════╝

• F9  → Activar / Desactivar auto-healer  (configurable)
• F10 → Cerrar el bot                      (configurable)
"""

        ctk.CTkLabel(
            scroll,
            text=help_text,
            font=ctk.CTkFont(family="Consolas", size=12),
            justify="left",
            anchor="nw",
        ).pack(fill="both", padx=10, pady=10)

    # ==================================================================
    # TAB: Logs
    # ==================================================================
    def _build_logs_tab(self):
        tab = self.tab_logs
        
        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(header, text="📋 LOGS DEL SISTEMA", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        # Controles a la derecha
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.pack(side="right")

        # Nivel de log
        ctk.CTkLabel(controls_frame, text="Nivel:").pack(side="right", padx=(10, 3))
        self.log_level_var = ctk.StringVar(value=self.config.log_level)
        ctk.CTkOptionMenu(
            controls_frame,
            variable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            width=90,
            command=self._change_log_level,
        ).pack(side="right", padx=3)

        # Auto-scroll checkbox
        self.autoscroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            controls_frame, text="Auto-scroll", variable=self.autoscroll_var, width=100
        ).pack(side="right", padx=10)

        # Botones
        ctk.CTkButton(
            controls_frame, text="Limpiar", width=70, height=26, command=self._clear_log
        ).pack(side="right", padx=3)
        ctk.CTkButton(
            controls_frame, text="Guardar", width=70, height=26, command=self._save_log
        ).pack(side="right", padx=3)

        # Textbox de logs
        log_container = ctk.CTkFrame(tab)
        log_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.log_text = ctk.CTkTextbox(
            log_container, font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text.configure(state="disabled")

        # Configurar tags de color
        self.log_text._textbox.tag_configure("DEBUG", foreground="#888888")
        self.log_text._textbox.tag_configure("INFO", foreground="#00CC66")
        self.log_text._textbox.tag_configure("WARNING", foreground="#FFAA00")
        self.log_text._textbox.tag_configure("ERROR", foreground="#FF3333")
        self.log_text._textbox.tag_configure("CRITICAL", foreground="#FF0000")

    # ==================================================================
    # Panel de Logs (mantenido por compatibilidad pero vacío)
    # ==================================================================
    def _build_log_panel(self):
        # Esta función se mantiene por compatibilidad pero no hace nada
        # El contenido se movió a la pestaña "Logs"
        pass

    def _configure_module_log_tags(self):
        """Configura tags de color para los textboxes de log de cada módulo."""
        for widget_name in ("log_targeting", "log_looter", "log_cavebot"):
            widget = getattr(self, widget_name, None)
            if widget:
                try:
                    widget._textbox.tag_configure("DEBUG", foreground="#888888")
                    widget._textbox.tag_configure("INFO", foreground="#00CC66")
                    widget._textbox.tag_configure("WARNING", foreground="#FFAA00")
                    widget._textbox.tag_configure("ERROR", foreground="#FF3333")
                    widget._textbox.tag_configure("CRITICAL", foreground="#FF0000")
                except Exception:
                    pass

    def _log_callback(self, msg: str, level: str):
        """Callback invocado por BotLogger (puede venir de cualquier hilo)."""
        self._log_queue.put((msg, level))

    def _drain_log_queue(self):
        """Procesa mensajes pendientes en el hilo principal de tkinter."""
        try:
            # Máximo 8 mensajes por tick para no bloquear la GUI
            for _ in range(8):
                msg, level = self._log_queue.get_nowait()
                # Determinar si es un mensaje de módulo
                routed = self._route_module_log(msg, level)
                # Solo enviar al log principal si NO pertenece a un módulo
                if not routed:
                    self._append_log(msg, level)
        except queue.Empty:
            pass
        if self._gui_ready:
            self.after(80, self._drain_log_queue)

    def _route_module_log(self, msg: str, level: str = "INFO") -> bool:
        """
        Redirige mensajes a los logs por módulo.
        Retorna True si el mensaje fue enrutado a un módulo (no debe ir al log principal).
        """
        try:
            lower = msg.lower()
            target_widget = None
            if "[targeting]" in lower:
                target_widget = getattr(self, "log_targeting", None)
            elif "[looter]" in lower:
                target_widget = getattr(self, "log_looter", None)
            elif "[cavebot]" in lower:
                target_widget = getattr(self, "log_cavebot", None)

            if target_widget:
                tag = level if level in LOG_COLORS else "INFO"
                target_widget.configure(state="normal")
                target_widget._textbox.insert("end", msg + "\n", tag)
                # Limitar líneas
                line_count = int(target_widget._textbox.index("end-1c").split(".")[0])
                if line_count > 500:
                    target_widget._textbox.delete("1.0", "200.0")
                target_widget._textbox.see("end")
                target_widget.configure(state="disabled")
                return True
        except Exception:
            pass
        return False

    def _append_log(self, msg: str, level: str):
        """Agrega un mensaje al panel de logs (thread-safe via after)."""
        self.log_text.configure(state="normal")
        tag = level if level in LOG_COLORS else "INFO"
        self.log_text._textbox.insert("end", msg + "\n", tag)

        # Limitar líneas
        line_count = int(self.log_text._textbox.index("end-1c").split(".")[0])
        if line_count > 2000:
            self.log_text._textbox.delete("1.0", "500.0")

        if self.autoscroll_var.get():
            self.log_text._textbox.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text._textbox.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt")],
            initialfile=f"tibia_healer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        )
        if path:
            try:
                content = self.log_text._textbox.get("1.0", "end")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.log.ok(f"Log guardado en: {path}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")

    def _change_log_level(self, level: str):
        self.log.set_level(level)
        self.config.log_level = level

    # ==================================================================
    # Actualización de estado
    # ==================================================================
    def _schedule_status_update(self):
        """Llamado desde el bot (hilo secundario). Programa update en GUI."""
        try:
            self.after(0, self._update_status_display)
        except Exception:
            pass

    def _start_status_loop(self):
        """Loop periódico para actualizar la GUI."""
        self._update_status_display()
        self._update_job = self.after(750, self._start_status_loop)

    def _update_status_display(self):
        """Actualiza todos los widgets de estado desde datos del bot."""
        try:
            # Estado
            if self.bot.active:
                self.lbl_status.configure(
                    text="Estado: ● ACTIVO", text_color="#2ECC71"
                )
                self.btn_toggle.configure(
                    text="■ DETENER",
                    fg_color="#E74C3C",
                    hover_color="#C0392B",
                )
            else:
                self.lbl_status.configure(
                    text="Estado: ○ EN ESPERA", text_color="#FFAA00"
                )
                self.btn_toggle.configure(
                    text="▶ ACTIVAR",
                    fg_color="#2ECC71",
                    hover_color="#27AE60",
                )

            # Barras HP
            hp = self.bot.hp_percent
            if hp is not None:
                self.hp_bar.set(hp)
                color_name = self.bot.hp_color
                if color_name == "VERDE":
                    self.hp_bar.configure(progress_color="#2ECC71")
                elif color_name == "AMARILLO":
                    self.hp_bar.configure(progress_color="#F39C12")
                else:
                    self.hp_bar.configure(progress_color="#E74C3C")
                self.lbl_hp.configure(text=f"{hp * 100:.0f}%  {color_name}")
            else:
                self.hp_bar.set(0)
                self.lbl_hp.configure(text="N/A")

            # Barras MP
            mp = self.bot.mp_percent
            if mp is not None:
                self.mp_bar.set(mp)
                self.lbl_mp.configure(text=f"{mp * 100:.0f}%  AZUL")
            else:
                self.mp_bar.set(0)
                self.lbl_mp.configure(text="N/A")

            # Conexión Tibia
            if self.bot.tibia_connected:
                self.lbl_tibia_status.configure(
                    text=f"Tibia: \"{self.bot.tibia_title}\" ✓",
                    text_color="#2ECC71",
                )
            else:
                self.lbl_tibia_status.configure(
                    text="Tibia: No conectado ✗",
                    text_color="#E74C3C",
                )

            # Conexión Proyector → OBS WebSocket
            if self.bot.projector_connected:
                ver = self.bot.obs_version or "conectado"
                src = self.bot.capture.source_name or "(sin fuente)"
                self.lbl_proj_status.configure(
                    text=f"OBS WebSocket: {ver} — Fuente: {src} ✓",
                    text_color="#2ECC71",
                )
            else:
                self.lbl_proj_status.configure(
                    text="OBS WebSocket: No conectado ✗",
                    text_color="#E74C3C",
                )

            # FPS y curaciones
            self.lbl_fps.configure(
                text=f"Capturas/seg: {self.bot.captures_per_sec:.1f}"
            )
            self.lbl_heals.configure(
                text=f"Curaciones: {self.bot.heal_count}"
            )

            # --- Calibración v3.1 ---
            try:
                cal = self.bot.calibrator
                if cal.calibrated:
                    confs = cal.last_confidences
                    bl_conf = confs.get("BattleList", 0)
                    mm_conf = confs.get("MapSettings", 0)
                    sqm_n = len(cal.sqms)
                    self.lbl_calibration.configure(
                        text=f"🎯 Calibración: ✓ OK | BL={bl_conf:.2f} MM={mm_conf:.2f} | SQMs={sqm_n}",
                        text_color="#2ECC71",
                    )
                else:
                    err = cal.last_error or "pendiente"
                    fail_n = cal._fail_count
                    self.lbl_calibration.configure(
                        text=f"🎯 Calibración: ✗ {err} (fallos: {fail_n})",
                        text_color="#E74C3C" if fail_n > 0 else "#FFAA00",
                    )
            except Exception:
                pass

            # --- Módulos activos ---
            try:
                active = self.bot.dispatcher.get_active_modules()
                active_str = ", ".join(active) if active else "ninguno"
                self.lbl_modules_status.configure(
                    text=f"📦 Módulos activos: {active_str}"
                )
            except Exception:
                pass

            # --- Módulos v3 status ---
            try:
                # Targeting status
                ts = self.bot.targeting_engine.get_status()
                target_txt = ts.get("current_target", "—") or "—"
                state_str = ts.get("state", "idle")
                state_icon = {"idle": "💤", "attacking": "⚔️",
                              "searching": "🔍"}.get(state_str, "❓")
                tpl_count = ts.get("templates_loaded", 0)
                self.lbl_targeting_state.configure(
                    text=f"{state_icon} {state_str} | "
                         f"Target: {target_txt} | "
                         f"Criaturas: {ts.get('monster_count', 0)} | "
                         f"Kills: {ts.get('monsters_killed', 0)} | "
                         f"Ataques: {ts.get('total_attacks', 0)} | "
                         f"Templates: {tpl_count}"
                )
            except Exception:
                pass

            try:
                # Looter status
                ls = self.bot.looter_engine.get_status()
                state_icon = {"idle": "💤", "waiting": "⏳",
                              "looting": "💰"}.get(ls.get('state', 'idle'), "❓")
                self.lbl_looter_state.configure(
                    text=f"{state_icon} {ls.get('state', 'idle')} | "
                         f"Cola: {ls.get('kill_queue', 0)} | "
                         f"Looteados: {ls.get('total_loots', 0)} | "
                         f"Clicks: {ls.get('total_clicks', 0)} | "
                         f"Método: {ls.get('loot_method', '?')} | "
                         f"SQMs: {ls.get('sqms_configured', 0)} | "
                         f"Tpl: {ls.get('template_detections', 0)} | "
                         f"HSV: {ls.get('visual_detections', 0)} | "
                         f"Ciegos: {ls.get('blind_fallbacks', 0)} | "
                         f"🖼️ {ls.get('corpse_templates', 0)} templates"
                )
                # Actualizar label de calibración
                cal = self.bot.calibrator
                if cal.game_region and cal.player_center and cal.sqm_size[0] > 0:
                    gx1, gy1, gx2, gy2 = cal.game_region
                    px, py = cal.player_center
                    sw, sh = cal.sqm_size
                    self.lbl_loot_calibration.configure(
                        text=f"✅ Calibrado: SQM={sw}×{sh}px, Center=({px},{py}), "
                             f"Game=({gx1},{gy1})-({gx2},{gy2})",
                        text_color="#55FF55",
                    )
            except Exception:
                pass

            try:
                # Cavebot status
                cs = self.bot.cavebot_engine.get_status()
                state_icon = {"idle": "💤", "walking": "🚶", "stuck": "⚠️",
                              "paused": "⏸️", "executing": "⚡"}.get(cs.get('state', 'idle'), "❓")
                self.lbl_cavebot_state.configure(
                    text=f"{state_icon} {cs.get('state', 'idle')} | "
                         f"WP: {cs.get('current_wp', 0)}/{cs.get('total_wps', 0)} | "
                         f"Pasos: {cs.get('step_count', 0)} | "
                         f"Ruta: {cs.get('route_name', 'ninguna')} | "
                         f"Modo: {cs.get('walk_mode', '?')}"
                )
            except Exception:
                pass
        except Exception:
            pass

    # ==================================================================
    # Control
    # ==================================================================
    def _toggle_bot(self):
        self.bot.toggle_active()

    # ==================================================================
    # Hotkeys globales
    # ==================================================================
    def _register_hotkeys(self):
        self._unregister_hotkeys()
        try:
            keyboard.add_hotkey(
                self.config.hotkey_toggle.lower(),
                self._on_hotkey_toggle,
                suppress=False,
            )
            self._hotkey_registered = True
        except Exception as e:
            self.log.warning(f"No se pudo registrar hotkey toggle: {e}")

        try:
            keyboard.add_hotkey(
                self.config.hotkey_exit.lower(),
                self._on_hotkey_exit,
                suppress=False,
            )
            self._exit_hotkey_registered = True
        except Exception as e:
            self.log.warning(f"No se pudo registrar hotkey exit: {e}")

    def _unregister_hotkeys(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._hotkey_registered = False
        self._exit_hotkey_registered = False

    def _on_hotkey_toggle(self):
        self.after(0, self._toggle_bot)

    def _on_hotkey_exit(self):
        self.after(0, self.destroy())

    # ==================================================================
    # Métodos del sistema de condiciones
    # ==================================================================
    def _on_conditions_toggle(self):
        """Callback cuando se activa/desactiva el sistema de condiciones."""
        enabled = self.conditions_enabled_var.get()
        conditions_cfg = self.config.conditions.copy()
        conditions_cfg["enabled"] = enabled
        self.config.conditions = conditions_cfg
        self.config.save()
        
        # Actualizar motor del bot
        if hasattr(self.bot, 'condition_engine'):
            self.bot.condition_engine.set_enabled(enabled)
        
        self.log.info(f"Sistema de condiciones {'activado' if enabled else 'desactivado'}")

    def _force_conditions_calibration(self):
        """Fuerza recalibración de las barras de condiciones."""
        try:
            if hasattr(self.bot, 'condition_engine'):
                self.bot.condition_engine.force_recalibration()
                self.log.ok("Recalibración forzada de barras de condiciones")
            else:
                self.log.warning("Motor de condiciones no disponible")
        except Exception as e:
            self.log.error(f"Error en recalibración: {e}")

    def _build_conditions_controls(self):
        """Construye dinámicamente los controles para todas las condiciones configuradas."""
        # Limpiar widgets existentes
        for widget in self.conditions_scroll_frame.winfo_children():
            widget.destroy()
        
        # Obtener todas las condiciones del config
        conditions = self.config.get_all_conditions()
        
        # Filtrar solo las condiciones individuales (no las globales)
        condition_configs = {}
        for key, value in conditions.items():
            if key not in ["enabled", "debug_mode", "global_cooldown"] and isinstance(value, dict):
                condition_configs[key] = value
        
        # Definir colores para cada tipo de condición
        condition_colors = {
            "haste": (0, 255, 0),      # Verde
            "paralyze": (255, 0, 255),    # Rojo
            "poison": (0, 0, 255),       # Azul
            "burning": (0, 165, 255),     # Naranja
            "curse": (128, 0, 128),     # Gris
            "hunger": (255, 165, 0),      # Amarillo oscuro
            "manashield": (255, 0, 255),     # Rojo
            "pz_zone": (255, 255, 255),   # Blanco
            "haste_medivia": (0, 255, 0),      # Verde
            "haste_otclient": (0, 255, 0),      # Verde
            "haste_otclientNewer": (0, 255, 0),      # Verde
            "haste_tibia-old": (0, 255, 0),      # Verde
            "haste_wearedragons": (0, 255, 0),      # Verde
            "paralyze_otclientNewer": (255, 0, 255),    # Rojo
            "poison_likeretro": (0, 0, 255),       # Azul
            "poison_medivia": (0, 0, 255),       # Azul
            "poison_otclientNewer": (0, 0, 255),       # Azul
            "poison_realera": (0, 0, 255),       # Azul
            "manashield_new": (255, 0, 255),     # Rojo
            "manashield_otclient": (255, 0, 255),     # Rojo
            "manashield_otclientNewer": (255, 0, 255),     # Rojo
            "hungry_lunos": (255, 165, 0),      # Amarillo oscuro
            "hungry_medivia": (255, 165, 0),      # Amarillo oscuro
            "hungry_nostalgic": (255, 165, 0),      # Amarillo oscuro
            "pz_zone_medivia": (255, 255, 255),   # Blanco
            "pz_zone_nostalgic": (255, 255, 255),   # Blanco
            "pz_zone_otclient": (255, 255, 255),   # Blanco
            "pz_zone_otclientv8": (255, 255, 255),   # Blanco
            "pz_zone_revolution": (255, 255, 255),   # Blanco
        }
        
        # Iconos para cada condición
        condition_icons = {
            "haste": "🏃",
            "paralyze": "⚡",
            "poison": "☠️",
            "burning": "🔥",
            "curse": "👻",
            "hunger": "🍽",
            "manashield": "🛡️",
            "pz_zone": "🛡️",
            "haste_medivia": "🏃",
            "haste_otclient": "🏃",
            "haste_otclientNewer": "🏃",
            "haste_tibia-old": "🏃",
            "haste_wearedragons": "🏃",
            "paralyze_otclientNewer": "⚡",
            "poison_likeretro": "☠️",
            "poison_medivia": "☠️",
            "poison_otclientNewer": "☠️",
            "poison_realera": "☠️",
            "manashield_new": "🛡️",
            "manashield_otclient": "🛡️",
            "manashield_otclientNewer": "🛡️",
            "hungry_lunos": "🍽",
            "hungry_medivia": "🍽",
            "hungry_nostalgic": "🍽",
            "pz_zone_medivia": "🛡️",
            "pz_zone_nostalgic": "🛡️",
            "pz_zone_otclient": "🛡️",
            "pz_zone_otclientv8": "🛡️",
            "pz_zone_revolution": "🛡️"
        }
        
        # Generar controles para cada condición
        for condition_name, condition_config in condition_configs.items():
            self._build_condition_control(condition_name, condition_config, condition_colors, condition_icons)
    
    def _build_condition_control(self, condition_name: str, condition_config: dict, colors: dict, icons: dict):
        """Construye el control para una condición específica."""
        # Frame para esta condición
        condition_frame = ctk.CTkFrame(self.conditions_scroll_frame)
        condition_frame.pack(fill="x", padx=5, pady=3)
        
        # Header con icono y color
        header_frame = ctk.CTkFrame(condition_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=(0, 3))
        
        icon_label = ctk.CTkLabel(header_frame, text=icons.get(condition_name, "❓"),
                                       font=ctk.CTkFont(size=16))
        icon_label.pack(side="left", padx=(0, 5))
        
        name_label = ctk.CTkLabel(header_frame, text=condition_name.upper(),
                                       font=ctk.CTkFont(size=14, weight="bold"))
        name_label.pack(side="left", padx=5)
        
        # Controles
        controls_frame = ctk.CTkFrame(condition_frame, fg_color="transparent")
        controls_frame.pack(fill="x", padx=(10, 0), pady=3)
        
        # Checkbox de activación
        enabled_var = ctk.BooleanVar(value=condition_config.get("enabled", False))
        ctk.CTkCheckBox(controls_frame, text="Activado", variable=enabled_var,
                     command=lambda: self._save_condition_config(condition_name)).pack(side="left", padx=(0, 10))
        
        # Hotkey
        hotkey_var = ctk.StringVar(value=condition_config.get("hotkey", ""))
        ctk.CTkLabel(controls_frame, text="Hotkey:").pack(side="left", padx=(10, 0))
        ctk.CTkOptionMenu(controls_frame, variable=hotkey_var,
                          values=[""] + [f"F{i}" for i in range(1, 13)],
                          width=80).pack(side="left", padx=3)
        
        # Sensibilidad
        threshold_var = ctk.DoubleVar(value=condition_config.get("threshold", 0.7))
        ctk.CTkLabel(controls_frame, text="Sensibilidad:").pack(side="left", padx=(10, 0))
        ctk.CTkSlider(controls_frame, from_=0.5, to=1.0, number_of_steps=10,
                     variable=threshold_var).pack(side="left", fill="x", expand=True)
        
        # Guardar referencia para actualización
        self._save_condition_control_vars(condition_name, enabled_var, hotkey_var, threshold_var)

    def _save_condition_control_vars(self, condition_name: str, enabled_var, hotkey_var, threshold_var):
        """Guarda las variables de control para una condición."""
        setattr(self, f"{condition_name}_enabled_var", enabled_var)
        setattr(self, f"{condition_name}_hotkey_var", hotkey_var)
        setattr(self, f"{condition_name}_threshold_var", threshold_var)

    def _save_condition_config(self, condition_name: str, enabled_var, hotkey_var, threshold_var):
        """Guarda configuración de una condición específica."""
        try:
            # Obtener configuración actual
            conditions_cfg = self.config.conditions.copy()
            
            # Actualizar configuración de la condición
            if condition_name not in conditions_cfg:
                conditions_cfg[condition_name] = {}
            
            conditions_cfg[condition_name]["enabled"] = enabled_var.get()
            conditions_cfg[condition_name]["hotkey"] = hotkey_var.get()
            conditions_cfg[condition_name]["threshold"] = threshold_var.get()
            
            # Guardar en config
            self.config.conditions = conditions_cfg
            self.config.save()
            
            # Actualizar motor del bot
            if hasattr(self.bot, 'condition_engine'):
                self.bot.condition_engine.update_from_config(conditions_cfg)
            
            self.log.ok(f"Configuración de {condition_name} guardada")
            
        except Exception as e:
            self.log.error(f"Error guardando configuración de {condition_name}: {e}")

    def _save_all_conditions_config(self):
        """Guarda toda la configuración de condiciones."""
        try:
            # Obtener todas las variables
            all_conditions = {}
            for condition_name in self.config.get_all_conditions().keys():
                if condition_name in ["enabled", "debug_mode", "global_cooldown"]:
                    continue  # Skip these, they're global
                
                # Buscar las variables correspondientes
                enabled_var = getattr(self, f"{condition_name}_enabled_var", None)
                hotkey_var = getattr(self, f"{condition_name}_hotkey_var", None)
                threshold_var = getattr(self, f"{condition_name}_threshold_var", None)
                
                if enabled_var and hotkey_var and threshold_var:
                    all_conditions[condition_name] = {
                        "enabled": enabled_var.get(),
                        "hotkey": hotkey_var.get(),
                        "threshold": threshold_var.get(),
                        "cooldown": self.config.get_condition(condition_name).get("cooldown", 1.0),
                        "last_triggered": 0.0
                    }
            
            # Actualizar configuración
            self.config.conditions = all_conditions
            self.config.save()
            
            # Actualizar motor del bot
            if hasattr(self.bot, 'condition_engine'):
                self.bot.condition_engine.update_from_config(all_conditions)
            
            self.log.ok("Configuración de condiciones guardada")
            
        except Exception as e:
            self.log.error(f"Error guardando configuración de condiciones: {e}")

    # ==================================================================
    # Cierre
    # ==================================================================
    def _on_close(self):
        """Limpieza al cerrar la aplicación."""
        self.log.info("Cerrando aplicación...")
        self._unregister_hotkeys()
        # Detener walk recorder
        if self.walk_recorder.is_recording:
            self.walk_recorder.stop_recording()
        if self.walk_recorder.is_playing:
            self.walk_recorder.stop_playback()
        if self._update_job:
            self.after_cancel(self._update_job)
        self.bot.cleanup()
        self.destroy()
