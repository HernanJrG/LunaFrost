# Implementation Plan: Feature #10 - Translation Cost Tracker (Token-Based)

## Overview
Implement a token usage tracking system that displays token counts for translations, allowing users to calculate costs themselves. This avoids maintaining a pricing database while still providing valuable cost estimation information.

## Goals
1. Extract and store token usage from API responses (input tokens, output tokens, total tokens)
2. Display token counts to users before and after translation
3. Show cumulative token usage per novel, per month, and overall
4. Provide a token usage dashboard for cost analysis
5. **NO pricing database** - users calculate costs themselves using current provider pricing

## Research: Automatic Price Fetching
Before implementation, we should check if we can automatically fetch pricing:
- **OpenRouter**: Has a pricing API endpoint (`/api/v1/models`) that returns current pricing
- **OpenAI**: Pricing is published but may require web scraping or manual updates
- **Google Gemini**: Pricing available via API documentation but may need manual updates

**Decision**: We'll implement a hybrid approach:
- Try to fetch pricing from OpenRouter API automatically (if available)
- For other providers, show token counts only
- If automatic pricing is available, show estimated cost; otherwise, show tokens with a note

---

## Phase 1: Backend - Token Extraction & Storage

### 1.1 Modify `services/ai_service.py`
**File**: `Translator/services/ai_service.py`

**Changes**:
- Modify `translate_text()` to return both translation text AND token usage
- Extract token usage from API responses:
  - **OpenRouter/OpenAI**: `response.json().get('usage', {})` contains:
    - `prompt_tokens` (input tokens)
    - `completion_tokens` (output tokens)  
    - `total_tokens`
  - **Google Gemini**: `response.json().get('usageMetadata', {})` contains:
    - `promptTokenCount` (input tokens)
    - `candidatesTokenCount` (output tokens)
    - `totalTokenCount`

**New Return Format**:
```python
{
    'translated_text': str,
    'token_usage': {
        'input_tokens': int,
        'output_tokens': int,
        'total_tokens': int,
        'provider': str,
        'model': str
    }
}
```

**Implementation Steps**:
1. Update `translate_text()` function signature to return dict instead of string
2. Extract usage data from response after successful translation
3. Handle both string errors (backward compatibility) and dict returns
4. Update all callers to handle new return format

### 1.2 Create Token Usage Model
**File**: `Translator/models/db_models.py`

**New Model**:
```python
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
```

**Migration**:
- Create Alembic migration to add new table
- Or use SQLAlchemy to create table on first run

### 1.3 Add Token Usage Fields to Chapter Model (Optional)
**File**: `Translator/models/db_models.py`

**Optional Enhancement**: Add summary fields to Chapter model for quick access:
```python
# Add to Chapter model
last_translation_input_tokens = Column(Integer)
last_translation_output_tokens = Column(Integer)
last_translation_total_tokens = Column(Integer)
last_translation_provider = Column(String(50))
last_translation_model = Column(String(100))  # Already exists
```

**Note**: This is optional - we can query `TranslationTokenUsage` table instead, but having it on Chapter makes queries faster.

### 1.4 Create Token Usage Service
**File**: `Translator/services/token_usage_service.py` (NEW)

**Functions**:
```python
def save_token_usage(user_id, chapter_id, provider, model, input_tokens, output_tokens, total_tokens, translation_type='content'):
    """Save token usage to database"""
    
def get_chapter_token_usage(chapter_id):
    """Get all token usage records for a chapter"""
    
def get_novel_token_usage(novel_id, user_id):
    """Get total token usage for all chapters in a novel"""
    
def get_user_token_usage(user_id, start_date=None, end_date=None):
    """Get user's total token usage for a date range"""
    
def get_token_usage_by_provider(user_id, start_date=None, end_date=None):
    """Get token usage breakdown by provider"""
    
def estimate_tokens(text, provider, model):
    """Estimate token count before translation (for pre-translation display)"""
    # Use tiktoken for OpenAI models
    # Use approximate estimation for others
```

### 1.5 Update API Routes
**File**: `Translator/routes/api_routes.py`

**Changes**:
1. Update `/api/translate` endpoint:
   - Handle new return format from `translate_text()`
   - Save token usage to database
   - Return token usage in response
   
2. Create new endpoints:
   - `GET /api/chapter/<chapter_id>/token-usage` - Get token usage for a chapter
   - `GET /api/novel/<novel_id>/token-usage` - Get token usage for a novel
   - `GET /api/token-usage/stats` - Get user's token usage statistics
   - `POST /api/translate/estimate` - Estimate tokens before translation

3. Update `/api/save-translation`:
   - Optionally save token usage if provided

### 1.6 Update Translation Tasks
**File**: `Translator/tasks/translation_tasks.py`

**Changes**:
- Update `translate_chapter_task()` to:
  - Handle new return format from `translate_text()`
  - Save token usage for both title and content translations
  - Store token usage in database

