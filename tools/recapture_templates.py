# tools/recapture_templates.py
# Auto-captura templates de nombres de monstruos desde el frame actual de OBS.
#
# MODO AUTOMATICO:
#   Analiza la battle region, detecta filas de texto y extrae cada nombre.
#   Guarda como PNG en images/Targets/Names/
#
# Uso:
#   python tools/recapture_templates.py
#
# Requiere que haya monstruos en el battle list de Tibia en ese momento.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import json
import time

# ── Config ───────────────────────────────────────────────────────────────────
with open("config.json", encoding="utf-8") as f:
    cfg = json.load(f)

obs_ws = cfg.get("obs_websocket", {})
HOST     = obs_ws.get("host", "localhost")
PORT     = obs_ws.get("port", 4455)
PASSWORD = obs_ws.get("password", "")
SOURCE   = obs_ws.get("source_name", "")

NAMES_DIR = os.path.join("images", "Targets", "Names")
BACKUP_DIR = os.path.join("images", "Targets", "Names_backup")
DEBUG_DIR  = "debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

print("=" * 60)
print("  RECAPTURA DE TEMPLATES DE NOMBRES")
print("=" * 60)
print()
print("INSTRUCCIONES:")
print("  1. Ten Tibia abierto con monstruos en el Battle List")
print("  2. Este script captura el frame y extrae las entradas")
print("  3. Verifica los PNGs generados antes de usarlos")
print()

# ── Conectar y capturar ───────────────────────────────────────────────────────
from screen_capture import ScreenCapture
cap = ScreenCapture()
if not cap.connect(host=HOST, port=PORT, password=PASSWORD, source_name=SOURCE):
    print(f"ERROR conectando a OBS: {cap.last_error}")
    sys.exit(1)

print("Capturando frame... (asegurate de tener monstruos en el Battle List)")
time.sleep(0.5)
frame = cap.capture_source()
if frame is None:
    print(f"ERROR: {cap.last_error}")
    sys.exit(1)

fh, fw = frame.shape[:2]
print(f"Frame: {fw}x{fh}")

# ── Calibrar ─────────────────────────────────────────────────────────────────
from screen_calibrator import ScreenCalibrator
cal = ScreenCalibrator()
if not cal.calibrate(frame):
    print("ERROR: Calibracion fallida")
    sys.exit(1)

x1, y1, x2, y2 = cal.battle_region
print(f"Battle region: ({x1},{y1}) -> ({x2},{y2})  ({x2-x1}x{y2-y1}px)")

# ── Extraer ROI ───────────────────────────────────────────────────────────────
roi_color = frame[y1:min(fh,y2), x1:min(fw,x2)]
roi_gray  = cv2.cvtColor(roi_color, cv2.COLOR_BGR2GRAY)
roi_h, roi_w = roi_gray.shape[:2]

print(f"ROI real: {roi_w}x{roi_h}px")

# Guardar ROI completo
cv2.imwrite(os.path.join(DEBUG_DIR, "recapture_roi_full.png"), roi_color)
big = cv2.resize(roi_color, (roi_w*3, roi_h*3), interpolation=cv2.INTER_NEAREST)
cv2.imwrite(os.path.join(DEBUG_DIR, "recapture_roi_x3.png"), big)
print(f"Guardado: debug/recapture_roi_full.png y debug/recapture_roi_x3.png")

# ── Detectar filas de texto (segmentacion horizontal) ────────────────────────
# En Tibia, cada entrada de battle list tiene ~14px de alto
# El texto en la columna de nombres es claro sobre fondo oscuro

# Buscar filas con texto: umbralizar y buscar bloques horizontales
_, binary = cv2.threshold(roi_gray, 100, 255, cv2.THRESH_BINARY)

# Suma horizontal: si una fila tiene muchos pixels blancos → tiene texto
row_sum = binary.sum(axis=1) / 255  # pixels blancos por fila

print(f"\nAnalizando filas de texto...")
print(f"  Rango de sumas: {row_sum.min():.0f} - {row_sum.max():.0f}")

# Detectar grupos de filas con texto (bloques)
TEXT_THRESHOLD = max(5, roi_w * 0.03)  # Al menos 3% del ancho con pixels blancos

in_text_block = False
blocks = []  # list of (y_start, y_end)
block_start = 0

for i, val in enumerate(row_sum):
    if not in_text_block and val >= TEXT_THRESHOLD:
        in_text_block = True
        block_start = i
    elif in_text_block and val < TEXT_THRESHOLD:
        in_text_block = False
        if i - block_start >= 3:  # minimo 3px de alto para ser valido
            blocks.append((block_start, i))

if in_text_block:
    blocks.append((block_start, len(row_sum)))

print(f"  Bloques de texto detectados: {len(blocks)}")
for bs, be in blocks:
    print(f"    y={bs}-{be} ({be-bs}px)")

# ── Agrupar bloques cercanos en entradas (~14px) ──────────────────────────────
# Juntar bloques que estén a menos de 4px uno del otro
merged = []
if blocks:
    cs, ce = blocks[0]
    for bs, be in blocks[1:]:
        if bs - ce <= 5:
            ce = max(ce, be)
        else:
            merged.append((cs, ce))
            cs, ce = bs, be
    merged.append((cs, ce))

print(f"\n  Bloques unificados: {len(merged)}")

# ── Guardar cada entrada como imagen ─────────────────────────────────────────
ENTRY_DIR = os.path.join(DEBUG_DIR, "recapture_entries")
os.makedirs(ENTRY_DIR, exist_ok=True)

