# LunaFrost Translator - Feature Recommendations

This document outlines potential features to enhance the Korean novel translation application. Features are organized by priority and category.

---

## 🎯 High-Value Features

### 1. Bulk Chapter Translation

**Priority**: High  
**Complexity**: Medium  
**Estimated Development Time**: 4-6 hours

#### Description
Add a "Translate All Untranslated Chapters" button on the novel page that automatically queues translation jobs for all chapters that haven't been translated yet.

#### Current Limitation
Users must manually click "Translate" on each individual chapter, which is tedious for novels with 100+ chapters.

#### Proposed Solution
- Add a prominent button on `novel.html`: "⚡ Translate All Untranslated"
- Create a new API endpoint: `/api/novel/<novel_id>/bulk-translate`
- Use the existing Celery task queue system to process translations in the background
- Show a progress modal with:
  - Total chapters to translate
  - Currently translating chapter
  - Completed count
  - Estimated time remaining
  - Cancel button

#### Technical Implementation
1. **Backend** (`routes/api_routes.py`):
   ```python
   @api_bp.route('/novel/<novel_id>/bulk-translate', methods=['POST'])
   def bulk_translate_novel(novel_id):
       # Get all untranslated chapters
       # Queue each as a Celery task
       # Return task group ID for tracking
   ```

2. **Frontend** (`novel.html`):
   - Add button that triggers bulk translation
   - Poll `/api/task-status/<task_id>` for progress updates
   - Update UI with real-time progress

3. **Task Management** (`tasks/translation_tasks.py`):
   - Use Celery groups or chains to batch translate
   - Implement retry logic for failed translations
   - Send notification when complete

#### User Benefits
- Save hours of manual clicking
- Translate entire novels overnight
- Set it and forget it workflow

#### Configuration Options
- Select which AI model to use (thinking mode vs. standard)
- Choose translation order (sequential vs. random)
- Set concurrent translation limit (to manage API costs)

---

### 2. Translation Quality Comparison

**Priority**: Medium  
**Complexity**: Medium  
**Estimated Development Time**: 6-8 hours

#### Description
Allow users to generate multiple translations of the same chapter using different AI models, then compare them side-by-side to choose the best version.

#### Current Limitation
Once a chapter is translated, re-translating overwrites the previous version. Users can't A/B test different models or translation approaches.

#### Proposed Solution
- Store multiple translation versions per chapter
- Add "Try Another Model" button on chapter page
- Show dropdown to select which translation version to view
- Add comparison view showing 2-3 versions side-by-side

#### Technical Implementation
1. **Database Schema** (`models/db_models.py`):
   ```python
   # Add new table
   class ChapterTranslationVersion(Base):
       id = Column(Integer, primary_key=True)
       chapter_id = Column(Integer, ForeignKey('chapters.id'))
       version_number = Column(Integer)
       translated_content = Column(Text)
       translation_model = Column(String)
       created_at = Column(DateTime)
       is_active = Column(Boolean, default=False)  # Currently displayed version
   ```

2. **API Endpoints**:
   - `POST /api/chapter/<id>/translate-new-version` - Create new translation
   - `GET /api/chapter/<id>/versions` - List all versions
   - `POST /api/chapter/<id>/set-active-version` - Switch active version

3. **UI** (`chapter.html`):
   - Add version selector dropdown
   - Add "Compare Versions" button (opens 2-column view)
   - Show metadata for each version (model, date, cost estimate)

#### User Benefits
- Experiment with different AI models
- Choose the highest quality translation
- No risk in trying new translation approaches
- Learn which models work best for specific content types

#### Advanced Features
- Auto-rate translations (word count, readability scores)
- Community voting on best translations
- Diff view showing changes between versions

---

### 3. Reading Statistics Dashboard

**Priority**: Low  
**Complexity**: Low  
**Estimated Development Time**: 3-4 hours

#### Description
Create a personal dashboard showing reading statistics: chapters completed, time spent reading, favorite novels, reading streaks, etc.

#### Current Limitation
Users have no visibility into their reading habits or progress across multiple novels.

#### Proposed Solution
Add a new page `/profile/stats` with:
- Total chapters read
- Total novels imported
- Reading time (estimated)
- Favorite novels (most chapters read)
- Reading calendar (GitHub-style contribution graph)
- Current reading streak

#### Technical Implementation
1. **Tracking** (Client-side):
   ```javascript
   // Already tracking in chapter.html - expand this
   const readingSession = {
       novelId: novelId,
       chapterNumber: chapterNumber,
       startTime: Date.now(),
       endTime: null  // Set when leaving page
   };
   localStorage.setItem('current_session', JSON.stringify(readingSession));
   ```