---

## Phase 2: Optional - Automatic Price Fetching

### 2.1 OpenRouter Price Fetcher
**File**: `Translator/services/pricing_service.py` (NEW)

**Function**:
```python
def fetch_openrouter_pricing():
    """Fetch current pricing from OpenRouter API"""
    try:
        response = requests.get('https://openrouter.ai/api/v1/models')
        # Parse and return pricing data
    except:
        return None

def get_model_pricing(provider, model):
    """Get pricing for a specific model"""
    if provider == 'openrouter':
        pricing = fetch_openrouter_pricing()
        # Look up model in pricing data
    # For other providers, return None (user calculates manually)
```

**Note**: This is optional. If we can't reliably fetch prices, we skip this and only show tokens.

---

## Phase 3: Frontend - Token Display

### 3.1 Update Translation UI
**File**: `Translator/static/js/chapter.js`

**Changes**:
1. **Before Translation**: 
   - Add token estimation display in translation confirmation
   - Show estimated input/output tokens before user confirms

2. **After Translation**:
   - Display token usage in success message
   - Show token counts in a badge/indicator
   - Update UI to show: "Translation complete! Used X input tokens, Y output tokens (Z total)"

3. **Token Display Component**:
   - Create a reusable token display widget
   - Show: Input tokens | Output tokens | Total tokens
   - Optional: Show estimated cost if pricing available

### 3.2 Update Chapter Template
**File**: `Translator/templates/chapter.html`

**Changes**:
- Add token usage display section (after translation status)
- Show token counts if available
- Add tooltip explaining what tokens mean

**Example**:
```html
<div id="token-usage-display" class="token-usage hidden">
    <span class="token-badge">
        📊 Tokens: <span id="input-tokens">-</span> input / 
        <span id="output-tokens">-</span> output 
        (<span id="total-tokens">-</span> total)
    </span>
    <span class="token-help" title="Use these token counts with your provider's pricing to calculate cost">ℹ️</span>
</div>
```

### 3.3 Update Novel Page
**File**: `Translator/templates/novel.html`

**Changes**:
- Show total token usage per chapter in chapter list
- Add summary at top: "Total tokens used: X (across all chapters)"
- Show token usage badge next to translated chapters

### 3.4 Create Token Usage Dashboard
**File**: `Translator/templates/token_usage.html` (NEW)

**Features**:
- Total tokens used (all time, this month, this week)
- Token breakdown by provider
- Token breakdown by novel
- Token breakdown by model
- Most token-intensive chapters
- Average tokens per chapter
- Token usage trend chart (over time)
- Export token usage data as CSV

**Route**: `GET /token-usage` in `main_routes.py`

---

## Phase 4: Token Estimation (Pre-Translation)

### 4.1 Token Estimation Service
**File**: `Translator/services/token_usage_service.py`

**Function**:
```python
def estimate_translation_tokens(text, provider, model, glossary=None, images=None):
    """Estimate token count before translation"""
    import tiktoken
    
    # Build full prompt (same as translate_text)
    system_prompt = "..."  # Same as in translate_text
    user_prompt = f"...{text}..."  # Same structure
    
    # Estimate tokens
    if provider in ['openrouter', 'openai']:
        try:
            encoding = tiktoken.get_encoding('cl100k_base')  # For most OpenAI models
            input_tokens = len(encoding.encode(system_prompt + user_prompt))
            # Estimate output: typically 1.2x input for translations
            output_tokens = int(input_tokens * 1.2)
            return {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens
            }
        except:
            # Fallback estimation
            return estimate_tokens_rough(text)
    else:
        # Rough estimation for Google and others
        return estimate_tokens_rough(text)

def estimate_tokens_rough(text):
    """Rough token estimation (4 chars per token for Korean, 3 for English)"""
    # Korean text: ~4 characters per token
    # English text: ~3 characters per token
    # Mixed: use average
    korean_chars = len([c for c in text if ord(c) >= 0xAC00 and ord(c) <= 0xD7A3])
    total_chars = len(text)
    estimated_tokens = (korean_chars / 4) + ((total_chars - korean_chars) / 3)
    return {
        'input_tokens': int(estimated_tokens),
        'output_tokens': int(estimated_tokens * 1.2),
        'total_tokens': int(estimated_tokens * 2.2)
    }
```

### 4.2 Pre-Translation Estimation API
**File**: `Translator/routes/api_routes.py`

**Endpoint**:
```python
@api_bp.route('/translate/estimate', methods=['POST'])
def estimate_translation_tokens():
    """Estimate token usage before translation"""
    user_id = get_user_id()
    data = request.json
    text = data.get('text', '')
    novel_id = data.get('novel_id', '')
    
    settings = load_settings(user_id)
    provider = settings.get('selected_provider', 'openrouter')
    selected_model = settings.get('provider_models', {}).get(provider, '')
    
    glossary = get_novel_glossary(user_id, novel_id) if novel_id else {}
    images = data.get('images', [])
    
    estimation = estimate_translation_tokens(text, provider, selected_model, glossary, images)
    
    return jsonify({
        'success': True,
        'estimation': estimation
    })
```

