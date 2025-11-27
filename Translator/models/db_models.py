"""
SQLAlchemy database models for LunaFrost Translator

This module defines the ORM models for storing novels, chapters, settings,
and exports in PostgreSQL instead of JSON files.
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, ForeignKey, Index, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Novel(Base):
    """Novel model - stores novel metadata"""
    __tablename__ = 'novels'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=False)  # Korean title
    original_title = Column(String(500))  # Original Korean title (duplicate for compatibility)
    translated_title = Column(String(500))  # English translated title
    author = Column(String(255))  # Korean author
    translated_author = Column(String(255))  # English translated author
    cover_url = Column(Text)
    tags = Column(ARRAY(String))  # Korean tags
    translated_tags = Column(ARRAY(String))  # English translated tags
    synopsis = Column(Text)  # Korean synopsis
    translated_synopsis = Column(Text)  # English translated synopsis
    glossary = Column(JSONB)  # Character name glossary for translations
    source_url = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    chapters = relationship('Chapter', back_populates='novel', cascade='all, delete-orphan', lazy='dynamic')
    exports = relationship('Export', back_populates='novel', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_novels_user_slug', 'user_id', 'slug', unique=True),
    )
    
    def __repr__(self):
        return f"<Novel(id={self.id}, title='{self.title}', user_id='{self.user_id}')>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'slug': self.slug,
            'title': self.title,
            'original_title': self.original_title,
            'translated_title': self.translated_title,
            'author': self.author,
            'translated_author': self.translated_author,
            'cover_url': self.cover_url,
            'cover': self.cover_url,  # Backward compatibility
            'cover_image': self.cover_url,  # For api_routes.py compatibility
            'tags': self.tags or [],
            'translated_tags': self.translated_tags or [],
            'synopsis': self.synopsis,
            'translated_synopsis': self.translated_synopsis,
            'glossary': self.glossary or {},
            'source_url': self.source_url,
            'novel_source_url': self.source_url,  # Backward compatibility
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'chapter_count': self.chapters.count() if self.chapters else 0
        }


class Chapter(Base):
    """Chapter model - stores chapter content"""
    __tablename__ = 'chapters'
    
    id = Column(Integer, primary_key=True)
    novel_id = Column(Integer, ForeignKey('novels.id', ondelete='CASCADE'), nullable=False, index=True)
    slug = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)  # Korean title
    original_title = Column(String(500))  # Original Korean title
    translated_title = Column(String(500))  # English translated title
    chapter_number = Column(String(50))
    content = Column(Text, nullable=False)  # Korean content
    translated_content = Column(Text)  # English translated content
    translation_model = Column(String(100))  # Model used for translation
    
    # Translation status tracking
    translation_status = Column(String(20), default='pending')  # pending, in_progress, completed, failed
    translation_task_id = Column(String(100))  # Celery task ID
    translation_started_at = Column(TIMESTAMP)
    translation_completed_at = Column(TIMESTAMP)
    
    images = Column(JSONB)  # Store as JSON array: ["url1", "url2"]
    source_url = Column(Text)
    position = Column(Integer, nullable=False)
    is_bonus = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    novel = relationship('Novel', back_populates='chapters')
    
    # Indexes
    __table_args__ = (
        Index('idx_chapters_novel_slug', 'novel_id', 'slug', unique=True),
        Index('idx_chapters_position', 'novel_id', 'position'),
    )
    
    def __repr__(self):
        return f"<Chapter(id={self.id}, title='{self.title}', novel_id={self.novel_id}, position={self.position})>"
    
    def to_dict(self, include_content=True):
        """Convert to dictionary for API responses"""
        data = {
            'id': self.id,
            'novel_id': self.novel_id,
            'slug': self.slug,
            'title': self.title,
            'original_title': self.original_title,
            'translated_title': self.translated_title or self.title,  # Use DB field, fallback to title
            'chapter_number': self.chapter_number,
            'images': self.images or [],
            'source_url': self.source_url,
            'position': self.position,
            'is_bonus': self.is_bonus,
            'translation_status': self.translation_status or 'pending',
            'translation_task_id': self.translation_task_id,
            'translation_started_at': self.translation_started_at.isoformat() if self.translation_started_at else None,
            'translation_completed_at': self.translation_completed_at.isoformat() if self.translation_completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'imported_at': self.created_at.isoformat() if self.created_at else None,  # Backward compatibility
        }
        
        if include_content:
            data['content'] = self.content
            data['korean_text'] = self.content  # Backward compatibility
            data['translated_text'] = self.translated_content or ''  # Use DB field
            data['translated_content'] = self.translated_content or ''  # Ensure compatibility with API
            data['translation_model'] = self.translation_model or ''
        
        return data


class UserSettings(Base):
    """User settings model - stores user preferences"""
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, unique=True, index=True)
    translation_api_key = Column(Text)
    translation_model = Column(String(100), default='gpt-4o-mini')
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<UserSettings(user_id='{self.user_id}', model='{self.translation_model}')>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'user_id': self.user_id,
            'translation_api_key': self.translation_api_key,
            'translation_model': self.translation_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Export(Base):
    """Export model - tracks generated EPUB/TXT files"""
    __tablename__ = 'exports'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    novel_id = Column(Integer, ForeignKey('novels.id', ondelete='CASCADE'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    format = Column(String(10), nullable=False)  # 'epub' or 'txt'
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    
    # Relationships
    novel = relationship('Novel', back_populates='exports')
    
    def __repr__(self):
        return f"<Export(id={self.id}, filename='{self.filename}', format='{self.format}')>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'novel_id': self.novel_id,
            'filename': self.filename,
            'file_path': self.file_path,
            'format': self.format,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TranslationTokenUsage(Base):
    """Track token usage for each translation"""
    __tablename__ = 'translation_token_usage'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # 'openrouter', 'openai', 'google'
    model = Column(String(100), nullable=False)  # Model name used
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    translation_type = Column(String(20), default='content')  # 'content', 'title', 'both'
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    
    # Relationships
    chapter = relationship('Chapter', backref='token_usage_records')
    
    # Indexes
    __table_args__ = (
        Index('idx_token_usage_user_date', 'user_id', 'created_at'),
        Index('idx_token_usage_chapter', 'chapter_id'),
    )
    
    def __repr__(self):
        return f"<TranslationTokenUsage(id={self.id}, chapter_id={self.chapter_id}, total_tokens={self.total_tokens})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'chapter_id': self.chapter_id,
            'provider': self.provider,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'translation_type': self.translation_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }