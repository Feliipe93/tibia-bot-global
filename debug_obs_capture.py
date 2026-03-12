#!/usr/bin/env python3
"""
Script para debug de captura OBS
"""

import cv2
import numpy as np
from obswebsocket import obsws, requests
import time
from config import Config
import base64

def debug_obs_capture():
    """Debug del proceso de captura OBS."""
    
    # Cargar configuración
    config = Config()
    obs_config = config.data.get('obs', {})
    
    host = obs_config.get('host', 'localhost')
    port = obs_config.get('port', 4455)
    password = obs_config.get('password', '')
    source_name = obs_config.get('source_name', 'Captura de juego')
    
    try:
        ws = obsws(host, port, password)
        ws.connect()
        print("Conectado a OBS")
        
        # Obtener screenshot
        response = ws.call(requests.GetSourceScreenshot(sourceName=source_name, imageFormat="png"))
        
        if hasattr(response, 'datain') and 'imageData' in response.datain:
            img_data_b64 = response.datain['imageData']
            
            # Guardar datos base64 para análisis
            timestamp = int(time.time())
            b64_filename = f"debug/obs_b64_{timestamp}.txt"
            
            import os
            os.makedirs("debug", exist_ok=True)
            
            with open(b64_filename, 'w') as f:
                f.write(img_data_b64)
            
            print(f"Datos base64 guardados: {b64_filename}")
            print(f"Longitud: {len(img_data_b64)}")
            
            # Intentar diferentes métodos de decodificación
            try:
                # Método 1: Directo
                img_data = base64.b64decode(img_data_b64)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    filename = f"debug/obs_decode1_{timestamp}.png"
                    cv2.imwrite(filename, img)
                    print(f"Metodo 1 exitoso: {filename}")
                    return img
                else:
                    print("Metodo 1 fallido")
            except Exception as e:
                print(f"Error metodo 1: {e}")
            
            try:
                # Método 2: Con padding
                missing_padding = len(img_data_b64) % 4
                if missing_padding:
                    img_data_b64_padded = img_data_b64 + '=' * (4 - missing_padding)
                else:
                    img_data_b64_padded = img_data_b64
                
                img_data = base64.b64decode(img_data_b64_padded)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    filename = f"debug/obs_decode2_{timestamp}.png"
                    cv2.imwrite(filename, img)
                    print(f"Metodo 2 exitoso: {filename}")
                    return img
                else:
                    print("Metodo 2 fallido")
            except Exception as e:
                print(f"Error metodo 2: {e}")
            
            try:
                # Método 3: Como string sin procesar
                img_data = base64.b64decode(img_data_b64.encode('utf-8'))
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    filename = f"debug/obs_decode3_{timestamp}.png"
                    cv2.imwrite(filename, img)
                    print(f"Metodo 3 exitoso: {filename}")
                    return img
                else:
                    print("Metodo 3 fallido")
            except Exception as e:
                print(f"Error metodo 3: {e}")
        
        ws.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("Debug de captura OBS...")
    img = debug_obs_capture()
    
    if img is not None:
        print("Captura exitosa!")
    else:
        print("No se pudo capturar")
