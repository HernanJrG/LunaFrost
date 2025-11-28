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
    
    
    # Handle novel overview pages - extract and save metadata
    if is_novel_page or (not content and not chapter_data.get('chapter_number')):
        print(f"DEBUG [process_chapter_import]: Detected novel overview page")
        
        # Find or create novel
        novel_data = find_novel_by_title_db(user_id, original_title)
        if not novel_data:
            novel_data = find_novel_by_source_url_db(user_id, novel_source_url)
        
        novel_id = novel_data['slug'] if novel_data else None
        
        if novel_id:
            # Update existing novel with metadata (already translated by API route layer)
            print(f"DEBUG [process_chapter_import]: Updating existing novel {novel_id} with metadata from overview page")
            update_data = {}
            
            # Cover
            cover_url = chapter_data.get('cover_url', '')
            print(f"DEBUG [process_chapter_import]: Overview page cover_url = '{cover_url}'")
            if cover_url:
                cover_image_path = download_image(cover_url, user_id, overwrite=True)
                print(f"DEBUG [process_chapter_import]: Downloaded cover to = '{cover_image_path}'")
                if cover_image_path:
                    update_data['cover_url'] = cover_image_path
            
            # Metadata - FORCE translation to English (ignore what API route sent)
            from services.ai_service import translate_text
            settings = load_settings(user_id)
            provider = settings.get('selected_provider', 'openrouter')
            api_key = settings.get('api_keys', {}).get(provider, '')
            selected_model = settings.get('provider_models', {}).get(provider, '')
            
            print(f"DEBUG [process_chapter_import]: API key configured: {bool(api_key)}")
            print(f"DEBUG [process_chapter_import]: Provider: {provider}, Model: {selected_model}")
            
            # Helper to check for Korean
            import re
            has_korean = lambda text: bool(re.search(r'[\uac00-\ud7a3]', text)) if text else False
            
            # ALWAYS translate title
            if api_key and original_title:
                try:
                    translated_title = translate_text(original_title, provider, api_key, selected_model, {})
                    print(f"DEBUG [process_chapter_import]: Translated title: '{original_title}' -> '{translated_title}'")
                    if isinstance(translated_title, dict):
                        translated_title = translated_title.get('translated_text', original_title)
                    update_data['translated_title'] = translated_title
                except Exception as e:
                    print(f"DEBUG [process_chapter_import]: Error translating title: {e}")
                    update_data['translated_title'] = original_title
            
            # Author
            author = chapter_data.get('author', '')
            if author:
                update_data['author'] = author
                if api_key:
                    try:
                        translated_author = translate_text(author, provider, api_key, selected_model, {})
                        print(f"DEBUG [process_chapter_import]: Translated author: '{author}' -> '{translated_author}'")
                        if isinstance(translated_author, dict):
                            translated_author = translated_author.get('translated_text', author)
                        update_data['translated_author'] = translated_author
                    except Exception as e:
                        print(f"DEBUG [process_chapter_import]: Error translating author: {e}")
                        update_data['translated_author'] = author
            
            # Tags
            tags = chapter_data.get('tags', [])
            if tags:
                update_data['tags'] = tags
                if api_key:
                    try:
                        tags_text = ', '.join(tags)
                        translated_tags_result = translate_text(tags_text, provider, api_key, selected_model, {})
                        if isinstance(translated_tags_result, dict):
                            translated_tags_result = translated_tags_result.get('translated_text', tags_text)
                        translated_tags = [tag.strip() for tag in translated_tags_result.split(',')]
                        print(f"DEBUG [process_chapter_import]: Translated tags: {tags} -> {translated_tags}")
                        update_data['translated_tags'] = translated_tags
                    except Exception as e:
                        print(f"DEBUG [process_chapter_import]: Error translating tags: {e}")
                        update_data['translated_tags'] = tags
            
            # Synopsis
            synopsis = chapter_data.get('synopsis', '')
            if synopsis:
                update_data['synopsis'] = synopsis
                if api_key:
                    try:
                        translated_synopsis = translate_text(synopsis, provider, api_key, selected_model, {})
                        if isinstance(translated_synopsis, dict):
                            translated_synopsis = translated_synopsis.get('translated_text', synopsis)
                        print(f"DEBUG [process_chapter_import]: Translated synopsis ({len(synopsis)} chars -> {len(translated_synopsis)} chars)")
                        update_data['translated_synopsis'] = translated_synopsis
                    except Exception as e:
                        print(f"DEBUG [process_chapter_import]: Error translating synopsis: {e}")
                        update_data['translated_synopsis'] = synopsis
            
            if update_data:
                print(f"DEBUG [process_chapter_import]: Updating novel with: {list(update_data.keys())}")
                update_novel_db(user_id, novel_id, update_data)
            else:
                print(f"DEBUG [process_chapter_import]: No metadata to update")
        else:
            # Create new novel from overview page data
            print(f"DEBUG [process_chapter_import]: Creating new novel from overview page")
            novel_id = create_novel_from_data(user_id, chapter_data, skip_translation)
            print(f"DEBUG [process_chapter_import]: Created novel {novel_id}")
        
        return {
            'success': True, 
            'message': 'Novel metadata captured from overview page', 
            'novel_id': novel_id,
            'is_overview': True
        }
    
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
        print(f"DEBUG [process_chapter_import]: Existing novel update - cover_url = '{cover_url}'")
        if cover_url:
            cover_image_path = download_image(cover_url, user_id, overwrite=True)
            print(f"DEBUG [process_chapter_import]: Downloaded cover to = '{cover_image_path}'")
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

    # Generate novel ID (slug) with username suffix to avoid conflicts between users
    # user_id is already the username in lowercase
    base_slug = slugify_english(original_title)
    if not base_slug:
        base_slug = f"novel_{hashlib.md5(original_title.encode()).hexdigest()[:8]}"

    # Append username to make slugs unique per user
    slug = f"{base_slug}_{user_id}"
    
    # Translate metadata if not skipped
    if skip_translation or chapter_data.get('translated_title'):
        novel_translated_title = chapter_data.get('translated_title', original_title)
        translated_author = chapter_data.get('translated_author', chapter_data.get('author', ''))
        translated_synopsis = chapter_data.get('translated_synopsis', chapter_data.get('synopsis', ''))
    else:
        settings = load_settings(user_id)
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        # Translate title
        try:
            novel_translated_title_result = translate_text(
                original_title, provider, api_key, selected_model, {}
            )
            if isinstance(novel_translated_title_result, dict):
                novel_translated_title = novel_translated_title_result.get('translated_text', original_title)
            else:
                novel_translated_title = novel_translated_title_result
        except:
            novel_translated_title = original_title
        
        translated_author = chapter_data.get('author', '')
        translated_synopsis = chapter_data.get('synopsis', '')
    
    # Download cover
    cover_image_path = ''
    cover_url = chapter_data.get('cover_url', '')
    print(f"DEBUG [create_novel_from_data]: cover_url from chapter_data = '{cover_url}'")
    if cover_url:
        cover_image_path = download_image(cover_url, user_id, overwrite=True)
        print(f"DEBUG [create_novel_from_data]: downloaded cover to = '{cover_image_path}'")
    
    # Create novel entry in DB
    novel_data = {
        'slug': slug,
        'title': original_title,
        'original_title': original_title,
        'translated_title': novel_translated_title,
        'author': chapter_data.get('author', ''),
        'translated_author': translated_author,
        'tags': chapter_data.get('tags', []),
        'translated_tags': chapter_data.get('translated_tags', chapter_data.get('tags', [])),
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
            
            # DEBUG: Log all chapter data keys and metadata values
            print(f"\n{'='*80}")
            print(f"DEBUG [batch_import] Chapter {idx + 1}/{len(chapters_data)}")
            print(f"DEBUG [batch_import] All keys in chapter_data: {list(chapter_data.keys())}")
            print(f"DEBUG [batch_import] original_title: '{original_title}'")
            print(f"DEBUG [batch_import] cover_url: '{chapter_data.get('cover_url', 'NOT PROVIDED')}'")
            print(f"DEBUG [batch_import] author: '{chapter_data.get('author', 'NOT PROVIDED')}'")
            print(f"DEBUG [batch_import] tags: {chapter_data.get('tags', 'NOT PROVIDED')}")
            print(f"DEBUG [batch_import] synopsis: '{chapter_data.get('synopsis', 'NOT PROVIDED')[:100] if chapter_data.get('synopsis') else 'NOT PROVIDED'}...'")
            print(f"{'='*80}\n")
            
            # Find existing novel by Korean title first
            novel_data = find_novel_by_title_db(user_id, original_title)
            if not novel_data:
                novel_data = find_novel_by_source_url_db(user_id, novel_source_url)
            
            novel_id = novel_data['slug'] if novel_data else None
            
            # Update novel metadata if novel exists and metadata is provided
            if novel_id:
                update_data = {}
                
                # Cover
                cover_url = chapter_data.get('cover_url', '')
                print(f"DEBUG [process_batch_chapter_import]: Existing novel update - cover_url = '{cover_url}'")
                if cover_url:
                    cover_image_path = download_image(cover_url, user_id, overwrite=True)
                    print(f"DEBUG [process_batch_chapter_import]: Downloaded cover to = '{cover_image_path}'")
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

