import json
import re
import requests
import html

def clean_korean_text(text):
    """Clean and normalize Korean text before translation (unchanged)"""
    text = re.sub(r'[A-Za-z0-9+/]{40,}={0,2}', '', text)
    text = html.unescape(text)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        cleaned = ' '.join(line.split())
        cleaned_lines.append(cleaned)
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    return text

def extract_translation_text(result):
    """
    Helper function to extract translated text from translate_text result.
    Handles both old string format and new dict format for backward compatibility.
    
    Args:
        result: Result from translate_text (can be dict or string)
    
    Returns:
        tuple: (translated_text: str or None, error: str or None, token_usage: dict or None)
    """
    if isinstance(result, dict):
        if result.get('error'):
            return None, result.get('error'), None
        return result.get('translated_text'), None, result.get('token_usage')
    elif isinstance(result, str):
        # Old format: string result
        if result.startswith("Error") or any(result.startswith(p) for p in ["OpenRouter", "OpenAI", "Google"]):
            return None, result, None
        return result, None, None
    return None, "Unknown result format", None

def translate_text(text, provider, api_key, selected_model, glossary=None, images=None, is_thinking_mode=False):
    """
    Translate Korean text to English using the selected provider via requests.
    
    Returns:
        dict: {
            'translated_text': str or None,
            'token_usage': dict or None (with input_tokens, output_tokens, total_tokens, provider, model),
            'error': str or None
        }
    """
    if not api_key:
        return {'error': 'API key not configured.', 'translated_text': None, 'token_usage': None}
    
    try:
        text = clean_korean_text(text)
        
        # Build glossary instructions (unchanged)
        glossary_instructions = ""
        if glossary and len(glossary) > 0:
            glossary_instructions = "\n\nCHARACTER GLOSSARY - Use these EXACT translations:\n"
            for char_id, char_info in glossary.items():
                korean_name = char_info.get('korean_name', '')
                english_name = char_info.get('english_name', '')
                gender = char_info.get('gender', '')
                # Note: description is not sent to AI - it's only for user notes and popup display
                
                glossary_instructions += f"\n- {korean_name} → {english_name}"
                
                if gender == 'male':
                    glossary_instructions += " (Use he/him pronouns)"
                elif gender == 'female':
                    glossary_instructions += " (Use she/her pronouns)"
                elif gender == 'other':
                    glossary_instructions += " (Use they/them pronouns)"
                elif gender == 'auto':
                    glossary_instructions += " (Determine appropriate pronouns from context)"
                
                # Description removed from AI prompt - kept only for user reference
                # if description:
                #     glossary_instructions += f" - {description}"
        
        # Build image context (unchanged)
        image_context = ""
        if images and len(images) > 0:
            image_context = "\n\nNote: This chapter contains images at the following positions:\n"
            for img in images:
                image_context += f"[IMAGE_{img.get('index', 0)}] - {img.get('alt', 'Image')}\n"
        
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

        headers = {"Content-Type": "application/json"}
        json_payload = {}
        
        # Set token limit based on mode
        # Thinking models need significantly more tokens for internal reasoning
        max_tokens = 64000 if is_thinking_mode else 4000
        
        if provider == 'openrouter':
            headers["Authorization"] = f"Bearer {api_key}"
            headers["HTTP-Referer"] = "http://localhost:5000"
            headers["X-Title"] = "Novel Translator"
            json_payload = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": max_tokens
            }
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'openai':
            headers["Authorization"] = f"Bearer {api_key}"
            
            # OpenAI o1 models use max_completion_tokens instead of max_tokens
            # and may not support system messages in the same way (mapped to developer or user)
            # But for compatibility we keep structure, just update token param name if needed
            token_param = "max_completion_tokens" if "o1-" in selected_model else "max_tokens"
            
            json_payload = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 1 if "o1-" in selected_model else 0.3, # o1 fixed temp
            }
            json_payload[token_param] = max_tokens
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'google':
            # Gemini uses a different structure; API key in URL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
            json_payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_prompt}\n\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.3
                }
            }
            response = requests.post(url, headers=headers, json=json_payload)
        
        else:
            return {'error': 'Unsupported provider. Please use OpenRouter, OpenAI, or Google Gemini.', 'translated_text': None, 'token_usage': None}
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract token usage from response
            token_usage = None
            if provider == 'google':
                # Gemini-specific response parsing
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        translated_text = parts[0].get('text', '')
                    else:
                        return {'error': 'Google API Error: No content in response.', 'translated_text': None, 'token_usage': None}
                else:
                    return {'error': 'Google API Error: No candidates in response.', 'translated_text': None, 'token_usage': None}
                
                # Extract token usage from Gemini response
                usage_metadata = data.get('usageMetadata', {})
                if usage_metadata:
                    token_usage = {
                        'input_tokens': usage_metadata.get('promptTokenCount', 0),
                        'output_tokens': usage_metadata.get('candidatesTokenCount', 0),
                        'total_tokens': usage_metadata.get('totalTokenCount', 0),
                        'provider': provider,
                        'model': selected_model
                    }
            else:
                # OpenRouter/OpenAI structure
                choices = data.get('choices', [])
                if choices:
                    translated_text = choices[0].get('message', {}).get('content', '')
                else:
                    return {'error': f'{provider.capitalize()} API Error: No choices in response.', 'translated_text': None, 'token_usage': None}
                
                # Extract token usage from OpenRouter/OpenAI response
                usage = data.get('usage', {})
                if usage:
                    token_usage = {
                        'input_tokens': usage.get('prompt_tokens', 0),
                        'output_tokens': usage.get('completion_tokens', 0),
                        'total_tokens': usage.get('total_tokens', 0),
                        'provider': provider,
                        'model': selected_model
                    }
            
            # Clean response (unchanged)
            translated_text = re.sub(r'[A-Za-z0-9+/]{40,}={0,2}', '[corrupted data removed]', translated_text)
            
            # Return dict with translation and token usage
            return {
                'translated_text': translated_text,
                'token_usage': token_usage,
                'error': None
            }
        else:
            error_msg = f"{provider.capitalize()} API Error: {response.status_code}"
            try:
                error_data = response.json()
                error_msg += f" - {error_data.get('error', {}).get('message', 'Unknown error')}"
            except:
                pass
            return {'error': error_msg, 'translated_text': None, 'token_usage': None}
            
    except Exception as e:
        return {'error': f'{provider.capitalize()} error: {str(e)}', 'translated_text': None, 'token_usage': None}

