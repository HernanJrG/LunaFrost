"""
Background tasks for AI translation processing
"""
from celery_app import celery
from models.novel import load_novels, save_novels
from models.settings import load_settings
from services.ai_service import translate_text
from services.token_usage_service import save_token_usage
import re
from datetime import datetime


def slugify_english(text):
    """Slugify English text for URLs"""
    if not text:
        return 'unknown_novel'
    
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    text = text.strip('-')
    
    return text or 'unknown_novel'


@celery.task(bind=True, name='tasks.translate_novel_title')
def translate_novel_title_task(self, user_id, novel_id):
    """
    Background task to translate novel metadata (title, author, tags, synopsis)
    
    Args:
        user_id: User ID
        novel_id: Novel ID (slug)
    
    Returns:
        dict: Result with status and translated data
    """
    try:
        # Update task state
        self.update_state(state='PROGRESS', meta={'status': 'Loading novel data...'})
        
        # Load settings and novel
        settings = load_settings(user_id)
        novels = load_novels(user_id)
        
        if novel_id not in novels:
            return {'error': 'Novel not found'}
        
        novel = novels[novel_id]
        korean_title = novel.get('title', '')
        
        # Get AI settings
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        if not api_key:
            return {'error': 'No API key configured'}
        
        # Translate title
        self.update_state(state='PROGRESS', meta={'status': 'Translating title...'})
        translated_title = translate_text(
            korean_title,
            provider,
            api_key,
            selected_model,
            glossary=None,
            images=None
        )
        
        if isinstance(translated_title, dict):
            translated_title = translated_title.get('translated_text', '')
            
        if translated_title.startswith("Error") or translated_title.startswith(provider.capitalize()):
            translated_title = korean_title  # Fallback to original
        
        # Translate author if present
        translated_author = novel.get('author', '')
        if novel.get('author'):
            self.update_state(state='PROGRESS', meta={'status': 'Translating author...'})
            author_result = translate_text(
                novel['author'],
                provider,
                api_key,
                selected_model,
                glossary=None,
                images=None
            )
            
            if isinstance(author_result, dict):
                author_result = author_result.get('translated_text', '')
                
            if not author_result.startswith("Error"):
                translated_author = author_result
        
        # Update novel
        novels[novel_id]['translated_title'] = translated_title
        if translated_author:
            novels[novel_id]['translated_author'] = translated_author
        
        # Update slug if title changed
        new_id = slugify_english(translated_title)
        if new_id != novel_id and new_id not in novels:
            novels[new_id] = novels.pop(novel_id)
            novel_id = new_id
        
        save_novels(user_id, novels)
        
        return {
            'status': 'complete',
            'novel_id': novel_id,
            'translated_title': translated_title,
            'translated_author': translated_author
        }
        
    except Exception as e:
        return {'error': str(e)}


