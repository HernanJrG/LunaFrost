from flask import Blueprint, request, jsonify, send_file, session
from datetime import datetime
from models.novel import (
    load_novels, save_novels, get_novel_glossary, 
    save_novel_glossary, delete_novel, delete_chapter, sort_chapters_by_number
)
from models.settings import load_settings, save_settings
from services.ai_service import translate_text, detect_characters, translate_names, detect_character_genders
from services.image_service import download_image, extract_images_from_content, delete_images_for_chapter, get_user_images_dir
from services.export_service import export_to_epub, export_to_pdf
from services.token_usage_service import save_token_usage, estimate_translation_tokens
from services.pricing_service import (
    calculate_cost, format_cost, get_model_pricing,
    get_model_pricing_with_key, fetch_openrouter_pricing_with_key,
    fetch_openrouter_raw_with_key, get_cached_openrouter_pricing
)
import os
import re
import hashlib
import threading

api_bp = Blueprint('api', __name__)

def get_user_id():
    """Get current user ID from session"""
    return session.get('user_id')

# Simple in-memory cache for recent translations
translation_cache = {}
MAX_CACHE_SIZE = 100
DEBUG_LOGS = []

def get_cache_key(text):
    """Generate a cache key for text"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# Per-user semaphores to control concurrent imports
user_import_semaphores = {}
user_semaphore_lock = threading.Lock()

def get_user_import_semaphore(user_id, max_concurrent=3):
    """
    Get or create a semaphore for a user to limit concurrent imports.
    
    Args:
        user_id: User ID
        max_concurrent: Maximum concurrent imports allowed (default: 3)
    
    Returns:
        threading.Semaphore: Semaphore for this user
    """
    with user_semaphore_lock:
        if user_id not in user_import_semaphores:
            user_import_semaphores[user_id] = threading.Semaphore(max_concurrent)
        return user_import_semaphores[user_id]

def slugify_english(text):
    """Slugify English text for URLs"""
    if not text:
        return 'unknown_novel'
    
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    text = text.strip('-')
    
    return text or 'unknown_novel'

def find_novel_by_korean_title(novels, korean_title):
    """Find a novel by its Korean title, return novel_id if found"""
    if not korean_title:
        return None
    
    korean_title = korean_title.strip()
    
    for novel_id, novel in novels.items():
        if novel.get('title') == korean_title:
            return novel_id
    
    return None

def find_novel_by_source_url(novels, source_url):
    """Find a novel by its source URL, return novel_id if found"""
    if not source_url:
        return None
    
    # Normalize URL (remove trailing slash, query params)
    source_url = source_url.split('?')[0].rstrip('/')
    
    for novel_id, novel in novels.items():
        novel_url = novel.get('novel_source_url', '')
        if novel_url:
            novel_url = novel_url.split('?')[0].rstrip('/')
            if novel_url == source_url:
                return novel_id
            
            # Also check if one is a substring of the other (for safety)
            # e.g. https://novelpia.com/novel/123 vs https://novelpia.com/novel/123/
            if len(source_url) > 20 and len(novel_url) > 20:
                if source_url in novel_url or novel_url in source_url:
                    return novel_id
    
    return None

def recalculate_all_positions(chapters):
    """
    Recalculate positions for all chapters.
    
    LOGIC:
    1. If all chapters have UNIQUE positions: sort by position (batch import)
    2. If there are conflicts or missing positions: sort by chapter number, append BONUS
    """
    if not chapters:
        return chapters
    
    # Filter out None chapters
    chapters_list = [ch for ch in chapters if ch]
    
    # Check if ALL chapters have positions
    all_have_positions = all(
        ch.get('position') is not None and isinstance(ch.get('position'), int) 
        for ch in chapters_list
    )
    
    # Check for position conflicts (duplicates)
    has_conflicts = False
    if all_have_positions:
        positions = [ch.get('position') for ch in chapters_list]
        if len(positions) != len(set(positions)):
            has_conflicts = True
    
    if all_have_positions and not has_conflicts:
        # Simple sort by position - trust the batch import order completely
        sorted_chapters = sorted(chapters_list, key=lambda ch: ch.get('position', 999999))
    else:
        # Separate chapters with and without positions
        chapters_with_pos = [ch for ch in chapters_list if ch.get('position') is not None]
        chapters_without_pos = [ch for ch in chapters_list if ch.get('position') is None]
        
        if len(chapters_with_pos) > 0 and len(chapters_without_pos) > 0:
            # Sort chapters with positions first
            sorted_base = sorted(chapters_with_pos, key=lambda ch: ch.get('position', 999999))
            
            # Insert chapters without positions based on their chapter_number
            for ch_without in chapters_without_pos:
                is_bonus = ch_without.get('is_bonus') or ch_without.get('chapter_number') == 'BONUS'
                
                if is_bonus:
                    sorted_base.append(ch_without)
                else:
                    try:
                        ch_num = int(ch_without.get('chapter_number'))
                        
                        # Find the insertion point
                        insert_idx = len(sorted_base)
                        for idx, existing_ch in enumerate(sorted_base):
                            if existing_ch.get('is_bonus'):
                                continue
                            try:
                                existing_num = int(existing_ch.get('chapter_number'))
                                if ch_num < existing_num:
                                    insert_idx = idx
                                    break
                            except (ValueError, TypeError):
                                continue
                        
                        sorted_base.insert(insert_idx, ch_without)
                    except (ValueError, TypeError):
                        sorted_base.append(ch_without)
            
            sorted_chapters = sorted_base
        else:
            # Fallback: Sort regular chapters by number, BONUS at end
            regular_chapters = []
            bonus_chapters = []
            
            for ch in chapters_list:
                is_bonus = ch.get('is_bonus') or ch.get('chapter_number') == 'BONUS'
                
                if is_bonus:
                    bonus_chapters.append(ch)
                else:
                    regular_chapters.append(ch)
            
            # Sort regular chapters by chapter_number
            def get_chapter_num(ch):
                try:
                    num = ch.get('chapter_number')
                    if num == 'BONUS':
                        return 999999
                    return int(num) if num else 999999
                except (ValueError, TypeError):
                    return 999999
                                
            regular_chapters.sort(key=get_chapter_num)
            
            # Insert BONUS chapters in the right places based on their positions
            sorted_chapters = []
            bonus_inserted = set()
            
            for idx, reg_ch in enumerate(regular_chapters):
                sorted_chapters.append(reg_ch)
                
                for bonus_idx, bonus_ch in enumerate(bonus_chapters):
                    if bonus_idx in bonus_inserted:
                        continue
                    
                    bonus_pos = bonus_ch.get('position')
                    
                    if bonus_pos is not None:
                        reg_before = sum(1 for r in regular_chapters if r.get('position') is not None and r.get('position') < bonus_pos)
                        
                        if len([c for c in sorted_chapters if not c.get('is_bonus')]) == reg_before:
                            sorted_chapters.append(bonus_ch)
                            bonus_inserted.add(bonus_idx)
            
            # Add remaining BONUS at the end
            for bonus_idx, bonus_ch in enumerate(bonus_chapters):
                if bonus_idx not in bonus_inserted:
                    sorted_chapters.append(bonus_ch)
    
    # Assign sequential positions
    for idx, ch in enumerate(sorted_chapters):
        ch['position'] = idx
    
    return sorted_chapters

@api_bp.route('/import-chapter', methods=['POST'])
def import_chapter():
    """API endpoint to import a new chapter from the browser extension"""
    try:
        user_id = get_user_id()
        data = request.json
        
        # Get concurrent import limit from request (sent by extension)
        # Default to 3 if not provided, clamp between 1-10 for safety
        max_concurrent = data.get('max_concurrent_imports', 3)
        max_concurrent = max(1, min(10, max_concurrent))
        
        # Get user's import semaphore
        semaphore = get_user_import_semaphore(user_id, max_concurrent)
        
        # Try to acquire semaphore (non-blocking)
        if not semaphore.acquire(blocking=False):
            return jsonify({
                'success': False,
                'error': f'Too many concurrent imports. Maximum allowed: {max_concurrent}. Please wait for current imports to complete.',
                'error_code': 'RATE_LIMIT_EXCEEDED'
            }), 429
        
        try:  # Inner try block for the actual import logic
            # Extract data
            original_title = data.get('original_title', '')
            # Helper to check for Korean
            has_korean = lambda text: bool(re.search(r'[\uac00-\ud7a3]', text)) if text else False
            # Check if it's a novel overview page (no chapter content)
            is_novel_page = False
            url_for_detection = source_url or novel_source_url or ''
            if url_for_detection:
                is_novel_page = '/novel/' in url_for_detection and '/viewer/' not in url_for_detection
            if not content and not is_novel_page:
                return jsonify({'error': 'No content provided'}), 400
            # Check if chapter already exists - REMOVED (handled by atomic import)
            novels = load_novels(user_id)
              # Try to find existing novel by Korean title FIRST (Most reliable)
            novel_id = find_novel_by_korean_title(novels, original_title)
            # If not found, try by Source URL
            if not novel_id:
                novel_id = find_novel_by_source_url(novels, novel_source_url)
            
            # Translate novel metadata
            novel_translated_title = translated_title_from_extension
            translated_author = data.get('author', '')
            translated_tags = data.get('tags', [])[:] 
            translated_synopsis = data.get('synopsis', '')
            author = data.get('author', '')
            tags = data.get('tags', [])
            synopsis = data.get('synopsis', '')
            
            # Find existing novel FIRST to avoid re-translating title
            if not novel_id:
                 novel_id = find_novel_by_korean_title(novels, original_title)
            if not novel_id:
                novel_id = find_novel_by_source_url(novels, novel_source_url)

            # Skip translations if skip_translation is True (batch import mode)
            if skip_translation:
                # Use Korean titles as-is, no translation
                if not novel_translated_title:
                    novel_translated_title = original_title
                translated_author = author
                translated_tags = tags
                translated_synopsis = synopsis
            elif api_key:
                print(f"DEBUG: Attempting translation with provider: {provider}")
                try:
                    # Translate novel title with caching
                    should_translate_title = True
                    
                    # If novel exists and has a valid translation, use it
                    if novel_id and novels[novel_id].get('translated_title'):
                        existing_trans = novels[novel_id].get('translated_title')
                        # If existing translation is different from original AND doesn't have Korean, keep it
                        if existing_trans != original_title and not has_korean(existing_trans):
                            novel_translated_title = existing_trans
                            should_translate_title = False
                    
                    # If the incoming title has Korean, force translation
                    if novel_translated_title and has_korean(novel_translated_title):
                        should_translate_title = True
                        novel_translated_title = None

                    if should_translate_title and not novel_translated_title and original_title:
                        cache_key = get_cache_key(f"title:{original_title}")
                        if cache_key in translation_cache:
                            novel_translated_title = translation_cache[cache_key]
                        else:
                            translated_title_result = translate_text(
                                original_title, provider, api_key, selected_model,
                                glossary=None, images=None
                            )
                            if not translated_title_result.startswith("Error") and not translated_title_result.startswith(provider.capitalize()):
                                novel_translated_title = translated_title_result
                                translation_cache[cache_key] = novel_translated_title
                                if len(translation_cache) > MAX_CACHE_SIZE:
                                    translation_cache.pop(next(iter(translation_cache)))
                    
                    # Translate author with caching
                    if author:
                        cache_key = get_cache_key(f"author:{author}")
                        if cache_key in translation_cache:
                            translated_author = translation_cache[cache_key]
                        else:
                            translated_author_result = translate_text(
                                author, provider, api_key, selected_model,
                                glossary=None, images=None
                            )
                            if not translated_author_result.startswith("Error") and not translated_author_result.startswith(provider.capitalize()):
                                translated_author = translated_author_result
                                translation_cache[cache_key] = translated_author
                                if len(translation_cache) > MAX_CACHE_SIZE:
                                    translation_cache.pop(next(iter(translation_cache)))
                    
                    # Translate tags
                    if tags:
                        tags_text = ', '.join(tags)
                        translated_tags_result = translate_text(
                            tags_text, provider, api_key, selected_model,
                            glossary=None, images=None
                        )
                        if not translated_tags_result.startswith("Error") and not translated_tags_result.startswith(provider.capitalize()):
                            translated_tags_text = translated_tags_result
                            translated_tags = [tag.strip() for tag in translated_tags_text.split(',')]
                    
                    # Translate synopsis
                    if synopsis:
                        translated_synopsis_result = translate_text(
                            synopsis, provider, api_key, selected_model,
                            glossary=None, images=None
                        )
                        if not translated_synopsis_result.startswith("Error") and not translated_synopsis_result.startswith(provider.capitalize()):
                            translated_synopsis = translated_synopsis_result
                
                except Exception as e:
                    pass
            
            # Use original title if translation failed
            if not novel_translated_title:
                novel_translated_title = original_title
            
            # Update data with translations
            data['translated_title'] = novel_translated_title
            data['translated_author'] = translated_author
            data['translated_tags'] = translated_tags
            data['translated_synopsis'] = translated_synopsis
            data['translated_chapter_title'] = translated_chapter_title
            
            # Call process_chapter_import (Atomic)
            from services.import_service import process_chapter_import
            result = process_chapter_import(user_id, data)
            
            if result.get('success'):
                if result.get('already_exists'):
                     return jsonify(result)
                
                # Queue auto-translation if requested
                translation_queued = False
                if (auto_translate_title or auto_translate_content) and not skip_translation and api_key:
                    try:
                        from tasks.translation_tasks import translate_chapter_task, translate_chapter_title_task
                        
                        chapter_id = result.get('chapter_id')
                        chapter_index = result.get('chapter_index')
                        
                        # Determine what to translate
                        translate_title_only = auto_translate_title and not auto_translate_content
                        translate_both = auto_translate_title and auto_translate_content
                        translate_content_only = auto_translate_content and not auto_translate_title
                            
                        print(f"[AUTO-TRANSLATE] Queueing translation for chapter {chapter_index}")
                        print(f"[AUTO-TRANSLATE] auto_translate_title={auto_translate_title}, auto_translate_content={auto_translate_content}, skip_translation={skip_translation}")
                        
                        # Queue appropriate translation task
                        if translate_title_only and chapter_id:
                            # Title only - use faster title-only task
                            task = translate_chapter_title_task.delay(
                                user_id=user_id,
                                novel_id=result['novel_id'],
                                chapter_id=chapter_id
                            )
                            print(f"[AUTO-TRANSLATE] ✅ Queued title-only translation task {task.id}")
                            translation_queued = True
                        elif translate_content_only:
                            # Content only
                            if chapter_id:
                                task = translate_chapter_task.delay(
                                    user_id=user_id,
                                    novel_id=result['novel_id'],
                                    chapter_id=chapter_id,
                                    translate_content=True,
                                    translate_title=False
                                )
                            else:
                                task = translate_chapter_task.delay(
                                    user_id=user_id,
                                    novel_id=result['novel_id'],
                                    chapter_index=chapter_index,
                                    translate_content=True,
                                    translate_title=False
                                )
                            print(f"[AUTO-TRANSLATE] ✅ Queued content-only translation task {task.id}")
                            translation_queued = True
                        elif translate_both:
                            # Both title and content
                            if chapter_id:
                                task = translate_chapter_task.delay(
                                    user_id=user_id,
                                    novel_id=result['novel_id'],
                                    chapter_id=chapter_id,
                                    translate_content=True,
                                    translate_title=True
                                )
                            else:
                                task = translate_chapter_task.delay(
                                    user_id=user_id,
                                    novel_id=result['novel_id'],
                                    chapter_index=chapter_index,
                                    translate_content=True,
                                    translate_title=True
                                )
                            print(f"[AUTO-TRANSLATE] ✅ Queued full translation task (title + content) {task.id}")
                            translation_queued = True
                            
                    except Exception as e:
                        print(f"[AUTO-TRANSLATE] ❌ Failed to queue translation: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[AUTO-TRANSLATE] Skipping...")  
                
                return jsonify({  # ← Should be 16 spaces (same level as 'if auto_translate_content')
                    'success': True,
                    'message': 'Chapter imported successfully',
                    'novel_id': result['novel_id'],
                    'chapter_index': result['chapter_index'],
                    'chapter_url': f'http://localhost:5000/chapter/{result["novel_id"]}/{result["chapter_index"]}',
                    'translated_title': novel_translated_title,
                    'images_count': 0,
                    'translation_queued': translation_queued
                })
            else:
                return jsonify({'error': result.get('error')}), 500
        
        except Exception as e:  # This matches the try at line 245
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            # Always release the semaphore
            semaphore.release()
    
    except Exception as e:  # This matches the outer try
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/check-chapter-translation', methods=['GET'])
def check_chapter_translation():
    """Check if a chapter has been translated (for polling)"""
    import sys
    
    def log(msg):
        """Log to stdout (Docker container)"""
        print(f"[CHECK-TRANSLATION] {msg}", flush=True)
        sys.stdout.flush()
    
    try:
        user_id = get_user_id()
        novel_id = request.args.get('novel_id')
        chapter_index = request.args.get('chapter_index')
        
        log(f"Request received: novel_id={novel_id}, chapter_index={chapter_index}, user_id={user_id}")
        
        if not novel_id or chapter_index is None:
            log("ERROR: Missing parameters")
            return jsonify({'error': 'Missing parameters'}), 400
        
        try:
            chapter_index = int(chapter_index)
        except ValueError:
            log(f"ERROR: Invalid chapter index: {chapter_index}")
            return jsonify({'error': 'Invalid chapter index'}), 400
        
        # Get chapter from database
        from models.db_novel import get_novel_with_chapters_db
        from models.novel import sort_chapters_by_number
        from models.settings import load_settings
        
        log(f"Loading novel: {novel_id}")
        novel = get_novel_with_chapters_db(user_id, novel_id)
        if not novel or not novel.get('chapters'):
            log(f"ERROR: Novel not found: {novel_id}")
            return jsonify({'error': 'Novel not found'}), 404
        
        log(f"Novel loaded, total chapters: {len(novel.get('chapters', []))}")
        
        # Sort chapters to match frontend display
        settings = load_settings(user_id)
        if 'sort_order_override' in novel and novel['sort_order_override'] is not None:
            order = novel['sort_order_override']
        else:
            order = settings.get('default_sort_order', 'asc')
        
        log(f"Sorting chapters with order: {order}")
        sorted_chapters = sort_chapters_by_number(novel['chapters'], order)
        
        if chapter_index >= len(sorted_chapters):
            log(f"ERROR: Chapter index {chapter_index} out of range (max: {len(sorted_chapters)-1})")
        chapter = sorted_chapters[chapter_index]
        log(f"Chapter found: id={chapter.get('id')}, title={chapter.get('title', 'N/A')[:50]}")
        
        # Check if chapter has translation
        has_translation = bool(chapter.get('translated_content'))
        translation_status = chapter.get('translation_status', 'none')
        
        log(f"Translation status: has_translation={has_translation}, status={translation_status}")
        
        if has_translation:
            content_length = len(chapter.get('translated_content', ''))
            log(f"✅ Translation available! Content length: {content_length}")
        else:
            log(f"⏳ No translation yet. Status: {translation_status}")
        
        response = {
            'success': True,
            'translated': has_translation,
            'translation_status': translation_status,
            'chapter_id': chapter.get('id'),
            'translated_title': chapter.get('translated_title'),
            'translated_content': chapter.get('translated_content') if has_translation else None,
            'translation_model': chapter.get('translation_model')
        }
        
        log(f"Returning response: translated={response['translated']}, status={response['translation_status']}")
        return jsonify(response)
        
    except Exception as e:
        import traceback
        log(f"ERROR: Exception occurred: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/batch-import-chapters', methods=['POST'])
def batch_import_chapters():
    """
    Batch import multiple chapters in one request with optimized parallel processing.
    Uses parallel image downloads and efficient database operations for 4x speed improvement.
    """
    try:
        from services.import_service import process_batch_chapter_import
        
        user_id = get_user_id()
        data = request.json
        chapters = data.get('chapters', [])
        
        if not chapters or not isinstance(chapters, list):
            return jsonify({
                'success': False, 
                'error': 'Invalid chapters array'
            }), 400
        
        # Use optimized batch import function
        result = process_batch_chapter_import(user_id, chapters)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/export/<novel_id>/<format>')
def export_novel(novel_id, format):
    """Export novel to PDF or EPUB"""
    try:
        user_id = get_user_id()
        novels = load_novels(user_id)
        if novel_id not in novels:
            return jsonify({'error': 'Novel not found'}), 404
        
        novel = novels[novel_id]
        
        if format == 'pdf':
            file_path = export_to_pdf(novel_id, novel, user_id)
        elif format == 'epub':
            file_path = export_to_epub(novel_id, novel, user_id)
        else:
            return jsonify({'error': 'Invalid format. Use pdf or epub'}), 400
        
        if file_path and os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'Export failed. Make sure required libraries are installed.'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/translate', methods=['POST'])
def translate():
    """API endpoint to translate Korean text"""
    try:
        user_id = get_user_id()
        data = request.json
        text = data.get('text', '')
        novel_id = data.get('novel_id', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        settings = load_settings(user_id)
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        # Handle Thinking Mode
        use_thinking_mode = data.get('use_thinking_mode', False)
        if use_thinking_mode:
            thinking_models = settings.get('thinking_mode_models', {})
            thinking_model = thinking_models.get(provider)
            if thinking_model:
                selected_model = thinking_model
        
        glossary = get_novel_glossary(user_id, novel_id) if novel_id else {}
        images = data.get('images', [])
        chapter_id = data.get('chapter_id')  # Optional chapter ID for token tracking
        
        result = translate_text(text, provider, api_key, selected_model, glossary, images, is_thinking_mode=use_thinking_mode)
        
        # Handle new dict return format
        if isinstance(result, dict):
            if result.get('error'):
                return jsonify({
                    'success': False,
                    'error': result['error'],
                    'translated_text': None
                }), 500
            
            translated_text = result.get('translated_text', '')
            token_usage_data = result.get('token_usage')
            
            # Calculate cost if pricing is available
            cost_info = None
            if token_usage_data:
                cost_info = calculate_cost(
                    token_usage_data.get('input_tokens', 0),
                    token_usage_data.get('output_tokens', 0),
                    token_usage_data.get('provider', provider),
                    token_usage_data.get('model', selected_model)
                )
            
            # Save token usage if available and chapter_id provided
            if token_usage_data and chapter_id:
                try:
                    save_token_usage(
                        user_id=user_id,
                        chapter_id=chapter_id,
                        provider=token_usage_data.get('provider', provider),
                        model=token_usage_data.get('model', selected_model),
                        input_tokens=token_usage_data.get('input_tokens', 0),
                        output_tokens=token_usage_data.get('output_tokens', 0),
                        total_tokens=token_usage_data.get('total_tokens', 0),
                        translation_type='content'
                    )
                except Exception as e:
                    print(f"Error saving token usage: {e}")
                    # Don't fail the translation if token saving fails
            
            return jsonify({
                'success': True,
                'translated_text': translated_text,
                'model_used': selected_model,
                'token_usage': token_usage_data,
                'cost_info': cost_info
            })
        else:
            # Backward compatibility: if it's still a string (shouldn't happen with new code)
            return jsonify({
                'success': True,
                'translated_text': result if isinstance(result, str) else '',
                'model_used': selected_model,
                'token_usage': None
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/save-translation', methods=['POST'])
def save_translation():
    """Save translated text for a chapter"""
    try:
        from models.database import db_session_scope
        from models.db_models import Chapter
        from models.settings import load_settings
        from models.novel import sort_chapters_by_number, get_novel_with_chapters_db
        
        user_id = get_user_id()
        data = request.json
        novel_id = data.get('novel_id')
        chapter_index = data.get('chapter_index')
        translated_text = data.get('translated_text', '')
        translation_model = data.get('translation_model', '')
        
        # Get novel with chapters as dict (includes sort_order_override)
        novel = get_novel_with_chapters_db(user_id, novel_id)
        if not novel or not novel.get('chapters'):
            return jsonify({'error': 'Novel not found'}), 404
        
        # Apply the same sorting as the frontend to ensure index matches
        settings = load_settings(user_id)
        if 'sort_order_override' in novel and novel['sort_order_override'] is not None:
            order = novel['sort_order_override']
        else:
            order = settings.get('default_sort_order', 'asc')
        
        # Sort chapters to match frontend display
        sorted_chapters = sort_chapters_by_number(novel['chapters'], order)
        
        if chapter_index >= len(sorted_chapters):
            return jsonify({'error': 'Chapter index out of range'}), 404
        
        # Get the actual chapter ID from the sorted list
        target_chapter_id = sorted_chapters[chapter_index]['id']
        
        # Update the chapter in database
        with db_session_scope() as session:
            chapter = session.query(Chapter).filter_by(id=target_chapter_id).first()
            if not chapter:
                return jsonify({'error': 'Chapter not found'}), 404
            
            # Update the translated_content field
            chapter.translated_content = translated_text
            if translation_model:
                chapter.translation_model = translation_model
            session.flush()
            
        return jsonify({'success': True, 'message': 'Translation saved'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/chapter/<chapter_id>/token-usage', methods=['GET'])
def get_chapter_token_usage(chapter_id):
    """Get token usage for a specific chapter"""
    try:
        from services.token_usage_service import get_chapter_token_usage
        user_id = get_user_id()
        
        # Verify chapter belongs to user
        from models.db_novel import get_chapter_db
        chapter = get_chapter_db(chapter_id)
        if not chapter or chapter.novel.user_id != user_id:
            return jsonify({'error': 'Chapter not found'}), 404
        
        records = get_chapter_token_usage(chapter_id)
        
        # Calculate costs for each record
        token_usage_with_costs = []
        for record in records:
            record_dict = record.to_dict()
            cost_info = calculate_cost(
                record.input_tokens,
                record.output_tokens,
                record.provider,
                record.model
            )
            record_dict['cost_info'] = cost_info if cost_info and cost_info.get('pricing_available') else None
            token_usage_with_costs.append(record_dict)
        
        return jsonify({
            'success': True,
            'token_usage': token_usage_with_costs
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/novel/<novel_id>/token-usage', methods=['GET'])
def get_novel_token_usage(novel_id):
    """Get token usage for all chapters in a novel"""
    try:
        from services.token_usage_service import get_novel_token_usage
        user_id = get_user_id()
        
        stats = get_novel_token_usage(novel_id, user_id)
        return jsonify({
            'success': True,
            'token_usage': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/token-usage/stats', methods=['GET'])
def get_token_usage_stats():
    """Get user's token usage statistics"""
    try:
        from services.token_usage_service import (
            get_user_token_usage, get_token_usage_by_provider,
            get_token_usage_by_model, get_recent_token_usage
        )
        from datetime import datetime, timedelta
        
        user_id = get_user_id()
        
        # Get date range if provided
        days = request.args.get('days', 30, type=int)
        start_date = None
        end_date = None
        
        if days:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        # Get all-time stats
        all_time = get_user_token_usage(user_id)
        
        # Get this month stats
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)
        this_month = get_user_token_usage(user_id, month_start, now)
        
        # Get this week stats
        week_start = now - timedelta(days=now.weekday())
        this_week = get_user_token_usage(user_id, week_start, now)
        
        # Get breakdowns
        by_provider = get_token_usage_by_provider(user_id, start_date, end_date)
        by_model = get_token_usage_by_model(user_id, start_date, end_date)
        recent = get_recent_token_usage(user_id, days=30)
        
        # For model breakdown, calculate costs
        model_costs = {}
        for model, model_stats in by_model.items():
            provider = model_stats.get('provider', 'openrouter')
            cost_info = calculate_cost(
                model_stats['input_tokens'],
                model_stats['output_tokens'],
                provider,
                model
            )
            model_costs[model] = cost_info if cost_info and cost_info.get('pricing_available') else None
        
        return jsonify({
            'success': True,
            'stats': {
                'all_time': all_time,
                'this_month': this_month,
                'this_week': this_week,
                'by_provider': by_provider,
                'by_model': by_model,
                'recent_daily': recent,
                'model_costs': model_costs
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/translate/estimate', methods=['POST'])
def estimate_translation_tokens_endpoint():
    """Estimate token usage before translation"""
    try:
        user_id = get_user_id()
        data = request.json
        text = data.get('text', '')
        novel_id = data.get('novel_id', '')
        
        # Get requested model/provider
        req_model = data.get('model')
        req_provider = data.get('provider')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        settings = load_settings(user_id)
        
        # Determine provider and model
        if req_model:
            selected_model = req_model
            # If provider not specified, try to infer or default to openrouter if model looks like path
            if req_provider:
                provider = req_provider
            else:
                # Heuristic: if model contains '/', assume openrouter
                if '/' in selected_model:
                    provider = 'openrouter'
                else:
                    # Fallback to selected provider from settings, or 'openrouter'
                    provider = settings.get('selected_provider', 'openrouter')
        else:
            provider = settings.get('selected_provider', 'openrouter')
            selected_model = settings.get('provider_models', {}).get(provider, '')
        
        # Handle Thinking Mode
        use_thinking_mode = data.get('use_thinking_mode', False)
        if use_thinking_mode and not req_model:
            thinking_models = settings.get('thinking_mode_models', {})
            thinking_model = thinking_models.get(provider)
            if thinking_model:
                selected_model = thinking_model
        
        glossary = get_novel_glossary(user_id, novel_id) if novel_id else {}
        images = data.get('images', [])
        
        estimation = estimate_translation_tokens(text, provider, selected_model, glossary, images)
        
        # Calculate estimated cost if pricing is available
        cost_info = None
        if estimation:
            cost_info = calculate_cost(
                estimation.get('input_tokens', 0),
                estimation.get('output_tokens', 0),
                provider,
                selected_model
            )
        
        return jsonify({
            'success': True,
            'estimation': estimation,
            'provider': provider,
            'model': selected_model,
            'cost_info': cost_info
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Get or update global settings"""
    user_id = get_user_id()
    
    if request.method == 'GET':
        return jsonify(load_settings(user_id))
    
    elif request.method == 'POST':
        try:
            new_settings = request.json
            save_settings(user_id, new_settings)
            return jsonify({'success': True, 'message': 'Settings saved'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@api_bp.route('/pricing', methods=['GET', 'POST'])
def pricing():
    """Get or update per-model pricing saved in user settings

    Pricing is stored in the user's settings under the key 'model_pricing' as a
    mapping from model name to { 'input_per_1k': '0.00', 'output_per_1k': '0.00' }.
    """
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    if request.method == 'GET':
        try:
            settings = load_settings(user_id)
            pricing = settings.get('model_pricing', {}) or {}

            # Ensure configured provider models are present in the returned pricing
            provider_models = settings.get('provider_models', {}) or {}

            # Collect suggested prices (from OpenRouter) where available.
            # Try using the user's API key first; if that yields an empty catalog
            # we'll fall back to the public cached catalog.
            suggested = {}
            api_key = settings.get('api_keys', {}).get('openrouter')
            try:
                for prov, model_name in (provider_models.items() if isinstance(provider_models, dict) else []):
                    if not model_name:
                        continue
                    if prov != 'openrouter':
                        continue

                    try:
                        mp = None
                        # Try API-key-backed lookup first
                        if api_key:
                            mp = get_model_pricing_with_key('openrouter', model_name, api_key)

                        # If key-backed lookup returned nothing, try public cached catalog
                        if mp and mp.get('available'):
                            input_price_per_token = mp.get('input_price')
                            output_price_per_token = mp.get('output_price')
                            if input_price_per_token is not None or output_price_per_token is not None:
                                entry = {}
                                if input_price_per_token is not None:
                                    # Convert from per-token to per-1K-tokens
                                    entry['input_per_1k'] = f"{(float(input_price_per_token) * 1000.0):.10f}"
                                if output_price_per_token is not None:
                                    # Convert from per-token to per-1K-tokens
                                   entry['output_per_1k'] = f"{(float(output_price_per_token) * 1000.0):.10f}"
                                suggested[model_name] = entry
                    except Exception:
                        continue
            except Exception:
                suggested = {}

            # Ensure each configured model has an editable row in the response
            try:
                for prov, model_name in (provider_models.items() if isinstance(provider_models, dict) else []):
                    if not model_name:
                        continue
                    if model_name not in pricing:
                        pricing[model_name] = {'input_per_1k': '', 'output_per_1k': ''}
            except Exception:
                pass

            # Normalize stored zero-like values to empty so suggestions can be shown
            for m, p in list(pricing.items()):
                try:
                    if isinstance(p, dict):
                        for key in ('input_per_1k', 'output_per_1k'):
                            val = p.get(key)
                            if val in (None, '', 0, '0', '0.0'):
                                p[key] = ''
                except Exception:
                    continue

            # Merge suggested numeric values into pricing entries when empty
            if suggested:
                pricing.setdefault('suggested', {})
                for k, v in suggested.items():
                    pricing['suggested'][k] = v
                    if k in pricing:
                        # If stored price is empty, populate it from suggested
                        if not pricing[k].get('input_per_1k') and v.get('input_per_1k'):
                            pricing[k]['input_per_1k'] = v.get('input_per_1k')
                        if not pricing[k].get('output_per_1k') and v.get('output_per_1k'):
                            pricing[k]['output_per_1k'] = v.get('output_per_1k')

            return jsonify({'success': True, 'pricing': pricing})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.json or {}
            settings = load_settings(user_id)
            settings['model_pricing'] = data
            save_settings(user_id, settings)
            return jsonify({'success': True, 'message': 'Pricing saved'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@api_bp.route('/debug/openrouter-catalog', methods=['GET'])
def debug_openrouter_catalog():
    """Return OpenRouter catalog fetched with the user's API key (if present)
    and the matching result for configured provider models. This endpoint is
    intended for debugging only and requires authentication.
    """
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        settings = load_settings(user_id)
        api_key = settings.get('api_keys', {}).get('openrouter')

        raw_catalog = None
        if api_key:
            catalog = fetch_openrouter_pricing_with_key(api_key)
            # Also fetch raw response for diagnostics
            raw_catalog = fetch_openrouter_raw_with_key(api_key)
            source = 'with_key'
        else:
            catalog = get_cached_openrouter_pricing()
            source = 'public_cached'

        provider_models = settings.get('provider_models', {}) or {}
        matched = {}
        for prov, model_name in (provider_models.items() if isinstance(provider_models, dict) else []):
            if not model_name:
                continue
            if prov == 'openrouter':
                if api_key:
                    mp = get_model_pricing_with_key('openrouter', model_name, api_key)
                else:
                    mp = get_model_pricing('openrouter', model_name)
            else:
                mp = get_model_pricing(prov, model_name)

            matched[model_name] = mp or {'available': False}

        return jsonify({'success': True, 'catalog_source': source, 'catalog': catalog or {}, 'raw_catalog': raw_catalog or {}, 'matched': matched})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/novel/<novel_id>/glossary', methods=['GET', 'POST'])
def novel_glossary(novel_id):
    """Get or update novel-specific character glossary"""
    user_id = get_user_id()
    
    if request.method == 'GET':
        glossary = get_novel_glossary(user_id, novel_id)
        return jsonify({'success': True, 'glossary': glossary})
    
    elif request.method == 'POST':
        try:
            from urllib.parse import unquote
            novel_id = unquote(novel_id)
            
            data = request.json
            glossary = data.get('glossary', {})
            
            save_novel_glossary(user_id, novel_id, glossary)
            
            return jsonify({'success': True, 'message': 'Glossary saved'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

@api_bp.route('/novel/<novel_id>/auto-detect-characters', methods=['POST'])
def auto_detect_characters(novel_id):
    """Auto-detect characters from novel chapters using AI and translate their names"""
    try:
        from urllib.parse import unquote
        user_id = get_user_id()
        novel_id = unquote(novel_id)
        
        novels = load_novels(user_id)
        if novel_id not in novels:
            return jsonify({'error': f'Novel not found: {novel_id}'}), 404
        
        novel = novels[novel_id]
        
        if not novel.get('chapters') or len(novel['chapters']) == 0:
            return jsonify({'error': 'No chapters available to analyze'}), 400
        
        sample_text = ""
        for i, chapter in enumerate(novel['chapters'][:3]):
            if chapter:
                sample_text += chapter.get('korean_text', '') + "\n\n"
                if len(sample_text) > 5000:
                    break
        
        if not sample_text:
            return jsonify({'error': 'No text content available'}), 400
        
        settings = load_settings(user_id)
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        if not api_key:
            return jsonify({'error': 'API key not configured'}), 400
        
        # Detect character names
        detect_result = detect_characters(sample_text, provider, api_key, selected_model)
        
        if not detect_result.get('success'):
            return jsonify({'error': detect_result.get('error', 'Failed to detect characters')}), 500
        
        korean_names = detect_result['characters']
        
        # Translate names
        translate_result = translate_names(korean_names, provider, api_key, selected_model)
        
        # Detect genders
        gender_result = detect_character_genders(korean_names, sample_text, provider, api_key, selected_model)
        
        response_data = {
            'success': True, 
            'characters': korean_names,
            'translations': translate_result.get('translations', {}) if translate_result.get('success') else {},
            'genders': gender_result.get('genders', {}) if gender_result.get('success') else {name: 'auto' for name in korean_names}
        }
        
        return jsonify(response_data)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/update-novel-title', methods=['POST'])
def update_novel_title():
    """Update a novel's translated title"""
    try:
        user_id = get_user_id()
        data = request.json
        novel_id = data.get('novel_id')
        translated_title = data.get('translated_title')
        
        if not novel_id or not translated_title:
            return jsonify({'error': 'Missing novel_id or translated_title'}), 400
        
        novels = load_novels(user_id)
        
        if novel_id not in novels:
            return jsonify({'error': 'Novel not found'}), 404
        
        novels[novel_id]['translated_title'] = translated_title
        save_novels(user_id, novels)
        
        return jsonify({'success': True, 'message': 'Novel title updated'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/update-novel-sort-order', methods=['POST'])
def update_novel_sort_order():
    """Update the sort order for a novel"""
    try:
        user_id = get_user_id()
        data = request.json
        novel_id = data.get('novel_id')
        sort_order = data.get('sort_order')
        
        if not novel_id:
            return jsonify({'error': 'Invalid data'}), 400
        
        novels = load_novels(user_id)
        if novel_id not in novels:
            return jsonify({'error': 'Novel not found'}), 404
        
        if sort_order == 'default':
            if 'sort_order_override' in novels[novel_id]:
                del novels[novel_id]['sort_order_override']
            if 'sort_order' in novels[novel_id]:
                del novels[novel_id]['sort_order']
        elif sort_order in ['asc', 'desc']:
            novels[novel_id]['sort_order_override'] = sort_order
            novels[novel_id]['sort_order'] = sort_order
        else:
            return jsonify({'error': 'Invalid sort order'}), 400
        
        save_novels(user_id, novels)
        
        return jsonify({'success': True, 'message': 'Sort order updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/task-status/<task_id>', methods=['GET'])
def task_status(task_id):
    """Check the status of a background Celery task"""
    try:
        from celery.result import AsyncResult
        from celery_app import celery
        
        task = AsyncResult(task_id, app=celery)
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Pending...',
                'progress': 0
            }
        elif task.state == 'STARTED':
            response = {
                'state': task.state,
                'status': 'Started...',
                'progress': 10
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'status': task.info.get('status', 'Processing...'),
                'progress': 50
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'status': 'Complete',
                'result': task.result,
                'progress': 100
            }
        elif task.state == 'FAILURE':
            response = {
                'state': task.state,
                'status': 'Failed',
                'error': str(task.info),
                'progress': 0
            }
        else:
            response = {
                'state': task.state,
                'status': str(task.info),
                'progress': 0
            }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/translate-novel-title', methods=['POST'])
def translate_novel_title():
    """Queue a background task to translate novel metadata"""
    try:
        user_id = get_user_id()
        data = request.json
        novel_id = data.get('novel_id')
        
        if not novel_id:
            return jsonify({'error': 'Novel ID required'}), 400
        
        # Load novels to verify it exists
        novels = load_novels(user_id)
        if novel_id not in novels:
            return jsonify({'error': f'Novel not found: {novel_id}'}), 404
        
        # Queue the translation task
        from tasks.translation_tasks import translate_novel_title_task
        task = translate_novel_title_task.delay(user_id, novel_id)
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': 'Translation queued'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Keep the old synchronous version as translate-novel-title-sync for backwards compatibility
@api_bp.route('/translate-novel-title-sync', methods=['POST'])
def translate_novel_title_sync():
    """Translate a novel's title, author, tags, and synopsis after batch import"""
    try:
        user_id = get_user_id()
        data = request.json
        novel_id = data.get('novel_id')
        
        if not novel_id:
            return jsonify({'error': 'Novel ID required'}), 400
        
        # Load novels
        novels = load_novels(user_id)
        if novel_id not in novels:
            return jsonify({'error': f'Novel not found: {novel_id}'}), 404
        
        novel = novels[novel_id]
        
        # Get Korean versions
        korean_title = novel.get('title', '')
        korean_author = novel.get('author', '')
        korean_tags = novel.get('tags', [])
        korean_synopsis = novel.get('synopsis', '')
        
        # Load settings for AI translations
        settings = load_settings(user_id)
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        if not api_key:
            return jsonify({'error': 'No API key configured for translations'}), 400
        
        translated_title = korean_title
        translated_author = korean_author
        translated_tags = korean_tags[:]
        translated_synopsis = korean_synopsis
        
        try:
            # Translate title
            if korean_title:
                cache_key = get_cache_key(f"title:{korean_title}")
                if cache_key in translation_cache:
                    translated_title = translation_cache[cache_key]
                else:
                    translated_title_result = translate_text(
                        korean_title, provider, api_key, selected_model,
                        glossary=None, images=None
                    )
                    if not translated_title_result.startswith("Error") and not translated_title_result.startswith(provider.capitalize()):
                        translated_title = translated_title_result
                        translation_cache[cache_key] = translated_title
                        if len(translation_cache) > MAX_CACHE_SIZE:
                            translation_cache.pop(next(iter(translation_cache)))
            
            # Translate author
            if korean_author:
                cache_key = get_cache_key(f"author:{korean_author}")
                if cache_key in translation_cache:
                    translated_author = translation_cache[cache_key]
                else:
                    translated_author_result = translate_text(
                        korean_author, provider, api_key, selected_model,
                        glossary=None, images=None
                    )
                    if not translated_author_result.startswith("Error") and not translated_author_result.startswith(provider.capitalize()):
                        translated_author = translated_author_result
                        translation_cache[cache_key] = translated_author
                        if len(translation_cache) > MAX_CACHE_SIZE:
                            translation_cache.pop(next(iter(translation_cache)))
            
            # Translate tags
            if korean_tags:
                tags_text = ', '.join(korean_tags)
                translated_tags_result = translate_text(
                    tags_text, provider, api_key, selected_model,
                    glossary=None, images=None
                )
                if not translated_tags_result.startswith("Error") and not translated_tags_result.startswith(provider.capitalize()):
                    translated_tags_text = translated_tags_result
                    translated_tags = [tag.strip() for tag in translated_tags_text.split(',')]
            
            # Translate synopsis
            if korean_synopsis:
                translated_synopsis_result = translate_text(
                    korean_synopsis, provider, api_key, selected_model,
                    glossary=None, images=None
                )
                if not translated_synopsis_result.startswith("Error") and not translated_synopsis_result.startswith(provider.capitalize()):
                    translated_synopsis = translated_synopsis_result
        
        except Exception as e:
            # If translation fails, keep Korean versions
            pass
        
        # Update novel with translations (but keep original slug!)
        novels[novel_id]['translated_title'] = translated_title
        novels[novel_id]['translated_author'] = translated_author
        novels[novel_id]['translated_tags'] = translated_tags
        novels[novel_id]['translated_synopsis'] = translated_synopsis
        
        # Save changes
        save_novels(user_id, novels)
        
        return jsonify({
            'success': True,
            'translated_title': translated_title,
            'translated_author': translated_author,
            'translated_tags': translated_tags,
            'translated_synopsis': translated_synopsis
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/check-auth')
def check_auth():
    """Check if user is logged in"""
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user_id': session['user_id'],
            'username': session.get('username')
        })
    return jsonify({'authenticated': False})

@api_bp.route('/debug-tools', methods=['POST'])
def debug_tools():
    """Debug endpoint to test image download and translation"""
    try:
        user_id = get_user_id()
        data = request.json
        action = data.get('action')
        
        result = {'success': True, 'logs': []}
        
        def log(msg):
            result['logs'].append(str(msg))
            print(f"DEBUG-TOOL: {msg}")
            
        if action == 'test_image':
            url = data.get('url')
            log(f"Testing image download: {url}")
            
            # Test headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://novelpia.com/'
            }
            log(f"Using headers: {headers}")
            
            import requests
            try:
                if url.startswith('//'):
                    url = 'https:' + url
                
                resp = requests.get(url, headers=headers, timeout=10)
                log(f"Status Code: {resp.status_code}")
                log(f"Content Type: {resp.headers.get('Content-Type')}")
                log(f"Content Length: {len(resp.content)} bytes")
                
                if resp.status_code == 200:
                    result['message'] = "Image download successful"
                else:
                    result['success'] = False
                    result['error'] = f"Status code {resp.status_code}"
                    
            except Exception as e:
                log(f"Error: {str(e)}")
                result['success'] = False
                result['error'] = str(e)
                
        elif action == 'test_translation':
            text = data.get('text', '안녕하세요')
            log(f"Testing translation: {text}")
            
            settings = load_settings(user_id)
            provider = settings.get('selected_provider', 'openrouter')
            api_key = settings.get('api_keys', {}).get(provider, '')
            model = settings.get('provider_models', {}).get(provider, '')
            
            log(f"Provider: {provider}")
            log(f"API Key set: {'Yes' if api_key else 'No'}")
            log(f"Model: {model}")
            
            if not api_key:
                result['success'] = False
                result['error'] = "No API key set"
            else:
                try:
                    trans = translate_text(text, provider, api_key, model)
                    log(f"Result: {trans}")
                    result['translation'] = trans
                except Exception as e:
                    log(f"Error: {str(e)}")
                    result['success'] = False
                    result['error'] = str(e)
        
        elif action == 'get_logs':
            result['logs'] = DEBUG_LOGS
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/delete-novel', methods=['POST'])
def delete_novel_endpoint():
    """Delete a novel"""
    try:
        data = request.get_json()
        novel_id = data.get('novel_id')
        user_id = get_user_id()
        
        if not novel_id:
            return jsonify({'error': 'Missing novel_id'}), 400
            
        success = delete_novel(user_id, novel_id)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Novel not found or could not be deleted'}), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/delete-chapter', methods=['POST'])
def delete_chapter_endpoint():
    """Delete a chapter"""
    try:
        data = request.get_json()
        novel_id = data.get('novel_id')
        chapter_index = data.get('chapter_index')
        user_id = get_user_id()
        
        if not novel_id or chapter_index is None:
            return jsonify({'error': 'Missing parameters'}), 400
            
        success = delete_chapter(user_id, novel_id, int(chapter_index))
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Chapter not found or could not be deleted'}), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/version', methods=['GET'])
def get_version():
    """Get API version for debugging"""
    # Try writing to log to test permissions
    try:
        log_path = os.path.join('data', 'debug_test.log')
        with open(log_path, 'a') as f:
            f.write(f"Test write at {datetime.now()}\n")
        write_status = "success"
    except Exception as e:
        write_status = f"failed: {str(e)}"
        
    return jsonify({
        'version': 'debug-v2', 
        'timestamp': datetime.now().isoformat(),
        'log_write': write_status
    })

@api_bp.route('/debug/view-logs', methods=['GET'])
def view_debug_logs():
    """View the debug_delete.log file"""
    try:
        log_path = os.path.join('data', 'debug_delete.log')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                content = f.read()
            return f"<pre>{content}</pre>"
        else:
            return f"Log file not found at {log_path} (try deleting a chapter first)"
    except Exception as e:
        return f"Error reading log: {str(e)}"

@api_bp.route('/translate-chapter-titles', methods=['POST'])
def translate_chapter_titles():
    """Batch translate all chapter titles for a novel"""
    try:
        from models.database import db_session_scope
        from models.db_models import Novel, Chapter
        from services.ai_service import translate_text
        
        user_id = get_user_id()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json()
        novel_slug = data.get('novel_id')
        
        if not novel_slug:
            return jsonify({'error': 'Novel ID required'}), 400
        
        # Get settings for AI translation
        settings = load_settings(user_id)
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        if not api_key:
            return jsonify({'error': 'No API key configured'}), 400
        
        with db_session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_slug, user_id=user_id).first()
            if not novel:
                return jsonify({'error': 'Novel not found'}), 404
            
            # Get all chapters with untranslated titles (where translated_title == title)
            chapters = session.query(Chapter).filter_by(novel_id=novel.id).all()
            
            untranslated_chapters = []
            for ch in chapters:
                # Check if title needs translation (Korean title with no English translation)
                if ch.translated_title == ch.title or not ch.translated_title:
                    untranslated_chapters.append(ch)
            
            if not untranslated_chapters:
                return jsonify({
                    'success': True,
                    'message': 'All chapter titles already translated',
                    'translated_count': 0
                })
            
            # Batch translate all titles in one API call
            titles_to_translate = [ch.title for ch in untranslated_chapters]
            batch_text = '\n'.join([f"{i+1}. {title}" for i, title in enumerate(titles_to_translate)])
            
            try:
                translated_batch = translate_text(
                    f"Translate these chapter titles from Korean to English (keep the numbering):\n{batch_text}",
                    provider, api_key, selected_model, {}
                )
                
                # Parse the translated titles
                translated_lines = translated_batch.strip().split('\n')
                translated_titles = []
                for line in translated_lines:
                    # Remove numbering (e.g., "1. " or "1) ")
                    cleaned = line.strip()
                    if '. ' in cleaned:
                        cleaned = cleaned.split('. ', 1)[1]
                    elif ') ' in cleaned:
                        cleaned = cleaned.split(') ', 1)[1]
                    translated_titles.append(cleaned)
                
                # Update database
                count = 0
                for i, ch in enumerate(untranslated_chapters):
                    if i < len(translated_titles):
                        ch.translated_title = translated_titles[i]
                        count += 1
                
                session.flush()
                
                return jsonify({
                    'success': True,
                    'message': f'Translated {count} chapter titles',
                    'translated_count': count
                })
                
            except Exception as e:
                return jsonify({'error': f'Translation failed: {str(e)}'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/resort-chapters', methods=['POST'])
def resort_chapters():
    """Re-sort all chapters by their episode number from source URL"""
    try:
        from models.database import db_session_scope
        from models.db_models import Novel, Chapter
        
        user_id = get_user_id()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json()
        novel_slug = data.get('novel_id')
        print(f"DEBUG: Resorting chapters for novel: {novel_slug}")
        
        with db_session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_slug).first()
            if not novel:
                print(f"DEBUG: Novel not found: {novel_slug}")
                return jsonify({'success': False, 'error': 'Novel not found'})
            
            # Get all chapters
            chapters = session.query(Chapter).filter_by(novel_id=novel.id).all()
            print(f"DEBUG: Found {len(chapters)} chapters to sort")
            
            # Sort by episode number extracted from source_url
            def get_episode_no(ch):
                try:
                    # Extract episode number from URL like https://novelpia.com/viewer/2888224
                    if ch.source_url and '/viewer/' in ch.source_url:
                        return int(ch.source_url.split('/viewer/')[-1])
                    return 999999999  # Fallback
                except (ValueError, AttributeError):
                    return 999999999
            
            sorted_chapters = sorted(chapters, key=get_episode_no)
            
            # Reassign positions
            for idx, ch in enumerate(sorted_chapters):
                if ch.position != idx:
                    print(f"DEBUG: Updating Ch {ch.chapter_number} position from {ch.position} to {idx}")
                    ch.position = idx
            
            return jsonify({'success': True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    

@api_bp.route('/debug/chapter-positions/<novel_slug>', methods=['GET'])
def debug_chapter_positions_route(novel_slug):
    """Debug endpoint to see actual chapter positions vs display order"""
    try:
        from urllib.parse import unquote
        from models.db_novel import extract_episode_id_from_url
        from models.database import db_session_scope
        from models.db_models import Novel, Chapter
        from sqlalchemy import and_
        
        user_id = get_user_id()
        novel_slug = unquote(novel_slug)
        
        with db_session_scope() as session:
            novel = session.query(Novel).filter(
                and_(Novel.user_id == user_id, Novel.slug == novel_slug)
            ).first()
            
            if not novel:
                return jsonify({'error': 'Novel not found'}), 404
            
            # Get chapters ordered by position (database order)
            chapters_by_position = session.query(Chapter).filter_by(
                novel_id=novel.id
            ).order_by(Chapter.position).all()
            
            # Get chapters around position 156-160 and 177-178
            problem_area_1 = []
            problem_area_2 = []
            
            for ch in chapters_by_position:
                episode_id = extract_episode_id_from_url(ch.source_url)
                ch_info = {
                    'position': ch.position,
                    'chapter_number': ch.chapter_number,
                    'episode_id': episode_id,
                    'title': ch.title[:60],
                    'source_url': ch.source_url
                }
                
                # Capture area around 156-157
                if 154 <= ch.position <= 162:
                    problem_area_1.append(ch_info)
                
                # Capture area around 177-178
                if 175 <= ch.position <= 179:
                    problem_area_2.append(ch_info)
            
            return jsonify({
                'novel': novel.title,
                'total_chapters': len(chapters_by_position),
                'area_156_to_162': problem_area_1,
                'area_177_to_178': problem_area_2,
                'note': 'Check if chapter 175 appears in both areas or just one'
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/find-chapter/<novel_slug>/<chapter_number>', methods=['GET'])
def find_chapter_by_number(novel_slug, chapter_number):
    """Find where a specific chapter number is located"""
    try:
        from urllib.parse import unquote
        from models.db_novel import extract_episode_id_from_url
        from models.database import db_session_scope
        from models.db_models import Novel, Chapter
        from sqlalchemy import and_
        
        user_id = get_user_id()
        novel_slug = unquote(novel_slug)
        
        with db_session_scope() as session:
            novel = session.query(Novel).filter(
                and_(Novel.user_id == user_id, Novel.slug == novel_slug)
            ).first()
            
            if not novel:
                return jsonify({'error': 'Novel not found'}), 404
            
            # Find all chapters with this chapter_number
            chapters = session.query(Chapter).filter(
                and_(Chapter.novel_id == novel.id, Chapter.chapter_number == str(chapter_number))
            ).all()
            
            results = []
            for ch in chapters:
                episode_id = extract_episode_id_from_url(ch.source_url)
                results.append({
                    'id': ch.id,
                    'position': ch.position,
                    'chapter_number': ch.chapter_number,
                    'episode_id': episode_id,
                    'source_url': ch.source_url,
                    'title': ch.title
                })
            
            return jsonify({
                'found': len(results),
                'chapters': results
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/test-repair', methods=['GET'])
def test_repair():
    """Test endpoint to verify routes are loading"""
    return jsonify({'status': 'repair endpoint exists', 'test': 'ok'})
    try:
        from urllib.parse import unquote
        from models.db_novel import extract_episode_id_from_url
        from models.database import db_session_scope
        from models.db_models import Novel, Chapter
        from sqlalchemy import and_
        
        user_id = get_user_id()
        novel_slug = unquote(novel_slug)
        
        with db_session_scope() as session:
            novel = session.query(Novel).filter(
                and_(Novel.user_id == user_id, Novel.slug == novel_slug)
            ).first()
            
            if not novel:
                return jsonify({'error': 'Novel not found'}), 404
            
            # Get ALL chapters
            chapters = session.query(Chapter).filter_by(novel_id=novel.id).all()
            
            # Build list with episode IDs
            chapters_with_episodes = []
            for ch in chapters:
                episode_id = extract_episode_id_from_url(ch.source_url)
                if episode_id:
                    chapters_with_episodes.append((episode_id, ch))
                else:
                    # Chapters without episode IDs go to end
                    chapters_with_episodes.append((999999999, ch))
            
            # Sort by episode ID
            chapters_with_episodes.sort(key=lambda x: x[0])
            
            # Reassign positions sequentially
            updates = []
            for new_pos, (ep_id, ch) in enumerate(chapters_with_episodes):
                old_pos = ch.position
                if old_pos != new_pos:
                    ch.position = new_pos
                    updates.append(f"Ch#{ch.chapter_number} (Ep {ep_id}): {old_pos} → {new_pos}")
            
            session.flush()
            
            return jsonify({
                'success': True,
                'message': f'Repaired {len(updates)} chapter positions',
                'total_chapters': len(chapters_with_episodes),
                'changes': updates[:50]  # Show first 50 changes
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/translate-chapter-title', methods=['POST'])
def translate_chapter_title():
    """Queue a background task to translate a single chapter's title"""
    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.json
        novel_id = data.get('novel_id')
        chapter_index = data.get('chapter_index')
        
        if not novel_id or chapter_index is None:
            return jsonify({'error': 'Missing novel_id or chapter_index'}), 400
        
        # Load novel to get chapter ID
        from models.db_novel import get_novel_with_chapters_db
        from models.settings import load_settings
        from models.novel import sort_chapters_by_number
        
        novel = get_novel_with_chapters_db(user_id, novel_id)
        if not novel or not novel.get('chapters'):
            return jsonify({'error': 'Novel not found'}), 404
        
        # Apply the same sorting as the frontend
        settings = load_settings(user_id)
        if 'sort_order_override' in novel and novel['sort_order_override'] is not None:
            order = novel['sort_order_override']
        else:
            order = settings.get('default_sort_order', 'asc')
        
        sorted_chapters = sort_chapters_by_number(novel['chapters'], order)
        
        try:
            chapter_index = int(chapter_index)
        except ValueError:
            return jsonify({'error': 'Invalid chapter_index'}), 400
        
        if chapter_index >= len(sorted_chapters):
            return jsonify({'error': 'Chapter index out of range'}), 404
        
        chapter = sorted_chapters[chapter_index]
        chapter_id = chapter.get('id')
        
        if not chapter_id:
            return jsonify({'error': 'Chapter ID not found'}), 404
        
        # Queue the title translation task
        from tasks.translation_tasks import translate_chapter_title_task
        task = translate_chapter_title_task.delay(
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id
        )
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': 'Title translation queued'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500