"""
Novel model - PostgreSQL-based with backward compatibility

This module provides a unified interface for novel operations, now using PostgreSQL
instead of JSON files. Maintains compatibility with existing code.
"""
import os
from models.db_novel import (
    get_user_novels_db, get_novel_db, get_novel_with_chapters_db,
    create_novel_db, update_novel_db, delete_novel_db,
    create_chapter_db, update_chapter_db, delete_chapter_db,
    find_novel_by_source_url_db, get_next_chapter_position_db
)
from models.db_models import Novel as NovelModel

# Backward compatibility - keep old directory structure for images
DATA_DIR = 'data'


def get_user_images_dir(user_id):
    """Get path to user's images directory"""
    return os.path.join(DATA_DIR, 'users', user_id, 'images')


def initialize_user_data_files(user_id):
    """
    Initialize data directories for a user
    
    Note: We still use filesystem for images, just not for novel/chapter data
    """
    user_dir = os.path.join(DATA_DIR, 'users', user_id)
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'images'), exist_ok=True)


# ==================== NOVEL OPERATIONS (PostgreSQL) ====================

def load_novels(user_id):
    """
    Load all novels for a user from PostgreSQL
    
    Returns dict format for backward compatibility with existing code:
    {
        'novel-slug': {
            'slug': 'novel-slug',
            'title': 'Novel Title',
            'chapters': {...}
        }
    }
    """
    novels_list = get_user_novels_db(user_id)
    
    # Convert to dict format (slug -> novel data) for compatibility
    novels_dict = {}
    for novel in novels_list:
        novel_slug = novel['slug']
        # Get chapters for this novel
        novel_with_chapters = get_novel_with_chapters_db(user_id, novel_slug)
        if novel_with_chapters:
            # Keep chapters as list (routes expect list for .append())
            novel_data = novel_with_chapters.copy()
            # Chapters are already a list from get_novel_with_chapters_db
            novels_dict[novel_slug] = novel_data
    
    return novels_dict


