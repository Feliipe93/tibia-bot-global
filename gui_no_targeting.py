#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gui_no_targeting.py - Versión de la GUI que no carga targeting al inicio
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import threading
import time
from config import Config

class NoTargetingGUI:
    """GUI que no carga targeting al inicio para evitar congelación."""
    
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Tibia Auto Healer - Modo Seguro")
        self.root.geometry("800x600")
        
        self.targeting_engine = None
        self.targeting_loaded = False
        
        self.create_widgets()
        
    def create_widgets(self):
        """Crea los widgets principales."""
        # Frame principal
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Título
        title = ctk.CTkLabel(
            main_frame,
            text="TIBIA AUTO HEALER - MODO SEGURO",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Estado
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="Estado: Listo para cargar targeting",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(pady=10)
        
        # Botones
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(pady=20)
        
        # Botón de cargar targeting
        self.load_button = ctk.CTkButton(
            button_frame,
            text="Cargar Targeting",
            command=self.load_targeting_thread,
            width=200
        )
        self.load_button.pack(pady=5)
        
        # Botón de activar targeting
        self.enable_button = ctk.CTkButton(
            button_frame,
            text="Activar Targeting",
            command=self.enable_targeting,
            width=200,
            state="disabled"
        )
        self.enable_button.pack(pady=5)
        
        # Botón de prueba
        test_button = ctk.CTkButton(
            button_frame,
            text="Probar Detección",
            command=self.test_detection,
            width=200,
            state="disabled"
        )
        test_button.pack(pady=5)
        
        # Botón de salir
        exit_button = ctk.CTkButton(
            button_frame,
            text="Salir",
            command=self.root.quit,
            width=200
        )
        exit_button.pack(pady=5)
        
    def load_targeting_thread(self):
        """Carga el targeting en un hilo separado."""
        self.load_button.configure(state="disabled")
        self.status_label.configure(text="Estado: Cargando targeting...")
        self.root.update()
        
        def load_in_thread():
            try:
                from targeting_engine_v2 import TargetingEngineV2
                
                self.status_label.configure(text="Estado: Inicializando engine...")
                self.root.update()
                
                self.targeting_engine = TargetingEngineV2()
                
                self.status_label.configure(text="Estado: Cargando configuración...")
                self.root.update()
                
                config = Config()
                self.targeting_engine.configure(config)
                
                self.targeting_loaded = True
                
                self.status_label.configure(text="Estado: Targeting cargado correctamente")
                self.enable_button.configure(state="normal")
                test_button.configure(state="normal")
                
            except Exception as e:
                self.status_label.configure(text=f"Estado: Error - {e}")
                self.load_button.configure(state="normal")
        
        # Iniciar en hilo separado
        thread = threading.Thread(target=load_in_thread)
        thread.daemon = True
        thread.start()
    
    def enable_targeting(self):
        """Activa el targeting."""
        if self.targeting_engine and self.targeting_loaded:
            config = Config()
            targeting_config = config.get("targeting", {})
            targeting_config["enabled"] = True
            targeting_config["auto_attack"] = True
            
            self.targeting_engine.configure(config)
            
            self.status_label.configure(text="Estado: Targeting ACTIVADO")
            self.enable_button.configure(text="Targeting Activado", state="disabled")
    
    def test_detection(self):
        """Prueba la detección de Rotworm."""
        if self.targeting_engine and self.targeting_loaded:
            try:
                self.status_label.configure(text="Estado: Probando detección...")
                self.root.update()
                
                results = self.targeting_engine.search_creatures("Rotworm")
                
                self.status_label.configure(
                    text=f"Estado: {len(results)} Rotworms encontrados"
                )
                
            except Exception as e:
                self.status_label.configure(text=f"Estado: Error en prueba - {e}")
    
    def run(self):
        """Inicia la GUI."""
        self.root.mainloop()

if __name__ == "__main__":
    print("Iniciando GUI modo seguro...")
    gui = NoTargetingGUI()
    gui.run()
