"""
Herramienta para analizar el efecto/aura de los cuerpos de criaturas muertas
en la screenshot de Tibia, y crear un template para detección.

El aura es un efecto visual que aparece sobre TODOS los cuerpos de criaturas
muertas, independientemente de qué criatura sea. Es un destello/brillo
amarillo-blanco que se puede detectar por su patrón de color único.
"""

import cv2
import numpy as np
import os
import sys

# Buscar la screenshot más reciente del usuario
IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEBUG_DIR = os.path.join(IMAGES_DIR, "debug")


def analyze_screenshot(img_path: str):
    """Analiza una screenshot buscando el efecto aura."""
    img = cv2.imread(img_path)
    if img is None:
        print(f"No se pudo cargar: {img_path}")
        return

    print(f"Imagen: {img.shape[1]}x{img.shape[0]}")

    # Convertir a HSV para analizar colores
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # El aura de muerte en Tibia tiene colores característicos:
    # - Destello amarillo/dorado brillante
    # - Con tonos blancos en el centro
    # - Los blood splashes son rojos/verdes separados

    # === Método 1: Detección por brillo extremo en zona de juego ===
    # El aura es MUY brillante comparado con el terreno
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Zona del game window (aproximada de la screenshot)
    # Basado en calibración: game window está entre las barras de vida arriba y el hotbar abajo
    # Aprox: x=0-900 (hasta panel derecho), y=55-530 (bajo barras HP, sobre hotbar)
    gw_x1, gw_y1 = 0, 55
    gw_x2, gw_y2 = 900, 530
    game_roi = img[gw_y1:gw_y2, gw_x1:gw_x2]
    game_gray = gray[gw_y1:gw_y2, gw_x1:gw_x2]
    game_hsv = hsv[gw_y1:gw_y2, gw_x1:gw_x2]

    print(f"\nGame window ROI: ({gw_x1},{gw_y1}) to ({gw_x2},{gw_y2})")
    print(f"Game ROI shape: {game_roi.shape}")

    # === Analizar pixeles brillantes ===
    # El aura tiene saturación baja (es blanco/amarillo brillante) y alto brillo
    h, s, v = cv2.split(game_hsv)

    # Máscara de brillo alto (el aura es la zona más brillante del game window)
    # Excluir la barra de nombre del jugador (verde brillante)
    bright_mask = (v > 200) & (s < 100)  # Brillo alto, saturación baja = blanco/amarillo pálido
    bright_count = np.sum(bright_mask)
    print(f"\nPixeles brillantes (V>200, S<100): {bright_count}")

    # Otra opción: buscar amarillo brillante (el aura típica)
    # Amarillo en HSV: H=20-35, S=50-255, V>150
    yellow_mask = (h >= 15) & (h <= 40) & (s >= 30) & (v >= 150)
    yellow_count = np.sum(yellow_mask)
    print(f"Pixeles amarillo brillante: {yellow_count}")

    # Buscar CLUSTERS de pixeles brillantes (el aura es un grupo, no pixeles sueltos)
    # Combinar ambas máscaras
    aura_mask = np.uint8(bright_mask | yellow_mask) * 255

    # Dilatar para unir pixeles cercanos
    kernel = np.ones((5, 5), np.uint8)
    aura_dilated = cv2.dilate(aura_mask, kernel, iterations=2)

    # Encontrar contornos
    contours, _ = cv2.findContours(aura_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"\nContornos encontrados: {len(contours)}")

    # Filtrar contornos por tamaño (el aura es ~20-60px)
    aura_candidates = []
    for cnt in contours:
        x, y, w, h_c = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        if 100 < area < 5000 and 10 < w < 80 and 10 < h_c < 80:
            aura_candidates.append({
                "x": x + gw_x1, "y": y + gw_y1,
                "w": w, "h": h_c,
                "area": area,
                "center": (x + gw_x1 + w//2, y + gw_y1 + h_c//2),
            })
            print(f"  Candidato: pos=({x+gw_x1},{y+gw_y1}), size={w}x{h_c}, area={area}")

    print(f"\nCandidatos de aura: {len(aura_candidates)}")

    # === Visualizar resultados ===
    os.makedirs(DEBUG_DIR, exist_ok=True)

    # Dibujar candidatos en la imagen
    debug_img = img.copy()
    for i, cand in enumerate(aura_candidates):
        x, y, w, h_c = cand["x"], cand["y"], cand["w"], cand["h"]
        cv2.rectangle(debug_img, (x, y), (x+w, y+h_c), (0, 255, 0), 2)
        cv2.putText(debug_img, f"#{i} {cand['area']:.0f}",
                    (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    cv2.imwrite(os.path.join(DEBUG_DIR, "aura_candidates.png"), debug_img)
    print(f"\nImagen de debug guardada en: debug/aura_candidates.png")

    # Guardar la máscara del aura
    aura_vis = cv2.cvtColor(aura_mask, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(os.path.join(DEBUG_DIR, "aura_mask.png"), aura_vis)

    # === Recortar cada candidato como posible template ===
    for i, cand in enumerate(aura_candidates[:10]):  # Max 10
        x, y, w, h_c = cand["x"], cand["y"], cand["w"], cand["h"]
        # Expandir un poco para capturar contexto
        pad = 5
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img.shape[1], x + w + pad)
        y2 = min(img.shape[0], y + h_c + pad)
        crop = img[y1:y2, x1:x2]
        cv2.imwrite(os.path.join(DEBUG_DIR, f"aura_crop_{i}.png"), crop)

    # === Método 2: Analizar zonas específicas de los cuerpos visibles ===
    # Los 3 cuerpos en la screenshot están en estas zonas aproximadas
    # (estimado visualmente de la imagen adjunta):
    corpse_zones = [
        # Cuerpo 1: centro-izquierda (cerca del player)
        (530, 260, 610, 320),
        # Cuerpo 2: centro-derecha (sangre roja)
        (610, 250, 700, 320),
        # Cuerpo 3: abajo-centro
        (580, 350, 670, 430),
        # Cuerpo 4: abajo-derecha
        (610, 440, 680, 500),
    ]

    print("\n=== Análisis de zonas de cuerpos ===")
    for i, (zx1, zy1, zx2, zy2) in enumerate(corpse_zones):
        if zx2 > img.shape[1] or zy2 > img.shape[0]:
            continue
        zone = img[zy1:zy2, zx1:zx2]
        zone_hsv = hsv[zy1:zy2, zx1:zx2]
        zone_gray = gray[zy1:zy2, zx1:zx2]

        # Estadísticas de color
        mean_bgr = np.mean(zone, axis=(0, 1))
        mean_hsv_val = np.mean(zone_hsv, axis=(0, 1))
        max_bright = np.max(zone_gray)
        bright_pct = np.sum(zone_gray > 180) / zone_gray.size * 100

        print(f"\nZona cuerpo #{i}: ({zx1},{zy1})-({zx2},{zy2})")
        print(f"  BGR medio: B={mean_bgr[0]:.0f} G={mean_bgr[1]:.0f} R={mean_bgr[2]:.0f}")
        print(f"  HSV medio: H={mean_hsv_val[0]:.0f} S={mean_hsv_val[1]:.0f} V={mean_hsv_val[2]:.0f}")
        print(f"  Brillo máx: {max_bright}, % brillante (>180): {bright_pct:.1f}%")

        cv2.imwrite(os.path.join(DEBUG_DIR, f"corpse_zone_{i}.png"), zone)

    print("\n=== Análisis completo ===")
    print("Revisa las imágenes en debug/ para ver los resultados")


if __name__ == "__main__":
    # Buscar screenshots en el directorio debug o usar argumento
    if len(sys.argv) > 1:
        analyze_screenshot(sys.argv[1])
    else:
        # Buscar en debug/ la screenshot más reciente
        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug")
        if os.path.exists(debug_dir):
            pngs = [f for f in os.listdir(debug_dir) if f.endswith(".png") and "calib" in f.lower()]
            if pngs:
                latest = sorted(pngs)[-1]
                print(f"Usando: {latest}")
                analyze_screenshot(os.path.join(debug_dir, latest))
            else:
                print("No se encontraron screenshots de calibración en debug/")
                print("Usa: python analyze_corpse_aura.py <ruta_imagen>")
        else:
            print("No hay directorio debug/")
            print("Usa: python analyze_corpse_aura.py <ruta_imagen>")
