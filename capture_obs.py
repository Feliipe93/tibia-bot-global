#!/usr/bin/env python3
"""
Script para capturar y guardar imagen de OBS para diagnóstico
"""

import cv2
import numpy as np
from obswebsocket import obsws, requests
import time
from config import Config

def capture_obs_image():
    """Captura una imagen desde OBS y la guarda para análisis."""
    
    # Cargar configuración
    config = Config()
    obs_config = config.data.get('obs', {})
    
    host = obs_config.get('host', 'localhost')
    port = obs_config.get('port', 4455)
    password = obs_config.get('password', '')
    source_name = obs_config.get('source_name', 'Captura de juego')
    
    print(f"Conectando a OBS en {host}:{port}")
    print(f"Fuente: {source_name}")
    
    try:
        # Conectar a OBS
        ws = obsws(host, port, password)
        ws.connect()
        print("Conectado a OBS")
        
        # Obtener screenshot
        print("Capturando imagen desde OBS...")
        response = ws.call(requests.GetSourceScreenshot(sourceName=source_name, imageFormat="png"))
        
        if hasattr(response, 'datain') and 'imageData' in response.datain:
            # Decodificar imagen base64
            import base64
            img_data = base64.b64decode(response.datain['imageData'])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is not None:
                # Guardar imagen
                timestamp = int(time.time())
                filename = f"debug/obs_capture_{timestamp}.png"
                
                import os
                os.makedirs("debug", exist_ok=True)
                cv2.imwrite(filename, img)
                
                print(f"Imagen guardada: {filename}")
                print(f"   Dimensiones: {img.shape}")
                
                # Analizar la imagen para detectar barras
                analyze_bars(img, filename)
                
                return img
            else:
                print("Error decodificando imagen")
        else:
            print(f"Error capturando screenshot: {response}")
        
        ws.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def analyze_bars(img, filename):
    """Analiza la imagen para detectar barras de HP/Mana/Condiciones."""
    h, w = img.shape[:2]
    print(f"\nAnalizando imagen ({w}x{h})...")
    
    # Buscar barras en la parte inferior
    bottom_region = img[h - 200:h, :]
    
    # Convertir a HSV para análisis de color
    hsv = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2HSV)
    
    # Buscar colores de barras
    # Rojo (HP)
    red_mask = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
    red_pixels = cv2.countNonZero(red_mask)
    
    # Azul (Mana)
    blue_mask = cv2.inRange(hsv, (100, 50, 50), (130, 255, 255))
    blue_pixels = cv2.countNonZero(blue_mask)
    
    print(f"Analisis de colores:")
    print(f"   Rojo (HP): {red_pixels} pixeles")
    print(f"   Azul (Mana): {blue_pixels} pixeles")
    
    # Buscar colores de condiciones
    condition_colors = {
        'Verde (Haste)': cv2.inRange(hsv, (40, 50, 50), (80, 255, 255)),
        'Amarillo (Poison)': cv2.inRange(hsv, (20, 50, 50), (30, 255, 255)),
        'Naranja (Burning)': cv2.inRange(hsv, (10, 100, 50), (20, 255, 255)),
        'Purpura (Curse)': cv2.inRange(hsv, (130, 50, 50), (170, 255, 255)),
        'Magenta (Mana Shield)': cv2.inRange(hsv, (140, 50, 50), (170, 255, 255))
    }
    
    print(f"\nAnalisis de condiciones:")
    for color_name, mask in condition_colors.items():
        pixels = cv2.countNonZero(mask)
        print(f"   {color_name}: {pixels} pixeles")
    
    # Guardar imagen con análisis
    analysis_img = img.copy()
    
    # Dibujar región de análisis
    cv2.rectangle(analysis_img, (0, h - 200), (w, h), (0, 255, 0), 2)
    cv2.putText(analysis_img, "Region de Analisis", (10, h - 180), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Guardar análisis
    analysis_filename = filename.replace(".png", "_analysis.png")
    cv2.imwrite(analysis_filename, analysis_img)
    print(f"\nAnalisis guardado: {analysis_filename}")
    
    # Intentar detectar línea de condiciones
    gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    lines = cv2.HoughLinesP(edges, 1, np.pi/2, 100, minLineLength=50, maxLineGap=10)
    
    if lines is not None:
        print(f"\nLineas horizontales detectadas: {len(lines)}")
        for i, line in enumerate(lines[:5]):  # Mostrar primeras 5
            x1, y1, x2, y2 = line[0]
            global_y = (h - 200) + y1
            print(f"   Linea {i+1}: y={global_y}")
    else:
        print("\nNo se detectaron lineas horizontales")

if __name__ == "__main__":
    print("Capturando imagen desde OBS para diagnostico...")
    img = capture_obs_image()
    
    if img is not None:
        print("\nCaptura completada. Revisa las imagenes en la carpeta debug/")
        print("   - obs_capture_*.png: Imagen original")
        print("   - obs_capture_*_analysis.png: Imagen con analisis")
    else:
        print("\nNo se pudo capturar la imagen")
