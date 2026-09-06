import yaml
import os
import re
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent.parent / 'config'

def load_yaml(filename):
    with open(CONFIG_DIR / filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем переменные окружения в формате ${VAR_NAME}
    def replace_env_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, '')
    
    content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)
    return yaml.safe_load(content)

def load_config():
    config = load_yaml('config.yaml')
    # Дополнительные проверки и преобразования типов
    config['telegram']['api_id'] = int(config['telegram']['api_id'])
    config['notifications']['user_id'] = int(config['notifications']['user_id'])
    return config
#
# def load_keywords():
#     # Оставлено для обратной совместимости, но больше не используется
#     return load_yaml('keywords.yaml')['keywords']

def load_chats():
    data = load_yaml('chats.yaml')
    return data.get('whitelist', []), data.get('blacklist', [])

def load_rules():
    """Загружает правила из rules.yaml"""
    return load_yaml('rules.yaml')['rules']