2. **Backend** (`routes/main_routes.py`):
   ```python
   @main_bp.route('/profile/stats')
   def reading_stats():
       # Aggregate data from localStorage dump + DB queries
       # Calculate statistics
       # Return rendered template
   ```

3. **Database** (Optional - for server-side tracking):
   ```python
   class ReadingSession(Base):
       id = Column(Integer, primary_key=True)
       user_id = Column(String)
       novel_id = Column(Integer)
       chapter_id = Column(Integer)
       started_at = Column(DateTime)
       ended_at = Column(DateTime)
       duration_seconds = Column(Integer)
   ```

#### Statistics to Track
- **Reading Metrics**:
  - Total chapters read
  - Average reading time per chapter
  - Words read (approximate)
  - Reading speed (words per minute)

- **Novel Metrics**:
  - Total novels imported
  - Completed novels (all chapters read)
  - In-progress novels
  - Favorite genres/tags

- **Engagement Metrics**:
  - Current reading streak (consecutive days)
  - Longest reading streak
  - Most active reading time (hour of day)
  - Chapters read per week

- **Translation Metrics**:
  - Total chapters translated
  - API cost spent (estimate)
  - Most used AI model
  - Translation quality ratings

#### Visualization
- Reading calendar (green squares for days read)
- Line chart: chapters read over time
- Pie chart: reading by novel
- Bar chart: chapters per day of week

---

### 4. Search Across Novels

**Priority**: Medium  
**Complexity**: Low-Medium  
**Estimated Development Time**: 3-5 hours

#### Description
Full-text search across all novels and chapters, searching both Korean original text and English translations.

#### Current Limitation
No way to find specific content unless you remember which chapter it's in.

#### Proposed Solution
Add a global search bar that searches:
- Novel titles and descriptions
- Chapter content (Korean and English)
- Character names from glossaries
- Tags and metadata

#### Technical Implementation
1. **Search Endpoint** (`routes/api_routes.py`):
   ```python
   @api_bp.route('/search', methods=['GET'])
   def global_search():
       query = request.args.get('q', '')
       user_id = get_user_id()
       
       # PostgreSQL full-text search
       results = {
           'novels': search_novels(user_id, query),
           'chapters': search_chapters(user_id, query),
           'characters': search_glossary(user_id, query)
       }
       return jsonify(results)
   ```

2. **Database Queries** (`models/db_novel.py`):
   ```python
   def search_chapters(user_id, query):
       with db_session_scope() as session:
           # PostgreSQL ILIKE for simple search
           chapters = session.query(Chapter).join(Novel).filter(
               Novel.user_id == user_id,
               or_(
                   Chapter.content.ilike(f'%{query}%'),
                   Chapter.translated_content.ilike(f'%{query}%'),
                   Chapter.title.ilike(f'%{query}%')
               )
           ).limit(50).all()
           return chapters
   ```

3. **UI** (`base.html`):
   - Add search bar to navbar
   - Create `/search` page showing results
   - Group results by type (novels, chapters, characters)
   - Show context snippets with search term highlighted

#### Search Features
- **Basic**: Keyword search (case-insensitive)
- **Advanced**: 
  - Phrase search ("exact match")
  - Boolean operators (AND, OR, NOT)
  - Filter by novel, date range, translation status
  - Search in Korean or English only

#### Performance Optimization
- Add PostgreSQL full-text search indexes:
  ```sql
  CREATE INDEX idx_chapter_content_fts ON chapters USING gin(to_tsvector('english', content));
  CREATE INDEX idx_chapter_translated_fts ON chapters USING gin(to_tsvector('english', translated_content));
  ```
- Cache frequent searches
- Limit results to 50-100 per query

---

### 5. Chapter Notes/Annotations

**Priority**: Medium  
**Complexity**: Low  
**Estimated Development Time**: 2-3 hours

#### Description
Allow users to add personal notes and highlights to chapters for future reference.

#### Current Limitation
No way to save thoughts, questions, or important plot points while reading.

#### Proposed Solution
Add annotation features:
- Highlight text (multiple colors)
- Add text notes/comments
- Bookmark important chapters
- Tag chapters (e.g., "character development", "plot twist")

