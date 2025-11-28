import json
import os

DATA_DIR = 'data'

def get_user_settings_file(user_id):
    """Get path to user's settings.json file"""
    return os.path.join(DATA_DIR, 'users', user_id, 'settings.json')

def initialize_user_settings_file(user_id):
    """Initialize settings.json for a user"""
    settings_file = get_user_settings_file(user_id)
    if not os.path.exists(settings_file):
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump({
                'selected_provider': 'openrouter',
                'api_keys': {
                    'openrouter': '',
                    'openai': '',
                    'google': ''
                },
                'provider_models': {
                    'openrouter': '',
                    'openai': 'gpt-4',
                    'google': 'gemini-2.5-flash'
                },
                'show_covers': True,
                'dark_mode': False,
                'default_sort_order': 'asc',
                'encryption_enabled': True,
                'auto_translate_title': False,
                'auto_translate_content': False,
                'thinking_mode_enabled': False,
                'thinking_mode_models': {
                    'openrouter': '',
                    'openai': 'o1-preview',
                    'google': 'gemini-2.0-flash-thinking-exp-1219',
                    'xai': ''
                },
                'available_models': {
                    'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                    'google': [
                        'gemini-2.5-pro',
                        'gemini-2.5-flash',
                        'gemini-2.5-flash-lite',
                        'gemini-2.0-flash',
                        'gemini-2.0-flash-lite'
                    ]
                }
            }, f)

def load_settings(user_id):
    """Load settings for a user"""
    try:
        from services.encryption_service import decrypt_dict, is_encrypted
        
        settings_file = get_user_settings_file(user_id)
        with open(settings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Ensure new fields exist for backward compatibility
            data.setdefault('selected_provider', 'openrouter')
            data.setdefault('api_keys', {'openrouter': '', 'openai': '', 'google': ''})
            data.setdefault('provider_models', {
                'openrouter': '',
                'openai': 'gpt-4',
                'google': 'gemini-2.5-flash'
            })
            data.setdefault('dark_mode', False)
            data.setdefault('default_sort_order', 'asc')
            data.setdefault('encryption_enabled', True)
            data.setdefault('auto_translate_title', False)
            data.setdefault('auto_translate_content', False)
            data.setdefault('available_models', {
                'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                'google': [
                    'gemini-2.5-pro',
                    'gemini-2.5-flash',
                    'gemini-2.5-flash-lite',
                    'gemini-2.0-flash',
                    'gemini-2.0-flash-lite'
                ]
            })
            
            # Decrypt API keys if encryption is enabled
            if data.get('encryption_enabled', True):
                any_encrypted = any(
                    is_encrypted(key) 
                    for key in data.get('api_keys', {}).values() 
                    if key
                )
                
                if any_encrypted:
                    data['api_keys'] = decrypt_dict(data.get('api_keys', {}))
            
            return data
    except Exception as e:
        return {
            'selected_provider': 'openrouter',
            'api_keys': {'openrouter': '', 'openai': '', 'google': ''},
            'provider_models': {
                'openrouter': '',
                'openai': 'gpt-4',
                'google': 'gemini-2.5-flash'
            },
            'show_covers': True,
            'dark_mode': False,
            'default_sort_order': 'asc',
            'encryption_enabled': True,
            'auto_translate_title': False,
            'auto_translate_content': False,
            'available_models': {
                'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                'google': [
                    'gemini-2.5-pro',
                    'gemini-2.5-flash',
                    'gemini-2.5-flash-lite',
                    'gemini-2.0-flash',
                    'gemini-2.0-flash-lite'
                ]
            }
        }

def save_settings(user_id, settings):
    """Encrypt API keys and save settings for a user"""
    try:
        from services.encryption_service import migrate_to_encrypted
        
        settings_to_save = settings.copy()
        
        if settings_to_save.get('encryption_enabled', True):
            settings_to_save['api_keys'] = migrate_to_encrypted(settings_to_save.get('api_keys', {}))
        
        settings_file = get_user_settings_file(user_id)
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")
        raise

    """Initialize settings.json for a user"""
    settings_file = get_user_settings_file(user_id)
    if not os.path.exists(settings_file):
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump({
                'selected_provider': 'openrouter',
                'api_keys': {
                    'openrouter': '',
                    'openai': '',
                    'google': ''
                },
                'provider_models': {
                    'openrouter': '',
                    'openai': 'gpt-4',
                    'google': 'gemini-2.5-flash'
                },
                'show_covers': True,
                'dark_mode': False,
                'default_sort_order': 'asc',
                'encryption_enabled': True,
                'available_models': {
                    'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                    'google': [
                        'gemini-2.5-pro',
                        'gemini-2.5-flash',
                        'gemini-2.5-flash-lite',
                        'gemini-2.0-flash',
                        'gemini-2.0-flash-lite'
                    ]
                }
            }, f)

def load_settings(user_id):
    """Load settings for a user"""
    try:
        from services.encryption_service import decrypt_dict, is_encrypted
        
        settings_file = get_user_settings_file(user_id)
        with open(settings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Ensure new fields exist for backward compatibility
            data.setdefault('selected_provider', 'openrouter')
            data.setdefault('api_keys', {'openrouter': '', 'openai': '', 'google': ''})
            data.setdefault('provider_models', {
                'openrouter': '',
                'openai': 'gpt-4',
                'google': 'gemini-2.5-flash'
            })
            data.setdefault('dark_mode', False)
            data.setdefault('default_sort_order', 'asc')
            data.setdefault('encryption_enabled', True)
            data.setdefault('show_translation_cost', True)
            data.setdefault('available_models', {
                'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                'google': [
                    'gemini-2.5-pro',
                    'gemini-2.5-flash',
                    'gemini-2.5-flash-lite',
                    'gemini-2.0-flash',
                    'gemini-2.0-flash-lite'
                ]
            })

            # Decrypt API keys if encryption is enabled
            if data.get('encryption_enabled', True):
                any_encrypted = any(
                    is_encrypted(key)
                    for key in data.get('api_keys', {}).values()
                    if key
                )

                if any_encrypted:
                    data['api_keys'] = decrypt_dict(data.get('api_keys', {}))

            return data
    except Exception as e:
        return {
            'selected_provider': 'openrouter',
            'api_keys': {'openrouter': '', 'openai': '', 'google': ''},
            'provider_models': {
                'openrouter': '',
                'openai': 'gpt-4',
                'google': 'gemini-2.5-flash'
            },
            'show_covers': True,
            'dark_mode': False,
            'default_sort_order': 'asc',
            'encryption_enabled': True,
            'show_translation_cost': True,
            'available_models': {
                'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                'google': [
                    'gemini-2.5-pro',
                    'gemini-2.5-flash',
                    'gemini-2.5-flash-lite',
                    'gemini-2.0-flash',
                    'gemini-2.0-flash-lite'
                ]
            }
        }

def save_settings(user_id, settings):
    """Encrypt API keys and save settings for a user"""
    try:
        from services.encryption_service import migrate_to_encrypted
        
        settings_to_save = settings.copy()
        
        if settings_to_save.get('encryption_enabled', True):
            settings_to_save['api_keys'] = migrate_to_encrypted(settings_to_save.get('api_keys', {}))
        
        settings_file = get_user_settings_file(user_id)
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")
        raise
