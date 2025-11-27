"""
Import Service - Handles chapter and novel import logic
"""
import re
import time
import hashlib
from models.db_novel import (
    create_novel_db, get_novel_db, find_novel_by_source_url_db, 
    find_novel_by_title_db, add_chapter_atomic, update_novel_db
)
from models.settings import load_settings
from services.image_service import download_image, extract_images_from_content


def process_chapter_import(user_id, chapter_data, skip_translation=False):
    """
    Process a single chapter import.
    
    Args:
        user_id: User ID
        chapter_data: Dictionary containing chapter data from extension
        skip_translation: If True, skip translating metadata
        
    Returns:
        dict: Result with success status, novel_id, chapter_index, etc.
    """
    # Extract data
    original_title = chapter_data.get('original_title', '')
    chapter_title = chapter_data.get('chapter_title', '')
    content = chapter_data.get('content', '')
    source_url = chapter_data.get('source_url', '')
    novel_source_url = chapter_data.get('novel_source_url', source_url)
    if not source_url:
        source_url = novel_source_url
    images_from_extension = chapter_data.get('images', [])
    
    # DEBUG: Print chapter data keys
    print(f"DEBUG [import_service]: chapter_data keys: {list(chapter_data.keys())}")
    print(f"DEBUG [import_service]: chapter_title='{chapter_title}', chapter_number={chapter_data.get('chapter_number')}")
    print(f"DEBUG [import_service]: translated_chapter_title='{chapter_data.get('translated_chapter_title')}'")
    
    # Check if it's a novel overview page (no chapter content)
    # For Novelpia: /viewer/ = chapter page, /novel/ (without /viewer/) = novel overview page
    is_novel_page = False
    url_for_detection = source_url or novel_source_url or ''
    if url_for_detection:
        # If URL has /viewer/, it's definitely a chapter, not a novel page
        if '/viewer/' in url_for_detection:
            is_novel_page = False
        # If URL has /novel/ (but no /viewer/), it's a novel overview page
        elif '/novel/' in url_for_detection:
            is_novel_page = True
    
    # Skip importing novel overview pages as chapters
    if is_novel_page or (not content and not chapter_data.get('chapter_number')):
        return {'success': True, 'message': 'Skipped novel overview page', 'skipped': True}
    
    if not content:
        return {'success': False, 'error': 'No content provided'}
    
    # Try to find existing novel by Korean title FIRST (most reliable)
    novel_data = find_novel_by_title_db(user_id, original_title)
    
    # If not found, try by Source URL (exact match only)
    if not novel_data:
        novel_data = find_novel_by_source_url_db(user_id, novel_source_url)
    
    novel_id = novel_data['slug'] if novel_data else None
    
    if novel_id and not is_novel_page:
        # Update novel metadata if provided
        update_data = {}
        
        # Cover
        cover_url = chapter_data.get('cover_url', '')
        if cover_url:
            cover_image_path = download_image(cover_url, user_id, overwrite=True)
            if cover_image_path:
                update_data['cover_url'] = cover_image_path
        
        # Other metadata (only if provided)
        if chapter_data.get('translated_title'):
            update_data['translated_title'] = chapter_data.get('translated_title')
        if chapter_data.get('author'):
            update_data['author'] = chapter_data.get('author')
        if chapter_data.get('translated_author'):
            update_data['translated_author'] = chapter_data.get('translated_author')
        if chapter_data.get('tags'):
            update_data['tags'] = chapter_data.get('tags')
        if chapter_data.get('translated_tags'):
            update_data['translated_tags'] = chapter_data.get('translated_tags')
        if chapter_data.get('synopsis'):
            update_data['synopsis'] = chapter_data.get('synopsis')
        if chapter_data.get('translated_synopsis'):
            update_data['translated_synopsis'] = chapter_data.get('translated_synopsis')
            
        if update_data:
            update_novel_db(user_id, novel_id, update_data)
    
    # Download images
    images = []
    for img_data in images_from_extension:
        img_url = img_data.get('url', '')
        if img_url:
            local_filename = download_image(img_url, user_id)
            if local_filename:
                images.append({
                    'url': img_url,
                    'local_path': local_filename,
                    'alt': img_data.get('alt', 'Chapter Image')
                })
    
    # Extract images from content
    content_images = extract_images_from_content(content, user_id)
    existing_urls = {img['url'] for img in images}
    for content_img in content_images:
        if content_img['url'] not in existing_urls:
            images.append(content_img)
    
    # Create novel if needed
    if not novel_id:
        novel_id = create_novel_from_data(user_id, chapter_data, skip_translation)
    
    # Add chapter to novel (atomic)
    result = add_chapter_to_novel(
        user_id=user_id,
        novel_id=novel_id,
        chapter_data=chapter_data,
        images=images,
        skip_translation=skip_translation
    )
    
    return result


