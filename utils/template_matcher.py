"""
utils/template_matcher.py - Template matching con OpenCV.
Busca templates (imágenes pequeñas) dentro de frames capturados.
Usado para: encontrar posición en minimapa, detectar iconos, battle list, etc.
"""

import cv2
import numpy as np
import os
from typing import Dict, List, Optional, Tuple


class TemplateMatcher:
    """Busca templates dentro de imágenes usando cv2.matchTemplate."""

    def __init__(self, templates_dir: str = "assets"):
        self.templates_dir = templates_dir
        self._cache: Dict[str, np.ndarray] = {}

    def load_template(self, name: str, path: str) -> bool:
        """
        Carga un template desde archivo y lo guarda en caché.

        Args:
            name: Nombre identificador del template.
            path: Ruta al archivo de imagen.

        Returns:
            True si se cargó correctamente.
        """
        full_path = os.path.join(self.templates_dir, path) if not os.path.isabs(path) else path
        if not os.path.exists(full_path):
            return False
        img = cv2.imread(full_path, cv2.IMREAD_COLOR)
        if img is None:
            return False
        self._cache[name] = img
        return True

    def set_template(self, name: str, img: np.ndarray) -> None:
        """Registra un template desde un numpy array ya cargado."""
        self._cache[name] = img

    def find(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: float = 0.8,
        method: int = cv2.TM_CCOEFF_NORMED,
        grayscale: bool = True,
    ) -> Optional[Tuple[int, int, float]]:
        """
        Busca un template en el frame y retorna la mejor coincidencia.

        Args:
            frame: Imagen BGR donde buscar.
            template_name: Nombre del template (previamente cargado).
            threshold: Confianza mínima (0.0 - 1.0).
            method: Método de matching de OpenCV.
            grayscale: Convertir a escala de grises antes de comparar.

        Returns:
            (x, y, confidence) del centro de la mejor coincidencia, o None.
        """
        template = self._cache.get(template_name)
        if template is None:
            return None

        if grayscale:
            frame_g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            templ_g = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            frame_g = frame
            templ_g = template

        if (
            frame_g.shape[0] < templ_g.shape[0]
            or frame_g.shape[1] < templ_g.shape[1]
        ):
            return None

        result = cv2.matchTemplate(frame_g, templ_g, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            th, tw = templ_g.shape[:2]
            cx = max_loc[0] + tw // 2
            cy = max_loc[1] + th // 2
            return cx, cy, float(max_val)

        return None

    def find_all(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: float = 0.8,
        method: int = cv2.TM_CCOEFF_NORMED,
        grayscale: bool = True,
        min_distance: int = 10,
    ) -> List[Tuple[int, int, float]]:
        """
        Busca TODAS las coincidencias de un template en el frame.

        Returns:
            Lista de (x, y, confidence) para cada coincidencia.
        """
        template = self._cache.get(template_name)
        if template is None:
            return []

        if grayscale:
            frame_g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            templ_g = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            frame_g = frame
            templ_g = template

        if (
            frame_g.shape[0] < templ_g.shape[0]
            or frame_g.shape[1] < templ_g.shape[1]
        ):
            return []

        result = cv2.matchTemplate(frame_g, templ_g, method)
        th, tw = templ_g.shape[:2]

        locations = np.where(result >= threshold)
        matches: List[Tuple[int, int, float]] = []

        for pt_y, pt_x in zip(*locations):
            cx = int(pt_x) + tw // 2
            cy = int(pt_y) + th // 2
            conf = float(result[pt_y, pt_x])

            # Filtrar duplicados cercanos
            too_close = False
            for mx, my, _ in matches:
                if abs(cx - mx) < min_distance and abs(cy - my) < min_distance:
                    too_close = True
                    break
            if not too_close:
                matches.append((cx, cy, conf))

        # Ordenar por confianza descendente
        matches.sort(key=lambda m: m[2], reverse=True)
        return matches

    def find_in_region(
        self,
        frame: np.ndarray,
        template_name: str,
        region: Tuple[int, int, int, int],
        threshold: float = 0.8,
    ) -> Optional[Tuple[int, int, float]]:
        """
        Busca un template solo dentro de una región específica del frame.

        Args:
            region: (x, y, width, height) de la región a buscar.

        Returns:
            (x, y, confidence) en coordenadas del frame completo, o None.
        """
        rx, ry, rw, rh = region
        sub_frame = frame[ry:ry + rh, rx:rx + rw]
        result = self.find(sub_frame, template_name, threshold)
        if result is not None:
            return (result[0] + rx, result[1] + ry, result[2])
        return None

    @property
    def loaded_templates(self) -> List[str]:
        """Lista de nombres de templates cargados."""
        return list(self._cache.keys())

    def clear_cache(self) -> None:
        """Limpia todos los templates cargados."""
        self._cache.clear()
