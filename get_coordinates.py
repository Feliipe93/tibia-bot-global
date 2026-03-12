import cv2
import numpy as np

print("=== SCRIPT PARA OBTENER COORDENADAS EXACTAS ===")
print()
print("Instrucciones:")
print("1. Abre Tibia y ve a una zona donde tengas el icono de hunger/poison")
print("2. Presiona Print Screen para capturar la pantalla")
print("3. Pega la imagen en Paint y guardala como 'screen.png' en esta carpeta")
print("4. Ejecuta este script de nuevo")
print("5. Haz clic en el icono de hunger/poison en la imagen que se abrirá")
print("6. El script te dará las coordenadas exactas")
print()

# Función para manejar clics del mouse
def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"Coordenadas del clic: X={x}, Y={y}")
        
        # Dibujar un círculo en el punto de clic
        cv2.circle(img_display, (x, y), 5, (0, 255, 0), -1)
        cv2.circle(img_display, (x, y), 8, (0, 255, 0), 2)
        
        # Mostrar coordenadas en la imagen
        cv2.putText(img_display, f"({x},{y})", (x+10, y-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        cv2.imshow("Selecciona el icono de condicion", img_display)
        
        # Guardar coordenadas en un archivo
        with open("coordinates.txt", "a") as f:
            f.write(f"ICON_POSITION: X={x}, Y={y}\n")
        
        print("Coordenadas guardadas en 'coordinates.txt'")
        print("Puedes cerrar la ventana o hacer clic en otro icono")

# Intentar cargar la captura de pantalla
try:
    img = cv2.imread("screen.png")
    if img is None:
        print("ERROR: No se encontró 'screen.png'")
        print("Por favor:")
        print("1. Haz una captura de pantalla de Tibia (con el icono visible)")
        print("2. Guardala como 'screen.png' en esta misma carpeta")
        print("3. Ejecuta este script de nuevo")
    else:
        print("Imagen cargada correctamente")
        print("Haz clic en el icono de hunger/poison para obtener coordenadas")
        print()
        
        # Crear una copia para mostrar
        img_display = img.copy()
        
        # Crear ventana y configurar callback
        cv2.namedWindow("Selecciona el icono de condicion")
        cv2.setMouseCallback("Selecciona el icono de condicion", mouse_callback)
        
        # Mostrar imagen
        cv2.imshow("Selecciona el icono de condicion", img_display)
        
        # Instrucciones adicionales
        print("Presiona ESC para salir, o haz clic en los iconos")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        print("Script finalizado. Revisa el archivo 'coordinates.txt'")

except Exception as e:
    print(f"Error: {e}")

print()
print("=== ALTERNATIVA MANUAL ===")
print("Si no puedes usar el script, dime las coordenadas manualmente:")
print("- Abre la imagen en cualquier editor de imágenes")
print("- Mueve el mouse sobre el icono de hunger/poison")
print("- Apunta las coordenadas X,Y que muestra el editor")
print("- Ejemplo: X=450, Y=380")
