from flask import Flask, session
from dotenv import load_dotenv
import os
import secrets
import re


# Load .env
load_dotenv()


def create_app():
    app = Flask(__name__, template_folder='pages')
    
    # Set secret key for sessions (from env, then .env, then generate)
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        secret_key = secrets.token_hex(32)
    app.secret_key = secret_key
    
    # Create data directories
    DATA_DIR = 'data'
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'users'), exist_ok=True)
    
    # Initialize database schema (auto-creates tables from models)
    from database.database import init_db
    init_db()
    
    # Initialize user management
    from models.user import initialize_users_file, initialize_password_resets_file
    initialize_users_file()
    initialize_password_resets_file()
    
    # Start the export cleanup service
    from services.cleanup_service import start_cleanup_thread
    start_cleanup_thread()
    
    # Initialize rate limiter (protects against brute-force attacks)
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        storage_uri=os.getenv('REDIS_URL', 'redis://redis:6379/0'),
        default_limits=[]  # No default limits, apply per-route
    )
    
    # Middleware to check authentication for main routes
    @app.before_request
    def check_authentication():
        from flask import request, redirect, url_for
        
        # Routes that don't require authentication
        no_auth_required = [
            'auth.login', 
            'auth.signup', 
            'auth.forgot_password',
            'auth.reset_password',
            'static', 
            'auth.check_auth',
            'main.about',
            'main.contact'
        ]
        
        if request.endpoint and request.endpoint not in no_auth_required:
            # If not on auth routes and not authenticated, redirect to login
            if 'user_id' not in session and request.endpoint:
                if not request.endpoint.startswith('auth.') and not request.endpoint.startswith('static'):
                    return redirect(url_for('auth.login'))
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.main_routes import main_bp
    from routes.api_routes import api_bp
    
    # Store limiter in app config so routes can access it
    app.limiter = limiter
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register admin blueprint
    from routes.admin_routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    @app.template_filter('regex_search')
    def regex_search(text, pattern):
        """Check if text matches regex pattern"""
        if not text:
            return False
        return bool(re.search(pattern, str(text)))
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Get port from environment variable, default to 5000
    port = int(os.getenv('PORT', 5000))
    
    # Get host from environment variable, default to 0.0.0.0
    host = os.getenv('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=False)