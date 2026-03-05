"""
gui.py - Interfaz gráfica completa con customtkinter.
Contiene las 4 secciones principales + pestaña de Ayuda.
"""

import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional

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

        # ----------------------------------------------------------
        # Configuración de la ventana principal
        # ----------------------------------------------------------
        self.title("⚔️ Tibia Auto Healer")
        self.geometry("780x900")
        self.minsize(700, 750)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ----------------------------------------------------------
        # Layout principal con tabs
        # ----------------------------------------------------------
        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.tab_main = self.tabview.add("🏠 Principal")
        self.tab_config = self.tabview.add("⚙️ Configuración")
        self.tab_windows = self.tabview.add("🪟 Ventanas")
        self.tab_cavebot = self.tabview.add("🗺️ Cavebot")
        self.tab_targeting = self.tabview.add("⚔️ Targeting")
        self.tab_looter = self.tabview.add("💰 Looter")
        self.tab_help = self.tabview.add("❓ Ayuda")

        # Construir cada sección
        self._build_main_tab()
        self._build_config_tab()
        self._build_windows_tab()
        self._build_cavebot_tab()
        self._build_targeting_tab()
        self._build_looter_tab()
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
        self._drain_log_queue()
        self.log.ok("GUI iniciada correctamente")

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
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header,
            text="⚔️ TIBIA AUTO HEALER",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left")

        self.btn_toggle = ctk.CTkButton(
            header,
            text="▶ ACTIVAR",
            width=140,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2ECC71",
            hover_color="#27AE60",
            command=self._toggle_bot,
        )
        self.btn_toggle.pack(side="right")

        # --- Estado ---
        status_frame = ctk.CTkFrame(tab)
        status_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_status = ctk.CTkLabel(
            status_frame,
            text="Estado: ○ INACTIVO",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFAA00",
        )
        self.lbl_status.pack(anchor="w", padx=15, pady=(10, 5))

        # --- Barras HP/MP ---
        bars_frame = ctk.CTkFrame(tab)
        bars_frame.pack(fill="x", padx=10, pady=5)

        # HP
        hp_row = ctk.CTkFrame(bars_frame, fg_color="transparent")
        hp_row.pack(fill="x", padx=15, pady=(10, 3))
        ctk.CTkLabel(hp_row, text="HP:", font=ctk.CTkFont(size=14, weight="bold"), width=35).pack(side="left")
        self.hp_bar = ctk.CTkProgressBar(hp_row, height=22, width=350)
        self.hp_bar.pack(side="left", padx=(5, 10))
        self.hp_bar.set(0)
        self.lbl_hp = ctk.CTkLabel(hp_row, text="N/A", font=ctk.CTkFont(size=14), width=120)
        self.lbl_hp.pack(side="left")

        # MP
        mp_row = ctk.CTkFrame(bars_frame, fg_color="transparent")
        mp_row.pack(fill="x", padx=15, pady=(3, 10))
        ctk.CTkLabel(mp_row, text="MP:", font=ctk.CTkFont(size=14, weight="bold"), width=35).pack(side="left")
        self.mp_bar = ctk.CTkProgressBar(mp_row, height=22, width=350, progress_color="#3498DB")
        self.mp_bar.pack(side="left", padx=(5, 10))
        self.mp_bar.set(0)
        self.lbl_mp = ctk.CTkLabel(mp_row, text="N/A", font=ctk.CTkFont(size=14), width=120)
        self.lbl_mp.pack(side="left")

        # --- Info conexión ---
        info_frame = ctk.CTkFrame(tab)
        info_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_tibia_status = ctk.CTkLabel(
            info_frame, text="Tibia: No conectado", font=ctk.CTkFont(size=12)
        )
        self.lbl_tibia_status.pack(anchor="w", padx=15, pady=(8, 2))

        self.lbl_proj_status = ctk.CTkLabel(
            info_frame, text="OBS WebSocket: No conectado", font=ctk.CTkFont(size=12)
        )
        self.lbl_proj_status.pack(anchor="w", padx=15, pady=(2, 2))

        self.lbl_fps = ctk.CTkLabel(
            info_frame, text="Capturas/seg: 0.0", font=ctk.CTkFont(size=12)
        )
        self.lbl_fps.pack(anchor="w", padx=15, pady=(2, 2))

        self.lbl_heals = ctk.CTkLabel(
            info_frame, text="Curaciones: 0", font=ctk.CTkFont(size=12)
        )
        self.lbl_heals.pack(anchor="w", padx=15, pady=(2, 8))

    # ==================================================================
    # TAB: Configuración de curación
    # ==================================================================
    def _build_config_tab(self):
        tab = self.tab_config

        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(tab, label_text="REGLAS DE CURACIÓN")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Reglas de HP ---
        self.rules_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.rules_container.pack(fill="x", padx=5, pady=5)

        self._rebuild_rules_ui()

        # Botones agregar/quitar
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(
            btn_row, text="+ Agregar regla", width=150, command=self._add_rule
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_row,
            text="- Quitar última",
            width=150,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=self._remove_last_rule,
        ).pack(side="left", padx=5)

        # --- Curación de Mana ---
        mana_frame = ctk.CTkFrame(scroll)
        mana_frame.pack(fill="x", padx=5, pady=(15, 5))
        ctk.CTkLabel(mana_frame, text="CURACIÓN DE MANA", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 4)
        )

        mana_row = ctk.CTkFrame(mana_frame, fg_color="transparent")
        mana_row.pack(fill="x", padx=10, pady=5)

        self.mana_enabled_var = ctk.BooleanVar(value=self.config.mana_heal.get("enabled", False))
        ctk.CTkCheckBox(
            mana_row, text="Activar", variable=self.mana_enabled_var, command=self._save_mana_config
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(mana_row, text="MP <").pack(side="left")
        self.mana_threshold_var = ctk.StringVar(
            value=str(int(self.config.mana_heal.get("threshold", 0.30) * 100))
        )
        ctk.CTkEntry(mana_row, textvariable=self.mana_threshold_var, width=50).pack(side="left", padx=3)
        ctk.CTkLabel(mana_row, text="% → Tecla:").pack(side="left")

        self.mana_key_var = ctk.StringVar(value=self.config.mana_heal.get("key", "F3"))
        ctk.CTkOptionMenu(
            mana_row, variable=self.mana_key_var, values=AVAILABLE_KEYS, width=80, command=lambda _: self._save_mana_config()
        ).pack(side="left", padx=5)

        # --- Parámetros ---
        params_frame = ctk.CTkFrame(scroll)
        params_frame.pack(fill="x", padx=5, pady=(15, 5))
        ctk.CTkLabel(params_frame, text="PARÁMETROS", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 4)
        )

        # Cooldown
        p_row1 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row1.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(p_row1, text="Cooldown entre curaciones (seg):").pack(side="left")
        self.cooldown_var = ctk.StringVar(value=str(self.config.cooldown))
        ctk.CTkEntry(p_row1, textvariable=self.cooldown_var, width=70).pack(side="left", padx=5)

        # Intervalo
        p_row2 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row2.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(p_row2, text="Intervalo de chequeo (seg):").pack(side="left")
        self.interval_var = ctk.StringVar(value=str(self.config.check_interval))
        ctk.CTkEntry(p_row2, textvariable=self.interval_var, width=70).pack(side="left", padx=5)

        # Hotkeys
        p_row3 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row3.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(p_row3, text="Tecla Activar/Desactivar:").pack(side="left")
        self.toggle_key_var = ctk.StringVar(value=self.config.hotkey_toggle)
        ctk.CTkOptionMenu(
            p_row3, variable=self.toggle_key_var, values=AVAILABLE_KEYS, width=80
        ).pack(side="left", padx=5)

        p_row4 = ctk.CTkFrame(params_frame, fg_color="transparent")
        p_row4.pack(fill="x", padx=10, pady=(3, 10))
        ctk.CTkLabel(p_row4, text="Tecla Salir:").pack(side="left")
        self.exit_key_var = ctk.StringVar(value=self.config.hotkey_exit)
        ctk.CTkOptionMenu(
            p_row4, variable=self.exit_key_var, values=AVAILABLE_KEYS, width=80
        ).pack(side="left", padx=5)

        # Botón guardar
        ctk.CTkButton(
            scroll,
            text="💾 Guardar Configuración",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._save_all_config,
        ).pack(fill="x", padx=5, pady=15)

    def _rebuild_rules_ui(self):
        """Reconstruye los widgets de reglas de HP."""
        for frame in self._rule_frames:
            frame.destroy()
        self._rule_frames.clear()

        self._rule_vars = []

        for i, level in enumerate(self.config.heal_levels):
            frame = ctk.CTkFrame(self.rules_container)
            frame.pack(fill="x", pady=3)

            ctk.CTkLabel(frame, text=f"Nivel {i + 1}:", width=65).pack(side="left", padx=(10, 5))
            ctk.CTkLabel(frame, text="HP <").pack(side="left")

            thresh_var = ctk.StringVar(value=str(int(level["threshold"] * 100)))
            ctk.CTkEntry(frame, textvariable=thresh_var, width=50).pack(side="left", padx=3)
            ctk.CTkLabel(frame, text="% → Tecla:").pack(side="left")

            key_var = ctk.StringVar(value=level.get("key", "F1"))
            ctk.CTkOptionMenu(
                frame, variable=key_var, values=AVAILABLE_KEYS, width=80
            ).pack(side="left", padx=5)

            ctk.CTkLabel(frame, text="Desc:").pack(side="left")
            desc_var = ctk.StringVar(value=level.get("description", ""))
            ctk.CTkEntry(frame, textvariable=desc_var, width=120).pack(side="left", padx=5)

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

    def _save_mana_config(self):
        try:
            threshold = int(self.mana_threshold_var.get()) / 100.0
        except ValueError:
            threshold = 0.30
        self.config.mana_heal = {
            "enabled": self.mana_enabled_var.get(),
            "threshold": threshold,
            "key": self.mana_key_var.get(),
            "description": "Mana potion",
        }

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
        self.log.ok("Configuración guardada exitosamente")

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

        self.cb_chase = ctk.CTkSwitch(mode_frame, text="Perseguir monstruos")
        self.cb_chase.pack(anchor="w", padx=15, pady=(3, 8))
        if self.config.targeting.get("chase_monsters", True):
            self.cb_chase.select()

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

        # Listas de criaturas
        def parse_list(text: str) -> list:
            return [s.strip() for s in text.split(",") if s.strip()]

        targeting["attack_list"] = parse_list(self.entry_attack_list.get())
        targeting["ignore_list"] = parse_list(self.entry_ignore_list.get())
        targeting["priority_list"] = parse_list(self.entry_priority_list.get())

        self.config.targeting = targeting
        self.config.save()
        # Re-configure engine with new settings
        self.bot.targeting_engine.configure(targeting)
        self.log.ok("Configuración de Targeting guardada")

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
    # TAB: Looter (v2.2)
    # ==================================================================
    def _build_looter_tab(self):
        tab = self.tab_looter
        scroll = ctk.CTkScrollableFrame(tab, label_text="💰 LOOTER — Looteo Automático")
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

        # --- Método de looteo ---
        method_frame = ctk.CTkFrame(scroll)
        method_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(method_frame, text="MÉTODO DE LOOTEO", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        row1 = ctk.CTkFrame(method_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row1, text="Método:", width=80).pack(side="left")
        self.cb_loot_method = ctk.CTkComboBox(
            row1,
            values=["shift_click", "open_body", "right_click", "left_click"],
            width=150,
        )
        self.cb_loot_method.set(self.config.looter.get("loot_method", "shift_click"))
        self.cb_loot_method.pack(side="left", padx=5)

        row2 = ctk.CTkFrame(method_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row2, text="Rango (tiles):", width=100).pack(side="left")
        self.entry_loot_range = ctk.CTkEntry(row2, width=60)
        self.entry_loot_range.insert(0, str(self.config.looter.get("max_range", 2)))
        self.entry_loot_range.pack(side="left", padx=5)

        self.cb_auto_bp = ctk.CTkSwitch(method_frame, text="Abrir siguiente backpack automáticamente")
        self.cb_auto_bp.pack(anchor="w", padx=15, pady=(3, 8))
        if self.config.looter.get("auto_open_next_bp", True):
            self.cb_auto_bp.select()

        # --- Filtro de items ---
        filter_frame = ctk.CTkFrame(scroll)
        filter_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(filter_frame, text="FILTRO DE ITEMS", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

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

        # Valor mínimo
        val_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        val_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(val_row, text="Valor mínimo de item (gp):").pack(side="left")
        self.entry_min_value = ctk.CTkEntry(val_row, width=80)
        self.entry_min_value.insert(0, str(item_filter.get("min_item_value", 0)))
        self.entry_min_value.pack(side="left", padx=5)

        # --- Backpack Routing ---
        bp_frame = ctk.CTkFrame(scroll)
        bp_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(bp_frame, text="BACKPACK ROUTING", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            bp_frame,
            text="Asigna cada categoría a un índice de backpack (0=primera, 1=segunda, ...)",
            font=ctk.CTkFont(size=11),
            text_color="#AAAAAA",
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

        # Padding final
        ctk.CTkFrame(bp_frame, fg_color="transparent", height=8).pack()

        # --- Guardar looter config ---
        ctk.CTkButton(
            scroll,
            text="💾 Guardar Config Looter",
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_looter_config,
        ).pack(fill="x", padx=5, pady=8)

        # --- Estado ---
        state_frame = ctk.CTkFrame(scroll)
        state_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(state_frame, text="ESTADO", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self.lbl_looter_state = ctk.CTkLabel(
            state_frame,
            text="Estado: idle | Pendientes: 0 | Looteados: 0 | BP libres: —",
            font=ctk.CTkFont(size=12),
        )
        self.lbl_looter_state.pack(anchor="w", padx=15, pady=(0, 10))

        # --- Log del Looter ---
        log_frame_lt = ctk.CTkFrame(scroll)
        log_frame_lt.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(log_frame_lt, text="📋 LOG LOOTER", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        self.log_looter = ctk.CTkTextbox(log_frame_lt, height=120, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_looter.pack(fill="x", padx=10, pady=(2, 8))
        self.log_looter.configure(state="disabled")

    def _save_looter_config(self):
        """Guarda toda la configuración del looter desde la GUI."""
        looter = self.config.looter

        # Método
        looter["loot_method"] = self.cb_loot_method.get()
        try:
            looter["max_range"] = int(self.entry_loot_range.get())
        except ValueError:
            pass
        looter["auto_open_next_bp"] = bool(self.cb_auto_bp.get())

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
        self.config.save()
        # Wire to dispatcher + engine
        if enabled:
            # Aplicar configuración actual de la GUI antes de activar
            self._save_looter_config()
            self.bot.dispatcher.enable_module("looter")
            self.bot.looter_engine.start()
        else:
            self.bot.dispatcher.disable_module("looter")
            self.bot.looter_engine.stop()
        self.log.info(f"Looter {'habilitado' if enabled else 'deshabilitado'}")

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
    # Panel de Logs
    # ==================================================================
    def _build_log_panel(self):
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="x", padx=8, pady=(0, 8))

        # Header
        header = ctk.CTkFrame(log_frame, fg_color="transparent")
        header.pack(fill="x", padx=5, pady=(5, 2))

        ctk.CTkLabel(header, text="📋 LOGS", font=ctk.CTkFont(weight="bold")).pack(side="left")

        ctk.CTkButton(
            header, text="Guardar", width=70, height=26, command=self._save_log
        ).pack(side="right", padx=3)
        ctk.CTkButton(
            header, text="Limpiar", width=70, height=26, command=self._clear_log
        ).pack(side="right", padx=3)

        # Auto-scroll checkbox
        self.autoscroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            header, text="Auto-scroll", variable=self.autoscroll_var, width=100
        ).pack(side="right", padx=10)

        # Nivel de log
        ctk.CTkLabel(header, text="Nivel:").pack(side="right", padx=(10, 3))
        self.log_level_var = ctk.StringVar(value=self.config.log_level)
        ctk.CTkOptionMenu(
            header,
            variable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            width=90,
            command=self._change_log_level,
        ).pack(side="right")

        # Textbox de logs
        self.log_text = ctk.CTkTextbox(
            log_frame, height=180, font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.log_text.pack(fill="x", padx=5, pady=(2, 5))
        self.log_text.configure(state="disabled")

        # Configurar tags de color
        self.log_text._textbox.tag_configure("DEBUG", foreground="#888888")
        self.log_text._textbox.tag_configure("INFO", foreground="#00CC66")
        self.log_text._textbox.tag_configure("WARNING", foreground="#FFAA00")
        self.log_text._textbox.tag_configure("ERROR", foreground="#FF3333")
        self.log_text._textbox.tag_configure("CRITICAL", foreground="#FF0000")

    def _log_callback(self, msg: str, level: str):
        """Callback invocado por BotLogger (puede venir de cualquier hilo)."""
        self._log_queue.put((msg, level))

    def _drain_log_queue(self):
        """Procesa mensajes pendientes en el hilo principal de tkinter."""
        try:
            while True:
                msg, level = self._log_queue.get_nowait()
                self._append_log(msg, level)
                # Redirigir a log de módulo si aplica
                self._route_module_log(msg)
        except queue.Empty:
            pass
        if self._gui_ready:
            self.after(50, self._drain_log_queue)

    def _route_module_log(self, msg: str):
        """Redirige mensajes a los logs por módulo."""
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
                target_widget.configure(state="normal")
                target_widget._textbox.insert("end", msg + "\n")
                # Limitar líneas
                line_count = int(target_widget._textbox.index("end-1c").split(".")[0])
                if line_count > 500:
                    target_widget._textbox.delete("1.0", "200.0")
                target_widget._textbox.see("end")
                target_widget.configure(state="disabled")
        except Exception:
            pass

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
        self._update_job = self.after(250, self._start_status_loop)

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

            # --- Módulos v3 status ---
            try:
                # Targeting status
                ts = self.bot.targeting_engine.get_status()
                target_txt = ts.get("current_target", "—") or "—"
                self.lbl_targeting_state.configure(
                    text=f"Estado: {'activo' if ts['enabled'] else 'idle'} | "
                         f"Target: {target_txt} | "
                         f"Kills: {ts['monsters_killed']} | "
                         f"Ataques: {ts['total_attacks']} | "
                         f"Templates: {ts['templates_loaded']}"
                )
            except Exception:
                pass

            try:
                # Looter status
                ls = self.bot.looter_engine.get_status()
                self.lbl_looter_state.configure(
                    text=f"Estado: {ls['state']} | "
                         f"Pendientes: {ls['pending_loots']} | "
                         f"Looteados: {ls['corpses_looted']} | "
                         f"SQMs: {ls['sqms_configured']}"
                )
            except Exception:
                pass

            try:
                # Cavebot status
                cs = self.bot.cavebot_engine.get_status()
                self.lbl_cavebot_state.configure(
                    text=f"Estado: {cs['state']} | "
                         f"WP: {cs['current_wp']}/{cs['total_wps']} | "
                         f"Pasos: {cs['steps']} | "
                         f"Marcas: {cs['marks_loaded']}"
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
        self.after(0, self._on_close)

    # ==================================================================
    # Cierre
    # ==================================================================
    def _on_close(self):
        """Limpieza al cerrar la aplicación."""
        self.log.info("Cerrando aplicación...")
        self._unregister_hotkeys()
        if self._update_job:
            self.after_cancel(self._update_job)
        self.bot.cleanup()
        self.destroy()
