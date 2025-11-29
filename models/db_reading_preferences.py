"""
Database operations for reading preferences.

This module provides functions to get, save, and manage user reading preferences
for the Enhanced Reading Modes feature.
"""
from models.db_models import ReadingPreference
from models.db_connection import db_session_scope
from sqlalchemy.exc import SQLAlchemyError


def get_default_reading_preferences():
    """Return default reading preference values"""
    return {
        'color_mode': 'light',
        'font_size': 16,
        'line_height': '1.8',
        'font_family': 'var(--font-serif)',
        'reading_width': '720px',
        'text_alignment': 'left'
    }


def get_reading_preferences(user_id):
    """
    Get reading preferences for a user.
    Returns default values if no preferences are stored.
    
    Args:
        user_id: The user's ID
        
    Returns:
        dict: Reading preferences dictionary
    """
    try:
        with db_session_scope() as session:
            prefs = session.query(ReadingPreference).filter_by(user_id=user_id).first()
            
            if prefs:
                return prefs.to_dict()
            else:
                # Return defaults if no preferences exist
                return get_default_reading_preferences()
                
    except SQLAlchemyError as e:
        print(f"Error fetching reading preferences for user {user_id}: {e}")
        return get_default_reading_preferences()


def save_reading_preferences(user_id, prefs_dict):
    """
    Save or update reading preferences for a user.
    
    Args:
        user_id: The user's ID
        prefs_dict: Dictionary containing preference values
        
    Returns:
        dict: Saved preferences dictionary or None on error
    """
    try:
        with db_session_scope() as session:
            # Try to find existing preferences
            prefs = session.query(ReadingPreference).filter_by(user_id=user_id).first()
            
            if prefs:
                # Update existing
                prefs.color_mode = prefs_dict.get('color_mode', prefs.color_mode)
                prefs.font_size = prefs_dict.get('font_size', prefs.font_size)
                prefs.line_height = str(prefs_dict.get('line_height', prefs.line_height))
                prefs.font_family = prefs_dict.get('font_family', prefs.font_family)
                prefs.reading_width = prefs_dict.get('reading_width', prefs.reading_width)
                prefs.text_alignment = prefs_dict.get('text_alignment', prefs.text_alignment)
            else:
                # Create new
                defaults = get_default_reading_preferences()
                prefs = ReadingPreference(
                    user_id=user_id,
                    color_mode=prefs_dict.get('color_mode', defaults['color_mode']),
                    font_size=prefs_dict.get('font_size', defaults['font_size']),
                    line_height=str(prefs_dict.get('line_height', defaults['line_height'])),
                    font_family=prefs_dict.get('font_family', defaults['font_family']),
                    reading_width=prefs_dict.get('reading_width', defaults['reading_width']),
                    text_alignment=prefs_dict.get('text_alignment', defaults['text_alignment'])
                )
                session.add(prefs)
            
            session.commit()
            session.refresh(prefs)  # Refresh to get updated timestamps
            return prefs.to_dict()
            
    except SQLAlchemyError as e:
        print(f"Error saving reading preferences for user {user_id}: {e}")
        return None
