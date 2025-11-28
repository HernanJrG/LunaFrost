import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta

DATA_DIR = 'data'
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
PASSWORD_RESET_FILE = os.path.join(DATA_DIR, 'password_resets.json')

def initialize_users_file():
    """Initialize users.json if it doesn't exist"""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

def initialize_password_resets_file():
    """Initialize password_resets.json if it doesn't exist"""
    if not os.path.exists(PASSWORD_RESET_FILE):
        with open(PASSWORD_RESET_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"

def verify_password(stored_hash, password):
    """Verify password against stored hash"""
    try:
        salt, pwd_hash = stored_hash.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode(), 100000)
        return new_hash.hex() == pwd_hash
    except:
        return False

def load_users():
    """Load all users from JSON file"""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_password_resets():
    """Load password reset tokens from JSON file"""
    try:
        with open(PASSWORD_RESET_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_password_resets(resets):
    """Save password reset tokens to JSON file"""
    with open(PASSWORD_RESET_FILE, 'w', encoding='utf-8') as f:
        json.dump(resets, f, ensure_ascii=False, indent=2)

def create_user(username, email, password):
    """Create a new user account"""
    users = load_users()
    
    # Check if username already exists
    if username.lower() in users:
        return {'success': False, 'error': 'Username already exists'}
    
    # Check if email already exists
    for user_data in users.values():
        if user_data.get('email', '').lower() == email.lower():
            return {'success': False, 'error': 'Email already registered'}
    
    # Create new user
    user_id = username.lower()
    users[user_id] = {
        'username': username,
        'email': email,
        'password_hash': hash_password(password),
        'created_at': datetime.now().isoformat(),
        'last_login': None,
        'settings': {
            'selected_provider': 'openrouter',
            'api_keys': {
                'openrouter': '',
                'openai': '',
                'google': ''
            },
            'provider_models': {
                'openrouter': 'google/gemini-2.0-flash-001',
                'openai': 'gpt-4',
                'google': 'gemini-2.5-flash'
            },
            'show_covers': True,
            'dark_mode': False,
            'default_sort_order': 'asc',
            'encryption_enabled': True
        }
    }
    
    save_users(users)
    
    # Create user-specific data directory
    user_dir = os.path.join(DATA_DIR, 'users', user_id)
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'images'), exist_ok=True)
    
    # Initialize user's novels file
    novels_file = os.path.join(user_dir, 'novels.json')
    with open(novels_file, 'w', encoding='utf-8') as f:
        json.dump({}, f)
    
    # Initialize user's settings file
    settings_file = os.path.join(user_dir, 'settings.json')
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(users[user_id]['settings'], f, ensure_ascii=False, indent=2)
    
    return {'success': True, 'user_id': user_id, 'message': 'Account created successfully'}

def authenticate_user(username, password):
    """Authenticate user and return session token"""
    users = load_users()
    user_id = username.lower()
    
    if user_id not in users:
        return {'success': False, 'error': 'Invalid username or password'}
    
    user_data = users[user_id]
    
    if not verify_password(user_data['password_hash'], password):
        return {'success': False, 'error': 'Invalid username or password'}
    
    # Update last login
    user_data['last_login'] = datetime.now().isoformat()
    save_users(users)
    
    # Generate session token
    token = secrets.token_urlsafe(32)
    
    return {
        'success': True,
        'token': token,
        'user_id': user_id,
        'username': user_data['username'],
        'email': user_data['email']
    }

def get_user_info(user_id):
    """Get user information"""
    users = load_users()
    
    if user_id not in users:
        return None
    
    user_data = users[user_id]
    return {
        'username': user_data['username'],
        'email': user_data['email'],
        'created_at': user_data.get('created_at'),
        'last_login': user_data.get('last_login')
    }

def update_user_email(user_id, new_email):
    """Update user email address"""
    users = load_users()
    
    if user_id not in users:
        return {'success': False, 'error': 'User not found'}
    
    # Check if new email is already in use
    for other_user_id, user_data in users.items():
        if other_user_id != user_id and user_data.get('email', '').lower() == new_email.lower():
            return {'success': False, 'error': 'Email already in use'}
    
    users[user_id]['email'] = new_email
    save_users(users)
    
    return {'success': True, 'message': 'Email updated successfully'}

