"""Analiza la imagen del cadáver de swamp_troll para entender su estructura."""
import cv2
import numpy as np
import os

img = cv2.imread("corpse_loot/swamp_troll.png")
if img is None:
    print("No se pudo cargar la imagen")
    exit()

h, w = img.shape[:2]
print(f"=== swamp_troll.png ===")
print(f"Dimensiones: {w}x{h}")

# Analizar colores
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

print(f"\nHSV mean: H={hsv[:,:,0].mean():.1f} S={hsv[:,:,1].mean():.1f} V={hsv[:,:,2].mean():.1f}")
print(f"Gray mean: {gray.mean():.1f}, min: {gray.min()}, max: {gray.max()}")

# Esquinas (para ver si tiene fondo)
corners = [gray[0,0], gray[0,-1], gray[-1,0], gray[-1,-1]]
print(f"Esquinas (gray): {corners}")

# Guardar versión redimensionada a 32x32
resized = cv2.resize(img, (32, 32), interpolation=cv2.INTER_AREA)
os.makedirs("debug", exist_ok=True)
cv2.imwrite("debug/swamp_troll_32x32.png", resized)
print(f"\nGuardada versión 32x32 en debug/swamp_troll_32x32.png")

# También guardar una versión ampliada para ver detalle
big = cv2.resize(img, (w*4, h*4), interpolation=cv2.INTER_NEAREST)
cv2.imwrite("debug/swamp_troll_4x.png", big)
print(f"Guardada versión 4x en debug/swamp_troll_4x.png")
