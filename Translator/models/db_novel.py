"""
PostgreSQL-based novel and chapter operations

This module provides database operations for novels and chapters using SQLAlchemy.
Replaces the JSON file-based approach in models/novel.py
"""

from models.database import db_session_scope
from models.db_models import Novel, Chapter
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

# ==================== NOVEL OPERATIONS ====================

def get_user_novels_db(user_id):
    """Get all novels for a user from PostgreSQL."""
    with db_session_scope() as session:
        novels = session.query(Novel).filter_by(user_id=user_id).order_by(Novel.created_at.desc()).all()
        return [n.to_dict() for n in novels]

def get_novel_db(user_id, slug):
    """Get a single novel by slug from PostgreSQL."""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == slug)
        ).first()
        return novel.to_dict() if novel else None

def get_novel_with_chapters_db(user_id, slug):
    """Get a novel with all its chapters from PostgreSQL."""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == slug)
        ).first()
        if not novel:
            return None
        novel_dict = novel.to_dict()
        chapters = session.query(Chapter).filter_by(novel_id=novel.id).order_by(Chapter.position).all()
        novel_dict['chapters'] = [c.to_dict(include_content=True) for c in chapters]
        return novel_dict

def create_novel_db(user_id, novel_data):
    """Create a new novel in PostgreSQL."""
    with db_session_scope() as session:
        novel = Novel(
            user_id=user_id,
            slug=novel_data['slug'],
            title=novel_data.get('title', ''),
            original_title=novel_data.get('original_title'),
            translated_title=novel_data.get('translated_title'),
            author=novel_data.get('author'),
            translated_author=novel_data.get('translated_author'),
            cover_url=novel_data.get('cover_url'),
            tags=novel_data.get('tags', []),
            translated_tags=novel_data.get('translated_tags', []),
            synopsis=novel_data.get('synopsis'),
            translated_synopsis=novel_data.get('translated_synopsis'),
            source_url=novel_data.get('source_url'),
            glossary=novel_data.get('glossary', {})
        )
        session.add(novel)
        session.flush()
        return novel.to_dict()

def update_novel_db(user_id, slug, updates):
    """Update a novel's fields in PostgreSQL."""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == slug)
        ).first()
        if not novel:
            return None
        allowed_fields = [
            'title', 'original_title', 'translated_title', 'author', 'translated_author',
            'cover_url', 'tags', 'translated_tags', 'synopsis', 'translated_synopsis',
            'source_url', 'slug', 'glossary'
        ]
        for field in allowed_fields:
            if field in updates:
                setattr(novel, field, updates[field])
        session.flush()
        return novel.to_dict()

def delete_novel_db(user_id, slug):
    """Delete a novel and all its chapters from PostgreSQL (cascade)."""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == slug)
        ).first()
        if not novel:
            return False
        session.delete(novel)
        return True

def find_novel_by_source_url_db(user_id, source_url):
    """Find a novel by its source URL."""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.source_url == source_url)
        ).first()
        return novel.to_dict() if novel else None

def get_next_chapter_position_db(novel_id):
    """Get the next available chapter position for a novel."""
    with db_session_scope() as session:
        max_position = session.query(Chapter.position).filter_by(novel_id=novel_id).order_by(Chapter.position.desc()).first()
        return (max_position[0] + 1) if max_position else 0

def find_novel_by_title_db(user_id, title):
    """Find a novel by its title (Original or Translated)."""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(
                Novel.user_id == user_id,
                (Novel.title == title) |
                (Novel.original_title == title) |
                (Novel.translated_title == title)
            )
        ).first()
        return novel.to_dict() if novel else None

def parse_chapter_number(num_str):
    """Helper to parse chapter number string to float/int for sorting."""
    if not num_str:
        return 999999.0
    if num_str == 'BONUS':
        return 999999.0
    try:
        return float(num_str)
    except (ValueError, TypeError):
        return 999999.0

