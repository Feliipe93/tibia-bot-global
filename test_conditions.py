#!/usr/bin/env python3
"""
Script para probar el sistema de condiciones manualmente
"""

import sys
sys.path.append('.')

from config import Config

def activate_haste_test():
    """Activa la condición haste para prueba"""
    try:
        print("Activando condicion HASTE para prueba...")
        
        config = Config()
        
        # Activar haste con hotkey F3
        config.set_condition('haste', {
            'enabled': True,
            'hotkey': 'F3',
            'threshold': 0.7,
            'cooldown': 1.0
        })
        
        print("Condicion HASTE activada:")
        print(f"   - Enabled: True")
        print(f"   - Hotkey: F3")
        print(f"   - Threshold: 0.7")
        print(f"   - Cooldown: 1.0s")
        
        # Verificar que se guardó
        haste_config = config.get_condition('haste')
        print(f"Verificacion: {haste_config}")
        
        print("\nAhora:")
        print("1. Inicia el bot con: python main.py")
        print("2. Ve a la pestana 'Condiciones'")
        print("3. Veras que HASTE esta activado")
        print("4. Presiona F9 para activar el healer")
        print("5. El bot detectara cuando no tengas haste y enviara F3")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    activate_haste_test()
