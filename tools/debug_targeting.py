# tools/debug_targeting.py - Diagnostico completo del targeting.
#
# Que hace:
#   1. Conecta a OBS y captura un frame
#   2. Corre el calibrador para detectar la battle region
#   3. Dibuja la battle region sobre el frame y la guarda
#   4. Prueba el template matching de cada nombre de monstruo con distintos umbrales
#   5. Guarda imagenes de debug con los resultados
#
# Uso:
#   python tools/debug_targeting.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import json
import time

# ── Cargar config ────────────────────────────────────────────────────────────
try:
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
except Exception as e:
    print(f"ERROR cargando config.json: {e}")
    cfg = {}

obs_ws = cfg.get("obs_websocket", {})
HOST     = obs_ws.get("host", "localhost")
PORT     = obs_ws.get("port", 4455)
PASSWORD = obs_ws.get("password", "")
SOURCE   = obs_ws.get("source_name", "")

print(f"Conectando a OBS {HOST}:{PORT} fuente='{SOURCE}'")

# ── Capturar frame ────────────────────────────────────────────────────────────
from screen_capture import ScreenCapture
cap = ScreenCapture()
if not cap.connect(host=HOST, port=PORT, password=PASSWORD, source_name=SOURCE):
    print(f"ERROR conectando a OBS: {cap.last_error}")
    print("  Asegúrate de que OBS esté abierto y el WebSocket esté activo.")
    sys.exit(1)

print("Capturando frame...")
frame = cap.capture_source()
if frame is None:
    print(f"ERROR capturando frame: {cap.last_error}")
    sys.exit(1)

fh, fw = frame.shape[:2]
print(f"Frame capturado: {fw}x{fh}")

# ── Calibrar ──────────────────────────────────────────────────────────────────
from screen_calibrator import ScreenCalibrator
cal = ScreenCalibrator()
logs = []
cal.set_log_callback(lambda m: logs.append(m))

ok = cal.calibrate(frame)
print(f"\n=== CALIBRACIÓN: {'OK' if ok else 'FALLIDA'} ===")
for l in logs:
    print(f"  {l}")

if not ok:
    print("\nCalibración fallida — guardando frame para inspección...")
    os.makedirs("debug", exist_ok=True)
    cv2.imwrite("debug/debug_targeting_raw.png", frame)
    print("  Guardado: debug/debug_targeting_raw.png")
    sys.exit(1)

print(f"\nBattle region: {cal.battle_region}")
print(f"Game region: {cal.game_region}")
print(f"Player center: {cal.player_center}")
print(f"SQMs: {len(cal.sqms)} posiciones")

# ── Dibujar battle region en el frame ─────────────────────────────────────────
debug_frame = frame.copy()
if cal.battle_region:
    x1, y1, x2, y2 = cal.battle_region
    cv2.rectangle(debug_frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
    cv2.putText(debug_frame, f"Battle ({x2-x1}x{y2-y1})",
                (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

if cal.game_region:
    gx1, gy1, gx2, gy2 = cal.game_region
    cv2.rectangle(debug_frame, (gx1, gy1), (gx2, gy2), (0, 255, 0), 2)

if cal.player_center:
    cv2.circle(debug_frame, cal.player_center, 8, (255, 255, 0), 2)

os.makedirs("debug", exist_ok=True)
cv2.imwrite("debug/debug_targeting_regions.png", debug_frame)
print(f"\nGuardado: debug/debug_targeting_regions.png")

# ── Template matching en la battle region ─────────────────────────────────────
NAMES_DIR = os.path.join("images", "Targets", "Names")
x1, y1, x2, y2 = cal.battle_region
roi = frame[max(0,y1):min(fh,y2), max(0,x1):min(fw,x2)]
roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

print(f"\n=== TEMPLATE MATCHING EN BATTLE REGION ({x2-x1}x{y2-y1}px) ===")
print(f"  ROI size: {roi.shape[1]}x{roi.shape[0]}")

# Guardar el ROI de la battle region
cv2.imwrite("debug/debug_battle_roi.png", roi)
print(f"  ROI guardado: debug/debug_battle_roi.png")

results = []
for fname in sorted(os.listdir(NAMES_DIR)):
    if not fname.endswith(".png"):
        continue
    tpl_path = os.path.join(NAMES_DIR, fname)
    tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        continue

    th, tw = tpl.shape[:2]
    if roi_gray.shape[0] < th or roi_gray.shape[1] < tw:
        print(f"  {fname}: SKIP (ROI {roi_gray.shape[1]}x{roi_gray.shape[0]} < template {tw}x{th})")
        continue

    res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    # Marcar posición en el ROI si la confianza es > 0.5
    status = ""
    if max_val >= 0.80:
        status = "✅ DETECTADO (>=0.80)"
    elif max_val >= 0.65:
        status = "⚠️  MARGINAL (>=0.65)"
    elif max_val >= 0.50:
        status = "❌ BAJA (>=0.50)"
    else:
        status = "❌ NO (< 0.50)"

    results.append((max_val, fname, max_loc, status))
    print(f"  {fname:30s}: conf={max_val:.4f}  {status}")

    # Guardar imagen del match si tiene confianza útil
    if max_val >= 0.50:
        match_img = roi.copy()
        mx, my = max_loc
        cv2.rectangle(match_img, (mx, my), (mx + tw, my + th), (0, 255, 0), 1)
        cv2.putText(match_img, f"{max_val:.3f}", (mx, my - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        safe = fname.replace(".png", "")
        cv2.imwrite(f"debug/debug_match_{safe}_{max_val:.3f}.png", match_img)

# ── Resumen ────────────────────────────────────────────────────────────────────
print("\n=== RESUMEN ===")
detected_080 = [r for r in results if r[0] >= 0.80]
detected_065 = [r for r in results if 0.65 <= r[0] < 0.80]

print(f"Detectados con umbral 0.80: {len(detected_080)}")
for v, n, loc, _ in detected_080:
    print(f"  {n}: {v:.4f} en ROI{loc}")

print(f"\nDetectados con umbral 0.65: {len(detected_065)}")
for v, n, loc, _ in detected_065:
    print(f"  {n}: {v:.4f} en ROI{loc}")

# ── Verificar si la battle region tiene el ancho correcto ────────────────────
print(f"\n=== ANÁLISIS DE BATTLE REGION ===")
bw = x2 - x1
bh = y2 - y1
max_tpl_w = max(
    cv2.imread(os.path.join(NAMES_DIR, f), cv2.IMREAD_GRAYSCALE).shape[1]
    for f in os.listdir(NAMES_DIR) if f.endswith(".png")
)
print(f"  Ancho de battle region: {bw}px")
print(f"  Template más ancho: {max_tpl_w}px")
if bw < max_tpl_w:
    print(f"  ⚠️ PROBLEMA: battle region ({bw}px) < template más ancho ({max_tpl_w}px)")
    print(f"     El template matching FALLARÁ para ese monstruo")
else:
    print(f"  ✅ Ancho OK")

print(f"  Alto de battle region: {bh}px (debe cubrir al menos 1 entrada ~14px)")

print("\nDiagnóstico completado. Revisa los archivos en debug/")