#### Technical Implementation
1. **Database Schema**:
   ```python
   class ChapterAnnotation(Base):
       id = Column(Integer, primary_key=True)
       user_id = Column(String)
       chapter_id = Column(Integer, ForeignKey('chapters.id'))
       annotation_type = Column(String)  # 'highlight', 'note', 'bookmark'
       content = Column(Text)  # Note text
       position = Column(Integer)  # Character offset in text
       length = Column(Integer)  # Length of highlighted text
       color = Column(String)  # For highlights
       tags = Column(JSON)  # Array of tag strings
       created_at = Column(DateTime)
   ```

2. **API Endpoints**:
   - `POST /api/chapter/<id>/annotations` - Create annotation
   - `GET /api/chapter/<id>/annotations` - Get all annotations
   - `PUT /api/annotation/<id>` - Update annotation
   - `DELETE /api/annotation/<id>` - Delete annotation

3. **UI** (`chapter.html`):
   ```javascript
   // Text selection handling
   document.addEventListener('mouseup', () => {
       const selection = window.getSelection();
       if (selection.toString().length > 0) {
           showAnnotationMenu(selection);  // Show highlight/note buttons
       }
   });
   
   // Render highlights
   function renderHighlights() {
       annotations.forEach(annot => {
           highlightText(annot.position, annot.length, annot.color);
       });
   }
   ```

#### Features
- **Highlights**:
  - 5 color options (yellow, blue, green, pink, red)
  - Click highlight to view/edit note
  - Remove highlight option

- **Notes**:
  - Rich text editor for longer notes
  - Attach notes to specific text or entire chapter
  - Timestamp and auto-save

- **Bookmarks**:
  - Star/flag chapters for quick access
  - Create bookmark collections ("Important Scenes", "Questions")

- **Tags**:
  - Custom tags for organization
  - Filter chapters by tag
  - Tag autocomplete from previous tags

#### Notes Dashboard
Add `/notes` page showing:
- All annotations across all novels
- Filter by novel, type, tag, date
- Search within notes
- Export notes as markdown

---

### 6. Auto-Translate on Import ✅ Completed

**Priority**: High  
**Complexity**: Low  
**Estimated Development Time**: 2 hours

#### Description
Add an option in the browser extension to automatically translate chapters as they're imported, eliminating the manual translation step.

#### Status
This feature is now implemented and working as expected. Chapters imported with auto-translate enabled are automatically translated and the page updates to show the English text.

---

### 7. Translation Memory/Cache

**Priority**: Medium  
**Complexity**: Medium  
**Estimated Development Time**: 5-6 hours

#### Description
Build a translation memory system that saves and reuses common phrase translations across all novels, improving consistency and reducing API costs.

#### Current Limitation
The same phrases (character names, common expressions, locations) get translated repeatedly, costing money and potentially creating inconsistencies.

#### Proposed Solution
- Maintain a database of previously translated segments
- Before translating, check if segments exist in translation memory
- Reuse cached translations
- Allow manual editing of translation memory

#### Technical Implementation
1. **Database Schema**:
   ```python
   class TranslationMemory(Base):
       id = Column(Integer, primary_key=True)
       source_text = Column(Text, unique=True)  # Korean text
       target_text = Column(Text)  # English translation
       context = Column(String)  # 'character_name', 'location', 'general'
       usage_count = Column(Integer, default=1)
       last_used = Column(DateTime)
       confidence = Column(Float)  # 0.0-1.0
       created_by = Column(String)  # user_id or 'auto'
   ```

2. **Translation Flow** (`services/ai_service.py`):
   ```python
   def translate_with_memory(text, provider, api_key, model):
       # 1. Split text into segments
       segments = split_into_segments(text)
       
       # 2. Check each segment against translation memory
       translations = []
       for segment in segments:
           cached = get_from_translation_memory(segment)
           if cached and cached.confidence > 0.8:
               translations.append(cached.target_text)
           else:
               # Translate and save to memory
               translation = translate_text(segment, provider, api_key, model)
               save_to_translation_memory(segment, translation)
               translations.append(translation)
       
       # 3. Combine translations
       return ' '.join(translations)
   ```

3. **Segmentation Strategy**:
   - Split on sentences (Korean sentence endings)
   - Extract character names separately
   - Identify repeated phrases (appears 3+ times)

#### Translation Memory Features
- **Auto-population**: Build from existing translations
- **Manual entries**: Users can add custom translations
- **Confidence scoring**: Track accuracy over time
- **User-specific vs. global**: Personal memory + community memory
- **Import/Export**: Share translation memories

#### UI for Managing Memory
Add `/translation-memory` page:
- Table of all saved translations
- Edit, delete, add entries
- Search and filter
- Import/export as JSON or TMX format

#### Cost Savings
- Estimate 20-40% reduction in API costs for series novels
- Faster translation (no API call for cached segments)
- More consistent character names and terminology