---

## Phase 5: Database Migration

### 5.1 Create Migration Script
**File**: `Translator/migrations/add_token_usage_table.py` (or use Alembic)

**SQL**:
```sql
CREATE TABLE translation_token_usage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    translation_type VARCHAR(20) DEFAULT 'content',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_token_usage_user_date ON translation_token_usage(user_id, created_at);
CREATE INDEX idx_token_usage_chapter ON translation_token_usage(chapter_id);
```

---

## Phase 6: Testing & Validation

### 6.1 Test Cases
1. **Token Extraction**:
   - Test with OpenRouter API response
   - Test with OpenAI API response
   - Test with Google Gemini API response
   - Test error handling when usage data missing

2. **Token Storage**:
   - Verify tokens saved correctly
   - Test with multiple translations of same chapter
   - Test token aggregation queries

3. **UI Display**:
   - Test token display after translation
   - Test token estimation before translation
   - Test dashboard displays correctly

4. **Edge Cases**:
   - Translation failures (no tokens to save)
   - Missing API response data
   - Very long chapters (token limits)

---

## Implementation Order

1. **Phase 1.1**: Modify `ai_service.py` to extract tokens ✅
2. **Phase 1.2**: Create `TranslationTokenUsage` model ✅
3. **Phase 1.4**: Create token usage service ✅
4. **Phase 1.5**: Update API routes to save tokens ✅
5. **Phase 1.6**: Update translation tasks ✅
6. **Phase 5**: Database migration ✅
7. **Phase 3.1**: Update frontend to display tokens ✅
8. **Phase 3.2**: Update chapter template ✅
9. **Phase 3.3**: Update novel page ✅
10. **Phase 4**: Add token estimation ✅
11. **Phase 3.4**: Create token usage dashboard ✅
12. **Phase 2**: (Optional) Add automatic price fetching ✅
13. **Phase 6**: Testing ✅

---

## Files to Create/Modify

### New Files:
- `Translator/services/token_usage_service.py`
- `Translator/services/pricing_service.py` (optional)
- `Translator/templates/token_usage.html`
- `Translator/migrations/add_token_usage_table.py`

### Modified Files:
- `Translator/services/ai_service.py`
- `Translator/models/db_models.py`
- `Translator/routes/api_routes.py`
- `Translator/routes/main_routes.py`
- `Translator/tasks/translation_tasks.py`
- `Translator/static/js/chapter.js`
- `Translator/templates/chapter.html`
- `Translator/templates/novel.html`

---

## User Experience Flow

### Before Translation:
1. User clicks "Translate" button
2. System estimates token usage
3. Shows: "Estimated: ~X input tokens, ~Y output tokens"
4. User confirms translation

### During Translation:
1. Translation in progress (existing UI)
2. Token usage extracted from API response

### After Translation:
1. Success message: "Translation complete!"
2. Token badge: "📊 Tokens: 1,234 input / 1,480 output (2,714 total)"
3. Tooltip: "Use these counts with your provider's pricing to calculate cost"

### Token Dashboard:
1. User navigates to `/token-usage`
2. Sees comprehensive breakdown:
   - Total tokens: 125,430
   - By provider: OpenRouter (80K), OpenAI (45K)
   - By novel: Novel A (60K), Novel B (65K)
   - This month: 15,230 tokens
   - Average per chapter: 2,100 tokens

---

## Notes & Considerations

1. **Backward Compatibility**: 
   - Existing translations won't have token data
   - Handle gracefully (show "N/A" or hide token display)

2. **Performance**:
   - Token usage queries should be indexed
   - Consider caching aggregated stats

3. **Privacy**:
   - Token usage is user-specific
   - No sharing of usage data

4. **Accuracy**:
   - Actual tokens may differ from estimates
   - Always show actual tokens after translation
   - Estimates are rough approximations

5. **Future Enhancements**:
   - Export token usage as CSV
   - Set token usage alerts/budgets
   - Compare token efficiency across models
   - Token usage recommendations ("Switch to model X to save Y tokens")

---

## Success Criteria

✅ Token usage extracted from all API responses  
✅ Token usage stored in database  
✅ Token counts displayed to users  
✅ Token estimation before translation works  
✅ Token usage dashboard functional  
✅ No pricing database required  
✅ Users can calculate costs themselves using token counts  

---

## Estimated Development Time

- Phase 1 (Backend): 3-4 hours
- Phase 2 (Optional Pricing): 1-2 hours
- Phase 3 (Frontend): 2-3 hours
- Phase 4 (Estimation): 1-2 hours
- Phase 5 (Migration): 30 minutes
- Phase 6 (Testing): 1-2 hours

**Total**: 8-13 hours (depending on optional features)

