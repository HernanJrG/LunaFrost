from flask import Blueprint, render_template, request, send_file, redirect, url_for, session
from models.novel import load_novels, get_display_title, sort_chapters_by_number
from models.settings import load_settings
import os
import mimetypes

main_bp = Blueprint('main', __name__)

def get_user_id():
    """Get current user ID from session"""
    return session.get('user_id')

def get_user_images_dir():
    """Get current user's images directory"""
    from models.image_service import get_user_images_dir
    return get_user_images_dir(get_user_id())

DATA_DIR = 'data'

@main_bp.route('/')
def index():
    """Main page showing all novels"""
    user_id = get_user_id()
    novels = load_novels(user_id)
    settings = load_settings(user_id)
    return render_template('index.html', novels=novels, settings=settings, get_display_title=get_display_title)

@main_bp.route('/novel/<novel_id>')
def view_novel(novel_id):
    """View a specific novel and its chapters"""
    user_id = get_user_id()
    novels = load_novels(user_id)
    novel = novels.get(novel_id)
    
    if not novel:
        return "Novel not found", 404
    
    settings = load_settings(user_id)
    
    has_positions = any(ch and 'position' in ch and ch['position'] is not None for ch in novel.get('chapters', []))
    
    if has_positions:
        order = novel.get('sort_order_override') or settings.get('default_sort_order', 'asc')
    else:
        order = novel.get('sort_order_override') or settings.get('default_sort_order', 'asc')
    
    novel['sort_order'] = order
    novel['chapters'] = sort_chapters_by_number(novel['chapters'], order)
    
    return render_template('novel.html', novel=novel, novel_id=novel_id, get_display_title=get_display_title)

@main_bp.route('/chapter/<novel_id>/<int:chapter_index>')
def view_chapter(novel_id, chapter_index):
    """View a specific chapter by index"""
    user_id = get_user_id()
    novels = load_novels(user_id)
    novel = novels.get(novel_id)
    
    if not novel or chapter_index >= len(novel.get('chapters', [])):
        return "Chapter not found", 404
    
    settings = load_settings(user_id)
    
    if 'sort_order_override' in novel and novel['sort_order_override'] is not None:
        order = novel['sort_order_override']
    else:
        order = settings.get('default_sort_order', 'asc')
    
    novel['sort_order'] = order
    novel['chapters'] = sort_chapters_by_number(novel['chapters'], order)
    
    chapter = novel['chapters'][chapter_index]
    
    return render_template(
        'chapter.html', 
        novel=novel, 
        novel_id=novel_id,
        chapter=chapter, 
        chapter_index=chapter_index,
        glossary=novel.get('glossary', {}),
        get_display_title=get_display_title,
        thinking_mode_enabled=settings.get('thinking_mode_enabled', False)
    )

