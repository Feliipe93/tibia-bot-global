# tools/extract_name_templates.py
# Extrae templates de nombres de monstruos del battle list actual.
#
# COMO FUNCIONA:
#   1. Captura el frame de OBS
#   2. Calibra para encontrar la battle region
#   3. Detecta cada entrada del battle list (via separadores negros)
#   4. Para cada entrada extrae solo la zona del nombre (sin icono, sin barras)
#   5. Guarda en debug/extracted/ para revision
#   6. Pregunta al usuario el nombre de cada monstruo
#   7. Copia los archivos a images/Targets/Names/
#
# Uso:
#   python tools/extract_name_templates.py
#   Con Tibia abierto y monstruos en el Battle List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import json
import time
import shutil

# ── Config ───────────────────────────────────────────────────────────────────
with open("config.json", encoding="utf-8") as f:
    cfg = json.load(f)

obs_ws   = cfg.get("obs_websocket", {})
HOST     = obs_ws.get("host", "localhost")
PORT     = obs_ws.get("port", 4455)
PASSWORD = obs_ws.get("password", "")
SOURCE   = obs_ws.get("source_name", "")

NAMES_DIR  = os.path.join("images", "Targets", "Names")
BACKUP_DIR = os.path.join("images", "Targets", "Names_backup")
EXTRACT_DIR = os.path.join("debug", "extracted_names")
os.makedirs(EXTRACT_DIR, exist_ok=True)

print("=" * 60)
print("  EXTRACCION DE TEMPLATES DE NOMBRES")
print("=" * 60)
print()
print("Asegurate de tener Tibia con monstruos en el Battle List.")
print()

# ── Conectar y capturar ───────────────────────────────────────────────────────
from screen_capture import ScreenCapture
cap = ScreenCapture()
if not cap.connect(host=HOST, port=PORT, password=PASSWORD, source_name=SOURCE):
    print(f"ERROR conectando a OBS: {cap.last_error}")
    sys.exit(1)

print("Capturando frame...")
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
print(f"Battle region: ({x1},{y1}) -> ({x2},{y2})")

# ── Extraer ROI ───────────────────────────────────────────────────────────────
roi_color = frame[y1:min(fh,y2), x1:min(fw,x2)]
roi_gray  = cv2.cvtColor(roi_color, cv2.COLOR_BGR2GRAY)
roi_h, roi_w = roi_gray.shape[:2]
print(f"ROI: {roi_w}x{roi_h}px")

# ── Detectar entradas via separadores negros ──────────────────────────────────
row_means = roi_gray.mean(axis=1)
separators = [i for i, m in enumerate(row_means) if m < 20]

# Agrupar separadores contiguos
sep_groups = []
if separators:
    sg = [separators[0]]
    for s in separators[1:]:
        if s - sg[-1] <= 3:
            sg.append(s)
        else:
            sep_groups.append((sg[0], sg[-1]))
            sg = [s]
    sep_groups.append((sg[0], sg[-1]))

print(f"Separadores detectados: {len(sep_groups)}")

# Construir entradas a partir de separadores
# Estructura de una entrada: [icono+texto] | [sep] | [barras HP/MP] | [sep]
# Los pares de separadores delimitan las barras HP/MP
entries = []
# Colectar los rangos entre el inicio y el primer sep de cada "bloque"
prev_end = 0
i = 0
while i < len(sep_groups) - 1:
    sep1_start, sep1_end = sep_groups[i]
    sep2_start, sep2_end = sep_groups[i+1]

    # Zona de texto: desde prev_end hasta sep1_start
    text_y1 = prev_end
    text_y2 = sep1_start

    # Zona de barras: desde sep1_end+1 hasta sep2_start
    bars_y1 = sep1_end + 1
    bars_y2 = sep2_start

    # La siguiente entrada empieza en sep2_end+1
    prev_end = sep2_end + 1
    i += 2

    if text_y2 - text_y1 >= 4:
        entries.append({
            'text': (text_y1, text_y2),
            'bars': (bars_y1, bars_y2),
        })

print(f"Entradas detectadas: {len(entries)}")

