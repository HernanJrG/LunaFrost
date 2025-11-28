from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from flask_limiter import Limiter
from models.user import (
    create_user, authenticate_user, initialize_users_file, initialize_password_resets_file,
    request_password_reset, validate_reset_token, reset_password_with_token,
    update_user_email, update_user_password, get_user_info, cleanup_expired_reset_tokens
)
from models.settings import initialize_user_settings_file
from models.novel import initialize_user_data_files
from services.email_service import send_password_reset_email, send_welcome_email, send_email_change_confirmation

auth_bp = Blueprint('auth', __name__)

# Helper to get limiter from app
def get_limiter():
    return current_app.limiter

@auth_bp.before_request
def initialize():
    """Initialize user files on first request"""
    initialize_users_file()
    initialize_password_resets_file()
    cleanup_expired_reset_tokens()

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User signup page - Rate limited to prevent account spam"""
    if request.method == 'GET':
        return render_template('signup.html')
    
    # Apply rate limit for POST requests (5 attempts per minute)
    get_limiter().limit("5 per minute")(lambda: None)()
    
    # POST request - handle signup
    try:
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        password_confirm = data.get('password_confirm', '')
        
        # Validation
        if not username or len(username) < 3:
            return jsonify({'success': False, 'error': 'Username must be at least 3 characters'}), 400
        
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'Invalid email address'}), 400
        
        if not password or len(password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        
        if password != password_confirm:
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400
        
        # Create user
        result = create_user(username, email, password)
        
        if not result['success']:
            return jsonify(result), 400
        
        user_id = result['user_id']
        
        # Initialize user data files
        initialize_user_data_files(user_id)
        initialize_user_settings_file(user_id)
        
        # Send welcome email
        send_welcome_email(email, username)
        
        # Set session
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'redirect': '/'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page - Rate limited to prevent brute-force attacks"""
    if request.method == 'GET':
        return render_template('login.html')
    
    # Apply rate limit for POST requests (5 attempts per minute)
    get_limiter().limit("5 per minute")(lambda: None)()
    
    # POST request - handle login
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password required'}), 400
        
        result = authenticate_user(username, password)
        
        if not result['success']:
            return jsonify(result), 401
        
        # Set session
        session['user_id'] = result['user_id']
        session['username'] = result['username']
        
        return jsonify({
            'success': True,
            'message': 'Logged in successfully',
            'redirect': '/'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page - Rate limited to prevent email spam"""
    if request.method == 'GET':
        return render_template('forgot_password.html')
    
    # Apply rate limit for POST requests (3 attempts per minute)
    get_limiter().limit("3 per minute")(lambda: None)()
    
    # POST request - handle password reset request
    try:
        data = request.json
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email address required'}), 400
        
        # Request password reset
        result = request_password_reset(email)
        
        if result.get('email_found'):
            # Send reset email
            reset_token = result['reset_token']
            user_id = result['user_id']
            send_password_reset_email(email, reset_token, user_id)
        
        # Always return success for security (don't reveal if email exists)
        return jsonify({
            'success': True,
            'message': 'If an account exists with that email, a password reset link has been sent'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Reset password page with token"""
    if request.method == 'GET':
        token = request.args.get('token', '')
        
        # Validate token
        validation = validate_reset_token(token)
        
        if not validation['success']:
            return render_template('reset_password.html', 
                                 success=False, 
                                 error=validation['error'],
                                 token=token)
        
        return render_template('reset_password.html', 
                             success=True, 
                             token=token,
                             email=validation['email'])
    
    # POST request - handle password reset
    try:
        data = request.json
        token = data.get('token', '')
        new_password = data.get('password', '')
        password_confirm = data.get('password_confirm', '')
        
        if not token:
            return jsonify({'success': False, 'error': 'Reset token missing'}), 400
        
        if not new_password or len(new_password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        
        if new_password != password_confirm:
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400
        
        # Reset password
        result = reset_password_with_token(token, new_password)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'redirect': '/auth/login'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/profile', methods=['GET'])
def profile():
    """User profile page"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_info = get_user_info(session['user_id'])
    return render_template('profile.html', user=user_info)

@auth_bp.route('/api/profile', methods=['GET'])
def get_profile():
    """Get current user profile"""
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 401
    
    user_info = get_user_info(session['user_id'])
    return jsonify({'success': True, 'user': user_info})

@auth_bp.route('/api/update-email', methods=['POST'])
def api_update_email():
    """Update user email"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.json
        new_email = data.get('email', '').strip()
        
        if not new_email or '@' not in new_email:
            return jsonify({'success': False, 'error': 'Invalid email address'}), 400
        
        user_id = session['user_id']
        
        # Update email
        result = update_user_email(user_id, new_email)
        
        if not result['success']:
            return jsonify(result), 400
        
        # Send confirmation email
        send_email_change_confirmation(new_email, session.get('username', 'User'))
        
        return jsonify({'success': True, 'message': 'Email updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/api/update-password', methods=['POST'])
def api_update_password():
    """Update user password"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.json
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        password_confirm = data.get('password_confirm', '')
        
        if not old_password:
            return jsonify({'success': False, 'error': 'Current password required'}), 400
        
        if not new_password or len(new_password) < 8:
            return jsonify({'success': False, 'error': 'New password must be at least 8 characters'}), 400
        
        if new_password != password_confirm:
            return jsonify({'success': False, 'error': 'New passwords do not match'}), 400
        
        if old_password == new_password:
            return jsonify({'success': False, 'error': 'New password must be different from current password'}), 400
        
        user_id = session['user_id']
        
        # Update password
        result = update_user_password(user_id, old_password, new_password)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify({'success': True, 'message': 'Password updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/logout')
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/check-auth')
def check_auth():
    """Check if user is logged in"""
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user_id': session['user_id'],
            'username': session.get('username')
        })
    return jsonify({'authenticated': False})
