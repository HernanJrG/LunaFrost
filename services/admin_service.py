"""
Admin service for authentication and authorization
"""
import os
from flask import request, session


def get_allowed_admin_ips():
    """
    Get list of allowed admin IPs from environment variable.
    
    Returns:
        list: List of allowed IP addresses
    """
    # Format: ADMIN_ALLOWED_IPS=24.88.90.213,192.168.1.100
    allowed_ips_str = os.environ.get('ADMIN_ALLOWED_IPS', '24.88.90.213')
    return [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()]


def get_admin_username():
    """
    Get admin username from environment variable.
    
    Returns:
        str: Admin username (defaults to 'admin')
    """
    return os.environ.get('ADMIN_USERNAME', 'admin')


def get_client_ip(request_obj):
    """
    Get the client's IP address from the request.
    Handles proxies via X-Forwarded-For and X-Real-IP headers.
    
    Args:
        request_obj: Flask request object
    
    Returns:
        str: Client IP address
    """
    # Check for proxy headers first
    if request_obj.headers.get('X-Forwarded-For'):
        # X-Forwarded-For can contain multiple IPs, take the first one
        return request_obj.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    if request_obj.headers.get('X-Real-IP'):
        return request_obj.headers.get('X-Real-IP').strip()
    
    # Fall back to remote_addr
    return request_obj.remote_addr


def is_admin_authorized(request_obj, username):
    """
    Check if the user is authorized to access admin panel.
    """
    # Check IP whitelist
    client_ip = get_client_ip(request_obj)
    allowed_ips = get_allowed_admin_ips()
    
    # TEMPORARY DEBUG - REMOVE AFTER TESTING
    
    if client_ip not in allowed_ips:
        return False
    
    # Check IP whitelist
    client_ip = get_client_ip(request_obj)
    allowed_ips = get_allowed_admin_ips()
    
    if client_ip not in allowed_ips:
        return False
    
    # Check username
    admin_username = get_admin_username()
    
    if not username or username.lower() != admin_username.lower():
        return False
    
    return True


def log_admin_action(username, action, details=None):
    """
    Log admin actions for audit trail.
    
    Args:
        username: Admin username
        action: Action description
        details: Optional additional details
    """
    from datetime import datetime
    
    log_entry = f"[{datetime.now().isoformat()}] ADMIN ({username}): {action}"
    if details:
        log_entry += f" - {details}"
    
    
    # TODO: Consider writing to a dedicated admin log file
    # log_file = os.path.join('data', 'admin_actions.log')
    # with open(log_file, 'a') as f:
    #     f.write(log_entry + '\n')
