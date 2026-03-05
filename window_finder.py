"""
window_finder.py - Detección de ventanas de Tibia y Proyector OBS.
Usa win32gui.EnumWindows para buscar ventanas por título parcial.
"""

import win32gui
import win32con
from typing import Dict, List, Optional


def find_tibia_windows() -> List[Dict]:
    """
    Busca todas las ventanas visibles que contengan 'tibia' en el título.
    La ventana de Tibia se llama 'Tibia - NombreDelPersonaje'.

    Retorna una lista de diccionarios con info de cada ventana encontrada.
    """
    results = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if "tibia" in title.lower():
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            w = x2 - x
            h = y2 - y
            # Filtrar ventanas muy pequeñas (splash screens, tooltips)
            if w > 300 and h > 200:
                results.append({
                    "hwnd": hwnd,
                    "title": title,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                })

    win32gui.EnumWindows(callback, None)
    return results


def find_obs_projectors() -> List[Dict]:
    """
    Busca ventanas del Proyector de OBS (fuente de captura de juego).
    Soporta OBS en español e inglés.

    Retorna una lista de todos los proyectores encontrados.
    """
    results = []
    keywords = [
        "proyector - fuente",       # OBS en español
        "projector - source",       # OBS en inglés
        "proyector de fuente",      # variante español
        "source projector",         # variante inglés
    ]

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        title_lower = title.lower()
        if any(k in title_lower for k in keywords):
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            w = x2 - x
            h = y2 - y
            if w > 200 and h > 200:
                # Prioridad: proyectores de "fuente"/"source" sobre vista previa
                is_source = any(
                    k in title_lower
                    for k in ["fuente", "source"]
                )
                results.append({
                    "hwnd": hwnd,
                    "title": title,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "is_source": is_source,
                })

    win32gui.EnumWindows(callback, None)

    # Ordenar: preferir proyectores de fuente
    results.sort(key=lambda r: (not r["is_source"], r["title"]))
    return results


def find_best_obs_projector() -> Optional[Dict]:
    """
    Retorna el mejor proyector OBS disponible.
    Prefiere 'Fuente'/'Source' sobre 'Vista Previa'/'Preview'.
    """
    projectors = find_obs_projectors()
    if not projectors:
        return None
    # Preferir fuente sobre vista previa
    for p in projectors:
        if p.get("is_source"):
            return p
    return projectors[0]


def is_window_valid(hwnd: int) -> bool:
    """Verifica si un handle de ventana sigue siendo válido y visible."""
    try:
        return bool(win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd))
    except Exception:
        return False


def get_window_rect(hwnd: int) -> Optional[Dict]:
    """Obtiene la posición y tamaño actual de una ventana."""
    try:
        if not win32gui.IsWindow(hwnd):
            return None
        rect = win32gui.GetWindowRect(hwnd)
        x, y, x2, y2 = rect
        return {
            "x": x,
            "y": y,
            "width": x2 - x,
            "height": y2 - y,
        }
    except Exception:
        return None


def get_window_title(hwnd: int) -> str:
    """Obtiene el título actual de una ventana."""
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return ""


def is_window_minimized(hwnd: int) -> bool:
    """Verifica si una ventana está minimizada."""
    try:
        return bool(win32gui.IsIconic(hwnd))
    except Exception:
        return True
