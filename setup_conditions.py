from config import Config

config = Config()

# Configurar condiciones con umbrales bajos
conditions_to_setup = {
    'hunger': {'enabled': True, 'hotkey': 'F10', 'threshold': 0.25},
    'poison': {'enabled': True, 'hotkey': 'F2', 'threshold': 0.25},
    'haste': {'enabled': True, 'hotkey': 'F3', 'threshold': 0.25},
    'paralyze': {'enabled': True, 'hotkey': 'F4', 'threshold': 0.25}
}

for cond_name, cond_config in conditions_to_setup.items():
    config.set_condition(cond_name, cond_config)
    print(f'{cond_name}: enabled={cond_config["enabled"]}, hotkey={cond_config["hotkey"]}, threshold={cond_config["threshold"]}')

print('Sistema de condiciones configurado con umbrales bajos')
