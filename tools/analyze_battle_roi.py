# tools/analyze_battle_roi.py
# Analiza la battle region capturada y exporta una imagen compuesta anotada
# para entender la estructura real del battle list.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

roi = cv2.imread('debug/debug_battle_roi.png')
if roi is None:
    print("ERROR: No se encontro debug/debug_battle_roi.png")
    print("Ejecuta primero: python tools/debug_targeting.py")
    sys.exit(1)

gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
h, w = gray.shape
print(f"ROI: {w}x{h}px")

# --- Comparar cada template con la ROI ---
NAMES_DIR = os.path.join("images", "Targets", "Names")

print("\n=== COMPARACION DIRECTA template vs ROI ===")
print("Buscando la mejor posicion para cada template...")

for fname in sorted(os.listdir(NAMES_DIR)):
    if not fname.endswith(".png"):
        continue
    tpl = cv2.imread(os.path.join(NAMES_DIR, fname), cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        continue
    th, tw = tpl.shape[:2]
    if gray.shape[0] < th or gray.shape[1] < tw:
        print(f"  {fname}: skip (ROI menor que template)")
        continue

    res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, best_val, _, best_loc = cv2.minMaxLoc(res)

    # Extraer parche del ROI donde mejor coincide
    bx, by = best_loc
    patch = roi[by:by+th, bx:bx+tw].copy()

    # Crear imagen comparativa side-by-side
    tpl_color = cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR)

    # Ajustar alturas al mismo tamaño para apilar
    max_h = max(th, th)
    cmp_h = max_h + 4
    comparison = np.zeros((cmp_h, tw*2 + 6, 3), dtype=np.uint8)
    # Template a la izquierda
    comparison[2:2+th, 0:tw] = tpl_color
    # Parche del ROI a la derecha
    comparison[2:2+th, tw+6:tw+6+tw] = patch if patch.shape[1] == tw else patch[:,:min(tw,patch.shape[1])]
    # Linea separadora
    comparison[:, tw+2:tw+4] = (100, 100, 100)

    # Ampliar x4 para ver
    cmp_big = cv2.resize(comparison, (comparison.shape[1]*4, comparison.shape[0]*4),
                         interpolation=cv2.INTER_NEAREST)

    safe = fname.replace(".png", "")
    out_path = f"debug/cmp_{safe}_{best_val:.3f}.png"
    cv2.imwrite(out_path, cmp_big)
    print(f"  {fname:30s}: conf={best_val:.4f}  guardado: {out_path}")

print("\nListo. Las imagenes 'cmp_*.png' muestran:")
print("  IZQUIERDA: template original")
print("  DERECHA: mejor coincidencia en el ROI actual")
print()
print("Si el template se ve MUY diferente al parche del ROI,")
print("los templates necesitan ser recapturados.")
