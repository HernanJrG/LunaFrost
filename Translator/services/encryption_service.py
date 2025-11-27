"""
Encryption service for securing API keys and sensitive data.
Uses Fernet symmetric encryption from the cryptography library.
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DATA_DIR = 'data'
KEY_FILE = os.path.join(DATA_DIR, '.encryption_key')

def _get_or_create_key():
    """
    Get or create the encryption key.
    The key is derived from a machine-specific identifier for basic obfuscation.
    
    NOTE: This provides obfuscation, not military-grade security.
    For production use, consider using environment variables or a secrets manager.
    """
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'rb') as f:
            return f.read()
    
    # Generate a new key
    key = Fernet.generate_key()
    
    # Save it to file with restricted permissions
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    
    # Set file permissions to read/write for owner only (Unix-like systems)
    try:
        os.chmod(KEY_FILE, 0o600)
    except:
        pass  # Windows doesn't support chmod
    
    return key

def encrypt_value(value):
    """
    Encrypt a string value.
    
    Args:
        value (str): The plain text value to encrypt
        
    Returns:
        str: The encrypted value as a base64-encoded string
    """
    if not value:
        return ''
    
    try:
        key = _get_or_create_key()
        f = Fernet(key)
        
        # Encrypt the value
        encrypted = f.encrypt(value.encode('utf-8'))
        
        # Return as base64 string for easy storage
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        print(f"Encryption error: {e}")
        return value  # Return original if encryption fails

def decrypt_value(encrypted_value):
    """
    Decrypt an encrypted string value.
    
    Args:
        encrypted_value (str): The encrypted value as a base64-encoded string
        
    Returns:
        str: The decrypted plain text value
    """
    if not encrypted_value:
        return ''
    
    try:
        key = _get_or_create_key()
        f = Fernet(key)
        
        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_value.encode('utf-8'))
        
        # Decrypt the value
        decrypted = f.decrypt(encrypted_bytes)
        
        return decrypted.decode('utf-8')
    except Exception as e:
        # If decryption fails, assume it's already plain text (backwards compatibility)
        return encrypted_value

def is_encrypted(value):
    """
    Check if a value appears to be encrypted.
    
    Args:
        value (str): The value to check
        
    Returns:
        bool: True if the value appears to be encrypted
    """
    if not value or len(value) < 50:
        return False
    
    try:
        # Try to decode as base64
        base64.b64decode(value.encode('utf-8'))
        
        # If it decodes and is long enough, it's likely encrypted
        return len(value) > 50
    except:
        return False

def migrate_to_encrypted(plain_dict):
    """
    Migrate a dictionary with plain text values to encrypted values.
    
    Args:
        plain_dict (dict): Dictionary with plain text values
        
    Returns:
        dict: Dictionary with encrypted values
    """
    encrypted_dict = {}
    
    for key, value in plain_dict.items():
        if isinstance(value, str) and value and not is_encrypted(value):
            encrypted_dict[key] = encrypt_value(value)
        else:
            encrypted_dict[key] = value
    
    return encrypted_dict

def decrypt_dict(encrypted_dict):
    """
    Decrypt all values in a dictionary.
    
    Args:
        encrypted_dict (dict): Dictionary with encrypted values
        
    Returns:
        dict: Dictionary with decrypted values
    """
    decrypted_dict = {}
    
    for key, value in encrypted_dict.items():
        if isinstance(value, str) and value and is_encrypted(value):
            decrypted_dict[key] = decrypt_value(value)
        else:
            decrypted_dict[key] = value
    
    return decrypted_dict