"""
PostgreSQL-based user settings operations

This module provides database operations for user settings using SQLAlchemy.
Replaces the JSON file-based approach in models/settings.py
"""
from models.database import db_session_scope
from models.db_models import UserSettings


def get_user_settings_db(user_id):
    """
    Get user settings from PostgreSQL
    
    Args:
        user_id (str): User ID
        
    Returns:
        dict: User settings dictionary with default values if not found
    """
    with db_session_scope() as session:
        settings = session.query(UserSettings).filter_by(user_id=user_id).first()
        
        if settings:
            return settings.to_dict()
        else:
            # Return default settings if not found
            return {
                'user_id': user_id,
                'translation_api_key': None,
                'translation_model': 'gpt-4o-mini'
            }


def create_user_settings_db(user_id, settings_data=None):
    """
    Create user settings in PostgreSQL
    
    Args:
        user_id (str): User ID
        settings_data (dict, optional): Initial settings data
        
    Returns:
        dict: Created settings dictionary
    """
    if settings_data is None:
        settings_data = {}
    
    with db_session_scope() as session:
        # Check if settings already exist
        existing = session.query(UserSettings).filter_by(user_id=user_id).first()
        if existing:
            return existing.to_dict()
        
        # Create new settings
        settings = UserSettings(
            user_id=user_id,
            translation_api_key=settings_data.get('translation_api_key'),
            translation_model=settings_data.get('translation_model', 'gpt-4o-mini')
        )
        session.add(settings)
        session.flush()
        return settings.to_dict()


def update_user_settings_db(user_id, updates):
    """
    Update user settings in PostgreSQL
    
    Args:
        user_id (str): User ID
        updates (dict): Fields to update
        
    Returns:
        dict: Updated settings dictionary
    """
    with db_session_scope() as session:
        settings = session.query(UserSettings).filter_by(user_id=user_id).first()
        
        if not settings:
            # Create if doesn't exist
            settings = UserSettings(user_id=user_id)
            session.add(settings)
        
        # Update allowed fields
        allowed_fields = ['translation_api_key', 'translation_model']
        for field in allowed_fields:
            if field in updates:
                setattr(settings, field, updates[field])
        
        session.flush()
        return settings.to_dict()


def delete_user_settings_db(user_id):
    """
    Delete user settings from PostgreSQL
    
    Args:
        user_id (str): User ID
        
    Returns:
        bool: True if deleted, False if not found
    """
    with db_session_scope() as session:
        settings = session.query(UserSettings).filter_by(user_id=user_id).first()
        
        if not settings:
            return False
        
        session.delete(settings)
        return True