def update_user_password(user_id, old_password, new_password):
    """Update user password"""
    users = load_users()
    
    if user_id not in users:
        return {'success': False, 'error': 'User not found'}
    
    user_data = users[user_id]
    
    # Verify old password
    if not verify_password(user_data['password_hash'], old_password):
        return {'success': False, 'error': 'Current password is incorrect'}
    
    # Check new password length
    if len(new_password) < 8:
        return {'success': False, 'error': 'New password must be at least 8 characters'}
    
    # Update password
    user_data['password_hash'] = hash_password(new_password)
    save_users(users)
    
    return {'success': True, 'message': 'Password updated successfully'}

def request_password_reset(email):
    """Generate password reset token for email"""
    users = load_users()
    
    # Find user by email
    user_id = None
    for uid, user_data in users.items():
        if user_data.get('email', '').lower() == email.lower():
            user_id = uid
            break
    
    if not user_id:
        # Return success even if email not found (security best practice)
        return {
            'success': True,
            'message': 'If an account exists with that email, a reset link will be sent',
            'email_found': False
        }
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    
    # Store reset token with expiration (1 hour)
    resets = load_password_resets()
    resets[reset_token] = {
        'user_id': user_id,
        'email': email,
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(hours=1)).isoformat(),
        'used': False
    }
    save_password_resets(resets)
    
    return {
        'success': True,
        'message': 'If an account exists with that email, a reset link will be sent',
        'email_found': True,
        'reset_token': reset_token,
        'user_id': user_id
    }

def validate_reset_token(reset_token):
    """Validate password reset token"""
    resets = load_password_resets()
    
    if reset_token not in resets:
        return {'success': False, 'error': 'Invalid reset token'}
    
    reset_data = resets[reset_token]
    
    # Check if already used
    if reset_data.get('used'):
        return {'success': False, 'error': 'This reset link has already been used'}
    
    # Check if expired
    expires_at = datetime.fromisoformat(reset_data['expires_at'])
    if datetime.now() > expires_at:
        return {'success': False, 'error': 'This reset link has expired. Please request a new one.'}
    
    return {
        'success': True,
        'user_id': reset_data['user_id'],
        'email': reset_data['email']
    }

def reset_password_with_token(reset_token, new_password):
    """Reset password using valid reset token"""
    resets = load_password_resets()
    
    if reset_token not in resets:
        return {'success': False, 'error': 'Invalid reset token'}
    
    reset_data = resets[reset_token]
    
    # Check if already used
    if reset_data.get('used'):
        return {'success': False, 'error': 'This reset link has already been used'}
    
    # Check if expired
    expires_at = datetime.fromisoformat(reset_data['expires_at'])
    if datetime.now() > expires_at:
        return {'success': False, 'error': 'This reset link has expired'}
    
    # Check new password length
    if len(new_password) < 8:
        return {'success': False, 'error': 'Password must be at least 8 characters'}
    
    # Update password
    users = load_users()
    user_id = reset_data['user_id']
    
    if user_id not in users:
        return {'success': False, 'error': 'User not found'}
    
    users[user_id]['password_hash'] = hash_password(new_password)
    save_users(users)
    
    # Mark token as used
    reset_data['used'] = True
    reset_data['used_at'] = datetime.now().isoformat()
    save_password_resets(resets)
    
    return {'success': True, 'message': 'Password reset successfully. Please log in with your new password.'}

def cleanup_expired_reset_tokens():
    """Clean up expired reset tokens"""
    resets = load_password_resets()
    now = datetime.now()
    
    expired_tokens = []
    for token, data in resets.items():
        expires_at = datetime.fromisoformat(data['expires_at'])
        if now > expires_at:
            expired_tokens.append(token)
    
    for token in expired_tokens:
        del resets[token]
    
    if expired_tokens:
        save_password_resets(resets)

def update_user_settings(user_id, new_settings):
    """Update user settings"""
    users = load_users()
    
    if user_id not in users:
        return {'success': False, 'error': 'User not found'}
    
    users[user_id]['settings'].update(new_settings)
    save_users(users)
    
    return {'success': True}

def get_user_settings(user_id):
    """Get user settings"""
    users = load_users()
    
    if user_id not in users:
        return {}
    
    return users[user_id].get('settings', {})
