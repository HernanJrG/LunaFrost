""" 
Pricing service for fetching and managing AI model pricing.

This service attempts to fetch current pricing from provider APIs.
Currently supports OpenRouter API for automatic pricing updates.
"""
import requests
import json
from datetime import datetime, timedelta
from functools import lru_cache
import time
import re

# Cache pricing data for 24 hours
PRICING_CACHE_DURATION = timedelta(hours=24)
_pricing_cache = {
    'data': None,
    'timestamp': None,
    'source': None
}


def fetch_openrouter_pricing():
    """
    Fetch current pricing from OpenRouter API.
    
    Returns:
        dict: Pricing data by model, or None if fetch fails
        Format: {
            'model_id': {
                'pricing': {
                    'prompt': float,  # price per 1M input tokens
                    'completion': float  # price per 1M output tokens
                },
                'context_length': int,
                'architecture': dict
            }
        }
    """
    try:
        response = requests.get(
            'https://openrouter.ai/api/v1/models',
            headers={
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse OpenRouter models response
            pricing_data = {}
            
            if 'data' in data:
                for model in data['data']:
                    model_id = model.get('id', '')
                    if not model_id:
                        continue
                    
                    # Extract pricing information (may be absent or zero)
                    pricing_info = model.get('pricing', {})
                    # Keep None when provider does not include a field
                    prompt_price = pricing_info.get('prompt')
                    completion_price = pricing_info.get('completion')

                    # Include the model in the returned catalog even if pricing is 0 or missing.
                    pricing_data[model_id] = {
                        'pricing': {
                            'prompt': prompt_price,  # per 1M tokens or None
                            'completion': completion_price  # per 1M tokens or None
                        },
                        'context_length': model.get('context_length', 0),
                        'architecture': model.get('architecture', {}),
                        'name': model.get('name', model_id),
                        'raw': model
                    }
            
            return pricing_data
        else:
            print(f"OpenRouter API returned status {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching OpenRouter pricing: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching OpenRouter pricing: {e}")
        return None


def get_cached_openrouter_pricing():
    """
    Get cached OpenRouter pricing, fetching if cache is expired.
    Manual cache management (not using lru_cache due to time-based expiration).
    
    Returns:
        dict: Pricing data or None
    """
    global _pricing_cache
    
    now = datetime.now()
    
    # Check if cache is valid
    if (_pricing_cache['data'] is not None and 
        _pricing_cache['timestamp'] is not None and
        _pricing_cache['source'] == 'openrouter' and
        now - _pricing_cache['timestamp'] < PRICING_CACHE_DURATION):
        return _pricing_cache['data']
    
    # Fetch new pricing
    pricing_data = fetch_openrouter_pricing()
    
    if pricing_data:
        _pricing_cache['data'] = pricing_data
        _pricing_cache['timestamp'] = now
        _pricing_cache['source'] = 'openrouter'
    
    return pricing_data


def normalize_model_name(name):
    """Normalize model name for comparison."""
    if not name:
        return ''
    # Lowercase and strip common suffixes like -001, -v1, etc.
    n = name.lower()
    # Remove trailing version-like suffixes
    n = re.sub(r'[-_]v?\d+(?:\.\d+)*$', '', n)
    n = re.sub(r'[-_]\d{1,4}$', '', n)
    return n


def strip_variants(name):
    """Remove common suffixes/versions to increase match probability."""
    if not name:
        return name
    n = re.sub(r'[-_]v?\d+(?:\.\d+)*$', '', name)
    n = re.sub(r'[-_](lite|flash|o1|r1|001)$', '', n)
    return n


def find_best_model_match(target_model, pricing_data):
    """
    Find the best matching model from pricing data.
    
    Args:
        target_model: Model identifier to search for
        pricing_data: Dictionary of available models
    
    Returns:
        tuple: (model_id, model_data) or (None, None) if no match
    """
    target = normalize_model_name(target_model)
    candidates = []
    
    for model_id, model_data in pricing_data.items():
        mid = normalize_model_name(model_id)
        
        # Exact match - highest priority
        if target == mid:
            candidates.append((0, model_id, model_data))
            continue

        # Contains / substring matches
        if target in mid or mid in target:
            candidates.append((1, model_id, model_data))
            continue

        # Match on last path component (e.g., 'gemini-2.0-flash')
        try:
            target_last = target.split('/')[-1]
            mid_last = mid.split('/')[-1]
            if target_last == mid_last or target_last in mid_last or mid_last in target_last:
                candidates.append((2, model_id, model_data))
                continue
        except Exception:
            pass

        # Try stripping common suffixes and compare
        try:
            if strip_variants(target) == strip_variants(mid):
                candidates.append((3, model_id, model_data))
                continue
        except Exception:
            pass

    if candidates:
        # Choose best candidate by lowest score
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1], candidates[0][2]
    
    return None, None


def get_model_pricing(provider, model):
    """
    Get pricing for a specific model.
    
    Args:
        provider: Provider name ('openrouter', 'openai', 'google')
        model: Model identifier
    
    Returns:
        dict: {
            'input_price': float,  # per 1M tokens
            'output_price': float,  # per 1M tokens
            'source': str,  # 'openrouter_api', 'manual', or None
            'available': bool
        } or None if pricing not available
    """
    if provider == 'openrouter':
        pricing_data = get_cached_openrouter_pricing()
        
        if pricing_data:
            # Try exact match first
            if model in pricing_data:
                model_pricing = pricing_data[model]
                return {
                    'input_price': model_pricing['pricing']['prompt'],
                    'output_price': model_pricing['pricing']['completion'],
                    'source': 'openrouter_api',
                    'available': True,
                    'model_name': model_pricing.get('name', model)
                }
            
            # Try fuzzy matching
            best_id, best_data = find_best_model_match(model, pricing_data)
            if best_data:
                return {
                    'input_price': best_data['pricing']['prompt'],
                    'output_price': best_data['pricing']['completion'],
                    'source': 'openrouter_api',
                    'available': True,
                    'model_name': best_data.get('name', best_id)
                }
    
    # For OpenAI and Google, pricing is not available via API
    # Users will need to check pricing pages manually
    return {
        'input_price': None,
        'output_price': None,
        'source': None,
        'available': False
    }


def fetch_openrouter_pricing_with_key(api_key):
    """
    Fetch OpenRouter models using a provided API key (server-side per-user).
    Returns the same format as `fetch_openrouter_pricing` or None on failure.
    """
    if not api_key:
        return None

    try:
        response = requests.get(
            'https://openrouter.ai/api/v1/models',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            pricing_data = {}
            if 'data' in data:
                for model in data['data']:
                    model_id = model.get('id', '')
                    if not model_id:
                        continue
                    pricing_info = model.get('pricing', {})
                    prompt_price = pricing_info.get('prompt')
                    completion_price = pricing_info.get('completion')
                    # Include the model even if pricing values are zero/absent.
                    pricing_data[model_id] = {
                        'pricing': {
                            'prompt': prompt_price,
                            'completion': completion_price
                        },
                        'context_length': model.get('context_length', 0),
                        'architecture': model.get('architecture', {}),
                        'name': model.get('name', model_id),
                        'raw': model
                    }
            return pricing_data
        else:
            print(f"OpenRouter API returned status {response.status_code} when using key")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching OpenRouter pricing with key: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching OpenRouter pricing with key: {e}")
        return None


def fetch_openrouter_raw_with_key(api_key):
    """
    Fetch the raw OpenRouter /models response using the provided API key.
    Returns the parsed JSON on success, or None on failure. This is intended
    for diagnostics so callers can inspect why pricing entries may be missing.
    """
    if not api_key:
        return None

    try:
        response = requests.get(
            'https://openrouter.ai/api/v1/models',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            timeout=10
        )

        try:
            data = response.json()
        except Exception:
            data = {'_raw_text': response.text}

        return {'status_code': response.status_code, 'json': data}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching OpenRouter raw with key: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching OpenRouter raw with key: {e}")
        return None


def get_model_pricing_with_key(provider, model, api_key):
    """
    Try to get model pricing using a provided API key for OpenRouter. Returns
    the same dict shape as `get_model_pricing`.
    """
    if provider != 'openrouter' or not api_key:
        return {
            'input_price': None,
            'output_price': None,
            'source': None,
            'available': False
        }

    pricing_data = fetch_openrouter_pricing_with_key(api_key)
    if not pricing_data:
        return {
            'input_price': None,
            'output_price': None,
            'source': None,
            'available': False
        }

    # Try exact match first
    if model in pricing_data:
        model_pricing = pricing_data[model]
        return {
            'input_price': model_pricing['pricing']['prompt'],
            'output_price': model_pricing['pricing']['completion'],
            'source': 'openrouter_api',
            'available': True,
            'model_name': model_pricing.get('name', model)
        }
    
    # Try fuzzy matching
    best_id, best_data = find_best_model_match(model, pricing_data)
    if best_data:
        return {
            'input_price': best_data['pricing']['prompt'],
            'output_price': best_data['pricing']['completion'],
            'source': 'openrouter_api',
            'available': True,
            'model_name': best_data.get('name', best_id)
        }

    return {
        'input_price': None,
        'output_price': None,
        'source': None,
        'available': False
    }


def calculate_cost(input_tokens, output_tokens, provider, model):
    """
    Calculate estimated cost based on token usage and pricing.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        provider: Provider name
        model: Model identifier
    
    Returns:
        dict: {
            'input_cost': float,
            'output_cost': float,
            'total_cost': float,
            'currency': str,
            'pricing_available': bool,
            'source': str
        }
    """
    pricing = get_model_pricing(provider, model)
    
    if pricing and pricing.get('available'):
        input_price = pricing.get('input_price')
        output_price = pricing.get('output_price')
        
        # Check if prices are available (not None)
        if input_price is not None and output_price is not None:
            # Calculate cost (pricing is per token from OpenRouter API)
            input_cost = input_tokens * input_price
            output_cost = output_tokens * output_price
            total_cost = input_cost + output_cost
            
            return {
                'input_cost': input_cost,
                'output_cost': output_cost,
                'total_cost': total_cost,
                'currency': 'USD',
                'pricing_available': True,
                'source': pricing.get('source', 'unknown')
            }
    
    return {
        'input_cost': None,
        'output_cost': None,
        'total_cost': None,
        'currency': 'USD',
        'pricing_available': False,
        'source': None
    }


def format_cost(cost_dict):
    """
    Format cost for display.
    
    Args:
        cost_dict: Cost dictionary from calculate_cost()
    
    Returns:
        str: Formatted cost string or None
    """
    if not cost_dict or not cost_dict.get('pricing_available'):
        return None
    
    total_cost = cost_dict.get('total_cost')
    if total_cost is None:
        return None
    
    currency = cost_dict.get('currency', 'USD')
    
    if total_cost < 0.01:
        return f"${total_cost:.4f}"
    elif total_cost < 1:
        return f"${total_cost:.3f}"
    else:
        return f"${total_cost:.2f}"


def refresh_pricing_cache():
    """
    Force refresh of pricing cache.
    Useful for manual updates or testing.
    """
    global _pricing_cache
    _pricing_cache['data'] = None
    _pricing_cache['timestamp'] = None
    _pricing_cache['source'] = None
    
    # Fetch new data
    return get_cached_openrouter_pricing()