---

### 8. Export with Images

**Priority**: High  
**Complexity**: Medium  
**Estimated Development Time**: 4-5 hours

#### Description
Update PDF and EPUB export functionality to include images from chapters.

#### Current Limitation
The current export system in `services/export_service.py` skips images entirely, creating text-only exports.

#### Proposed Solution
- Embed downloaded chapter images in EPUB/PDF exports
- Preserve image placement and captions
- Optimize image sizes for file size management

#### Technical Implementation
1. **EPUB Export** (`services/export_service.py`):
   ```python
   def export_to_epub(novel_id, novel, user_id):
       from ebooklib import epub
       import shutil
       
       book = epub.EpubBook()
       # ... existing setup ...
       
       for idx, chapter in enumerate(novel.get('chapters', [])):
           # Add images to EPUB
           if chapter.get('images'):
               for img_idx, img in enumerate(chapter['images']):
                   img_path = get_image_path(user_id, img['local_path'])
                   
                   # Read image file
                   with open(img_path, 'rb') as f:
                       img_data = f.read()
                   
                   # Create EPUB image
                   img_item = epub.EpubImage()
                   img_item.file_name = f'images/{novel_id}_ch{idx}_img{img_idx}.jpg'
                   img_item.content = img_data
                   book.add_item(img_item)
                   
                   # Insert image into chapter HTML
                   content = f'<img src="{img_item.file_name}" alt="{img.get("alt", "")}" />'
                   # ... add to chapter content ...
   ```

2. **PDF Export**:
   ```python
   def export_to_pdf(novel_id, novel, user_id):
       from reportlab.platypus import Image as RLImage
       
       # ... existing setup ...
       
       for chapter in novel['chapters']:
           if chapter.get('images'):
               for img in chapter['images']:
                   img_path = get_image_path(user_id, img['local_path'])
                   
                   # Add image to PDF
                   img_obj = RLImage(img_path, width=400, height=300)
                   story.append(img_obj)
                   
                   # Add caption if present
                   if img.get('alt'):
                       story.append(Paragraph(img['alt'], caption_style))
   ```

#### Challenges & Solutions
- **Large file sizes**: 
  - Compress images before embedding
  - Resize to reasonable dimensions (max 800px wide)
  - Option to export with/without images

- **Image formats**: 
  - Convert all to JPEG for PDFs
  - Support PNG, JPEG, WebP for EPUB

- **Missing images**:
  - Skip gracefully if image file not found
  - Log warnings for debugging

#### Export Options
Add checkboxes to export UI:
- ☑️ Include images (default: on)
- ☑️ Compress images (default: on)
- Maximum image width: [800px]
- Image quality: [High/Medium/Low]

---

### 9. Batch Delete Chapters

**Priority**: Low  
**Complexity**: Low  
**Estimated Development Time**: 2-3 hours

#### Description
Add ability to select and delete multiple chapters at once from the novel page.

#### Current Limitation
Can only delete chapters one at a time, making cleanup of failed imports tedious.

#### Proposed Solution
- Add checkboxes to each chapter in chapter list
- "Select All" option
- "Delete Selected" button
- Confirmation dialog showing chapters to be deleted

#### Technical Implementation
1. **UI** (`templates/novel.html`):
   ```html
   <!-- Add to each chapter item -->
   <input type="checkbox" class="chapter-checkbox" data-chapter-id="{{ chapter.id }}">
   
   <!-- Add toolbar -->
   <div class="bulk-actions" style="display: none;">
       <button id="select-all-btn">Select All</button>
       <button id="delete-selected-btn" class="btn-danger">Delete Selected</button>
       <span id="selected-count">0 selected</span>
   </div>
   ```

2. **JavaScript**:
   ```javascript
   // Show/hide bulk actions toolbar
   document.querySelectorAll('.chapter-checkbox').forEach(checkbox => {
       checkbox.addEventListener('change', () => {
           const selected = document.querySelectorAll('.chapter-checkbox:checked');
           document.querySelector('.bulk-actions').style.display = 
               selected.length > 0 ? 'block' : 'none';
           document.getElementById('selected-count').textContent = 
               `${selected.length} selected`;
       });
   });
   
   // Delete selected chapters
   document.getElementById('delete-selected-btn').addEventListener('click', async () => {
       const selected = Array.from(document.querySelectorAll('.chapter-checkbox:checked'))
           .map(cb => cb.dataset.chapterId);
       
       if (confirm(`Delete ${selected.length} chapters?`)) {
           await fetch('/api/chapters/batch-delete', {
               method: 'POST',
               body: JSON.stringify({ chapter_ids: selected })
           });
           location.reload();
       }
   });
   ```

