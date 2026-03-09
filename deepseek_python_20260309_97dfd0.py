# main.py (versión modificada)
from screen_capture import OBSCapture
from window_finder import find_tibia_windows
from bot_controller import BotController
import threading
import time

def main():
    # Conectar a OBS
    obs = OBSCapture(host='localhost', port=4455)
    
    # Encontrar Tibia
    tibia_windows = find_tibia_windows()
    if not tibia_windows:
        print("❌ No se encontró Tibia")
        return
    
    tibia_hwnd = tibia_windows[0]['hwnd']
    print(f"✅ Tibia encontrado: {tibia_windows[0]['title']}")
    
    # Crear bot
    bot = BotController(obs, tibia_hwnd)
    
    # Iniciar bot en hilo
    bot_thread = threading.Thread(target=bot.run, daemon=True)
    bot_thread.start()
    
    # Menú simple
    print("\n🎮 Comandos:")
    print("  'load' - Cargar ruta")
    print("  'start' - Iniciar cavebot")
    print("  'stop' - Detener cavebot")
    print("  'stats' - Ver estadísticas")
    print("  'exit' - Salir\n")
    
    while True:
        cmd = input("> ").strip().lower()
        
        if cmd == "load":
            path = input("Ruta del archivo JSON: ")
            bot.load_route(path)
        
        elif cmd == "start":
            bot.start_walking()
        
        elif cmd == "stop":
            bot.stop_walking()
        
        elif cmd == "stats":
            stats = bot.get_stats()
            print(f"\n📊 ESTADÍSTICAS:")
            print(f"  Tiempo activo: {stats['runtime']:.0f} segundos")
            print(f"  HP: {stats['hp']:.1f}% | Mana: {stats['mana']:.1f}%")
            print(f"  Posición: ({stats['position'].x if stats['position'] else '?'})")
            print(f"  Estado: {stats['state']}")
            print(f"  Curaciones: {stats['heals']}")
            print(f"  Ataques: {stats['attacks']}")
            print(f"  Looteos: {stats['loots']}")
            print(f"  Pasos: {stats['steps']}")
            print(f"  Waypoint: {stats['waypoint']}\n")
        
        elif cmd == "exit":
            break
        
        time.sleep(0.1)
    
    print("👋 Saliendo...")

if __name__ == "__main__":
    main()