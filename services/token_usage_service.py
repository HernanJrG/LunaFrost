"""
Token usage service for tracking translation token consumption.

This service handles saving and retrieving token usage data from translations.
"""
from datetime import datetime, timedelta
from models.database import db_session_scope
from models.db_models import TranslationTokenUsage, Chapter, Novel
import tiktoken


def save_token_usage(user_id, chapter_id, provider, model, input_tokens, output_tokens, total_tokens, translation_type='content'):
    """
    Save token usage to database.
    
    Args:
        user_id: User ID
        chapter_id: Chapter ID
        provider: Provider name ('openrouter', 'openai', 'google')
        model: Model name used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        total_tokens: Total tokens used
        translation_type: Type of translation ('content', 'title', 'both')
    
    Returns:
        TranslationTokenUsage object or None if error
    """
    try:
        with db_session_scope() as session:
            token_usage = TranslationTokenUsage(
                user_id=user_id,
                chapter_id=chapter_id,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                translation_type=translation_type
            )
            session.add(token_usage)
            session.flush()
            return token_usage
    except Exception as e:
        print(f"Error saving token usage: {e}")
        return None


def get_chapter_token_usage(chapter_id):
    """
    Get all token usage records for a chapter.
    
    Args:
        chapter_id: Chapter ID
    
    Returns:
        List of TranslationTokenUsage objects
    """
    try:
        with db_session_scope() as session:
            records = session.query(TranslationTokenUsage).filter(
                TranslationTokenUsage.chapter_id == chapter_id
            ).order_by(TranslationTokenUsage.created_at.desc()).all()
            return records
    except Exception as e:
        print(f"Error getting chapter token usage: {e}")
        return []


def get_novel_token_usage(novel_id, user_id):
    """
    Get total token usage for all chapters in a novel.
    
    Args:
        novel_id: Novel ID
        user_id: User ID (for security)
    
    Returns:
        dict with total tokens and breakdown
    """
    try:
        with db_session_scope() as session:
            # Get all chapters for this novel
            chapters = session.query(Chapter).filter(
                Chapter.novel_id == novel_id
            ).all()
            
            chapter_ids = [ch.id for ch in chapters]
            
            if not chapter_ids:
                return {
                    'total_input_tokens': 0,
                    'total_output_tokens': 0,
                    'total_tokens': 0,
                    'record_count': 0
                }
            
            # Get token usage for all chapters
            records = session.query(TranslationTokenUsage).filter(
                TranslationTokenUsage.chapter_id.in_(chapter_ids),
                TranslationTokenUsage.user_id == user_id
            ).all()
            
            total_input = sum(r.input_tokens for r in records)
            total_output = sum(r.output_tokens for r in records)
            total = sum(r.total_tokens for r in records)
            
            return {
                'total_input_tokens': total_input,
                'total_output_tokens': total_output,
                'total_tokens': total,
                'record_count': len(records)
            }
    except Exception as e:
        print(f"Error getting novel token usage: {e}")
        return {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_tokens': 0,
            'record_count': 0
        }


def get_user_token_usage(user_id, start_date=None, end_date=None):
    """
    Get user's total token usage for a date range.
    
    Args:
        user_id: User ID
        start_date: Start date (datetime) or None for all time
        end_date: End date (datetime) or None for all time
    
    Returns:
        dict with total tokens and breakdown
    """
    try:
        with db_session_scope() as session:
            query = session.query(TranslationTokenUsage).filter(
                TranslationTokenUsage.user_id == user_id
            )
            
            if start_date:
                query = query.filter(TranslationTokenUsage.created_at >= start_date)
            if end_date:
                query = query.filter(TranslationTokenUsage.created_at <= end_date)
            
            records = query.all()
            
            total_input = sum(r.input_tokens for r in records)
            total_output = sum(r.output_tokens for r in records)
            total = sum(r.total_tokens for r in records)
            
            return {
                'total_input_tokens': total_input,
                'total_output_tokens': total_output,
                'total_tokens': total,
                'record_count': len(records)
            }
    except Exception as e:
        print(f"Error getting user token usage: {e}")
        return {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_tokens': 0,
            'record_count': 0
        }



