"""
debug_visual.py - Generación de imágenes de debug con análisis visual de barras.
"""

import os
import cv2
import numpy as np
from datetime import datetime
from typing import Optional, Tuple

DEBUG_DIR = "debug"


class DebugVisual:
    """Genera imágenes de debug mostrando el análisis de barras HP/Mana."""

    def __init__(self, enabled: bool = True, save_dir: str = DEBUG_DIR):
        self.enabled = enabled
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)

    def generate_debug_image(
        self,
        img: np.ndarray,
        hp_pct: Optional[float],
        mp_pct: Optional[float],
        mask_hp: Optional[np.ndarray],
        mask_mp: Optional[np.ndarray],
        scan_height: int = 60,
        save: bool = True,
    ) -> Optional[np.ndarray]:
        """
        Genera una imagen de debug que muestra:
        1. La captura original con zona de análisis marcada
        2. Los valores detectados como texto
        3. Las máscaras de color como panel inferior

        Args:
            img: Imagen BGR original del proyector.
            hp_pct: Porcentaje de HP detectado (0.0-1.0) o None.
            mp_pct: Porcentaje de Mana detectado (0.0-1.0) o None.
            mask_hp: Máscara binaria de HP.
            mask_mp: Máscara binaria de Mana.
            scan_height: Altura de la región escaneada.
            save: Si True, guarda la imagen en disco.

        Returns:
            Imagen BGR de debug, o None si la entrada es inválida.
        """
        if not self.enabled or img is None or img.size == 0:
            return None

        debug = img.copy()
        h, w = debug.shape[:2]

        # Rectángulo amarillo marcando zona de análisis
        cv2.rectangle(debug, (0, 0), (w, scan_height), (0, 255, 255), 2)

        # Texto con valores detectados
        y_text = scan_height + 30

        # HP
        if hp_pct is not None:
            hp_color = (
                (0, 255, 0)
                if hp_pct > 0.60
                else (0, 200, 255)
                if hp_pct > 0.30
                else (0, 0, 255)
            )
            cv2.putText(
                debug,
                f"HP: {hp_pct * 100:.1f}%",
                (10, y_text),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                hp_color,
                2,
            )
        else:
            cv2.putText(
                debug,
                "HP: N/A",
                (10, y_text),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (128, 128, 128),
                2,
            )

        # Mana
        y_text += 30
        if mp_pct is not None:
            cv2.putText(
                debug,
                f"MP: {mp_pct * 100:.1f}%",
                (10, y_text),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 120, 0),
                2,
            )
        else:
            cv2.putText(
                debug,
                "MP: N/A",
                (10, y_text),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (128, 128, 128),
                2,
            )

        # Crear panel de máscaras debajo de la imagen principal
        if mask_hp is not None and mask_mp is not None:
            panel = self._create_mask_panel(mask_hp, mask_mp, w)
            debug = np.vstack([debug, panel])

        # Guardar
        if save:
            fname = os.path.join(
                self.save_dir,
                f"debug_{datetime.now().strftime('%H%M%S_%f')}.png",
            )
            cv2.imwrite(fname, debug)
            return debug

        return debug

    def generate_bar_zoom(
        self,
        region: np.ndarray,
        mask_hp: np.ndarray,
        mask_mp: np.ndarray,
        zoom: int = 4,
    ) -> Optional[np.ndarray]:
        """
        Genera un zoom de la región de barras con las máscaras superpuestas.

        Args:
            region: Región BGR de la franja de barras.
            mask_hp: Máscara HP.
            mask_mp: Máscara MP.
            zoom: Factor de zoom.

        Returns:
            Imagen BGR ampliada.
        """
        if region is None or region.size == 0:
            return None

        h, w = region.shape[:2]
        new_w, new_h = w * zoom, h * zoom

        # Imagen original ampliada
        zoomed = cv2.resize(region, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

        # Máscara HP en verde
        if mask_hp is not None:
            hp_zoomed = cv2.resize(
                mask_hp, (new_w, new_h), interpolation=cv2.INTER_NEAREST
            )
            overlay = np.zeros_like(zoomed)
            overlay[:, :, 1] = hp_zoomed  # canal verde
            zoomed = cv2.addWeighted(zoomed, 0.7, overlay, 0.3, 0)

        # Máscara MP en azul
        if mask_mp is not None:
            mp_zoomed = cv2.resize(
                mask_mp, (new_w, new_h), interpolation=cv2.INTER_NEAREST
            )
            overlay = np.zeros_like(zoomed)
            overlay[:, :, 0] = mp_zoomed  # canal azul
            zoomed = cv2.addWeighted(zoomed, 0.7, overlay, 0.3, 0)

        return zoomed

    def _create_mask_panel(
        self,
        mask_hp: np.ndarray,
        mask_mp: np.ndarray,
        target_width: int,
    ) -> np.ndarray:
        """Crea un panel visual con las máscaras HP y MP coloreadas."""
        mh, mw = mask_hp.shape[:2]

        # Crear imágenes coloreadas de las máscaras
        hp_colored = np.zeros((mh, mw, 3), dtype=np.uint8)
        hp_colored[:, :, 1] = mask_hp  # verde para HP

        mp_colored = np.zeros((mh, mw, 3), dtype=np.uint8)
        mp_colored[:, :, 0] = mask_mp  # azul para MP

        # Unir horizontalmente
        if mw * 2 <= target_width:
            panel = np.hstack([hp_colored, mp_colored])
        else:
            panel = np.vstack([hp_colored, mp_colored])

        # Ajustar al ancho target
        ph, pw = panel.shape[:2]
        if pw != target_width:
            scale = target_width / pw
            panel = cv2.resize(
                panel, (target_width, int(ph * scale)), interpolation=cv2.INTER_NEAREST
            )

        # Agregar etiquetas
        cv2.putText(
            panel, "HP Mask", (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
        )
        cv2.putText(
            panel,
            "MP Mask",
            (panel.shape[1] // 2 + 5, 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 100, 0),
            1,
        )

        return panel

    def cleanup_old_files(self, max_files: int = 200) -> int:
        """Limpia archivos de debug antiguos si hay demasiados."""
        try:
            files = sorted(
                [
                    os.path.join(self.save_dir, f)
                    for f in os.listdir(self.save_dir)
                    if f.endswith(".png")
                ],
                key=os.path.getmtime,
            )
            if len(files) <= max_files:
                return 0
            to_delete = files[: len(files) - max_files]
            for f in to_delete:
                os.remove(f)
            return len(to_delete)
        except Exception:
            return 0