if not entries:
    print()
    print("No se detectaron entradas. Posibles causas:")
    print("  1. No hay monstruos en el Battle List")
    print("  2. El battle list esta vacio o el personaje no esta en combate")
    print("  3. La separacion entre entradas tiene un formato diferente")
    print()
    print(f"Guardando el ROI para inspeccion: debug/battle_roi_full.png")
    cv2.imwrite("debug/battle_roi_full.png", roi_color)
    big = cv2.resize(roi_color, (roi_w*4, roi_h*4), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite("debug/battle_roi_full_x4.png", big)
    sys.exit(1)

# ── Extraer el nombre de cada entrada ────────────────────────────────────────
# El texto del nombre esta en las columnas x=18-150 (despues del icono de 16px)
# y en las filas de texto de la entrada

extracted = []
for j, e in enumerate(entries):
    ty1, ty2 = e['text']

    # La zona del nombre es despues del icono (~16px a la derecha del borde)
    # El borde del battle list es en x=0-1 (linea clara), luego el fondo,
    # luego el icono en x=2-17, luego el nombre en x=18+
    name_x1 = 18
    name_x2 = min(roi_w - 5, 150)

    crop_gray  = roi_gray[ty1:ty2, name_x1:name_x2]
    crop_color = roi_color[ty1:ty2, name_x1:name_x2]

    ch, cw = crop_gray.shape[:2]
    if cw < 5 or ch < 2:
        continue

    # Recortar el texto: encontrar donde empieza y termina el texto en X
    text_pixels = (crop_gray > 150).sum(axis=0)
    text_cols = np.where(text_pixels > 0)[0]

    if len(text_cols) < 3:
        print(f"  Entrada {j}: sin texto visible (max pixel={crop_gray.max()})")
        continue

    text_start = max(0, int(text_cols[0]))
    text_end   = min(cw, int(text_cols[-1]) + 1)

    final_crop  = crop_gray[:, text_start:text_end]
    final_color = crop_color[:, text_start:text_end]

    fch, fcw = final_crop.shape[:2]
    if fcw < 3:
        continue

    # Guardar para revision
    fname = f"entry_{j:02d}_y{ty1}-{ty2}_w{fcw}.png"
    cv2.imwrite(os.path.join(EXTRACT_DIR, fname), final_crop)

    # Version x5 en color para ver bien
    big_color = cv2.resize(final_color, (fcw*5, fch*5), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(os.path.join(EXTRACT_DIR, f"BIG_{fname}"), big_color)

    extracted.append({
        'index': j,
        'fname': fname,
        'path': os.path.join(EXTRACT_DIR, fname),
        'size': (fcw, fch),
        'y': (ty1, ty2),
    })

    print(f"  Entrada {j}: y={ty1}-{ty2} -> {fcw}x{fch}px  [{fname}]")

print(f"\nExtraccion completada: {len(extracted)} entradas en: {EXTRACT_DIR}/")
print(f"Abre los archivos BIG_entry_*.png para ver los nombres.")
print()

if not extracted:
    print("No se extrajeron entradas. Verifica las imagenes en el directorio debug/.")
    sys.exit(1)

# ── Pedir nombre al usuario para cada entrada ─────────────────────────────────
print("=" * 60)
print("  ASIGNACION DE NOMBRES")
print("=" * 60)
print()
print("Para cada entrada, escribe el nombre del monstruo (CamelCase).")
print("Ejemplos: Rat, CaveRat, Rotworm, Dog, Cyclops")
print("Escribe 'skip' o presiona Enter para omitir.")
print()

os.makedirs(BACKUP_DIR, exist_ok=True)

# Backup de templates existentes (una vez)
backup_done = False
new_templates = []

for e in extracted:
    name = input(f"  Entrada {e['index']} ({e['size'][0]}x{e['size'][1]}px) -> nombre: ").strip()
    if not name or name.lower() == 'skip':
        print(f"  Omitida.")
        continue

    # Normalizar: quitar espacios
    fname_out = name.replace(" ", "") + ".png"
    dst = os.path.join(NAMES_DIR, fname_out)

    # Backup si existe
    if not backup_done:
        count_bk = 0
        for f in os.listdir(NAMES_DIR):
            if f.endswith(".png"):
                shutil.copy2(os.path.join(NAMES_DIR, f), os.path.join(BACKUP_DIR, f))
                count_bk += 1
        if count_bk > 0:
            print(f"  Backup: {count_bk} templates copiados a {BACKUP_DIR}/")
        backup_done = True

    shutil.copy2(e['path'], dst)
    new_templates.append(fname_out)
    print(f"  Guardado: {dst} ({e['size'][0]}x{e['size'][1]}px)")

print()
if new_templates:
    print(f"Templates guardados ({len(new_templates)}):")
    for t in new_templates:
        print(f"  {t}")
    print()
    print("Reinicia el bot para que use los nuevos templates.")
else:
    print("No se guardaron templates. Puedes copiar manualmente los archivos de:")
    print(f"  {EXTRACT_DIR}/")
    print(f"a: {NAMES_DIR}/")