@celery.task(bind=True, name='tasks.translate_chapter')
def translate_chapter_task(self, user_id, novel_id, chapter_index=None, chapter_id=None, translate_content=True, translate_title=True):
    """
    Background task to translate chapter title and/or content
    
    Args:
        user_id: User ID
        novel_id: Novel ID (slug)
        chapter_index: Index of chapter in novel (optional, use chapter_id if available)
        chapter_id: Database ID of chapter (preferred, more reliable)
        translate_content: Whether to translate content (default True)
        translate_title: Whether to translate title (default True)
    
    Returns:
        dict: Result with status
    """
    try:
        from database.db_novel import get_novel_with_chapters_db, update_chapter_db, get_chapter_db
        from models.settings import load_settings
        from database.database import db_session_scope
        from database.db_models import Chapter
        
        self.update_state(state='PROGRESS', meta={'status': 'Loading chapter data...'})
        
        # Load data from database
        settings = load_settings(user_id)
        
        # Get novel first (needed for glossary)
        novel = get_novel_with_chapters_db(user_id, novel_id)
        if not novel:
            return {'error': 'Novel not found'}
        
        # If chapter_id is provided, use it directly (more reliable)
        if chapter_id:
            with db_session_scope() as session:
                chapter_obj = session.query(Chapter).filter_by(id=chapter_id).first()
                if not chapter_obj:
                    return {'error': 'Chapter not found'}
                
                chapter = chapter_obj.to_dict(include_content=True)
        else:
            # Fallback to chapter_index lookup
            chapters = novel['chapters']
            
            if chapter_index is None or chapter_index >= len(chapters):
                return {'error': 'Chapter not found or invalid chapter_index'}
            
            chapter = chapters[chapter_index]
            chapter_id = chapter.get('id')

        if chapter_id:
            pass  # Chapter ID is available
        else:
            pass  # Using chapter_index
        
        # UPDATE STATUS: In Progress
        if chapter_id:
            update_chapter_db(chapter_id, {
                'translation_status': 'in_progress',
                'translation_task_id': self.request.id,
                'translation_started_at': datetime.utcnow()
            })
        
        # Get AI settings
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        if not api_key:
            if chapter_id:
                update_chapter_db(chapter_id, {'translation_status': 'failed'})
            return {'error': 'No API key configured'}
        
        updates = {}
        
        # Translate chapter title if requested
        if translate_title:
            self.update_state(state='PROGRESS', meta={'status': 'Translating title...'})
            title_result = translate_text(
                chapter.get('title', ''),
                provider,
                api_key,
                selected_model,
                glossary=novel.get('glossary')
            )
            
            # Handle new dict return format
            if isinstance(title_result, dict):
                if not title_result.get('error'):
                    translated_title = title_result.get('translated_text', '')
                    updates['translated_title'] = translated_title
                    
                    # Save token usage for title translation
                    token_usage = title_result.get('token_usage')
                    if token_usage and chapter_id:
                        try:
                            save_token_usage(
                                user_id=user_id,
                                chapter_id=chapter_id,
                                provider=token_usage.get('provider', provider),
                                model=token_usage.get('model', selected_model),
                                input_tokens=token_usage.get('input_tokens', 0),
                                output_tokens=token_usage.get('output_tokens', 0),
                                total_tokens=token_usage.get('total_tokens', 0),
                                translation_type='title'
                            )
                        except Exception as e:
                            pass
            elif isinstance(title_result, str) and not title_result.startswith("Error"):
                # Backward compatibility
                updates['translated_title'] = title_result
        
        # Translate content if requested
        if translate_content:
            self.update_state(state='PROGRESS', meta={'status': 'Translating content...'})
            content_result = translate_text(
                chapter.get('content', ''),
                provider,
                api_key,
                selected_model,
                glossary=novel.get('glossary'),
                images=chapter.get('images')
            )
            
            # Handle new dict return format
            if isinstance(content_result, dict):
                if not content_result.get('error'):
                    translated_content = content_result.get('translated_text', '')
                    updates['translated_content'] = translated_content
                    
                    # Save token usage for content translation
                    token_usage = content_result.get('token_usage')
                    if token_usage and chapter_id:
                        try:
                            save_token_usage(
                                user_id=user_id,
                                chapter_id=chapter_id,
                                provider=token_usage.get('provider', provider),
                                model=token_usage.get('model', selected_model),
                                input_tokens=token_usage.get('input_tokens', 0),
                                output_tokens=token_usage.get('output_tokens', 0),
                                total_tokens=token_usage.get('total_tokens', 0),
                                translation_type='content'
                            )
                        except Exception as e:
                            pass
            elif isinstance(content_result, str) and not content_result.startswith("Error"):
                # Backward compatibility
                updates['translated_content'] = content_result

        # UPDATE STATUS: Completed or Failed
        if updates:
            updates['translation_status'] = 'completed'
            updates['translation_completed_at'] = datetime.utcnow()
            update_chapter_db(chapter['id'], updates)
        else:
            update_chapter_db(chapter['id'], {'translation_status': 'failed'})
        
        return {
            'status': 'complete',
            'chapter_id': chapter.get('id'),
            'chapter_index': chapter_index,
            'novel_id': novel_id
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        # UPDATE STATUS: Failed
        if chapter_id:
            try:
                from database.db_novel import update_chapter_db
                update_chapter_db(chapter_id, {'translation_status': 'failed'})
            except:
                pass
        return {'error': str(e)}

@celery.task(bind=True, name='tasks.translate_chapter_title')
def translate_chapter_title_task(self, user_id, novel_id, chapter_id):
    """
    Background task to translate ONLY chapter title (faster)
    """
    try:
        from database.db_novel import get_novel_with_chapters_db, update_chapter_db, get_chapter_db
        from models.settings import load_settings
        from database.db_models import Chapter
        from database.database import db_session_scope
        
        # Load settings
        settings = load_settings(user_id)
        provider = settings.get('selected_provider', 'openrouter')
        api_key = settings.get('api_keys', {}).get(provider, '')
        selected_model = settings.get('provider_models', {}).get(provider, '')
        
        if not api_key:
            return {'error': 'No API key'}

        # Get chapter
        with db_session_scope() as session:
            chapter = session.query(Chapter).filter_by(id=chapter_id).first()
            if not chapter:
                return {'error': 'Chapter not found'}
            
            original_title = chapter.title
            novel_id_db = chapter.novel_id
            
            # Get novel for glossary
            from database.db_models import Novel
            novel = session.query(Novel).filter_by(id=novel_id_db).first()
            glossary = novel.glossary if novel else None

        # Translate
        title_result = translate_text(
            original_title,
            provider,
            api_key,
            selected_model,
            glossary=glossary
        )
        
        # Handle new dict return format
        if isinstance(title_result, dict):
            if not title_result.get('error'):
                translated_title = title_result.get('translated_text', '')
                update_chapter_db(chapter_id, {'translated_title': translated_title})
                
                # Save token usage
                token_usage = title_result.get('token_usage')
                if token_usage:
                    try:
                        save_token_usage(
                            user_id=user_id,
                            chapter_id=chapter_id,
                            provider=token_usage.get('provider', provider),
                            model=token_usage.get('model', selected_model),
                            input_tokens=token_usage.get('input_tokens', 0),
                            output_tokens=token_usage.get('output_tokens', 0),
                            total_tokens=token_usage.get('total_tokens', 0),
                            translation_type='title'
                        )
                    except Exception as e:
                        pass  # Silently ignore token save errors
                
                return {'status': 'complete', 'translated_title': translated_title}
            else:
                return {'error': title_result.get('error', 'Translation failed')}
        elif isinstance(title_result, str) and not title_result.startswith("Error"):
            # Backward compatibility
            update_chapter_db(chapter_id, {'translated_title': title_result})
            return {'status': 'complete', 'translated_title': title_result}
            
        return {'error': 'Translation failed'}
        
    except Exception as e:
        return {'error': str(e)}
