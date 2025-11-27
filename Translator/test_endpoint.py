from flask import jsonify, request
from models.settings import load_settings  
from models.novel import get_novel_glossary
from services.token_usage_service import estimate_translation_tokens
from services.pricing_service import calculate_cost

def estimate_translation_tokens_endpoint():
    """Estimate token usage before translation"""
    try:
        # Get user_id mockup
        user_id = 'test'
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
            if req_provider:
                provider = req_provider
            else:
                if '/' in selected_model:
                    provider = 'openrouter'
                else:
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