def detect_characters(text, provider, api_key, selected_model):
    """Use AI to detect character names in Korean text."""
    if not api_key:
        return {'error': 'API key not configured'}
    
    try:
        sample_text = text[:3000] if len(text) > 3000 else text
        
        system_prompt = """You are a Korean web novel character name extraction expert.
Your task is to identify ALL character names mentioned in the Korean text.

Rules:
1. Extract both full names and single names (e.g., 김철수 and 철수)
2. Only extract actual character names, not titles or occupations
3. Return as a JSON array of unique Korean names
4. Focus on recurring names that are likely main or supporting characters"""

        user_prompt = f"""Analyze this Korean novel text and extract all character names.

Return ONLY a valid JSON array like this:
["김철수", "이영희", "박민수"]

Korean text:
{sample_text}"""

        headers = {"Content-Type": "application/json"}
        json_payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        if provider == 'openrouter':
            headers["Authorization"] = f"Bearer {api_key}"
            headers["HTTP-Referer"] = "http://localhost:5000"
            headers["X-Title"] = "Novel Translator"
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'openai':
            headers["Authorization"] = f"Bearer {api_key}"
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'google':
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
            json_payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_prompt}\n\n{user_prompt}"}
                        ]
                    }
                ]
            }
            response = requests.post(url, headers=headers, json=json_payload)
        
        else:
            return {'error': 'Unsupported provider. Please use OpenRouter, OpenAI, or Google Gemini.'}
        
        if response.status_code == 200:
            data = response.json()
            
            if provider == 'google':
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        content_str = parts[0].get('text', '')
                    else:
                        return {'error': 'Google API: No content.'}
                else:
                    return {'error': 'Google API: No candidates.'}
            else:
                choices = data.get('choices', [])
                if choices:
                    content_str = choices[0].get('message', {}).get('content', '')
                else:
                    return {'error': f'{provider.capitalize()} API: No choices.'}
            
            try:
                if '```json' in content_str:
                    content_str = content_str.split('```json')[1].split('```')[0].strip()
                elif '```' in content_str:
                    content_str = content_str.split('```')[1].split('```')[0].strip()
                
                characters = json.loads(content_str)
                return {'success': True, 'characters': characters}
            except json.JSONDecodeError:
                return {'error': 'Failed to parse AI response'}
        else:
            return {'error': f'{provider.capitalize()} API Error: {response.status_code}'}
            
    except Exception as e:
        return {'error': str(e)}

