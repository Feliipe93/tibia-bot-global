from config import Config

config = Config()

# Configurar umbrales correctos basados en los valores reales
conditions_to_setup = {
    'hunger': {'enabled': True, 'hotkey': 'F10', 'threshold': 0.5},
    'poison': {'enabled': True, 'hotkey': 'F2', 'threshold': 0.6},
    'haste': {'enabled': True, 'hotkey': 'F3', 'threshold': 0.55},
    'paralyze': {'enabled': True, 'hotkey': 'F4', 'threshold': 0.5}
}

for cond_name, cond_config in conditions_to_setup.items():
    config.set_condition(cond_name, cond_config)
    print(f'{cond_name}: enabled={cond_config["enabled"]}, hotkey={cond_config["hotkey"]}, threshold={cond_config["threshold"]}')

print('Umbrales corregidos basados en valores reales de matching')
