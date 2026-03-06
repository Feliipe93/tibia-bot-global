"""Analyze the corpse template image to understand its background."""
import cv2
import numpy as np

BASE = r"c:\Users\felip\Documents\GitHub\bot_ia_claude"
tpl = cv2.imread(f"{BASE}/corpse_loot/swamp_troll.png")
print(f"Shape: {tpl.shape}")

# Show color distribution
h, w = tpl.shape[:2]
print(f"\nTop row colors (first 10 pixels):")
for i in range(min(10, w)):
    print(f"  [{i}]: {tpl[0,i].tolist()}")

print(f"\nBottom row colors (first 10 pixels):")
for i in range(min(10, w)):
    print(f"  [{i}]: {tpl[h-1,i].tolist()}")

print(f"\nLeft column colors (first 10 pixels):")
for i in range(min(10, h)):
    print(f"  [{i}]: {tpl[i,0].tolist()}")

print(f"\nCenter region colors (28,28 area):")
cx, cy = w//2, h//2
for dy in range(-2, 3):
    row = []
    for dx in range(-2, 3):
        row.append(tpl[cy+dy, cx+dx].tolist())
    print(f"  row {cy+dy}: {row}")

# Unique colors count
reshaped = tpl.reshape(-1, 3)
unique = np.unique(reshaped, axis=0)
print(f"\nTotal unique colors: {len(unique)}")

# HSV analysis
hsv = cv2.cvtColor(tpl, cv2.COLOR_BGR2HSV)
print(f"\nHSV ranges:")
print(f"  H: {hsv[:,:,0].min()}-{hsv[:,:,0].max()}")
print(f"  S: {hsv[:,:,1].min()}-{hsv[:,:,1].max()}")
print(f"  V: {hsv[:,:,2].min()}-{hsv[:,:,2].max()}")

# Try to find the body vs background using edge detection
gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
edges = cv2.Canny(gray, 30, 100)
edge_pct = np.count_nonzero(edges) / edges.size * 100
print(f"\nEdge pixels: {np.count_nonzero(edges)} ({edge_pct:.1f}%)")

# Save edge-based visualization
cv2.imwrite(f"{BASE}/debug/corpse_edges.png", edges)

# Try GrabCut or simple threshold to separate body from bg
# The body should be the darkest/most contrasting part
# Let's try Otsu threshold
_, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
print(f"Otsu threshold: body pixels = {np.count_nonzero(otsu==0)}, bg = {np.count_nonzero(otsu==255)}")
cv2.imwrite(f"{BASE}/debug/corpse_otsu.png", otsu)

# Save the original template as a larger view
zoomed = cv2.resize(tpl, (w*4, h*4), interpolation=cv2.INTER_NEAREST)
cv2.imwrite(f"{BASE}/debug/corpse_template_zoomed.png", zoomed)
print("Saved zoomed template to debug/")

# Try creating mask with the most common border color
# Sample all border pixels
border_pixels = []
for i in range(w):
    border_pixels.append(tpl[0, i].tolist())
    border_pixels.append(tpl[h-1, i].tolist())
for i in range(1, h-1):
    border_pixels.append(tpl[i, 0].tolist())
    border_pixels.append(tpl[i, w-1].tolist())

border_arr = np.array(border_pixels)
print(f"\nBorder pixel stats:")
print(f"  Mean BGR: {border_arr.mean(axis=0).astype(int).tolist()}")
print(f"  Std BGR: {border_arr.std(axis=0).astype(int).tolist()}")

# The background is Tibia's game terrain - it's part of the template
# This means matching WITH the terrain might work if the terrain is similar
# BUT the issue is the terrain changes as the player moves

# Better approach: CROP the template to just the body sprite
# Find the bounding box of non-bg content using edge detection
contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if contours:
    all_pts = np.vstack(contours)
    x, y, cw, ch = cv2.boundingRect(all_pts)
    print(f"\nBody bounding box: x={x}, y={y}, w={cw}, h={ch}")
    body_crop = tpl[y:y+ch, x:x+cw]
    cv2.imwrite(f"{BASE}/debug/corpse_body_crop.png", body_crop)
    print(f"Body crop shape: {body_crop.shape}")
    
    # Create a proper mask from edges + fill
    mask_filled = np.zeros_like(gray)
    cv2.drawContours(mask_filled, contours, -1, 255, -1)
    # Dilate to catch edges
    kernel = np.ones((3,3), np.uint8)
    mask_filled = cv2.dilate(mask_filled, kernel, iterations=2)
    cv2.imwrite(f"{BASE}/debug/corpse_mask_filled.png", mask_filled)
    print(f"Filled mask: body pixels = {np.count_nonzero(mask_filled)}")
