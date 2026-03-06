"""Test corpse template matching approaches against real debug frames."""
import cv2
import numpy as np
import os
import glob

BASE = r"c:\Users\felip\Documents\GitHub\bot_ia_claude"
TPL_PATH = os.path.join(BASE, "corpse_loot", "swamp_troll.png")
DEBUG_DIR = os.path.join(BASE, "debug")
GAME_REGION = (1, 2, 1183, 503)

tpl_bgr = cv2.imread(TPL_PATH)
print(f"Template shape: {tpl_bgr.shape}")

# Analyze the template background color
corners = [tpl_bgr[0,0], tpl_bgr[0,-1], tpl_bgr[-1,0], tpl_bgr[-1,-1]]
print(f"Corner pixels (BGR): {[c.tolist() for c in corners]}")
bg_color = corners[0]
print(f"Background color (BGR): {bg_color.tolist()}")

# === Method 1: Create alpha mask from background color ===
# Find pixels that are NOT the background and create a mask
tolerance = 15
diff = np.abs(tpl_bgr.astype(int) - bg_color.astype(int))
max_diff = np.max(diff, axis=2)
mask = (max_diff > tolerance).astype(np.uint8) * 255
print(f"\nMask: non-bg pixels = {np.count_nonzero(mask)}, total = {mask.size}")
print(f"Mask coverage: {np.count_nonzero(mask)/mask.size*100:.1f}%")

# Save mask for inspection
cv2.imwrite(os.path.join(BASE, "debug", "corpse_mask.png"), mask)
print("Saved corpse_mask.png to debug/")

# Get debug frames
frames = sorted(glob.glob(os.path.join(DEBUG_DIR, "debug_12*.png")))
if not frames:
    frames = sorted(glob.glob(os.path.join(DEBUG_DIR, "debug_*.png")))
print(f"\nFound {len(frames)} debug frames")

gx1, gy1, gx2, gy2 = GAME_REGION

for fpath in frames[-5:]:
    fname = os.path.basename(fpath)
    frame = cv2.imread(fpath)
    if frame is None:
        continue
    
    game_roi = frame[gy1:gy2, gx1:gx2]
    roi_gray = cv2.cvtColor(game_roi, cv2.COLOR_BGR2GRAY)
    tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
    
    print(f"\n--- {fname} ---")
    
    # Method A: Normal grayscale TM_CCOEFF_NORMED (current approach)
    result_a = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
    _, max_a, _, loc_a = cv2.minMaxLoc(result_a)
    print(f"  A) Grayscale CCOEFF_NORMED: max={max_a:.4f} at ({loc_a[0]+gx1},{loc_a[1]+gy1})")
    
    # Method B: Color TM_CCOEFF_NORMED (BGR)
    result_b = cv2.matchTemplate(game_roi, tpl_bgr, cv2.TM_CCOEFF_NORMED)
    _, max_b, _, loc_b = cv2.minMaxLoc(result_b)
    print(f"  B) Color CCOEFF_NORMED:     max={max_b:.4f} at ({loc_b[0]+gx1},{loc_b[1]+gy1})")
    
    # Method C: TM_CCOEFF_NORMED with mask (ignore background pixels)
    result_c = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_CCOEFF_NORMED, mask=mask)
    _, max_c, _, loc_c = cv2.minMaxLoc(result_c)
    print(f"  C) Grayscale + MASK:        max={max_c:.4f} at ({loc_c[0]+gx1},{loc_c[1]+gy1})")
    
    # Method D: TM_CCORR_NORMED with mask
    result_d = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_CCORR_NORMED, mask=mask)
    _, max_d, _, loc_d = cv2.minMaxLoc(result_d)
    print(f"  D) Grayscale CCORR + MASK:  max={max_d:.4f} at ({loc_d[0]+gx1},{loc_d[1]+gy1})")
    
    # Method E: TM_SQDIFF_NORMED with mask (lower = better)
    result_e = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_SQDIFF_NORMED, mask=mask)
    min_e, _, loc_e_min, _ = cv2.minMaxLoc(result_e)
    print(f"  E) Grayscale SQDIFF + MASK: min={min_e:.4f} at ({loc_e_min[0]+gx1},{loc_e_min[1]+gy1})")
    
    # Method F: Multi-scale template (try 90%, 100%, 110%)
    best_f = 0
    best_f_loc = (0,0)
    best_f_scale = 1.0
    for scale in [0.85, 0.9, 0.95, 1.0, 1.05, 1.1]:
        h, w = tpl_gray.shape
        new_w = int(w * scale)
        new_h = int(h * scale)
        if new_w < 10 or new_h < 10:
            continue
        scaled_tpl = cv2.resize(tpl_gray, (new_w, new_h))
        scaled_mask = cv2.resize(mask, (new_w, new_h))
        if scaled_tpl.shape[0] > roi_gray.shape[0] or scaled_tpl.shape[1] > roi_gray.shape[1]:
            continue
        res = cv2.matchTemplate(roi_gray, scaled_tpl, cv2.TM_CCOEFF_NORMED, mask=scaled_mask)
        _, mx, _, mloc = cv2.minMaxLoc(res)
        if mx > best_f:
            best_f = mx
            best_f_loc = mloc
            best_f_scale = scale
    print(f"  F) Multi-scale + MASK:      max={best_f:.4f} scale={best_f_scale:.2f} at ({best_f_loc[0]+gx1},{best_f_loc[1]+gy1})")

    # Show threshold counts for best method (C)
    for t in [0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]:
        locs = np.where(result_c >= t)
        if len(locs[0]) > 0:
            print(f"     C@{t}: {len(locs[0])} matches")