print(f"\n  Entradas guardadas en: {ENTRY_DIR}/")
entry_images = []
for i, (ys, ye) in enumerate(merged):
    # Agregar 1px de padding vertical
    ys2 = max(0, ys - 1)
    ye2 = min(roi_h, ye + 2)
    entry_gray   = roi_gray[ys2:ye2, :]
    entry_color  = roi_color[ys2:ye2, :]

    # Recortar el nombre: columna de nombre empieza ~después del icono de criatura
    # En Tibia, el icono de criatura está a la izquierda, el nombre empieza en ~x=16
    # Intentar detectar donde empieza el texto horizontalmente
    _, entry_bin = cv2.threshold(entry_gray, 100, 255, cv2.THRESH_BINARY)
    col_sum = entry_bin.sum(axis=0) / 255
    text_cols = np.where(col_sum >= 1)[0]

    if len(text_cols) == 0:
        print(f"  Entrada {i}: no hay texto detectable")
        continue

    x_start = max(0, int(text_cols[0]) - 1)
    x_end   = min(roi_w, int(text_cols[-1]) + 2)

    name_crop_gray  = entry_gray[:, x_start:x_end]
    name_crop_color = entry_color[:, x_start:x_end]

    h_crop, w_crop = name_crop_gray.shape[:2]
    if w_crop < 5 or h_crop < 3:
        print(f"  Entrada {i}: muy pequeña ({w_crop}x{h_crop}), skip")
        continue

    fname = f"entry_{i:02d}_y{ys}-{ye}_x{x_start}-{x_end}.png"
    cv2.imwrite(os.path.join(ENTRY_DIR, fname), name_crop_gray)

    # Version x4 para ver mejor
    big_e = cv2.resize(name_crop_color, (w_crop*4, h_crop*4), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(os.path.join(ENTRY_DIR, f"BIG_{fname}"), big_e)

    entry_images.append({
        "index": i,
        "y": (ys, ye),
        "x": (x_start, x_end),
        "size": (w_crop, h_crop),
        "file": fname,
        "gray_path": os.path.join(ENTRY_DIR, fname),
    })
    print(f"  Entrada {i}: y={ys}-{ye} x={x_start}-{x_end} -> {w_crop}x{h_crop}px [{fname}]")

# ── Visualizacion final ───────────────────────────────────────────────────────
# Dibujar las entradas detectadas sobre el ROI
viz = roi_color.copy()
for i, (ys, ye) in enumerate(merged):
    cv2.rectangle(viz, (0, ys), (roi_w-1, ye), (0, 255, 0), 1)
    cv2.putText(viz, str(i), (2, ys + (ye-ys)//2), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0,255,0), 1)

cv2.imwrite(os.path.join(DEBUG_DIR, "recapture_detected.png"), viz)
big_viz = cv2.resize(viz, (roi_w*3, roi_h*3), interpolation=cv2.INTER_NEAREST)
cv2.imwrite(os.path.join(DEBUG_DIR, "recapture_detected_x3.png"), big_viz)

print(f"\nGuardado: debug/recapture_detected_x3.png (con entradas marcadas)")

# ── Instrucciones finales ────────────────────────────────────────────────────
print()
print("=" * 60)
print("  SIGUIENTE PASO:")
print("=" * 60)
print()
print(f"  1. Abre las imagenes en: {ENTRY_DIR}/")
print(f"     Los archivos BIG_entry_*.png son versiones ampliadas x4")
print()
print(f"  2. Para cada entrada que sea un nombre de monstruo,")
print(f"     renombra el archivo entry_XX.png a:")
print(f"     NombreMonstruo.png  (sin espacios, CamelCase)")
print(f"     Ejemplos: Rat.png, CaveRat.png, Rotworm.png")
print()
print(f"  3. Copia/mueve esos PNGs a: {NAMES_DIR}/")
print(f"     (los originales quedan en Names_backup/)")
print()
print(f"  O usa el script interactivo (ver instrucciones al inicio)")

# ── Backup de templates existentes ───────────────────────────────────────────
print()
response = input("Hacer backup de los templates actuales y copiar los nuevos? [s/N]: ").strip().lower()
if response == 's':
    import shutil
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Backup
    count_backup = 0
    for f in os.listdir(NAMES_DIR):
        if f.endswith(".png"):
            shutil.copy2(os.path.join(NAMES_DIR, f), os.path.join(BACKUP_DIR, f))
            count_backup += 1
    print(f"  Backup de {count_backup} templates en: {BACKUP_DIR}/")

    # Preguntar qué entradas copiar
    print()
    print("  Entradas disponibles:")
    for e in entry_images:
        print(f"    [{e['index']}] {e['file']} ({e['size'][0]}x{e['size'][1]}px)")

    print()
    print("  Para cada entrada, escribe el nombre del monstruo (Enter para skip):")
    for e in entry_images:
        # Mostrar la imagen (si hay display)
        try:
            entry_big = cv2.imread(os.path.join(ENTRY_DIR, f"BIG_{e['file']}"))
            cv2.imshow(f"Entrada {e['index']}", entry_big)
            cv2.waitKey(100)
        except Exception:
            pass

        name = input(f"    Entrada {e['index']} -> nombre (Enter para skip): ").strip()
        if name:
            # Normalizar: quitar espacios para el filename
            fname_dest = name.replace(" ", "") + ".png"
            src = e["gray_path"]
            dst = os.path.join(NAMES_DIR, fname_dest)
            import shutil
            shutil.copy2(src, dst)
            print(f"    ✅ Copiado: {fname_dest} ({e['size'][0]}x{e['size'][1]}px)")

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

    print()
    print("  Templates actualizados!")
else:
    print()
    print(f"  No se realizaron cambios.")
    print(f"  Revisa las entradas en: {ENTRY_DIR}/")
    print(f"  y copia manualmente las que necesites a: {NAMES_DIR}/")
