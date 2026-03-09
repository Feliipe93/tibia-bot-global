"""
screen_capture.py - Captura de pantalla vía OBS WebSocket.
Usa GetSourceScreenshot para obtener frames directamente de la memoria
de OBS, sin depender de que el proyector sea visible en pantalla.
Esto resuelve el problema de que mss captura lo visible en el monitor
y falla cuando Tibia está en primer plano tapando el proyector.
"""

import base64
import threading
import numpy as np
import cv2
from typing import Optional

import obsws_python as obs


class ScreenCapture:
    """
    Captura screenshots de OBS via WebSocket (GetSourceScreenshot).
    Funciona incluso con OBS minimizado o detrás de otras ventanas.
    """

    def __init__(self):
        self._client: Optional[obs.ReqClient] = None
        self._lock = threading.Lock()
        self._last_brightness: float = 0.0
        self._connected: bool = False
        self._last_error: str = ""
        self._source_name: str = ""

        # Parámetros de conexión
        self._host: str = "localhost"
        self._port: int = 4455
        self._password: str = ""

    # ==================================================================
    # Conexión OBS WebSocket
    # ==================================================================
    def connect(
        self,
        host: str = "localhost",
        port: int = 4455,
        password: str = "",
        source_name: str = "",
    ) -> bool:
        """
        Conecta al servidor OBS WebSocket.

        Args:
            host: IP/hostname de OBS (normalmente localhost).
            port: Puerto WebSocket (por defecto 4455).
            password: Contraseña (vacío si no tiene).
            source_name: Nombre de la fuente en OBS (ej: "Captura de juego").

        Returns:
            True si la conexión fue exitosa.
        """
        self.disconnect()

        self._host = host
        self._port = port
        self._password = password
        self._source_name = source_name

        try:
            self._client = obs.ReqClient(
                host=host,
                port=port,
                password=password,
                timeout=5,
            )
            # Verificar conexión pidiendo la versión
            version_resp = self._client.get_version()
            self._connected = True
            self._last_error = ""
            return True
        except Exception as e:
            self._connected = False
            self._last_error = str(e)
            self._client = None
            return False

    def disconnect(self) -> None:
        """Desconecta del servidor OBS WebSocket."""
        with self._lock:
            if self._client is not None:
                try:
                    self._client.base_client.ws.close()
                except Exception:
                    pass
                self._client = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """True si hay conexión activa con OBS."""
        return self._connected and self._client is not None

    @property
    def last_error(self) -> str:
        """Último mensaje de error."""
        return self._last_error

    @property
    def source_name(self) -> str:
        """Nombre de la fuente configurada."""
        return self._source_name

    @source_name.setter
    def source_name(self, name: str) -> None:
        self._source_name = name

    # ==================================================================
    # Captura de frames
    # ==================================================================
    def capture_source(self, source_name: Optional[str] = None) -> Optional[np.ndarray]:
        """
        Captura un screenshot de una fuente de OBS via WebSocket.
        Usa GetSourceScreenshot → devuelve base64 → decodifica a numpy BGR.

        Args:
            source_name: Nombre de la fuente en OBS.
                         Si None, usa self._source_name.

        Returns:
            Imagen BGR como numpy array, o None si falla.
        """
        name = source_name or self._source_name
        if not name:
            self._last_error = "No se ha configurado el nombre de la fuente OBS"
            return None

        if not self.is_connected:
            self._last_error = "No conectado a OBS WebSocket"
            return None

        try:
            # Timeout de 3s para evitar congelamiento si OBS no responde
            acquired = self._lock.acquire(timeout=3.0)
            if not acquired:
                self._last_error = "Timeout esperando lock de captura (OBS bloqueado)"
                return None
            try:
                resp = self._client.get_source_screenshot(
                    name=name,
                    img_format="png",
                    width=None,
                    height=None,
                    quality=-1,
                )
            finally:
                self._lock.release()

            # resp.image_data contiene "data:image/png;base64,<BASE64>"
            image_data: str = resp.image_data
            # Extraer solo la parte base64
            if "," in image_data:
                b64_str = image_data.split(",", 1)[1]
            else:
                b64_str = image_data

            # Decodificar base64 → bytes → numpy → BGR
            img_bytes = base64.b64decode(b64_str)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if img is None:
                self._last_error = "Error al decodificar imagen"
                return None

            # Calcular brillo para detección de pantalla negra
            self._last_brightness = float(np.mean(img))
            self._last_error = ""
            return img

        except Exception as e:
            error_msg = str(e)
            # Error 702 = fuente no puede renderizarse (es audio, está deshabilitada, etc.)
            if "702" in error_msg:
                self._last_error = (
                    f"Captura fallida: la fuente '{name}' no puede generar imagen. "
                    f"Verifica que sea una fuente de VIDEO (no audio) y esté activa."
                )
            else:
                self._last_error = error_msg
            # Si la conexión se perdió, marcar como desconectado
            if "closed" in error_msg.lower() or "connect" in error_msg.lower():
                self._connected = False
            return None

    # Alias para compatibilidad con healer_bot.py
    def capture_projector(self, source_name: Optional[str] = None) -> Optional[np.ndarray]:
        """Alias de capture_source() para mantener compatibilidad."""
        return self.capture_source(source_name)

    # Tipos de inputs de OBS que son solo AUDIO (no pueden hacer screenshot)
    AUDIO_INPUT_KINDS = {
        "wasapi_input_capture",   # Captura de audio de entrada
        "wasapi_output_capture",  # Captura de audio de salida / Audio del escritorio
        "pulse_input_capture",    # PulseAudio entrada (Linux)
        "pulse_output_capture",   # PulseAudio salida (Linux)
        "coreaudio_input_capture",  # CoreAudio entrada (macOS)
        "coreaudio_output_capture", # CoreAudio salida (macOS)
        "alsa_input_capture",     # ALSA entrada (Linux)
        "sndio_input_capture",    # sndio entrada (BSD)
        "jack_output_capture",    # JACK (Linux)
    }

    # ==================================================================
    # Utilidades OBS
    # ==================================================================
    def get_obs_sources(self, include_audio: bool = False) -> list:
        """
        Obtiene la lista de fuentes (inputs) disponibles en OBS.
        Por defecto excluye fuentes de audio puro.

        Args:
            include_audio: Si True, incluye fuentes de audio.

        Returns:
            Lista de dicts con 'name', 'kind', 'is_audio'.
        """
        if not self.is_connected:
            return []
        try:
            with self._lock:
                resp = self._client.get_input_list()
            sources = []
            for inp in resp.inputs:
                kind = inp.get("inputKind", "")
                is_audio = kind in self.AUDIO_INPUT_KINDS
                if not include_audio and is_audio:
                    continue
                sources.append({
                    "name": inp.get("inputName", ""),
                    "kind": kind,
                    "is_audio": is_audio,
                })
            return sources
        except Exception:
            return []

    def get_obs_scenes(self) -> list:
        """
        Obtiene la lista de escenas disponibles en OBS.
        Las escenas también pueden usarse como fuente de screenshot.

        Returns:
            Lista de nombres de escenas.
        """
        if not self.is_connected:
            return []
        try:
            with self._lock:
                resp = self._client.get_scene_list()
            return [s.get("sceneName", "") for s in resp.scenes]
        except Exception:
            return []

    def get_obs_version(self) -> str:
        """Retorna la versión de OBS conectada, o cadena vacía."""
        if not self.is_connected:
            return ""
        try:
            acquired = self._lock.acquire(timeout=3.0)
            if not acquired:
                return ""
            try:
                resp = self._client.get_version()
            finally:
                self._lock.release()
            return f"OBS {resp.obs_version} (WebSocket {resp.obs_web_socket_version})"
        except Exception:
            return ""

    # ==================================================================
    # Propiedades de estado
    # ==================================================================
    @property
    def last_brightness(self) -> float:
        """Brillo promedio de la última captura (0-255). < 5 = pantalla negra."""
        return self._last_brightness

    def is_black_screen(self, threshold: float = 5.0) -> bool:
        """Detecta si la última captura fue una pantalla negra."""
        return self._last_brightness < threshold

    # ==================================================================
    # Limpieza
    # ==================================================================
    def close(self) -> None:
        """Libera recursos y desconecta."""
        self.disconnect()

    def __del__(self):
        self.close()