def create_novel_from_data(user_id, chapter_data, skip_translation=False):
    """Create a new novel from chapter data using DB"""
    from services.ai_service import translate_text
    
    original_title = chapter_data.get('original_title', '')
    novel_source_url = chapter_data.get('novel_source_url', '')
    
    # Generate novel ID (slug)
    slug = f"{slugify_english(original_title)}_{int(time.time())}"
    if not slug or slug == '_':
        slug = f"novel_{hashlib.md5(original_title.encode()).hexdigest()[:8]}"
    
    # Translate metadata if not skipped
    if skip_translation or chapter_data.get('translated_title'):
        novel_translated_title = chapter_data.get('translated_title', original_title)
        translated_author = chapter_data.get('author', '')
        translated_synopsis = chapter_data.get('synopsis', '')
    else:
        settings = load_settings(user_id)
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        # Translate title
        try:
            novel_translated_title = translate_text(
                original_title, provider, api_key, selected_model, {}
            )
        except:
            novel_translated_title = original_title
        
        translated_author = chapter_data.get('author', '')
        translated_synopsis = chapter_data.get('synopsis', '')
    
    # Download cover
    cover_image_path = ''
    cover_url = chapter_data.get('cover_url', '')
    if cover_url:
        cover_image_path = download_image(cover_url, user_id, overwrite=True)
    
    # Create novel entry in DB
    novel_data = {
        'slug': slug,
        'title': original_title,
        'original_title': original_title,
        'translated_title': novel_translated_title,
        'author': chapter_data.get('author', ''),
        'translated_author': translated_author,
        'tags': chapter_data.get('tags', []),
        'translated_tags': chapter_data.get('tags', []),
        'synopsis': chapter_data.get('synopsis', ''),
        'translated_synopsis': translated_synopsis,
        'cover_url': cover_image_path,
        'source_url': novel_source_url,
        'glossary': {}
    }
    
    create_novel_db(user_id, novel_data)
    return slug


def add_chapter_to_novel(user_id, novel_id, chapter_data, images, skip_translation=False):
    """Add a chapter to an existing novel using atomic DB operations"""
    
    # Ensure chapter_data has all necessary fields
    chapter_data['images'] = images
    
    # ALWAYS prioritize chapter_title over title (extension sends both, but title is often the novel title)
    if 'chapter_title' in chapter_data and chapter_data.get('chapter_title'):
        chapter_data['title'] = chapter_data['chapter_title']
        chapter_data['original_title'] = chapter_data['chapter_title']
    
    # Map translated chapter title
    # If translated_chapter_title is empty or missing, use the Korean chapter_title as fallback
    if 'translated_chapter_title' in chapter_data and chapter_data.get('translated_chapter_title'):
        chapter_data['translated_title'] = chapter_data['translated_chapter_title']
    elif 'chapter_title' in chapter_data and chapter_data.get('chapter_title'):
        # Fallback: use Korean chapter title if no translation provided
        chapter_data['translated_title'] = chapter_data['chapter_title']
    
    # Generate slug for chapter if not present
    if 'slug' not in chapter_data:
        chapter_num = chapter_data.get('chapter_number', '0')
        chapter_data['slug'] = f"{novel_id}_ch{chapter_num}_{int(time.time())}"
    
    # Call atomic function
    result = add_chapter_atomic(user_id, novel_id, chapter_data)
    
    return result


def slugify_english(text):
    """Slugify English text for URLs"""
    if not text:
        return 'unknown_novel'
    
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    text = text.strip('-')
    
    return text or 'unknown_novel'


def process_batch_chapter_import(user_id, chapters_data):
    """
    Process multiple chapter imports efficiently with optimized image downloads.
    
    Args:
        user_id: User ID
        chapters_data: List of chapter data dictionaries
        
    Returns:
        dict: Results with successful/failed counts and details
    """
    from services.image_service import download_images_parallel
    
    results = []
    successful = 0
    failed = 0
    
    # Process each chapter
    for idx, chapter_data in enumerate(chapters_data):
        try:
            # Extract basic data
            original_title = chapter_data.get('original_title', '')
            source_url = chapter_data.get('source_url', '')
            novel_source_url = chapter_data.get('novel_source_url', source_url)
            images_from_extension = chapter_data.get('images', [])
            content = chapter_data.get('content', '')
            skip_translation = chapter_data.get('skip_translation', False)
            
            # Find existing novel by Korean title first
            novel_data = find_novel_by_title_db(user_id, original_title)
            if not novel_data:
                novel_data = find_novel_by_source_url_db(user_id, novel_source_url)
            
            novel_id = novel_data['slug'] if novel_data else None
            
            # Check if chapter already exists - handled by atomic add, but we can check quickly if we have novel_data
            # Actually, let's rely on atomic add to handle existence check to avoid race conditions
            
            # Download images in parallel for this chapter
            images = []
            if images_from_extension:
                images = download_images_parallel(images_from_extension, user_id)
            
            # Extract images from content
            content_images = extract_images_from_content(content, user_id)
            existing_urls = {img['url'] for img in images}
            for content_img in content_images:
                if content_img['url'] not in existing_urls:
                    images.append(content_img)
            
            # Create novel if needed
            if not novel_id:
                novel_id = create_novel_from_data(user_id, chapter_data, skip_translation)
            
            # Add chapter to novel
            result = add_chapter_to_novel(
                user_id=user_id,
                novel_id=novel_id,
                chapter_data=chapter_data,
                images=images,
                skip_translation=skip_translation
            )
            
            if result.get('success'):
                results.append({
                    'index': idx,
                    'success': True,
                    'data': {
                        'novel_id': novel_id,
                        'chapter_index': result.get('chapter_index')
                    },
                    'chapter_title': chapter_data.get('chapter_title', 'Unknown'),
                    'already_exists': result.get('already_exists', False)
                })
                successful += 1
            else:
                raise Exception(result.get('error', 'Unknown error'))
            
        except Exception as e:
            results.append({
                'index': idx,
                'success': False,
                'error': str(e),
                'chapter_title': chapter_data.get('chapter_title', 'Unknown')
            })
            failed += 1
    
    return {
        'success': True,
        'total': len(chapters_data),
        'successful': successful,
        'failed': failed,
        'results': results
    }

