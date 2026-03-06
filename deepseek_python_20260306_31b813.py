"""
WAYPOINT RECORDER PARA TIBIA - VERSIÓN SIN OBS WEBSOCKET
Usa captura directa del proyector visible con mss
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import json
import os
from datetime import datetime
import numpy as np
import cv2
import mss
import win32gui
import win32con
import keyboard
from PIL import Image, ImageTk

class WaypointRecorderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 Tibia Waypoint Recorder - Modo Proyector OBS")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Variables de estado
        self.recording = False
        self.capturing = False
        self.current_position = None
        self.current_xyz = (0, 0, 0)
        self.waypoints = []
        self.last_save_time = time.time()
        self.tibia_hwnd = None
        self.projector_hwnd = None
        self.projector_rect = None
        
        # Configuración
        self.config = self.load_config()
        
        self.setup_gui()
        self.setup_hotkeys()
        
        # Iniciar detección de ventanas
        self.find_windows()
        
        # Iniciar hilo de captura
        self.start_capture_thread()
    
    def setup_gui(self):
        """Configura la interfaz gráfica"""
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # === SECCIÓN 1: Detección de Ventanas ===
        win_frame = ttk.LabelFrame(main_frame, text="🪟 Ventanas Detectadas", padding="10")
        win_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(win_frame, text="Cliente Tibia:").grid(row=0, column=0, sticky=tk.W)
        self.tibia_label = ttk.Label(win_frame, text="🔍 Buscando...", foreground="orange")
        self.tibia_label.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(win_frame, text="Proyector OBS:").grid(row=1, column=0, sticky=tk.W)
        self.obs_label = ttk.Label(win_frame, text="🔍 Buscando...", foreground="orange")
        self.obs_label.grid(row=1, column=1, sticky=tk.W, padx=10)
        
        ttk.Button(win_frame, text="🔄 Refrescar", command=self.find_windows).grid(row=0, column=2, rowspan=2, padx=20)
        
        # === SECCIÓN 2: Captura en Vivo ===
        capture_frame = ttk.LabelFrame(main_frame, text="📸 Vista del Proyector OBS", padding="10")
        capture_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Canvas para la captura
        self.canvas = tk.Canvas(capture_frame, width=400, height=300, bg='black')
        self.canvas.grid(row=0, column=0, padx=5)
        
        # Info en tiempo real
        info_frame = ttk.Frame(capture_frame)
        info_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=10)
        
        ttk.Label(info_frame, text="📊 POSICIÓN ACTUAL:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.pos_label = ttk.Label(info_frame, text="X: ---  Y: ---  Z: ---", font=('Arial', 12))
        self.pos_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        
        ttk.Label(info_frame, text="🎯 ESTADO:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W)
        self.status_label = ttk.Label(info_frame, text="Esperando captura...")
        self.status_label.grid(row=3, column=0, sticky=tk.W, pady=5)
        
        # Barras de HP/MANA (opcional)
        ttk.Label(info_frame, text="❤️ HP:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky=tk.W)
        self.hp_bar = ttk.Progressbar(info_frame, length=200, mode='determinate')
        self.hp_bar.grid(row=5, column=0, pady=2)
        
        ttk.Label(info_frame, text="💙 MANA:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky=tk.W)
        self.mana_bar = ttk.Progressbar(info_frame, length=200, mode='determinate')
        self.mana_bar.grid(row=7, column=0, pady=2)
        
        # === SECCIÓN 3: Controles de grabación ===
        control_frame = ttk.LabelFrame(main_frame, text="🎮 CONTROLES", padding="10")
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Teclas rápidas
        hotkey_frame = ttk.Frame(control_frame)
        hotkey_frame.grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Label(hotkey_frame, text="🟢 F2: Agregar waypoint", font=('Arial', 10)).grid(row=0, column=0, padx=10)
        ttk.Label(hotkey_frame, text="🔴 F3: Eliminar último", font=('Arial', 10)).grid(row=0, column=1, padx=10)
        ttk.Label(hotkey_frame, text="⏺️ F4: Iniciar/Detener", font=('Arial', 10)).grid(row=0, column=2, padx=10)
        
        # Botones
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=1, column=0, pady=10)
        
        self.record_btn = ttk.Button(btn_frame, text="⏺️ INICIAR GRABACIÓN", command=self.toggle_recording, width=25)
        self.record_btn.grid(row=0, column=0, padx=5)
        
        ttk.Button(btn_frame, text="➕ Agregar manual", command=self.add_waypoint).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="❌ Eliminar último", command=self.remove_last_waypoint).grid(row=0, column=2, padx=5)
        
        # === SECCIÓN 4: Lista de waypoints ===
        list_frame = ttk.LabelFrame(main_frame, text="📋 WAYPOINTS", padding="10")
        list_frame.grid(row=1, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Treeview
        columns = ('#', 'X', 'Y', 'Z', 'Acción')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        self.tree.heading('#', text='#')
        self.tree.heading('X', text='X')
        self.tree.heading('Y', text='Y')
        self.tree.heading('Z', text='Z')
        self.tree.heading('Acción', text='Acción')
        
        self.tree.column('#', width=40)
        self.tree.column('X', width=60)
        self.tree.column('Y', width=60)
        self.tree.column('Z', width=40)
        self.tree.column('Acción', width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Botones de gestión
        manage_frame = ttk.Frame(list_frame)
        manage_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        ttk.Button(manage_frame, text="✏️ Acción", command=self.edit_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(manage_frame, text="⬆️", command=self.move_up, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(manage_frame, text="⬇️", command=self.move_down, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(manage_frame, text="🗑️", command=self.delete_selected, width=3).pack(side=tk.LEFT, padx=2)
        
        # === SECCIÓN 5: Guardar/Cargar ===
        save_frame = ttk.LabelFrame(main_frame, text="💾 GUARDAR/CARGAR", padding="10")
        save_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.route_name = tk.StringVar(value="mi_ruta")
        ttk.Label(save_frame, text="Nombre:").grid(row=0, column=0, padx=5)
        ttk.Entry(save_frame, textvariable=self.route_name, width=30).grid(row=0, column=1, padx=5)
        
        ttk.Button(save_frame, text="💾 Guardar", command=self.save_waypoints).grid(row=0, column=2, padx=5)
        ttk.Button(save_frame, text="📂 Cargar", command=self.load_waypoints).grid(row=0, column=3, padx=5)
        ttk.Button(save_frame, text="🔄 Exportar NG", command=self.export_format).grid(row=0, column=4, padx=5)
        
        # === SECCIÓN 6: Logs ===
        log_frame = ttk.LabelFrame(main_frame, text="📝 LOGS", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.log_text = tk.Text(log_frame, height=5, width=100)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        scroll_log = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scroll_log.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scroll_log.set)
    
    def find_windows(self):
        """Busca las ventanas de Tibia y OBS"""
        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                
                # Buscar Tibia (contiene "Tibia" en el título)
                if "tibia" in title.lower():
                    rect = win32gui.GetWindowRect(hwnd)
                    results['tibia'] = {
                        'hwnd': hwnd,
                        'title': title,
                        'rect': rect
                    }
                
                # Buscar Proyector OBS
                obs_keywords = ["proyector", "projector", "fuente", "source", "captura"]
                if any(k in title.lower() for k in obs_keywords):
                    rect = win32gui.GetWindowRect(hwnd)
                    results['obs'] = {
                        'hwnd': hwnd,
                        'title': title,
                        'rect': rect
                    }
            return True
        
        results = {}
        win32gui.EnumWindows(enum_callback, results)
        
        # Actualizar labels
        if 'tibia' in results:
            self.tibia_hwnd = results['tibia']['hwnd']
            self.tibia_label.config(
                text=f"✅ {results['tibia']['title']}", 
                foreground="green"
            )
        else:
            self.tibia_hwnd = None
            self.tibia_label.config(text="❌ No encontrado", foreground="red")
        
        if 'obs' in results:
            self.projector_hwnd = results['obs']['hwnd']
            self.projector_rect = results['obs']['rect']
            self.obs_label.config(
                text=f"✅ {results['obs']['title']}", 
                foreground="green"
            )
            self.log(f"Proyector OBS encontrado: {results['obs']['rect'][2]-results['obs']['rect'][0]}x{results['obs']['rect'][3]-results['obs']['rect'][1]}")
        else:
            self.projector_hwnd = None
            self.projector_rect = None
            self.obs_label.config(text="❌ No encontrado", foreground="red")
    
    def capture_projector(self):
        """Captura el proyector OBS usando mss"""
        if not self.projector_rect:
            return None
        
        x, y, x2, y2 = self.projector_rect
        width = x2 - x
        height = y2 - y
        
        # Quitar bordes de Windows (ajusta según necesites)
        BORDER = 8
        TITLEBAR = 30
        
        monitor = {
            "left": x + BORDER,
            "top": y + TITLEBAR,
            "width": width - BORDER * 2,
            "height": height - TITLEBAR - BORDER
        }
        
        try:
            with mss.mss() as sct:
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img
        except Exception as e:
            self.log(f"Error capturando: {e}")
            return None
    
    def detect_hp_mana(self, img):
        """Detecta porcentajes de HP y Mana (opcional)"""
        if img is None:
            return 0, 0
        
        h, w = img.shape[:2]
        
        # Área de las barras (parte superior)
        bar_region = img[20:80, :]
        
        # Convertir a HSV
        hsv = cv2.cvtColor(bar_region, cv2.COLOR_BGR2HSV)
        
        # Máscara para HP (verde/amarillo/rojo)
        mask_hp = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([180, 255, 255]))
        
        # Máscara para Mana (azul)
        mask_mana = cv2.inRange(hsv, np.array([95, 50, 50]), np.array([135, 255, 255]))
        
        # Calcular porcentajes (simplificado)
        hp_pixels = np.sum(mask_hp > 0)
        mana_pixels = np.sum(mask_mana > 0)
        
        max_pixels = w * 20  # Altura de la región ~20px
        
        hp_pct = min(hp_pixels / max_pixels * 100, 100)
        mana_pct = min(mana_pixels / max_pixels * 100, 100)
        
        return hp_pct, mana_pct
    
    def detect_position_from_minimap(self, img):
        """
        Detecta la posición del jugador desde el minimapa
        """
        if img is None:
            return None
        
        h, w = img.shape[:2]
        
        # El minimapa está en la esquina superior derecha
        minimap_x = w - 180
        minimap_y = 20
        minimap_w = 160
        minimap_h = 160
        
        if minimap_x < 0 or minimap_y < 0:
            return None
        
        minimap = img[minimap_y:minimap_y+minimap_h, minimap_x:minimap_x+minimap_w]
        
        if minimap.size == 0:
            return None
        
        # Convertir a HSV
        hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)
        
        # Rango para punto amarillo del jugador
        yellow_min = np.array([20, 100, 100])
        yellow_max = np.array([35, 255, 255])
        
        mask = cv2.inRange(hsv, yellow_min, yellow_max)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Filtrar por tamaño
            valid_contours = [c for c in contours if 5 < cv2.contourArea(c) < 100]
            
            if valid_contours:
                # Tomar el más grande
                largest = max(valid_contours, key=cv2.contourArea)
                
                # Calcular centro
                M = cv2.moments(largest)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # Convertir a coordenadas de grid (cada tile ≈ 4 píxeles)
                    grid_x = cx // 4
                    grid_y = cy // 4
                    
                    # Detectar Z por color (simplificado)
                    # Área alrededor del punto
                    roi = minimap[max(0, cy-5):min(minimap_h, cy+5), 
                                  max(0, cx-5):min(minimap_w, cx+5)]
                    avg_color = np.mean(roi) if roi.size > 0 else 0
                    
                    # Si el color es oscuro, Z más profundo
                    z = 7 if avg_color < 100 else 6
                    
                    return (grid_x, grid_y, z)
        
        return None
    
    def capture_loop(self):
        """Loop principal de captura"""
        last_capture_time = 0
        frame_count = 0
        
        while self.capturing:
            try:
                current_time = time.time()
                
                # Capturar a 2 FPS
                if current_time - last_capture_time >= 0.5:
                    img = self.capture_projector()
                    
                    if img is not None:
                        frame_count += 1
                        
                        # Detectar HP/Mana
                        hp, mana = self.detect_hp_mana(img)
                        
                        # Detectar posición
                        pos = self.detect_position_from_minimap(img)
                        
                        if pos:
                            self.current_position = pos
                            self.current_xyz = pos
                            
                            # Actualizar GUI
                            self.root.after(0, lambda: self.update_display(img, hp, mana, pos))
                            
                            # Si está grabando, guardar automáticamente
                            if self.recording and current_time - self.last_save_time > 2:
                                self.add_waypoint(auto=True)
                                self.last_save_time = current_time
                    
                    last_capture_time = current_time
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error en capture_loop: {e}")
                time.sleep(1)
    
    def update_display(self, img, hp, mana, pos):
        """Actualiza la GUI con la última captura"""
        # Actualizar posición
        if pos:
            x, y, z = pos
            self.pos_label.config(text=f"X: {x}  Y: {y}  Z: {z}")
        
        # Actualizar barras
        self.hp_bar['value'] = hp
        self.mana_bar['value'] = mana
        
        # Actualizar canvas
        self.update_canvas(img)
        
        # Actualizar estado
        status = f"Captura OK | HP: {hp:.0f}% | Mana: {mana:.0f}%"
        if self.recording:
            status += " | 🔴 GRABANDO"
        self.status_label.config(text=status)
    
    def update_canvas(self, img):
        """Muestra la imagen en el canvas"""
        if img is None:
            return
        
        # Redimensionar para el canvas
        height, width = img.shape[:2]
        scale = min(400/width, 300/height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        img_resized = cv2.resize(img, (new_width, new_height))
        
        # Convertir a RGB para tkinter
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_tk = ImageTk.PhotoImage(img_pil)
        
        # Actualizar canvas
        self.canvas.delete("all")
        self.canvas.create_image(200, 150, image=img_tk, anchor=tk.CENTER)
        self.canvas.image = img_tk  # Mantener referencia
    
    def setup_hotkeys(self):
        """Configura las teclas rápidas"""
        keyboard.on_press_key("F2", lambda _: self.root.after(0, self.add_waypoint))
        keyboard.on_press_key("F3", lambda _: self.root.after(0, self.remove_last_waypoint))
        keyboard.on_press_key("F4", lambda _: self.root.after(0, self.toggle_recording))
    
    def start_capture_thread(self):
        """Inicia el hilo de captura"""
        self.capturing = True
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()
        self.log("🔄 Hilo de captura iniciado")
    
    def toggle_recording(self):
        """Inicia/detiene grabación"""
        self.recording = not self.recording
        if self.recording:
            self.record_btn.config(text="⏹️ DETENER GRABACIÓN")
            self.log("🎥 Grabación automática iniciada")
        else:
            self.record_btn.config(text="⏺️ INICIAR GRABACIÓN")
            self.log("⏹️ Grabación detenida")
    
    def add_waypoint(self, auto=False):
        """Agrega un waypoint"""
        if not self.current_xyz:
            self.log("⚠️ No hay posición detectada")
            return
        
        x, y, z = self.current_xyz
        waypoint = {
            "x": x,
            "y": y,
            "z": z,
            "action": "walk",
            "timestamp": time.time()
        }
        
        self.waypoints.append(waypoint)
        self.update_waypoints_list()
        
        action = "automático" if auto else "manual"
        self.log(f"➕ Waypoint {len(self.waypoints)}: ({x}, {y}, {z}) [{action}]")
    
    def remove_last_waypoint(self):
        """Elimina último waypoint"""
        if self.waypoints:
            removed = self.waypoints.pop()
            self.update_waypoints_list()
            self.log(f"❌ Eliminado: ({removed['x']}, {removed['y']}, {removed['z']})")
    
    def update_waypoints_list(self):
        """Actualiza lista de waypoints"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for i, wp in enumerate(self.waypoints, 1):
            self.tree.insert('', 'end', values=(
                i, wp['x'], wp['y'], wp['z'], wp.get('action', 'walk')
            ))
    
    def edit_action(self):
        """Edita acción del waypoint seleccionado"""
        selected = self.tree.selection()
        if not selected:
            return
        
        item = self.tree.item(selected[0])
        idx = int(item['values'][0]) - 1
        
        # Diálogo simple
        dialog = tk.Toplevel(self.root)
        dialog.title("Acción")
        dialog.geometry("200x150")
        
        ttk.Label(dialog, text="Selecciona acción:").pack(pady=10)
        
        actions = ["walk", "stand", "rope", "shovel", "ladder", "door", "use", "refill"]
        var = tk.StringVar(value=self.waypoints[idx].get('action', 'walk'))
        
        combo = ttk.Combobox(dialog, textvariable=var, values=actions)
        combo.pack(pady=10)
        
        def save():
            self.waypoints[idx]['action'] = var.get()
            self.update_waypoints_list()
            self.log(f"✏️ Waypoint {idx+1} acción: {var.get()}")
            dialog.destroy()
        
        ttk.Button(dialog, text="Guardar", command=save).pack(pady=10)
    
    def move_up(self):
        """Mueve waypoint arriba"""
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        idx = int(item['values'][0]) - 1
        if idx > 0:
            self.waypoints[idx], self.waypoints[idx-1] = self.waypoints[idx-1], self.waypoints[idx]
            self.update_waypoints_list()
    
    def move_down(self):
        """Mueve waypoint abajo"""
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        idx = int(item['values'][0]) - 1
        if idx < len(self.waypoints) - 1:
            self.waypoints[idx], self.waypoints[idx+1] = self.waypoints[idx+1], self.waypoints[idx]
            self.update_waypoints_list()
    
    def delete_selected(self):
        """Elimina waypoint seleccionado"""
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        idx = int(item['values'][0]) - 1
        removed = self.waypoints.pop(idx)
        self.update_waypoints_list()
        self.log(f"🗑️ Eliminado waypoint {idx+1}")
    
    def save_waypoints(self):
        """Guarda waypoints a JSON"""
        if not self.waypoints:
            messagebox.showwarning("Sin datos", "No hay waypoints")
            return
        
        filename = f"routes/{self.route_name.get()}.json"
        os.makedirs("routes", exist_ok=True)
        
        data = {
            "name": self.route_name.get(),
            "created": datetime.now().isoformat(),
            "waypoints": self.waypoints,
            "total": len(self.waypoints)
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.log(f"💾 Guardados {len(self.waypoints)} waypoints")
    
    def load_waypoints(self):
        """Carga waypoints desde JSON"""
        filename = filedialog.askopenfilename(
            initialdir="routes",
            filetypes=[("JSON", "*.json")]
        )
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
            self.waypoints = data['waypoints']
            self.route_name.set(data['name'])
            self.update_waypoints_list()
            self.log(f"📂 Cargados {len(self.waypoints)} waypoints")
    
    def export_format(self):
        """Exporta a formato NG"""
        if not self.waypoints:
            return
        
        ng_format = []
        for wp in self.waypoints:
            ng_format.append({
                "label": f"WP_{wp['x']}_{wp['y']}",
                "type": wp.get('action', 'walk'),
                "coordinate": [wp['x'], wp['y'], wp['z']],
                "options": {},
                "ignore": False,
                "passinho": False
            })
        
        filename = f"routes/{self.route_name.get()}_NG.json"
        with open(filename, 'w') as f:
            json.dump(ng_format, f, indent=2)
        
        self.log(f"🔄 Exportado a NG: {filename}")
    
    def log(self, message):
        """Añade mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        print(log_entry.strip())
    
    def load_config(self):
        """Carga configuración"""
        config_file = "waypoint_config.json"
        default = {
            "obs_host": "localhost",
            "obs_port": 4455
        }
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return default
    
    def on_closing(self):
        """Cierra la aplicación"""
        self.capturing = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=1)
        self.root.destroy()

def main():
    root = tk.Tk()
    app = WaypointRecorderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()