#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rotworm_visual_demo.py - Demostración de cómo el bot reconoce visualmente a Rotworm
"""

import cv2
import numpy as np
from PIL import Image
import logging
from targeting_v2_integration import TargetingV2Integration
from tibia_assets_reader import TibiaAssetsReader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== RECONOCIMIENTO VISUAL DE ROTWORM ===\n")
    
    # 1. Cargar sistema de assets
    print("1. CARGANDO ASSETS DE TIBIA:")
    assets_reader = TibiaAssetsReader("tibia_files_canary")
    assets_reader.load_all_assets()
    
    # Buscar información de Rotworm
    rotworm_info = None
    for creature_name, creature_data in assets_reader.creatures.items():
        if "rotworm" in creature_name.lower():
            rotworm_info = creature_data
            break
    
    if not rotworm_info:
        print("   [ERROR] No se encontró información de Rotworm")
        return
    
    print(f"   [OK] Rotworm encontrado: {rotworm_info.name}")
    print(f"   Look Type: {rotworm_info.look_type}")
    print(f"   HP: {rotworm_info.max_health}")
    print(f"   Experiencia: {rotworm_info.experience}")
    
    # 2. Mostrar información visual
    print(f"\n2. INFORMACIÓN VISUAL DE ROTWORM:")
    print(f"   =========================================")
    print(f"   DATOS VISUALES")
    print(f"   =========================================")
    print(f"   Look Type: {rotworm_info.look_type}")
    print(f"   Outfit Type: {rotworm_info.outfit_type}")
    print(f"   Head: {rotworm_info.look_head}")
    print(f"   Body: {rotworm_info.look_body}")
    print(f"   Legs: {rotworm_info.look_legs}")
    print(f"   Feet: {rotworm_info.look_feet}")
    print(f"   Addons: {rotworm_info.look_addons}")
    print(f"   =========================================")
    
    # 3. Información del cuerpo muerto
    corpse_info = None
    for corpse_name, corpse_data in assets_reader.corpses.items():
        if "worm" in corpse_name.lower() or "rotworm" in corpse_name.lower():
            corpse_info = corpse_data
            break
    
    if corpse_info:
        print(f"\n3. INFORMACIÓN DEL CUERPO MUERTO:")
        print(f"   =========================================")
        print(f"   DATOS DEL CUERPO")
        print(f"   =========================================")
        print(f"   Nombre: {corpse_info.name}")
        print(f"   Item ID: {corpse_info.item_id}")
        print(f"   Descripción: {corpse_info.description}")
        print(f"   Tamaño: {corpse_info.size}")
        print(f"   Duración: {corpse_info.decay_time}")
        print(f"   =========================================")
    
    # 4. Proceso de reconocimiento con OBS
    print(f"\n4. CÓMO RECONOCE EL BOT CON OBS:")
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
    print(f"   - Identifica Look Type {rotworm_info.look_type}")
    
    print(f"\n   PASO 4: LOCALIZACIÓN")
    print(f"   - Calcula coordenadas (x, y)")
    print(f"   - Verifica que sea un monstruo válido")
    print(f"   - Descarta jugadores y NPCs")
    
    print(f"\n   PASO 5: VALIDACIÓN")
    print(f"   - Cruza con battle list")
    print(f"   - Verifica nombre 'Rotworm'")
    print(f"   - Confirma que está en attack_list")
    
    # 5. Datos numéricos específicos
    print(f"\n5. DATOS NUMÉRICOS ESPECÍFICOS:")
    print(f"   =========================================")
    print(f"   IDENTIFICADOR ÚNICO")
    print(f"   =========================================")
    print(f"   Look Type: {rotworm_info.look_type}")
    print(f"   Head Color: {rotworm_info.look_head}")
    print(f"   Body Color: {rotworm_info.look_body}")
    print(f"   Legs Color: {rotworm_info.look_legs}")
    print(f"   Feet Color: {rotworm_info.look_feet}")
    print(f"   =========================================")
    
    if corpse_info:
        print(f"\n   DATOS DEL CUERPO MUERTO")
        print(f"   =========================================")
        print(f"   Item ID: {corpse_info.item_id}")
        print(f"   Nombre: {corpse_info.name}")
        print(f"   Descripción: {corpse_info.description}")
        print(f"   Tamaño: {corpse_info.size}")
        print(f"   Duración: {corpse_info.decay_time} segundos")
        print(f"   =========================================")
    
    # 6. Sistema de reconocimiento mejorado
    print(f"\n6. SISTEMA DE RECONOCIMIENTO MEJORADO:")
    integration = TargetingV2Integration()
    integration.initialize()
    
    visual_info = integration.get_creature_info('rotworm')
    print(f"   - Nombre: {visual_info['name']}")
    print(f"   - Look Type: {visual_info.get('look_type', 'N/A')}")
    print(f"   - HP: {visual_info.get('hp', 'N/A')}")
    print(f"   - Experiencia: {visual_info.get('experience', 'N/A')}")
    print(f"   - Tipo: {visual_info.get('class_type', 'N/A')}")
    print(f"   - Amenaza: {visual_info.get('threat_level', 'N/A')}")
    
    # 7. Ejemplo de código de detección
    print(f"\n7. EJEMPLO DE CÓDIGO DE DETECCIÓN:")
    print(f"   ```python")
    print(f"   # Capturar pantalla con OBS")
    print(f"   frame = obs.capture_frame()")
    print(f"   ")
    print(f"   # Buscar sprites de Rotworm")
    print(f"   rotworm_positions = find_sprites_by_look_type(")
    print(f"       frame, look_type={rotworm_info.look_type}")
    print(f"   )")
    print(f"   ")
    print(f"   # Validar con battle list")
    print(f"   for pos in rotworm_positions:")
    print(f"       if is_valid_target(pos, 'rotworm'):")
    print(f"           attack_position(pos)")
    print(f"   ```")
    
    # 8. Características visuales específicas
    print(f"\n8. CARACTERÍSTICAS VISUALES ESPECÍFICAS:")
    print(f"   COLOR PRINCIPAL:")
    print(f"   - Cuerpo: Color marrón oscuro ({rotworm_info.look_body})")
    print(f"   - Piernas: Color marrón ({rotworm_info.look_legs})")
    
    print(f"\n   FORMA:")
    print(f"   - Tamaño: Mediano (32x32 píxeles)")
    print(f"   - Animación: Movimiento serpenteante")
    print(f"   - Dirección: 8 direcciones posibles")
    
    print(f"\n   COMPORTAMIENTO:")
    print(f"   - Velocidad: Media")
    print(f"   - Rango de ataque: Melee (1 sqm)")
    print(f"   - Agresividad: Media")
    
    # 9. Proceso completo
    print(f"\n9. PROCESO COMPLETO DE ATAQUE:")
    print(f"   1. OBS captura pantalla → 2. Procesa imagen")
    print(f"   3. Detecta sprite Rotworm → 4. Verifica battle list")
    print(f"   5. Confirma en attack_list → 6. Calcula posición")
    print(f"   7. Mueve mouse → 8. Click para seleccionar")
    print(f"   9. Presiona ataque → 10. Inicia combate")
    
    print(f"\n=== RECONOCIMIENTO VISUAL COMPLETADO ===")
    print(f"El bot puede reconocer visualmente a Rotworm usando:")
    print(f"- Look Type único: {rotworm_info.look_type}")
    print(f"- Colores específicos: cuerpo={rotworm_info.look_body}, piernas={rotworm_info.look_legs}")
    print(f"- Forma y tamaño característicos")
    print(f"- Validación con battle list")
    print(f"- Integración con OBS para captura en tiempo real")

if __name__ == "__main__":
    main()