def clear_user_token_usage(user_id):
    """
    Delete all token usage records for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with db_session_scope() as session:
            session.query(TranslationTokenUsage).filter(
                TranslationTokenUsage.user_id == user_id
            ).delete()
            return True
    except Exception as e:
        print(f"Error clearing user token usage: {e}")
        return False


def get_token_usage_by_provider(user_id, start_date=None, end_date=None):
    """
    Get token usage breakdown by provider.
    
    Args:
        user_id: User ID
        start_date: Start date (datetime) or None for all time
        end_date: End date (datetime) or None for all time
    
    Returns:
        dict mapping provider to token usage stats
    """
    try:
        with db_session_scope() as session:
            query = session.query(TranslationTokenUsage).filter(
                TranslationTokenUsage.user_id == user_id
            )
            
            if start_date:
                query = query.filter(TranslationTokenUsage.created_at >= start_date)
            if end_date:
                query = query.filter(TranslationTokenUsage.created_at <= end_date)
            
            records = query.all()
            
            # Group by provider
            provider_stats = {}
            for record in records:
                provider = record.provider
                if provider not in provider_stats:
                    provider_stats[provider] = {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'count': 0
                    }
                
                provider_stats[provider]['input_tokens'] += record.input_tokens
                provider_stats[provider]['output_tokens'] += record.output_tokens
                provider_stats[provider]['total_tokens'] += record.total_tokens
                provider_stats[provider]['count'] += 1
            
            return provider_stats
    except Exception as e:
        print(f"Error getting token usage by provider: {e}")
        return {}


def get_token_usage_by_model(user_id, start_date=None, end_date=None):
    """
    Get token usage breakdown by model.
    
    Args:
        user_id: User ID
        start_date: Start date (datetime) or None for all time
        end_date: End date (datetime) or None for all time
    
    Returns:
        dict mapping model to token usage stats
    """
    try:
        with db_session_scope() as session:
            query = session.query(TranslationTokenUsage).filter(
                TranslationTokenUsage.user_id == user_id
            )
            
            if start_date:
                query = query.filter(TranslationTokenUsage.created_at >= start_date)
            if end_date:
                query = query.filter(TranslationTokenUsage.created_at <= end_date)
            
            records = query.all()
            
            # Group by model
            model_stats = {}
            for record in records:
                model = record.model
                if model not in model_stats:
                    model_stats[model] = {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'count': 0,
                        'provider': record.provider
                    }
                
                model_stats[model]['input_tokens'] += record.input_tokens
                model_stats[model]['output_tokens'] += record.output_tokens
                model_stats[model]['total_tokens'] += record.total_tokens
                model_stats[model]['count'] += 1
            
            return model_stats
    except Exception as e:
        print(f"Error getting token usage by model: {e}")
        return {}


def get_recent_token_usage(user_id, days=30):
    """
    Get token usage for the last N days.
    
    Args:
        user_id: User ID
        days: Number of days to look back
    
    Returns:
        dict with daily breakdown
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        with db_session_scope() as session:
            records = session.query(TranslationTokenUsage).filter(
                TranslationTokenUsage.user_id == user_id,
                TranslationTokenUsage.created_at >= start_date,
                TranslationTokenUsage.created_at <= end_date
            ).order_by(TranslationTokenUsage.created_at).all()
            
            # Group by date
            daily_stats = {}
            for record in records:
                date_key = record.created_at.date().isoformat()
                if date_key not in daily_stats:
                    daily_stats[date_key] = {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'count': 0
                    }
                
                daily_stats[date_key]['input_tokens'] += record.input_tokens
                daily_stats[date_key]['output_tokens'] += record.output_tokens
                daily_stats[date_key]['total_tokens'] += record.total_tokens
                daily_stats[date_key]['count'] += 1
            
            return daily_stats
    except Exception as e:
        print(f"Error getting recent token usage: {e}")
        return {}


