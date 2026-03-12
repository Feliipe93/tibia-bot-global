#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rotworm_visual_simple.py - Demostración simple de reconocimiento visual de Rotworm
"""

import logging
from targeting_v2_integration import TargetingV2Integration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== RECONOCIMIENTO VISUAL DE ROTWORM ===\n")
    
    # 1. Crear sistema de targeting
    print("1. INICIANDO SISTEMA DE TARGETING:")
    integration = TargetingV2Integration()
    integration.initialize()
    
    # 2. Obtener información de Rotworm
    print("2. OBTENIENDO INFORMACIÓN DE ROTWORM:")
    rotworm_info = integration.get_creature_info('rotworm')
    
    print(f"   Nombre: {rotworm_info['name']}")
    print(f"   HP: {rotworm_info.get('hp', 'N/A')}")
    print(f"   Experiencia: {rotworm_info.get('experience', 'N/A')}")
    print(f"   Prioridad: {rotworm_info['priority']}")
    print(f"   Seleccionado: {rotworm_info['selected']}")
    
    # 3. Datos visuales específicos
    print(f"\n3. DATOS VISUALES ESPECÍFICOS:")
    print(f"   =========================================")
    print(f"   IDENTIFICADOR ÚNICO")
    print(f"   =========================================")
    print(f"   Look Type: 26")
    print(f"   Head Color: 94")
    print(f"   Body Color: 94")
    print(f"   Legs Color: 94")
    print(f"   Feet Color: 94")
    print(f"   =========================================")
    
    # 4. Información del cuerpo muerto
    print(f"\n4. INFORMACIÓN DEL CUERPO MUERTO:")
    print(f"   =========================================")
    print(f"   DATOS DEL CUERPO")
    print(f"   =========================================")
    print(f"   Item ID: 4354")
    print(f"   Nombre: Dead Worm")
    print(f"   Descripción: The corpse of a rotworm.")
    print(f"   Tamaño: Medium")
    print(f"   Duración: 120 segundos")
    print(f"   =========================================")
    
    # 5. Cómo funciona el reconocimiento visual
    print(f"\n5. CÓMO RECONOCE EL BOT CON OBS:")
    print(f"   PASO 1: CAPTURA")
    print(f"   - OBS captura la pantalla del juego")
    print(f"   - Resolución: 1920x1080 (o la configurada)")
    print(f"   - FPS: 30 (para tiempo real)")
    
    print(f"\n   PASO 2: PROCESAMIENTO")
    print(f"   - Convierte imagen a array numpy")
    print(f"   - Aplica filtros para mejorar detección")
    print(f"   - Busca patrones de colores específicos")
    
    print(f"\n   PASO 3: DETECCIÓN")
    print(f"   - Escanea la pantalla buscando sprites")
    print(f"   - Compara con templates conocidos")
    print(f"   - Identifica Look Type 26")
    
    print(f"\n   PASO 4: LOCALIZACIÓN")
    print(f"   - Calcula coordenadas (x, y)")
    print(f"   - Verifica que sea un monstruo válido")
    print(f"   - Descarta jugadores y NPCs")
    
    print(f"\n   PASO 5: VALIDACIÓN")
    print(f"   - Cruza con battle list")
    print(f"   - Verifica nombre 'Rotworm'")
    print(f"   - Confirma que está en attack_list")
    
    # 6. Características visuales específicas
    print(f"\n6. CARACTERÍSTICAS VISUALES ESPECÍFICAS:")
    print(f"   COLOR PRINCIPAL:")
    print(f"   - Cuerpo: Color marrón oscuro (94)")
    print(f"   - Piernas: Color marrón (94)")
    print(f"   - Cabeza: Color marrón (94)")
    print(f"   - Pies: Color marrón (94)")
    
    print(f"\n   FORMA:")
    print(f"   - Tamaño: Mediano (32x32 píxeles)")
    print(f"   - Animación: Movimiento serpenteante")
    print(f"   - Dirección: 8 direcciones posibles")
    
    print(f"\n   COMPORTAMIENTO:")
    print(f"   - Velocidad: Media")
    print(f"   - Rango de ataque: Melee (1 sqm)")
    print(f"   - Agresividad: Media")
    
    # 7. Ejemplo de código de detección
    print(f"\n7. EJEMPLO DE CÓDIGO DE DETECCIÓN:")
    print(f"   ```python")
    print(f"   # Capturar pantalla con OBS")
    print(f"   frame = obs.capture_frame()")
    print(f"   ")
    print(f"   # Buscar sprites de Rotworm")
    print(f"   rotworm_positions = find_sprites_by_look_type(")
    print(f"       frame, look_type=26")
    print(f"   )")
    print(f"   ")
    print(f"   # Validar con battle list")
    print(f"   for pos in rotworm_positions:")
    print(f"       if is_valid_target(pos, 'rotworm'):")
    print(f"           attack_position(pos)")
    print(f"   ```")
    
    # 8. Proceso completo de ataque
    print(f"\n8. PROCESO COMPLETO DE ATAQUE:")
    print(f"   1. OBS captura pantalla → 2. Procesa imagen")
    print(f"   3. Detecta sprite Rotworm → 4. Verifica battle list")
    print(f"   5. Confirma en attack_list → 6. Calcula posición")
    print(f"   7. Mueve mouse → 8. Click para seleccionar")
    print(f"   9. Presiona ataque → 10. Inicia combate")
    
    # 9. Números específicos para reconocimiento
    print(f"\n9. NÚMEROS ESPECÍFICOS PARA RECONOCIMIENTO:")
    print(f"   =========================================")
    print(f"   DATOS NUMÉRICOS CLAVE")
    print(f"   =========================================")
    print(f"   Look Type ID: 26")
    print(f"   Head Color: 94")
    print(f"   Body Color: 94")
    print(f"   Legs Color: 94")
    print(f"   Feet Color: 94")
    print(f"   Outfit Type: 0")
    print(f"   Addons: 0")
    print(f"   =========================================")
    
    print(f"\n   DATOS DEL CUERPO MUERTO")
    print(f"   =========================================")
    print(f"   Corpse Item ID: 4354")
    print(f"   Corpse Name: Dead Worm")
    print(f"   Decay Time: 120 segundos")
    print(f"   Size: Medium")
    print(f"   =========================================")
    
    # 10. Resumen
    print(f"\n10. RESUMEN:")
    print(f"    El bot reconoce Rotworm usando:")
    print(f"    - Look Type único: 26")
    print(f"    - Colores específicos: 94 (marrón)")
    print(f"    - Forma y tamaño característicos")
    print(f"    - Validación con battle list")
    print(f"    - Integración con OBS para captura en tiempo real")
    
    print(f"\n=== RECONOCIMIENTO VISUAL COMPLETADO ===")
    print(f"Rotworm puede ser reconocido visualmente con estos datos:")
    print(f"- Look Type: 26 (identificador único)")
    print(f"- Colores: Head=94, Body=94, Legs=94, Feet=94")
    print(f"- Cuerpo muerto: Item ID 4354")
    print(f"- Tamaño: 32x32 píxeles")
    print(f"- Validación: Battle list + attack_list")

if __name__ == "__main__":
    main()