3. **API Endpoint** (`routes/api_routes.py`):
   ```python
   @api_bp.route('/chapters/batch-delete', methods=['POST'])
   def batch_delete_chapters():
       user_id = get_user_id()
       chapter_ids = request.json.get('chapter_ids', [])
       
       deleted_count = 0
       for chapter_id in chapter_ids:
           # Verify ownership
           chapter = get_chapter_by_id(chapter_id)
           if chapter and chapter.novel.user_id == user_id:
               delete_chapter_db(chapter_id)
               deleted_count += 1
       
       return jsonify({
           'success': True,
           'deleted': deleted_count
       })
   ```

#### Additional Features
- **Smart Selection**:
  - Select untranslated chapters only
  - Select chapters by date range
  - Select bonus chapters only

- **Bulk Actions** (beyond delete):
  - Bulk translate selected chapters
  - Export selected chapters
  - Mark as read/unread

---

### 10. Translation Cost Tracker

**Priority**: Medium  
**Complexity**: Medium  
**Estimated Development Time**: 4-5 hours

#### Description
Track and display estimated API costs for translations, helping users manage their translation budget.

#### Current Limitation
Users have no idea how much they're spending on API calls until they get their bill.

#### Proposed Solution
- Estimate cost before translation (show in UI)
- Track actual costs after translation
- Show cumulative costs per novel, per month, per provider
- Set budget alerts

#### Technical Implementation
1. **Pricing Database** (`models/pricing.py`):
   ```python
   # Token costs per provider (as of 2024)
   PRICING = {
       'openai': {
           'gpt-4-turbo': {'input': 0.01, 'output': 0.03},  # per 1K tokens
           'gpt-4o': {'input': 0.005, 'output': 0.015},
           'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015}
       },
       'openrouter': {
           'anthropic/claude-3.5-sonnet': {'input': 0.003, 'output': 0.015},
           'meta-llama/llama-3.1-70b': {'input': 0.0009, 'output': 0.0009}
       },
       'google': {
           'gemini-1.5-pro': {'input': 0.00125, 'output': 0.005},
           'gemini-1.5-flash': {'input': 0.000075, 'output': 0.0003}
       }
   }
   ```

2. **Cost Estimation** (`services/ai_service.py`):
   ```python
   def estimate_translation_cost(text, provider, model):
       import tiktoken
       
       # Estimate tokens (rough approximation)
       encoder = tiktoken.get_encoding('cl100k_base')
       input_tokens = len(encoder.encode(text))
       output_tokens = input_tokens * 1.2  # Estimate output is ~20% longer
       
       pricing = PRICING.get(provider, {}).get(model, {})
       input_cost = (input_tokens / 1000) * pricing.get('input', 0)
       output_cost = (output_tokens / 1000) * pricing.get('output', 0)
       
       return {
           'input_tokens': input_tokens,
           'output_tokens': output_tokens,
           'estimated_cost': input_cost + output_cost,
           'currency': 'USD'
       }
   ```

3. **Cost Tracking Table**:
   ```python
   class TranslationCost(Base):
       id = Column(Integer, primary_key=True)
       user_id = Column(String)
       chapter_id = Column(Integer, ForeignKey('chapters.id'))
       provider = Column(String)
       model = Column(String)
       input_tokens = Column(Integer)
       output_tokens = Column(Integer)
       estimated_cost = Column(Float)
       created_at = Column(DateTime)
   ```

4. **UI Components**:
   - **Before Translation**: Show estimated cost in confirmation dialog
   - **Chapter Page**: Display cost badge next to "Translated" status
   - **Novel Page**: Show total cost for all translated chapters
   - **Settings Page**: Add cost dashboard with charts

#### Cost Dashboard (`/costs`)
Display:
- Total spent (all time, this month, this week)
- Cost breakdown by provider
- Cost breakdown by novel
- Most expensive chapters
- Average cost per chapter
- Cost trend chart (spending over time)

#### Budget Features
- Set monthly budget limit
- Alert when approaching limit (80%, 90%, 100%)
- Pause auto-translation when budget exceeded
- Email notifications for costs

#### Cost Optimization Recommendations
Based on usage patterns, suggest:
- "Switch to GPT-3.5 to save 90% on costs"
- "Gemini Flash is 10x cheaper than GPT-4"
- "Translation memory could save you $X/month"

---

## 🔧 Quality of Life Improvements

### 11. Enhanced Reading Modes

