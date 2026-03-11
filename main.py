"""
main.py - Punto de entrada de la aplicación Tibia Auto Healer.
"""

import sys
import os

# Asegurar que el directorio de trabajo sea el del script
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def check_dependencies():
    """Verifica que todas las dependencias estén instaladas."""
    missing = []
    deps = {
        "obsws_python": "obsws-python",
        "cv2": "opencv-python",
        "numpy": "numpy",
        "win32gui": "pywin32",
        "win32api": "pywin32",
        "win32con": "pywin32",
        "keyboard": "keyboard",
        "customtkinter": "customtkinter",
        "PIL": "Pillow",
    }
    for module, package in deps.items():
        try:
            __import__(module)
        except ImportError:
            if package not in missing:
                missing.append(package)

    if missing:
        print("=" * 60)
        print("  DEPENDENCIAS FALTANTES")
        print("=" * 60)
        print()
        print("Los siguientes paquetes no están instalados:")
        for pkg in missing:
            print(f"  ❌ {pkg}")
        print()
        print("Instálalos ejecutando:")
        print(f"  pip install {' '.join(missing)}")
        print()
        print("O instala todas las dependencias con:")
        print("  pip install -r requirements.txt")
        print("=" * 60)
        sys.exit(1)


def main():
    """Función principal — lanza la GUI."""
    check_dependencies()

    # Crear directorios necesarios
    os.makedirs("logs", exist_ok=True)
    os.makedirs("debug", exist_ok=True)

    # Importar después de verificar dependencias
    from gui import TibiaHealerGUI

    print()
    print("=" * 50)
    print("  TIBIA AUTO HEALER")
    print("=" * 50)
    print("  Iniciando interfaz grafica...")
    print("  Usa F9 para activar/desactivar")
    print("  Usa F10 para cerrar")
    print("=" * 50)
    print()

    app = TibiaHealerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