def estimate_translation_tokens(text, provider, model, glossary=None, images=None):
    """
    Estimate token count before translation.
    
    Args:
        text: Korean text to translate
        provider: Provider name ('openrouter', 'openai', 'google')
        model: Model name
        glossary: Optional glossary dict
        images: Optional images list
    
    Returns:
        dict with input_tokens, output_tokens, total_tokens estimates
    """
    try:
        # Build the same prompt structure as translate_text
        system_prompt = """
You are a professional Korean-to-English literary translator specializing in web novels. 
Your goal is to produce natural, fluent English that faithfully reflects the tone, personality, and style of the original Korean text.

-------------------------------
CRITICAL FORMATTING RULES
-------------------------------
1. Preserve ALL line breaks EXACTLY as they appear in the original Korean text.  
2. Each paragraph separation (double newline) must be maintained.  
3. Single line breaks within paragraphs must be preserved.  
4. Do NOT add or remove any line breaks.  
5. Maintain the same number of blank lines between paragraphs.  
6. Translate naturally but keep the original paragraph and sentence structure intact.  
7. Do NOT include encoded strings, metadata, tags, or system text.  
8. Only output readable English text.  

-------------------------------
CHARACTER CONSISTENCY
-------------------------------
- If a character glossary is provided, you MUST use those exact names.  
- If pronouns (he/him, she/her, they/them) are specified, apply them consistently.  
- For characters marked "AI Auto-select," determine pronouns contextually based on tone and narrative cues.  
- Maintain consistent naming and pronoun choices throughout the story.  
- Never alter character names, ranks, or titles.  

-------------------------------
KOREAN→ENGLISH TRANSLATION STYLE GUIDE
-------------------------------
1. **Tone and Register**
   - Accurately reflect Korean honorifics, formality, and speech hierarchy in natural English.
   - Avoid overly literal translations of politeness levels; instead, express them through tone, diction, or context.
   - Preserve the emotional tone of dialogue (e.g., playful, formal, awkward, deferential, cold, etc.).

2. **Cultural and Linguistic Nuance**
   - Adapt culture-specific terms (e.g., oppa, sunbae, ahjumma) depending on context:
     - Retain them if they carry emotional or relational meaning not captured in English.
     - Translate descriptively if it improves clarity for the reader.
   - Preserve the spirit of idioms and proverbs using equivalent English expressions when possible.
   - Maintain flavor and rhythm typical of Korean web novels—introspective tone, casual inner monologue, or dramatic phrasing.

3. **Internal Monologue and Dialogue**
   - Clearly differentiate between spoken dialogue, thoughts, and narration.
   - Inner monologues should sound natural in English while preserving the Korean tone (e.g., self-deprecating, ironic, etc.).
   - Avoid robotic or overly formal phrasing.

4. **Terminology and Worldbuilding**
   - For fantasy or system-based novels, maintain consistent translation of recurring terms (skills, titles, items, etc.).
   - Use capitalization for system messages or interface terms if the original does (e.g., "Quest Completed", "Dungeon Gate").

5. **Faithfulness and Flow**
   - Translate meaning, not word order — prioritize readability and emotional accuracy.
   - Do not embellish or censor content; keep to the author's tone.
   - When nuance is ambiguous, default to the interpretation most consistent with prior context.

-------------------------------
QUALITY CONTROL
-------------------------------
- Double-check that each translated section preserves the **same paragraphing, line breaks, and structure** as the Korean text.  
- Eliminate mistranslations, missing lines, or formatting drift.  
- Ensure smooth, fluent English that reads like a professionally published web novel translation.

-------------------------------
OUTPUT RULES
-------------------------------
- Output only the translated English text.  
- Do NOT include explanations, metadata, or internal notes.  
- Maintain all formatting rules exactly.
"""

        # Build glossary instructions (same as translate_text)
        glossary_instructions = ""
        if glossary and len(glossary) > 0:
            glossary_instructions = "\n\nCHARACTER GLOSSARY - Use these EXACT translations:\n"
            for char_id, char_info in glossary.items():
                korean_name = char_info.get('korean_name', '')
                english_name = char_info.get('english_name', '')
                gender = char_info.get('gender', '')
                
                glossary_instructions += f"\n- {korean_name} → {english_name}"
                
                if gender == 'male':
                    glossary_instructions += " (Use he/him pronouns)"
                elif gender == 'female':
                    glossary_instructions += " (Use she/her pronouns)"
                elif gender == 'other':
                    glossary_instructions += " (Use they/them pronouns)"
                elif gender == 'auto':
                    glossary_instructions += " (Determine appropriate pronouns from context)"
        
        # Build image context
        image_context = ""
        if images and len(images) > 0:
            image_context = "\n\nNote: This chapter contains images at the following positions:\n"
            for img in images:
                image_context += f"[IMAGE_{img.get('index', 0)}] - {img.get('alt', 'Image')}\n"
        
        user_prompt = f"""CRITICAL INSTRUCTIONS:
1. Preserve ALL line breaks and paragraph spacing EXACTLY as in the original
2. Keep the same number of blank lines between paragraphs
3. Maintain the exact formatting structure
4. Preserve any [IMAGE_X] markers in their exact positions
5. Do not add or remove any line breaks
6. Translate the content naturally while keeping the original structure
7. IGNORE any encoded strings or metadata - only translate readable text
8. Output ONLY readable English text, no encoded content

{glossary_instructions}

{image_context}

Korean text:
{text}"""

        # Estimate tokens based on provider
        if provider in ['openrouter', 'openai']:
            try:
                # Use tiktoken for OpenAI-compatible models
                encoding = tiktoken.get_encoding('cl100k_base')  # Works for most OpenAI models

                # Estimate input tokens (system prompt + user prompt)
                input_tokens = len(encoding.encode(system_prompt + user_prompt))

                # Estimate output tokens based on the SOURCE TEXT only, not the entire prompt
                # Korean text is more compact, so English translation is typically 1.2-1.5x longer
                text_tokens = len(encoding.encode(text))
                output_tokens = int(text_tokens * 1.3)

                return {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'estimation_method': 'tiktoken'
                }
            except Exception as e:
                print(f"Error using tiktoken, falling back to rough estimation: {e}")
                return estimate_tokens_rough(text, system_prompt, user_prompt)
        else:
            # Google Gemini and others - use rough estimation
            return estimate_tokens_rough(text, system_prompt, user_prompt)

    except Exception as e:
        print(f"Error estimating translation tokens: {e}")
        return estimate_tokens_rough(text, system_prompt, user_prompt)


def estimate_tokens_rough(text, system_prompt="", user_prompt=""):
    """
    Rough token estimation when tiktoken is not available or for non-OpenAI models.

    Uses character-based estimation:
    - Korean text: ~4 characters per token
    - English text: ~3 characters per token
    - Mixed: weighted average
    """
    # Count Korean characters (Hangul range)
    korean_chars = sum(1 for c in text if ord(c) >= 0xAC00 and ord(c) <= 0xD7A3)
    total_chars = len(text)
    english_chars = total_chars - korean_chars

    # Estimate tokens for Korean and English portions of source text
    korean_tokens = korean_chars / 4.0
    english_tokens = english_chars / 3.0
    text_tokens = int(korean_tokens + english_tokens)

    # Estimate prompt tokens (mostly English)
    prompt_tokens = int(len(system_prompt + user_prompt) / 3.0)

    # Input = full prompt (system + user prompt which includes the text)
    input_tokens = prompt_tokens

    # Output = estimated based on source TEXT only, not entire prompt
    # Translations are typically 1.2-1.5x longer when going Korean -> English
    output_tokens = int(text_tokens * 1.3)

    return {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': input_tokens + output_tokens,
        'estimation_method': 'rough'
    }

