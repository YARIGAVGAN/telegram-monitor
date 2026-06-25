import yaml
import os
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent.parent / 'config'

def load_yaml(filename):
    with open(CONFIG_DIR / filename, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_config():
    config = load_yaml('config.yaml')
    config['telegram']['api_id'] = int(os.getenv('API_ID', config['telegram']['api_id']))
    config['telegram']['api_hash'] = os.getenv('API_HASH', config['telegram']['api_hash'])
    config['bot']['token'] = os.getenv('BOT_TOKEN', config['bot']['token'])
    config['notifications']['user_id'] = int(os.getenv('USER_ID', config['notifications']['user_id']))
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