def add_chapter_atomic(user_id, novel_slug, chapter_data):
    """Add a chapter to a novel atomically with row locking.

    Prevents race conditions during concurrent imports.
    Orders chapters by episode ID from source_url for correct chronological ordering.
    """
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == novel_slug)
        ).with_for_update().first()
        if not novel:
            raise ValueError(f"Novel not found: {novel_slug}")
        
        source_url = chapter_data.get('source_url')
        
        # Check if chapter already exists
        if source_url:
            existing_chapter = session.query(Chapter).filter(
                and_(Chapter.novel_id == novel.id, Chapter.source_url == source_url)
            ).first()
            if existing_chapter:
                return {
                    'success': True,
                    'message': 'Chapter already exists - skipped',
                    'already_exists': True,
                    'novel_id': novel.slug,
                    'chapter_index': existing_chapter.position,
                    'chapter_id': existing_chapter.id
                }
        
        position = chapter_data.get('position')
        
        if position is None:
            # Extract episode ID from the new chapter's URL
            new_episode_id = extract_episode_id_from_url(chapter_data.get('source_url'))
            
            print(f"\n[ADD_CHAPTER] Importing chapter with episode ID: {new_episode_id}")
            
            # Get ALL existing chapters ordered by current position
            existing_chapters = session.query(Chapter).filter(
                Chapter.novel_id == novel.id
            ).order_by(Chapter.position).all()
            
            print(f"[ADD_CHAPTER] Found {len(existing_chapters)} existing chapters")
            
            # Default: append at end
            insert_pos = len(existing_chapters)
            
            if new_episode_id is not None:
                # Find the correct position by comparing episode IDs
                for idx, existing_ch in enumerate(existing_chapters):
                    existing_episode_id = extract_episode_id_from_url(existing_ch.source_url)
                    
                    print(f"[ADD_CHAPTER] Comparing with position {idx}: Ch#{existing_ch.chapter_number}, Episode ID: {existing_episode_id}")
                    
                    # If existing chapter has no episode ID, skip comparison
                    if existing_episode_id is None:
                        continue
                    
                    # If new chapter should come BEFORE this existing chapter
                    if new_episode_id < existing_episode_id:
                        insert_pos = idx
                        print(f"[ADD_CHAPTER] Found insertion point at position {insert_pos}")
                        break
            else:
                # Fallback: use chapter number if no episode ID
                print(f"[ADD_CHAPTER] No episode ID found, falling back to chapter number sorting")
                new_chapter_num = parse_chapter_number(chapter_data.get('chapter_number'))
                
                for idx, existing_ch in enumerate(existing_chapters):
                    existing_ch_num = parse_chapter_number(existing_ch.chapter_number)
                    
                    if new_chapter_num < existing_ch_num:
                        insert_pos = idx
                        print(f"[ADD_CHAPTER] Found insertion point at position {insert_pos} (by chapter number)")
                        break
            
            print(f"[ADD_CHAPTER] Final insert position: {insert_pos}")
            
            # Shift all chapters at insert_pos and beyond UP by 1
            if insert_pos < len(existing_chapters):
                print(f"[ADD_CHAPTER] Shifting {len(existing_chapters) - insert_pos} chapters up by 1 position")
                session.query(Chapter).filter(
                    and_(Chapter.novel_id == novel.id, Chapter.position >= insert_pos)
                ).update(
                    {Chapter.position: Chapter.position + 1}, 
                    synchronize_session=False
                )
                session.flush()  # Apply the shifts immediately
            
            position = insert_pos
        
        # Create the new chapter
        new_chapter = Chapter(
            novel_id=novel.id,
            slug=chapter_data['slug'],
            title=chapter_data.get('title', ''),
            original_title=chapter_data.get('original_title'),
            translated_title=chapter_data.get('translated_title'),
            chapter_number=chapter_data.get('chapter_number'),
            content=chapter_data.get('content', ''),
            images=chapter_data.get('images', []),
            source_url=source_url,
            position=position,
            is_bonus=chapter_data.get('is_bonus', False)
        )
        session.add(new_chapter)
        session.flush()
        
        print(f"[ADD_CHAPTER] Successfully added chapter at position {position}")
        
        # Debug: Print final chapter order
        # debug_chapter_positions(session, novel.id)
        
        return {
            'success': True,
            'message': 'Chapter imported successfully',
            'novel_id': novel.slug,
            'chapter_index': new_chapter.position,
            'chapter_id': new_chapter.id
        }