**Priority**: Low  
**Complexity**: Low  
**Estimated Development Time**: 2-3 hours

#### Description
Add multiple reading modes beyond dark mode for improved reading comfort.

#### Proposed Features

##### Sepia Mode
- Warm, paper-like background (#f4ecd8)
- Reduced eye strain for long reading sessions
- Popular in e-reader apps

##### Font Controls
- **Font Size**: Adjustable from 12px to 24px
- **Line Height**: 1.2x, 1.5x, 1.8x, 2.0x
- **Font Family Options**:
  - System default (Arial, Helvetica)
  - Georgia (serif, classic)
  - Open Sans (modern, clean)
  - Noto Sans KR (Korean optimized)
  - Courier New (monospace, for code-like reading)

##### Reading Width
- Narrow (600px) - for focused reading
- Normal (800px) - default
- Wide (full width) - for side-by-side

##### Text Alignment
- Left-aligned (default)
- Justified (newspaper style)
- Center-aligned

#### Technical Implementation
```javascript
// Save to localStorage
const readingPrefs = {
    mode: 'sepia',  // 'light', 'dark', 'sepia'
    fontSize: 16,
    lineHeight: 1.8,
    fontFamily: 'Georgia',
    width: 'normal',
    alignment: 'left'
};

localStorage.setItem('reading_prefs', JSON.stringify(readingPrefs));

// Apply preferences
function applyReadingPrefs() {
    const prefs = JSON.parse(localStorage.getItem('reading_prefs'));
    const content = document.querySelector('.text-content');
    
    content.style.fontSize = `${prefs.fontSize}px`;
    content.style.lineHeight = prefs.lineHeight;
    content.style.fontFamily = prefs.fontFamily;
    content.style.maxWidth = widths[prefs.width];
    content.style.textAlign = prefs.alignment;
    
    document.body.classList.add(`mode-${prefs.mode}`);
}
```

#### UI
Add floating toolbar or settings panel:
- Icon buttons for quick toggles
- Sliders for font size and line height
- Dropdowns for font family and width
- Persist across all chapters

---

### 12. Chapter Download Queue Status

**Priority**: Medium  
**Complexity**: Medium  
**Estimated Development Time**: 3-4 hours

#### Description
Real-time status display for background translation tasks with progress tracking.

#### Proposed Features
- Live progress bar for active translations
- Queue visualization (what's pending)
- Ability to pause/cancel translations
- Completion notifications

#### Technical Implementation
1. **Backend** - Use existing Celery task status:
   ```python
   @api_bp.route('/translation-queue/status')
   def queue_status():
       from celery_app import celery
       
       # Get active tasks
       inspect = celery.control.inspect()
       active = inspect.active()
       scheduled = inspect.scheduled()
       
       return jsonify({
           'active': active,
           'scheduled': scheduled,
           'queue_length': len(scheduled)
       })
   ```

2. **Frontend** - Persistent status widget:
   ```javascript
   // Poll queue status every 2 seconds
   setInterval(async () => {
       const response = await fetch('/translation-queue/status');
       const status = await response.json();
       updateQueueWidget(status);
   }, 2000);
   ```

3. **UI** - Bottom-right floating widget:
   - Minimized: Shows "⚡ 3 translations in progress"
   - Expanded: Shows list of active/queued translations
   - Each item shows: chapter name, progress %, ETA
   - Click to expand/minimize

#### Notification System
- Browser notifications when translation completes
- Sound effect option
- Desktop notification (if permitted)

---

### 13. Duplicate Chapter Detection

**Priority**: Medium  
**Complexity**: Low  
**Estimated Development Time**: 2 hours

#### Description
Automatically detect and prevent importing duplicate chapters based on source URL or content hash.

#### Current Issue
Users accidentally import the same chapter multiple times, creating clutter.

#### Proposed Solution
1. **Source URL Check** (already partially implemented):
   ```python
   # In add_chapter_atomic() - already exists
   existing_chapter = session.query(Chapter).filter(
       Chapter.novel_id == novel.id,
       Chapter.source_url == source_url
   ).first()
   
   if existing_chapter:
       return {'already_exists': True, 'message': 'Chapter already imported'}
   ```

2. **Content Hash Check** (for chapters without URLs):
   ```python
   import hashlib
   
   def get_content_hash(text):
       return hashlib.sha256(text.encode()).hexdigest()
   
   # Check hash
   content_hash = get_content_hash(chapter_data['content'])
   existing = session.query(Chapter).filter(
       Chapter.novel_id == novel.id,
       Chapter.content_hash == content_hash
   ).first()
   ```

3. **Smart Deduplication**:
   - If content is 95%+ similar, flag as potential duplicate
   - Show warning in extension: "This chapter may already be imported"
   - Option to import anyway (for revised versions)

#### Database Addition
```python
# Add to Chapter model
content_hash = Column(String(64), index=True)
```

---

### 14. Novel Cover Upload

**Priority**: Low  
**Complexity**: Low  
**Estimated Development Time**: 2 hours

#### Description
Allow users to manually upload custom novel covers if auto-detected ones are missing or poor quality.

#### Implementation
1. **Upload Endpoint**:
   ```python
   @api_bp.route('/novel/<novel_id>/upload-cover', methods=['POST'])
   def upload_cover(novel_id):
       file = request.files['cover']
       # Save to user's images directory
       filename = save_uploaded_image(file, user_id)
       # Update novel
       update_novel_db(user_id, novel_id, {'cover_url': filename})
   ```

2. **UI** (`novel_settings.html`):
   ```html
   <div class="cover-section">
       <img src="/images/{{ novel.cover_url }}" id="current-cover">
       <input type="file" id="cover-upload" accept="image/*">
       <button onclick="uploadCover()">Upload New Cover</button>
   </div>
   ```

#### Features
- Drag-and-drop upload
- Image preview before upload
- Automatic resizing (max 800x1200)
- Crop tool for adjusting
- Option to restore auto-detected cover

---

### 15. Backup/Restore Function

**Priority**: Medium  
**Complexity**: Medium  
**Estimated Development Time**: 4-5 hours

#### Description
Export entire user database (novels, chapters, settings, glossaries) as JSON for backup or migration.

#### Use Cases
- Backup before major updates
- Migrate to another server
- Share entire reading library
- Disaster recovery

#### Implementation
1. **Export**:
   ```python
   @api_bp.route('/backup/export')
   def export_backup():
       user_id = get_user_id()
       
       backup_data = {
           'version': '1.0',
           'exported_at': datetime.now().isoformat(),
           'novels': get_user_novels_db(user_id),
           'settings': load_settings(user_id),
           'translation_memory': get_user_translation_memory(user_id),
           'annotations': get_user_annotations(user_id)
       }
       
       # Create ZIP with JSON + images
       zip_path = create_backup_zip(user_id, backup_data)
       return send_file(zip_path)
   ```

2. **Import**:
   ```python
   @api_bp.route('/backup/import', methods=['POST'])
   def import_backup():
       zip_file = request.files['backup']
       # Extract and validate
       # Import data
       # Handle conflicts (merge vs. replace)
   ```

#### Features
- **Full Backup**: Everything (novels, images, settings)
- **Selective Backup**: Choose specific novels
- **Incremental Backup**: Only new/changed data since last backup
- **Automatic Backups**: Schedule weekly backups
- **Cloud Sync**: Optional backup to Google Drive / Dropbox

---

## 🚀 Advanced Features

### 16. Community Glossary Sharing

**Priority**: Low  
**Complexity**: High  
**Estimated Development Time**: 10-15 hours

#### Description
Create a community platform where users can share and vote on character name translations for popular novels.

#### Vision
Instead of every user independently translating "김서준" as different English names, build a shared database:
- User A translates as "Kim Seo-jun"
- User B prefers "Kim Seojun"  
- User C uses "Seojun Kim"
- Community votes → consensus: "Seojun Kim" becomes official

#### Features
1. **Community Glossaries**:
   - Search for novel by title or source URL
   - View community-contributed glossaries
   - Download and apply to your novel

2. **Contribution System**:
   - Upload your glossary for a novel
   - Other users can upvote/downvote entries
   - Reputation system for contributors

3. **Voting & Consensus**:
   - Multiple translations per character
   - Votes determine "canonical" translation
   - Show alternative translations with vote counts

4. **Moderation**:
   - Report inappropriate translations
   - Community moderators can merge duplicates
   - Flag low-quality contributions

#### Technical Implementation
```python
# New tables
class CommunityNovel(Base):
    id = Column(Integer, primary_key=True)
    title = Column(String)
    source_url = Column(String, unique=True)
    contributor_count = Column(Integer)

class CommunityGlossaryEntry(Base):
    id = Column(Integer, primary_key=True)
    novel_id = Column(Integer, ForeignKey('community_novels.id'))
    korean_name = Column(String)
    english_name = Column(String)
    submitted_by = Column(String)  # user_id
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    is_canonical = Column(Boolean, default=False)
```

#### Privacy Considerations
- Users opt-in to sharing glossaries
- No personal information shared
- Can contribute anonymously

---

### 17. Translation History/Undo

**Priority**: Low  
**Complexity**: Medium  
**Estimated Development Time**: 5-6 hours

#### Description
Maintain version history for manual edits to translations, allowing undo/redo and diffing.

#### Features
- Track every edit to a translation
- Undo/redo buttons
- View edit history with timestamps
- Diff view showing changes
- Restore previous versions

#### Implementation
```python
class TranslationEdit(Base):
    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer)
    user_id = Column(String)
    previous_content = Column(Text)
    new_content = Column(Text)
    edit_type = Column(String)  # 'manual_edit', 'retranslate', 'restore'
    created_at = Column(DateTime)
```

#### UI
- "View History" button on chapter page
- Timeline showing all edits
- Click to preview each version
- "Restore this version" button

---

### 18. Reader Mode

**Priority**: Low  
**Complexity**: Low  
**Estimated Development Time**: 2-3 hours

#### Description
Distraction-free reading interface with advanced features.

#### Features
- **Distraction-Free UI**:
  - Hide all buttons and nav
  - Full-screen mode
  - Minimal styling

- **Auto-Scroll**:
  - Configurable speed
  - Pause on hover
  - Resume with spacebar

- **Text-to-Speech**:
  - Browser's built-in TTS
  - Adjustable speed and voice
  - Highlight current sentence

#### Implementation
```javascript
// Auto-scroll
function startAutoScroll(speed = 50) {
    autoScrollInterval = setInterval(() => {
        window.scrollBy(0, 1);
    }, speed);
}

// Text-to-speech
const utterance = new SpeechSynthesisUtterance(text);
utterance.rate = 1.2;
speechSynthesis.speak(utterance);
```

---

### 19. Mobile App

**Priority**: Low  
**Complexity**: Very High  
**Estimated Development Time**: 40+ hours

#### Description
Dedicated mobile app for iOS and Android with offline reading support.

#### Technology Options
- **React Native**: Single codebase, fast development
- **Flutter**: Better performance, native feel
- **PWA**: Web-based, no app store needed

#### Features
- Sync with web app
- Offline reading (download chapters)
- Push notifications for new chapters
- Mobile-optimized UI
- Swipe gestures for navigation

#### Offline Support
- Download novels for offline reading
- Queue translations for when online
- Sync progress across devices

---

### 20. Collaboration Features

**Priority**: Low  
**Complexity**: High  
**Estimated Development Time**: 15-20 hours

#### Description
Allow multiple users to work together on translating novels.

#### Features
1. **Shared Novels**:
   - Invite users to your novel
   - Permissions: viewer, commenter, editor
   - Real-time updates

2. **Collaborative Translation**:
   - Assign chapters to different translators
   - Review and approve translations
   - Suggest improvements

3. **Comments & Discussions**:
   - Comment threads on chapters
   - @mention other collaborators
   - Resolve discussions when done

4. **Translation Projects**:
   - Create a project for translating a novel
   - Task board (to-do, in progress, done)
   - Progress tracking for team

#### Use Cases
- Translation groups working on same novel
- Proofreading/editing workflows
- Fan translation teams
- Language learning groups

---

## Implementation Priority Matrix

| Feature | Priority | Complexity | ROI | Recommended Order |
|---------|----------|------------|-----|-------------------|
| Bulk Translation | High | Medium | High | 1 |
| Auto-Translate on Import | High | Low | High | 2 |
| Export with Images | High | Medium | High | 3 |
| Translation Cost Tracker | Medium | Medium | High | 4 |
| Search Across Novels | Medium | Low | Medium | 5 |
| Translation Quality Comparison | Medium | Medium | Medium | 6 |
| Chapter Notes/Annotations | Medium | Low | Medium | 7 |
| Translation Memory/Cache | Medium | Medium | High | 8 |
| Reading Statistics Dashboard | Low | Low | Low | 9 |
| Batch Delete Chapters | Low | Low | Low | 10 |

## Conclusion

This document outlines 20 potential features ranging from quick quality-of-life improvements to major system enhancements. The recommended implementation order prioritizes:

1. **Quick Wins**: Low complexity, high impact (Auto-translate on import)
2. **User Pain Points**: Features that solve major frustrations (Bulk translation)
3. **Value-Add**: Features that significantly improve the experience (Export with images)
4. **Long-term Investment**: Complex features with strategic value (Translation memory)

Next steps:
1. Review and prioritize based on your user needs
2. Create detailed implementation plans for selected features
3. Implement in sprints, gathering feedback along the way