def translate_names(korean_names, provider, api_key, selected_model):
    """Translate Korean character names to English."""
    if not api_key:
        return {'error': 'API key not configured'}
    
    try:
        system_prompt = """You are a Korean to English name translator for web novels.
Your task is to translate Korean names to natural English equivalents.

Rules:
1. Translate Korean names to English names that sound natural
2. Keep the Korean surname structure (e.g., Kim, Lee, Park)
3. Choose appropriate English given names
4. Return as a JSON object mapping Korean names to English names"""

        names_list = "\n".join(korean_names)
        user_prompt = f"""Translate these Korean character names to English.

Return ONLY a valid JSON object like this:
{{"김철수": "John Kim", "이영희": "Sarah Lee", "박민수": "Michael Park"}}

Korean names:
{names_list}"""

        headers = {"Content-Type": "application/json"}
        json_payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        if provider == 'openrouter':
            headers["Authorization"] = f"Bearer {api_key}"
            headers["HTTP-Referer"] = "http://localhost:5000"
            headers["X-Title"] = "Novel Translator"
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'openai':
            headers["Authorization"] = f"Bearer {api_key}"
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'google':
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
            json_payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_prompt}\n\n{user_prompt}"}
                        ]
                    }
                ]
            }
            response = requests.post(url, headers=headers, json=json_payload)
        
        else:
            return {'error': 'Unsupported provider. Please use OpenRouter, OpenAI, or Google Gemini.'}
        
        if response.status_code == 200:
            data = response.json()
            
            if provider == 'google':
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        content_str = parts[0].get('text', '')
                    else:
                        return {'error': 'Google API: No content.'}
                else:
                    return {'error': 'Google API: No candidates.'}
            else:
                choices = data.get('choices', [])
                if choices:
                    content_str = choices[0].get('message', {}).get('content', '')
                else:
                    return {'error': f'{provider.capitalize()} API: No choices.'}
            
            try:
                if '```json' in content_str:
                    content_str = content_str.split('```json')[1].split('```')[0].strip()
                elif '```' in content_str:
                    content_str = content_str.split('```')[1].split('```')[0].strip()
                
                translations = json.loads(content_str)
                return {'success': True, 'translations': translations}
            except json.JSONDecodeError:
                return {'error': 'Failed to parse AI response'}
        else:
            return {'error': f'{provider.capitalize()} API Error: {response.status_code}'}
            
    except Exception as e:
        return {'error': str(e)}

def detect_character_genders(korean_names, text_sample, provider, api_key, selected_model):
    """Use AI to detect likely gender/pronouns for each character based on context."""
    if not api_key:
        return {'error': 'API key not configured'}
    
    try:
        system_prompt = """You are a Korean web novel character analysis expert.
Your task is to determine the most appropriate pronouns for each character based on the story context.

Rules:
1. Analyze how each character is portrayed in the text
2. Determine if the character should use he/him, she/her, or they/them pronouns
3. Base your decision on Korean pronouns, titles, descriptions, and context clues
4. Return as a JSON object mapping Korean names to pronoun types
5. Use "male" for he/him, "female" for she/her, "other" for they/them
6. If uncertain, default to "auto" which means the translator should decide based on broader context"""

        names_list = "\n".join(korean_names)
        user_prompt = f"""Analyze these character names in the context of the story and determine appropriate pronouns.

Character names:
{names_list}

Story excerpt:
{text_sample[:2000]}

Return ONLY a valid JSON object like this:
{{"김철수": "male", "이영희": "female", "박민수": "male"}}

Valid values are: "male" (he/him), "female" (she/her), "other" (they/them), or "auto" (let translator decide)"""

        headers = {"Content-Type": "application/json"}
        json_payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        if provider == 'openrouter':
            headers["Authorization"] = f"Bearer {api_key}"
            headers["HTTP-Referer"] = "http://localhost:5000"
            headers["X-Title"] = "Novel Translator"
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'openai':
            headers["Authorization"] = f"Bearer {api_key}"
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=json_payload)
        
        elif provider == 'google':
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
            json_payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_prompt}\n\n{user_prompt}"}
                        ]
                    }
                ]
            }
            response = requests.post(url, headers=headers, json=json_payload)
        
        else:
            return {'error': 'Unsupported provider. Please use OpenRouter, OpenAI, or Google Gemini.'}
        
        if response.status_code == 200:
            data = response.json()
            
            if provider == 'google':
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        content_str = parts[0].get('text', '')
                    else:
                        return {'error': 'Google API: No content.'}
                else:
                    return {'error': 'Google API: No candidates.'}
            else:
                choices = data.get('choices', [])
                if choices:
                    content_str = choices[0].get('message', {}).get('content', '')
                else:
                    return {'error': f'{provider.capitalize()} API: No choices.'}
            
            try:
                if '```json' in content_str:
                    content_str = content_str.split('```json')[1].split('```')[0].strip()
                elif '```' in content_str:
                    content_str = content_str.split('```')[1].split('```')[0].strip()
                
                genders = json.loads(content_str)
                return {'success': True, 'genders': genders}
            except json.JSONDecodeError:
                return {'error': 'Failed to parse AI response'}
        else:
            return {'error': f'{provider.capitalize()} API Error: {response.status_code}'}
            
    except Exception as e:
        return {'error': str(e)}

