"""
User settings model - PostgreSQL-based with backward compatibility

This module provides a unified interface for settings operations, now using PostgreSQL
instead of JSON files. Maintains compatibility with existing code.
"""
from models.db_settings import (
    get_user_settings_db, create_user_settings_db,
   update_user_settings_db, delete_user_settings_db
)
import os

DATA_DIR = 'data'


def get_user_settings_file(user_id):
    """Get path to user's settings.json file (deprecated, kept for compatibility)"""
    return os.path.join(DATA_DIR, 'users', user_id, 'settings.json')


def initialize_user_settings_file(user_id):
    """Initialize settings for a user in PostgreSQL"""
    # Create default settings in database
    create_user_settings_db(user_id)


def load_settings(user_id):
    """
    Load settings for a user from PostgreSQL
    
    Returns settings dict with default values if not found
    """
    return get_user_settings_db(user_id)


def save_settings(user_id, settings):
    """
    Save settings for a user to PostgreSQL
    
    Args:
        user_id (str): User ID
        settings (dict): Settings to save
    """
    update_user_settings_db(user_id, settings)
