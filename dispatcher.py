"""
dispatcher.py - Distribuye frames capturados a cada módulo activo del bot.
Coordina la ejecución de Healer, Cavebot, Targeting y Looter
sobre el mismo frame de OBS WebSocket.
"""

import time
import threading
from enum import Enum
from typing import Callable, Dict, List, Optional

import numpy as np

from config import Config
from logger import BotLogger
from screen_capture import ScreenCapture


class ModuleState(Enum):
    """Estado de un módulo del bot."""
    DISABLED = "disabled"
    ENABLED = "enabled"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class BotDispatcher:
    """
    Distribuidor central de frames a los módulos del bot.

    Captura un frame de OBS y lo distribuye a:
    - Healer (siempre activo si habilitado)
    - Cavebot (si habilitado)
    - Targeting (si habilitado)
    - Looter (si habilitado)

    Cada módulo procesa el frame y solicita acciones al ActionDispatcher.
    """

    def __init__(self, config: Config, logger: BotLogger, capture: ScreenCapture):
        self.config = config
        self.log = logger
        self.capture = capture

        self._lock = threading.Lock()

        # Estado de módulos
        self.module_states: Dict[str, ModuleState] = {
            "healer": ModuleState.ENABLED,
            "cavebot": ModuleState.DISABLED,
            "targeting": ModuleState.DISABLED,
            "looter": ModuleState.DISABLED,
        }

        # Handlers registrados: nombre → callable(frame) -> None
        self._handlers: Dict[str, Optional[Callable]] = {
            "healer": None,
            "cavebot": None,
            "targeting": None,
            "looter": None,
        }

        # Métricas
        self.last_frame: Optional[np.ndarray] = None
        self.last_frame_time: float = 0.0
        self.frames_dispatched: int = 0

        # Callbacks para GUI
        self._on_module_change: Optional[Callable] = None

    # ==================================================================
    # Registro de módulos
    # ==================================================================
    def register_handler(self, module_name: str, handler: Callable) -> None:
        """
        Registra un handler que recibirá frames.
        El handler debe aceptar un numpy array BGR como argumento.
        """
        if module_name in self._handlers:
            self._handlers[module_name] = handler
            self.log.debug(f"Dispatcher: handler '{module_name}' registrado")

    def unregister_handler(self, module_name: str) -> None:
        """Elimina el handler de un módulo."""
        if module_name in self._handlers:
            self._handlers[module_name] = None

    # ==================================================================
    # Control de módulos
    # ==================================================================
    def enable_module(self, name: str) -> None:
        """Habilita un módulo."""
        if name in self.module_states:
            self.module_states[name] = ModuleState.ENABLED
            self.log.info(f"Módulo '{name}' habilitado")
            self._notify_change()

    def disable_module(self, name: str) -> None:
        """Deshabilita un módulo."""
        if name in self.module_states:
            self.module_states[name] = ModuleState.DISABLED
            self.log.info(f"Módulo '{name}' deshabilitado")
            self._notify_change()

    def pause_module(self, name: str) -> None:
        """Pausa un módulo temporalmente."""
        if name in self.module_states:
            self.module_states[name] = ModuleState.PAUSED
            self._notify_change()

    def resume_module(self, name: str) -> None:
        """Reanuda un módulo pausado."""
        if name in self.module_states:
            if self.module_states[name] == ModuleState.PAUSED:
                self.module_states[name] = ModuleState.ENABLED
                self._notify_change()

    def is_module_active(self, name: str) -> bool:
        """True si el módulo está habilitado o corriendo."""
        state = self.module_states.get(name, ModuleState.DISABLED)
        return state in (ModuleState.ENABLED, ModuleState.RUNNING)

    def toggle_module(self, name: str) -> bool:
        """Alterna el estado de un módulo. Retorna nuevo estado (True=activo)."""
        if self.is_module_active(name):
            self.disable_module(name)
            return False
        else:
            self.enable_module(name)
            return True

    def get_active_modules(self) -> List[str]:
        """Retorna la lista de módulos activos."""
        return [
            name for name, state in self.module_states.items()
            if state in (ModuleState.ENABLED, ModuleState.RUNNING)
        ]

    # ==================================================================
    # Distribución de frames
    # ==================================================================
    def dispatch_frame(self, frame: np.ndarray) -> Dict[str, bool]:
        """
        Distribuye un frame a todos los módulos activos.

        Orden de ejecución (por prioridad):
        1. Healer (siempre primero — vida del personaje)
        2. Targeting (atacar mobs)
        3. Cavebot (movimiento)
        4. Looter (recoger items)

        Returns:
            Dict con nombre de módulo → True si se ejecutó correctamente.
        """
        self.last_frame = frame
        self.last_frame_time = time.time()
        self.frames_dispatched += 1

        results: Dict[str, bool] = {}
        execution_order = ["healer", "targeting", "cavebot", "looter"]

        for module_name in execution_order:
            state = self.module_states.get(module_name, ModuleState.DISABLED)
            handler = self._handlers.get(module_name)

            if state not in (ModuleState.ENABLED, ModuleState.RUNNING):
                results[module_name] = False
                continue

            if handler is None:
                results[module_name] = False
                continue

            try:
                self.module_states[module_name] = ModuleState.RUNNING

                # Ejecutar handler directamente (ya estamos en hilo secundario)
                # NO crear thread + join — eso causaba starvation del main loop
                handler(frame)

                self.module_states[module_name] = ModuleState.ENABLED
                results[module_name] = True
            except Exception as e:
                self.module_states[module_name] = ModuleState.ERROR
                self.log.error(f"Error en módulo '{module_name}': {e}")
                results[module_name] = False

        return results

    # ==================================================================
    # Callbacks
    # ==================================================================
    def set_module_change_callback(self, callback: Callable) -> None:
        """Callback que se invoca cuando cambia el estado de un módulo."""
        self._on_module_change = callback

    def _notify_change(self) -> None:
        if self._on_module_change:
            try:
                self._on_module_change()
            except Exception:
                pass

    # ==================================================================
    # Info
    # ==================================================================
    def get_status(self) -> Dict:
        """Retorna estado completo del dispatcher."""
        return {
            "modules": {
                name: state.value
                for name, state in self.module_states.items()
            },
            "active": self.get_active_modules(),
            "frames_dispatched": self.frames_dispatched,
            "last_frame_time": self.last_frame_time,
        }

    def __repr__(self) -> str:
        active = self.get_active_modules()
        return (
            f"<BotDispatcher modules={active} "
            f"frames={self.frames_dispatched}>"
        )