@main_bp.route('/token-usage')
def token_usage_dashboard():
    """Token usage dashboard page"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('auth.login'))
    
    return render_template('token_usage.html')

@main_bp.route('/chapter/<novel_id>/number/<chapter_number>')
def view_chapter_by_number(novel_id, chapter_number):
    """View a specific chapter by chapter number"""
    user_id = get_user_id()
    novels = load_novels(user_id)
    novel = novels.get(novel_id)
    
    if not novel:
        return "Novel not found", 404
    
    settings = load_settings(user_id)
    
    if 'sort_order_override' in novel and novel['sort_order_override'] is not None:
        order = novel['sort_order_override']
    else:
        order = settings.get('default_sort_order', 'asc')
    
    novel['sort_order'] = order
    novel['chapters'] = sort_chapters_by_number(novel['chapters'], order)
    
    chapter_index = None
    for idx, chapter in enumerate(novel['chapters']):
        if chapter and str(chapter.get('chapter_number')) == str(chapter_number):
            chapter_index = idx
            break
    
    if chapter_index is None:
        return "Chapter not found", 404
    
    return redirect(url_for('main.view_chapter', novel_id=novel_id, chapter_index=chapter_index))

@main_bp.route('/settings')
def settings_page():
    """Global settings page"""
    user_id = get_user_id()
    settings = load_settings(user_id)
    return render_template('settings.html', settings=settings)

@main_bp.route('/novel/<novel_id>/settings')
def novel_settings_page(novel_id):
    """Per-novel settings page"""
    user_id = get_user_id()
    novels = load_novels(user_id)
    novel = novels.get(novel_id)
    
    if not novel:
        return "Novel not found", 404
    
    glossary = novel.get('glossary', {})
    chapter_index = request.args.get('chapter', type=int)
    
    # Sort chapters to match frontend display
    settings = load_settings(user_id)
    if 'sort_order_override' in novel and novel['sort_order_override'] is not None:
        order = novel['sort_order_override']
    else:
        order = settings.get('default_sort_order', 'asc')
        
    novel['chapters'] = sort_chapters_by_number(novel['chapters'], order)
    
    # Get the chapter if chapter_index is provided
    chapter = None
    if chapter_index is not None and chapter_index < len(novel.get('chapters', [])):
        chapter = novel['chapters'][chapter_index]
    
    show_delete_novel = chapter_index is None
    
    return render_template(
        'novel_settings.html', 
        novel=novel, 
        novel_id=novel_id, 
        glossary=glossary, 
        chapter_index=chapter_index,
        chapter=chapter,  # Add this line
        show_delete_novel=show_delete_novel,
        get_display_title=get_display_title
    )

    """Per-novel settings page"""
    user_id = get_user_id()
    novels = load_novels(user_id)
    novel = novels.get(novel_id)
    
    if not novel:
        return "Novel not found", 404
    
    glossary = novel.get('glossary', {})
    chapter_index = request.args.get('chapter', type=int)
    
    show_delete_novel = chapter_index is None
    
    return render_template(
        'novel_settings.html', 
        novel=novel, 
        novel_id=novel_id, 
        glossary=glossary, 
        chapter_index=chapter_index,
        show_delete_novel=show_delete_novel,
        get_display_title=get_display_title
    )

@main_bp.route('/images/<filename>')
def serve_image(filename):
    """Serve user-specific images"""
    user_id = session.get('user_id')
    
    print(f"\n🔍 serve_image called")
    print(f"   filename: {filename}")
    print(f"   user_id: {user_id}")
    
    # If not logged in, return 404
    if not user_id:
        print(f"   ❌ Not authenticated")
        return "Not authenticated", 401
    
    try:
        from services.image_service import get_user_images_dir
        images_dir = get_user_images_dir(user_id)
        img_path = os.path.join(images_dir, filename)
        
        print(f"   images_dir: {images_dir}")
        print(f"   img_path: {img_path}")
        print(f"   img_path exists: {os.path.exists(img_path)}")
        
        # Security check: make sure the path is within the user's images directory
        abs_img_path = os.path.abspath(img_path)
        abs_images_dir = os.path.abspath(images_dir)
        
        print(f"   abs_img_path: {abs_img_path}")
        print(f"   abs_images_dir: {abs_images_dir}")
        print(f"   path is safe: {abs_img_path.startswith(abs_images_dir)}")
        
        if not abs_img_path.startswith(abs_images_dir):
            print(f"   ❌ Security check failed - path outside images directory")
            return "Forbidden", 403
        
        if not os.path.exists(img_path):
            print(f"   ❌ File not found")
            return "Image not found", 404
        
        content_type = mimetypes.guess_type(filename)[0]
        
        if not content_type:
            print(f"   🔍 Guessing content type from file header")
            with open(img_path, 'rb') as f:
                header = f.read(12)
                if header[:8] == b'\x89PNG\r\n\x1a\n':
                    content_type = 'image/png'
                elif header[:3] == b'\xff\xd8\xff':
                    content_type = 'image/jpeg'
                elif header[:6] in (b'GIF87a', b'GIF89a'):
                    content_type = 'image/gif'
                elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                    content_type = 'image/webp'
                else:
                    content_type = 'image/jpeg'
        
        print(f"   content_type: {content_type}")
        print(f"   ✓ Serving image successfully")
        return send_file(img_path, mimetype=content_type)
        
    except FileNotFoundError as e:
        print(f"   ❌ FileNotFoundError: {e}")
        return "Image not found", 404
    except Exception as e:
        print(f"   ❌ Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return "Error serving image", 500
