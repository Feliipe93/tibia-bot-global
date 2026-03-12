#!/usr/bin/env python3
"""
Script alternativo para capturar imagen desde OBS
"""

import cv2
import numpy as np
from obswebsocket import obsws, requests
import time
from config import Config
import base64

def capture_obs_simple():
    """Captura imagen desde OBS usando método simple."""
    
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
        
        # Obtener screenshot con formato png
        print("Capturando imagen...")
        response = ws.call(requests.GetSourceScreenshot(sourceName=source_name, imageFormat="png", compressionQuality=100))
        
        print(f"Respuesta recibida: {type(response)}")
        if hasattr(response, 'datain'):
            print(f"Datain keys: {response.datain.keys()}")
            
        if hasattr(response, 'datain') and 'imageData' in response.datain:
            img_data_b64 = response.datain['imageData']
            print(f"Longitud de datos: {len(img_data_b64)}")
            
            # Intentar decodificar
            try:
                # Añadir padding si es necesario
                missing_padding = len(img_data_b64) % 4
                if missing_padding:
                    img_data_b64 += '=' * (4 - missing_padding)
                
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
                    
                    # Análisis simple
                    h, w = img.shape[:2]
                    print(f"Analizando region inferior ({w}x{h})...")
                    
                    # Guardar también la región inferior
                    bottom_region = img[h-150:h, :]
                    bottom_filename = filename.replace(".png", "_bottom.png")
                    cv2.imwrite(bottom_filename, bottom_region)
                    print(f"Region inferior guardada: {bottom_filename}")
                    
                    return img
                else:
                    print("Error: img es None despues de decodificar")
            except Exception as decode_error:
                print(f"Error en decodificacion: {decode_error}")
        else:
            print(f"Error: no se encontro imageData en respuesta")
            print(f"Response: {response}")
        
        ws.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("Captura simple desde OBS...")
    img = capture_obs_simple()
    
    if img is not None:
        print("Captura exitosa!")
    else:
        print("No se pudo capturar")