def create_chapter_db(user_id, novel_slug, chapter_data):
    """Create a new chapter in PostgreSQL.
    
    This is a wrapper around add_chapter_atomic for backward compatibility.
    """
    return add_chapter_atomic(user_id, novel_slug, chapter_data)


def get_chapter_db(chapter_id):
    """Get a single chapter by ID from PostgreSQL."""
    with db_session_scope() as session:
        chapter = session.query(Chapter).filter_by(id=chapter_id).first()
        return chapter.to_dict(include_content=True) if chapter else None


def update_chapter_db(chapter_id, updates):
    """Update a chapter's fields in PostgreSQL."""
    with db_session_scope() as session:
        chapter = session.query(Chapter).filter_by(id=chapter_id).first()
        if not chapter:
            return None
        
        allowed_fields = [
            'title', 'original_title', 'translated_title', 'chapter_number',
            'content', 'translated_content', 'translation_model',
            'images', 'source_url', 'position', 'is_bonus', 'slug',
            'translation_status', 'translation_task_id', 
            'translation_started_at', 'translation_completed_at'
        ]
        
        for field in allowed_fields:
            if field in updates:
                setattr(chapter, field, updates[field])
        
        session.flush()
        return chapter.to_dict(include_content=True)


def delete_chapter_db(chapter_id):
    """Delete a chapter from PostgreSQL."""
    with db_session_scope() as session:
        chapter = session.query(Chapter).filter_by(id=chapter_id).first()
        if not chapter:
            return False
        session.delete(chapter)
        return True


def get_chapters_for_novel_db(user_id, novel_slug):
    """Get all chapters for a novel from PostgreSQL."""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == novel_slug)
        ).first()
        if not novel:
            return []
        
        chapters = session.query(Chapter).filter_by(
            novel_id=novel.id
        ).order_by(Chapter.position).all()
        
        return [c.to_dict(include_content=True) for c in chapters]

def extract_episode_id_from_url(source_url):
    """Extract episode ID from Novelpia URL for proper ordering.
    
    Example: https://novelpia.com/viewer/4778400 -> 4778400
    """
    if not source_url:
        return None
    
    import re
    match = re.search(r'/viewer/(\d+)', source_url)
    if match:
        return int(match.group(1))
    return None


def debug_chapter_positions(session, novel_id):
    """Print all chapters with their positions and episode IDs for debugging"""
    chapters = session.query(Chapter).filter_by(novel_id=novel_id).order_by(Chapter.position).all()
    print(f"\n=== CURRENT CHAPTER ORDER (Total: {len(chapters)}) ===")
    for ch in chapters:
        episode_id = extract_episode_id_from_url(ch.source_url)
        print(f"Position {ch.position}: Ch#{ch.chapter_number} | Episode ID: {episode_id} | Title: {ch.title[:50]}")
    print("=" * 80)


def diagnose_chapter_order(user_id, novel_slug):
    """Diagnostic function to check current chapter ordering"""
    with db_session_scope() as session:
        novel = session.query(Novel).filter(
            and_(Novel.user_id == user_id, Novel.slug == novel_slug)
        ).first()
        
        if not novel:
            print(f"Novel not found: {novel_slug}")
            return
        
        chapters = session.query(Chapter).filter_by(novel_id=novel.id).order_by(Chapter.position).all()
        
        print(f"\n{'='*100}")
        print(f"NOVEL: {novel.title}")
        print(f"TOTAL CHAPTERS: {len(chapters)}")
        print(f"{'='*100}")
        print(f"{'Pos':<5} | {'Ch#':<8} | {'Episode ID':<12} | {'Title':<50}")
        print(f"{'-'*100}")
        
        for ch in chapters:
            episode_id = extract_episode_id_from_url(ch.source_url)
            ch_num = str(ch.chapter_number) if ch.chapter_number else 'N/A'
            title = (ch.title[:47] + '...') if len(ch.title) > 50 else ch.title
            print(f"{ch.position:<5} | {ch_num:<8} | {str(episode_id):<12} | {title}")
        
        print(f"{'='*100}\n")