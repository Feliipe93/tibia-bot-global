#!/usr/bin/env python3
"""
Script corregido para capturar imagen desde OBS
"""

import cv2
import numpy as np
from obswebsocket import obsws, requests
import time
from config import Config
import base64

def capture_obs_fixed():
    """Captura imagen desde OBS corrigiendo el formato base64."""
    
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
        ws = obsws(host, port, password)
        ws.connect()
        print("Conectado a OBS")
        
        # Obtener screenshot
        print("Capturando imagen...")
        response = ws.call(requests.GetSourceScreenshot(sourceName=source_name, imageFormat="png"))
        
        if hasattr(response, 'datain') and 'imageData' in response.datain:
            img_data_b64 = response.datain['imageData']
            
            # REMOVER el prefijo data:image/png;base64,
            if img_data_b64.startswith('data:image/png;base64,'):
                img_data_b64 = img_data_b64.replace('data:image/png;base64,', '')
                print("Prefijo data URL removido")
            
            # Decodificar base64
            img_data = base64.b64decode(img_data_b64)
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
                print(f"Dimensiones: {img.shape}")
                
                # Análisis detallado
                analyze_image(img, filename)
                
                return img
            else:
                print("Error: img es None despues de decodificar")
        else:
            print(f"Error: no se encontro imageData en respuesta")
        
        ws.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_image(img, filename):
    """Analiza la imagen capturada."""
    h, w = img.shape[:2]
    print(f"\nAnalizando imagen ({w}x{h})...")
    
    # Guardar diferentes regiones
    import os
    os.makedirs("debug", exist_ok=True)
    
    # Región inferior completa
    bottom_region = img[h-200:h, :]
    bottom_filename = filename.replace(".png", "_bottom.png")
    cv2.imwrite(bottom_filename, bottom_region)
    print(f"Region inferior guardada: {bottom_filename}")
    
    # Región de condiciones (donde deberían estar los iconos)
    condition_region = img[h-100:h, w-400:w]
    condition_filename = filename.replace(".png", "_conditions.png")
    cv2.imwrite(condition_filename, condition_region)
    print(f"Region de condiciones guardada: {condition_filename}")
    
    # Análisis de colores
    hsv = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2HSV)
    
    # Buscar colores de condiciones
    colors = {
        'Rojo (HP)': cv2.inRange(hsv, (0, 50, 50), (10, 255, 255)),
        'Azul (Mana)': cv2.inRange(hsv, (100, 50, 50), (130, 255, 255)),
        'Verde (Haste)': cv2.inRange(hsv, (40, 50, 50), (80, 255, 255)),
        'Amarillo (Poison)': cv2.inRange(hsv, (20, 50, 50), (30, 255, 255)),
        'Naranja (Burning)': cv2.inRange(hsv, (10, 100, 50), (20, 255, 255)),
        'Purpura (Curse)': cv2.inRange(hsv, (130, 50, 50), (170, 255, 255)),
        'Magenta (Mana Shield)': cv2.inRange(hsv, (140, 50, 50), (170, 255, 255))
    }
    
    print("\nAnalisis de colores:")
    for color_name, mask in colors.items():
        pixels = cv2.countNonZero(mask)
        print(f"   {color_name}: {pixels} pixeles")
        
        if pixels > 100:  # Si hay suficientes píxeles
            color_filename = filename.replace(".png", f"_{color_name.replace(' ', '_').replace('(', '').replace(')', '')}.png")
            color_result = cv2.bitwise_and(bottom_region, bottom_region, mask=mask)
            cv2.imwrite(color_filename, color_result)
            print(f"      -> Guardado: {color_filename}")

if __name__ == "__main__":
    print("Captura corregida desde OBS...")
    img = capture_obs_fixed()
    
    if img is not None:
        print("\nCaptura exitosa!")
        print("Revisa la carpeta debug/ para ver todas las imágenes generadas")
    else:
        print("\nNo se pudo capturar")