def save_novels(user_id, novels):
    """
    Save novels dict to PostgreSQL
    
    This syncs the modified dict structure back to PostgreSQL.
    Handles both new novels/chapters and updates to existing ones.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"save_novels called for user {user_id} with {len(novels)} novels")
    
    from models.database import db_session_scope
    from models.db_models import Novel, Chapter
    
    try:
        with db_session_scope() as session:
            for novel_slug, novel in novels.items():
                logger.info(f"Processing novel: {novel_slug}")
                logger.info(f"Novel has {len(novel.get('chapters', []))} chapters")
                
                # Smart lookup: Check multiple ways to find existing novel
                # 1. By dict key (original slug)
                # 2. By updated slug (if slug changed during translation)
                # 3. By Korean title (for safety)
                existing_novel = session.query(Novel).filter_by(
                    user_id=user_id, slug=novel_slug
                ).first()
                
                # If not found by dict key, try the updated slug
                if not existing_novel:
                    new_slug = novel.get('slug')
                    if new_slug and new_slug != novel_slug:
                        logger.info(f"Dict key slug '{novel_slug}' not found, trying updated slug '{new_slug}'")
                        existing_novel = session.query(Novel).filter_by(
                            user_id=user_id, slug=new_slug
                        ).first()
                
                # If still not found, try matching by Korean title
                if not existing_novel:
                    korean_title = novel.get('title') or novel.get('original_title')
                    if korean_title:
                        logger.info(f"Trying to find novel by Korean title: {korean_title}")
                        existing_novel = session.query(Novel).filter_by(
                            user_id=user_id, title=korean_title
                        ).first()
                
                if existing_novel:
                    # Update existing novel with all fields including translations
                    existing_novel.title = novel.get('title') or novel.get('translated_title', '')
                    existing_novel.original_title = novel.get('original_title')
                    existing_novel.translated_title = novel.get('translated_title')
                    existing_novel.author = novel.get('author')
                    existing_novel.translated_author = novel.get('translated_author')
                    existing_novel.cover_url = novel.get('cover_image')
                    existing_novel.tags = novel.get('tags', [])
                    existing_novel.translated_tags = novel.get('translated_tags', [])
                    existing_novel.synopsis = novel.get('synopsis')
                    existing_novel.translated_synopsis = novel.get('translated_synopsis')
                    existing_novel.glossary = novel.get('glossary', {})
                    existing_novel.source_url = novel.get('source_url')
                    
                    # Handle slug change (update slug if it changed)
                    new_slug = novel.get('slug')
                    if new_slug and new_slug != novel_slug:
                        existing_novel.slug = new_slug
                        logger.info(f"Updated novel slug from {novel_slug} to {new_slug}")
                    
                    novel_id = existing_novel.id
                    logger.info(f"Updated existing novel ID: {novel_id}")
                else:
                    # Create new novel with all fields including translations
                    new_novel = Novel(
                        user_id=user_id,
                        slug=novel_slug,
                        title=novel.get('title') or novel.get('translated_title', ''),
                        original_title=novel.get('original_title'),
                        translated_title=novel.get('translated_title'),
                        author=novel.get('author'),
                        translated_author=novel.get('translated_author'),
                        cover_url=novel.get('cover_image'),
                        tags=novel.get('tags', []),
                        translated_tags=novel.get('translated_tags', []),
                        synopsis=novel.get('synopsis'),
                        translated_synopsis=novel.get('translated_synopsis'),
                        glossary=novel.get('glossary', {}),
                        source_url=novel.get('source_url')
                    )
                    session.add(new_novel)
                    session.flush()  # Get ID
                    novel_id = new_novel.id
                    logger.info(f"Created new novel ID: {novel_id}")
                
                # Handle chapters (now a list)
                chapters = novel.get('chapters', [])
                logger.info(f"Chapters type: {type(chapters)}, count: {len(chapters) if isinstance(chapters, list) else 'N/A'}")
                
                if isinstance(chapters, list):
                    for idx, chapter in enumerate(chapters):
                        if not chapter:  # Skip None chapters
                            logger.warning(f"Skipping None chapter at index {idx}")
                            continue
                        
                        chapter_slug = chapter.get('slug')
                        if not chapter_slug:
                            logger.warning(f"Skipping chapter without slug at index {idx}")
                            continue
                        
                        logger.info(f"Processing chapter: {chapter_slug}")
                        
                        # Check if chapter exists
                        existing_chapter = session.query(Chapter).filter_by(
                            novel_id=novel_id, slug=chapter_slug
                        ).first()
                        
                        if existing_chapter:
                            # Update existing chapter with translations
                            existing_chapter.title = chapter.get('title') or chapter.get('translated_title', '')
                            existing_chapter.original_title = chapter.get('original_title')
                            existing_chapter.translated_title = chapter.get('translated_title')
                            existing_chapter.chapter_number = chapter.get('chapter_number')
                            existing_chapter.content = chapter.get('content', '')
                            existing_chapter.images = chapter.get('images', [])
                            existing_chapter.source_url = chapter.get('source_url')
                            existing_chapter.position = chapter.get('position', 0)
                            existing_chapter.is_bonus = chapter.get('is_bonus', False)
                            logger.info(f"Updated chapter: {chapter_slug}")
                        else:
                            # Create new chapter with translations
                            new_chapter = Chapter(
                                novel_id=novel_id,
                                slug=chapter_slug,
                                title=chapter.get('title') or chapter.get('translated_title', ''),
                                original_title=chapter.get('original_title'),
                                translated_title=chapter.get('translated_title'),
                                chapter_number=chapter.get('chapter_number'),
                                content=chapter.get('content', ''),
                                images=chapter.get('images', []),
                                source_url=chapter.get('source_url'),
                                position=chapter.get('position', 0),
                                is_bonus=chapter.get('is_bonus', False)
                            )
                            session.add(new_chapter)
                            logger.info(f"Created new chapter: {chapter_slug}")
        logger.info("save_novels completed successfully")
    except Exception as e:
        logger.error(f"Error in save_novels: {e}", exc_info=True)




def get_novel_glossary(user_id, novel_slug):
    """Get character glossary for a specific novel"""
    novel = get_novel_db(user_id, novel_slug)
    if novel:
        # Glossary stored as JSONB in future, for now return empty
        return {}
    return {}


def save_novel_glossary(user_id, novel_slug, glossary):
    """Save character glossary for a specific novel"""
    # Update novel with glossary
    update_novel_db(user_id, novel_slug, {'glossary': glossary})


def delete_novel(user_id, novel_slug):
    """Delete an entire novel and all its data including images"""
    from services.image_service import delete_images_for_novel
    
    # Get novel data before deleting
    novel = get_novel_with_chapters_db(user_id, novel_slug)
    if novel:
        # Delete images
        delete_images_for_novel(novel, user_id)
        
        # Delete cover image
        if novel.get('cover_url'):
            # cover_url in DB stores the filename
            cover_path = os.path.join(get_user_images_dir(user_id), novel['cover_url'])
            if os.path.exists(cover_path):
                try:
                    os.remove(cover_path)
                except Exception:
                    pass

        # Delete from database (cascades to chapters)
        return delete_novel_db(user_id, novel_slug)
    return False


def delete_chapter(user_id, novel_slug, chapter_index):
    """Delete a specific chapter and its images, then renormalize positions"""
    from services.image_service import delete_images_for_chapter
    from models.database import db_session_scope
    from models.db_models import Novel, Chapter
    from sqlalchemy import and_
    
    # Get novel with chapters
    novel = get_novel_with_chapters_db(user_id, novel_slug)
    if not novel or not novel.get('chapters'):
        print(f"DEBUG: Novel not found or no chapters for {novel_slug}")
        return False
        
    # Apply the same sorting as the frontend to ensure index matches
    from models.settings import load_settings
    settings = load_settings(user_id)
    
    if 'sort_order_override' in novel and novel['sort_order_override'] is not None:
        order = novel['sort_order_override']
    else:
        order = settings.get('default_sort_order', 'asc')
        
    # Sort chapters to match frontend display
    sorted_chapters = sort_chapters_by_number(novel['chapters'], order)
    
    if chapter_index >= len(sorted_chapters):
        return False
        
    chapter = sorted_chapters[chapter_index]
    chapter_id = chapter['id']
    deleted_position = chapter['position']
    
    # Delete images
    delete_images_for_chapter(chapter, user_id)
    
    # Delete from database and renormalize positions
    with db_session_scope() as session:
        # Get the novel for locking
        novel_obj = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == novel_slug)
        ).with_for_update().first()
        
        if not novel_obj:
            return False
        
        # Delete the chapter
        chapter_to_delete = session.query(Chapter).filter_by(id=chapter_id).first()
        if not chapter_to_delete:
            return False
        
        session.delete(chapter_to_delete)
        session.flush()
        
        # CRITICAL FIX: Renormalize all positions after deletion
        # Get all remaining chapters ordered by position
        remaining_chapters = session.query(Chapter).filter_by(
            novel_id=novel_obj.id
        ).order_by(Chapter.position).all()
        
        print(f"\n[DELETE_CHAPTER] Deleted chapter at position {deleted_position}")
        print(f"[DELETE_CHAPTER] Renormalizing {len(remaining_chapters)} remaining chapters")
        
        # Reassign sequential positions starting from 0
        for idx, ch in enumerate(remaining_chapters):
            if ch.position != idx:
                print(f"[DELETE_CHAPTER]   Ch#{ch.chapter_number}: position {ch.position} -> {idx}")
                ch.position = idx
        
        session.flush()
        print(f"[DELETE_CHAPTER] ✅ Renormalization complete\n")
    
    return True


def get_display_title(novel):
    """
    Get the display title for a novel (English if available, otherwise Korean)
    
    Works with both dict and ORM object
    """
    if isinstance(novel, NovelModel):
        return novel.translated_title or novel.title or novel.original_title or 'Untitled'
    else:
        # Dict format - prefer English translation
        return novel.get('translated_title') or novel.get('title') or novel.get('original_title', 'Untitled')


def sort_chapters_by_number(chapters, order='asc'):
    """
    Sort chapters by position
    
    Args:
        chapters: List of chapter dicts or ORM objects
        order: 'asc' or 'desc'
    
    Returns:
        Sorted list of chapters
    """
    if not chapters:
        return chapters
    
    valid_chapters = [ch for ch in chapters if ch is not None]
    
    # Handle both dict and ORM format
    if valid_chapters and isinstance(valid_chapters[0], dict):
        sorted_chapters = sorted(
            valid_chapters,
            key=lambda ch: ch.get('position', 999999),
            reverse=(order == 'desc')
        )
    else:
        # ORM objects
        sorted_chapters = sorted(
            valid_chapters,
            key=lambda ch: ch.position if hasattr(ch, 'position') else 999999,
            reverse=(order == 'desc')
        )
    
    return sorted_chapters


# ==================== HELPER FUNCTIONS ====================

def find_novel_by_source_url(user_id, source_url):
    """Find a novel by its source URL"""
    return find_novel_by_source_url_db(user_id, source_url)
