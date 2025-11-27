import os
import time
from datetime import datetime, timedelta
import threading

DATA_DIR = 'data'

def cleanup_old_exports(max_age_hours=1):
    """
    Delete export files older than max_age_hours from all user directories.
    This runs in a background thread.
    """
    while True:
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            deleted_count = 0
            
            # Look through all user directories
            users_dir = os.path.join(DATA_DIR, 'users')
            if os.path.exists(users_dir):
                for user_id in os.listdir(users_dir):
                    user_path = os.path.join(users_dir, user_id)
                    
                    # Skip if not a directory
                    if not os.path.isdir(user_path):
                        continue
                    
                    # Check the exports directory for this user
                    exports_dir = os.path.join(user_path, 'exports')
                    if not os.path.exists(exports_dir):
                        continue
                    
                    # Look for .pdf and .epub files
                    for filename in os.listdir(exports_dir):
                        if filename.endswith(('.pdf', '.epub')):
                            file_path = os.path.join(exports_dir, filename)
                            
                            # Skip if it's a directory
                            if os.path.isdir(file_path):
                                continue
                            
                            # Get file modification time
                            file_mtime = os.path.getmtime(file_path)
                            file_age_seconds = current_time - file_mtime
                            
                            # Delete if older than max_age
                            if file_age_seconds > max_age_seconds:
                                try:
                                    os.remove(file_path)
                                    age_hours = file_age_seconds / 3600
                                    print(f"[DELETED] Old export: {user_id}/{filename} (age: {age_hours:.1f}h)")
                                    deleted_count += 1
                                except Exception as e:
                                    print(f"[ERROR] Failed to delete {user_id}/{filename}: {e}")
            
            if deleted_count > 0:
                print(f"[OK] Cleanup complete: deleted {deleted_count} export file(s)")
            
            # Run cleanup every 15 minutes
            time.sleep(15 * 60)
            
        except Exception as e:
            print(f"[ERROR] Error in cleanup_old_exports: {e}")
            import traceback
            traceback.print_exc()
            # Wait before retrying
            time.sleep(60)

def start_cleanup_thread(max_age_hours=1):
    """
    Start the cleanup thread as a daemon.
    This should be called once when the app starts.
    
    Args:
        max_age_hours: Maximum age of export files before deletion (default: 1 hour)
    """
    cleanup_thread = threading.Thread(
        target=cleanup_old_exports, 
        args=(max_age_hours,),
        daemon=True
    )
    cleanup_thread.start()
    print(f"[OK] Export cleanup service started (max age: {max_age_hours} hour(s))")
