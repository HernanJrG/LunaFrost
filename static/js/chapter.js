document.addEventListener('DOMContentLoaded', function () {
    const translateBtn = document.getElementById('translate-btn');
    const thinkBtn = document.getElementById('think-btn');
    const compareBtn = document.getElementById('compare-btn');
    const saveBtn = document.getElementById('save-btn');
    const editBtn = document.getElementById('edit-btn');
    const textDisplay = document.getElementById('text-display');
    const editArea = document.getElementById('edit-area');
    const editTextarea = document.getElementById('edit-textarea');
    const saveEditBtn = document.getElementById('save-edit-btn');
    const cancelEditBtn = document.getElementById('cancel-edit-btn');
    const singleView = document.getElementById('single-view');
    const sideView = document.getElementById('side-by-side-view');
    const koreanPanel = document.getElementById('korean-panel');
    const englishPanel = document.getElementById('english-panel');
    const thinkingIndicator = document.getElementById('thinking-indicator');
    const tokenUsageDisplay = document.getElementById('token-usage-display');
    const inputTokensSpan = document.getElementById('input-tokens');
    const outputTokensSpan = document.getElementById('output-tokens');
    const totalTokensSpan = document.getElementById('total-tokens');


    let koreanText = window.chapterData.koreanText;
    let translatedText = window.chapterData.translatedText;
    let translationModel = window.chapterData.translationModel;
    let chapterTitle = window.chapterData.title || '';
    let translatedTitle = window.chapterData.translatedTitle || '';
    let isTranslated = translatedText && translatedText.trim().length > 0;
    let isCompareMode = false;



    // Helper to check if model is a thinking model
    function isThinkingModel(modelName) {
        if (!modelName) return false;
        const lowerName = modelName.toLowerCase();
        return lowerName.includes('o1-') || lowerName.includes('thinking') || lowerName.includes('r1');
    }

    // Update token usage display
    function updateTokenUsageDisplay(tokenUsage, costInfo = null) {
        if (!tokenUsage || !tokenUsageDisplay) return;

        const inputTokens = tokenUsage.input_tokens || 0;
        const outputTokens = tokenUsage.output_tokens || 0;
        const totalTokens = tokenUsage.total_tokens || (inputTokens + outputTokens);

        if (inputTokensSpan) inputTokensSpan.textContent = formatNumber(inputTokens);
        if (outputTokensSpan) outputTokensSpan.textContent = formatNumber(outputTokens);
        if (totalTokensSpan) totalTokensSpan.textContent = formatNumber(totalTokens);

        // Add cost information if available
        let costText = '';
        if (costInfo && costInfo.pricing_available && costInfo.total_cost !== null) {
            const cost = formatCost(costInfo.total_cost);
            if (cost) {
                costText = ` (Est. ${cost})`;
            }
        }

        // Update display with cost if available
        const tokenBadge = tokenUsageDisplay.querySelector('.token-badge');
        if (tokenBadge && costText) {
            const existingCost = tokenBadge.querySelector('.cost-info');
            if (existingCost) {
                existingCost.textContent = costText;
            } else {
                const costSpan = document.createElement('span');
                costSpan.className = 'cost-info';
                costSpan.style.color = '#2c5282';
                costSpan.style.fontWeight = '500';
                costSpan.textContent = costText;
                tokenBadge.appendChild(costSpan);
            }
        }

        tokenUsageDisplay.classList.remove('hidden');
        tokenUsageDisplay.style.display = 'block';

        // Remove auto-hide, click to dismiss instead
        if (window.tokenUsageTimeout) {
            clearTimeout(window.tokenUsageTimeout);
        }

        // Add click handler to dismiss if not already added
        if (!tokenUsageDisplay.hasAttribute('data-click-handler')) {
            tokenUsageDisplay.setAttribute('data-click-handler', 'true');
            tokenUsageDisplay.style.cursor = 'pointer';
            tokenUsageDisplay.title = 'Click to dismiss';
            tokenUsageDisplay.addEventListener('click', function () {
                this.style.display = 'none';
                this.classList.add('hidden');
            });
        }
    }

    function formatCost(cost) {
        if (cost < 0.01) {
            return `$${cost.toFixed(4)}`;
        } else if (cost < 1) {
            return `$${cost.toFixed(3)}`;
        } else {
            return `$${cost.toFixed(2)}`;
        }
    }

    // Format number with commas
    function formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // ---------------------------
    // Local model pricing helpers
    // ---------------------------
    function getStoredModelPricing() {
        // Try server-side pricing first, fall back to localStorage
        return (async function () {
            try {
                const resp = await fetch('/api/pricing');
                if (resp.ok) {
                    const data = await resp.json();
                    if (data.success && data.pricing) return data.pricing;
                }
            } catch (e) {
                // ignore and fallback to localStorage
            }

            try {
                const raw = localStorage.getItem('lf_model_pricing');
                return raw ? JSON.parse(raw) : {};
            } catch (e) {
                console.warn('Error reading model pricing from localStorage', e);
                return {};
            }
        })();
    }

    function saveStoredModelPricing(obj) {
        // Save to server-side pricing endpoint and localStorage for immediate use
        (async function () {
            try {
                await fetch('/api/pricing', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(obj)
                });
            } catch (e) {
                console.warn('Error saving pricing to server', e);
            }

            try {
                localStorage.setItem('lf_model_pricing', JSON.stringify(obj));
            } catch (e) {
                console.warn('Error saving model pricing to localStorage', e);
            }
        })();
    }

    // Compute cost using locally stored pricing (prices are per 1000 tokens)
    async function computeCostFromPricing(estimation, modelName) {
        try {
            if (!estimation) return null;
            const pricing = await getStoredModelPricing();
            const modelPricing = pricing[modelName] || pricing['default'] || null;
            if (!modelPricing) return null;

            const inputPricePer1k = parseFloat(modelPricing.input_per_1k) || 0;
            const outputPricePer1k = parseFloat(modelPricing.output_per_1k) || 0;

            const inputTokens = estimation.input_tokens || 0;
            const outputTokens = estimation.output_tokens || 0;

            const inputCost = (inputTokens / 1000.0) * inputPricePer1k;
            const outputCost = (outputTokens / 1000.0) * outputPricePer1k;

            return {
                pricing_available: true,
                total_cost: inputCost + outputCost,
                breakdown: {
                    input_cost: inputCost,
                    output_cost: outputCost
                },
                model: modelName
            };
        } catch (e) {
            console.warn('Error computing cost from pricing', e);
            return null;
        }
    }

    // Values removed from chapter page — use Settings / Token Usage page instead

    // Estimate translation tokens before translation
    async function estimateTranslationTokens(useThinkingMode = false) {
        try {
            const response = await fetch('/api/translate/estimate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: koreanText,
                    novel_id: window.chapterData.novelId,
                    images: [],
                    use_thinking_mode: useThinkingMode
                })
            });

            const data = await response.json();

            if (data.success && data.estimation) {
                const est = data.estimation;
                const inputTokens = formatNumber(est.input_tokens || 0);
                const outputTokens = formatNumber(est.output_tokens || 0);
                const totalTokens = formatNumber(est.total_tokens || 0);

                // Build estimation message
                let message = `Estimated Token Usage:\n\n` +
                    `Input: ~${inputTokens} tokens\n` +
                    `Output: ~${outputTokens} tokens\n` +
                    `Total: ~${totalTokens} tokens\n`;

                // Add cost estimate if available (API) or compute using local pricing
                let costInfo = data.cost_info || null;
                if ((!costInfo || !costInfo.pricing_available) && window.chapterData && window.chapterData.translationModel) {
                    const local = await computeCostFromPricing(data.estimation, window.chapterData.translationModel || data.model || 'default');
                    if (local) costInfo = local;
                }

                if (costInfo && costInfo.pricing_available && costInfo.total_cost !== null) {
                    const cost = formatCost(costInfo.total_cost);
                    message += `\nEstimated Cost: ${cost}\n`;
                } else {
                    message += `\nUse these counts with your provider's pricing or set model values (Values button) to auto-calculate cost.\n`;
                }

                message += `\nProceed with translation?`;

                // Show confirmation dialog with estimation
                const confirmed = confirm(message);

                return confirmed ? est : null;
            } else {
                // If estimation fails, proceed anyway (don't block translation)
                console.warn('Token estimation failed, proceeding anyway:', data.error);
                return true; // Return truthy value to proceed
            }
        } catch (error) {
            console.error('Error estimating tokens:', error);
            // If estimation fails, proceed anyway (don't block translation)
            return true; // Return truthy value to proceed
        }
    }

    // Silent estimation (no confirm) used for UI display purposes
    async function getEstimationOnly(useThinkingMode = false) {
        try {
            const response = await fetch('/api/translate/estimate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: koreanText, novel_id: window.chapterData.novelId, images: [], use_thinking_mode: useThinkingMode })
            });
            const data = await response.json();
            if (data && data.success && data.estimation) {
                return { estimation: data.estimation, cost_info: data.cost_info || null, model: data.model || window.chapterData.translationModel };
            }
            return null;
        } catch (e) {
            console.warn('Silent estimation failed', e);
            return null;
        }
    }

    // Fetch token usage for a chapter
    async function fetchChapterTokenUsage(chapterId) {
        if (!chapterId) return;

        try {
            // Check if show_translation_cost setting is enabled
            const settingsResp = await fetch('/api/settings');
            if (settingsResp.ok) {
                const settings = await settingsResp.json();
                if (settings.show_translation_cost === false) return;
            }

            const response = await fetch(`/api/chapter/${chapterId}/token-usage`);
            const data = await response.json();

            if (data.success && data.token_usage && data.token_usage.length > 0) {
                // Get the most recent token usage record
                const latest = data.token_usage[0];
                updateTokenUsageDisplay({
                    input_tokens: latest.input_tokens,
                    output_tokens: latest.output_tokens,
                    total_tokens: latest.total_tokens
                }, latest.cost_info || null);
            }
        } catch (error) {
            console.error('Error fetching token usage:', error);
        }
    }

    // Update chapter title in the UI
    function updateChapterTitle(newTranslatedTitle) {
        console.log('updateChapterTitle called with:', newTranslatedTitle);
        const titleElement = document.querySelector('.header-title h1');
        console.log('Title element found:', titleElement);

        if (titleElement && newTranslatedTitle) {
            // Update the main title text (preserve thinking badge if it exists)
            const thinkingBadge = titleElement.querySelector('.thinking-badge');
            const titleText = newTranslatedTitle.trim();

            // Get the current text content (excluding the badge)
            if (thinkingBadge) {
                // If there's a thinking badge, preserve it
                titleElement.innerHTML = titleText + ' ';
                titleElement.appendChild(thinkingBadge);
            } else {
                // Otherwise just update the text
                titleElement.textContent = titleText;
            }

            console.log('Title updated in DOM');

            // Update or create the original title display
            let originalTitleDiv = document.querySelector('.original-title');
            if (originalTitleDiv) {
                originalTitleDiv.textContent = 'Original: ' + chapterTitle;
            } else {
                // Create the original title div if it doesn't exist
                const headerTitle = document.querySelector('.header-title');
                if (headerTitle) {
                    originalTitleDiv = document.createElement('div');
                    originalTitleDiv.className = 'original-title';
                    originalTitleDiv.textContent = 'Original: ' + chapterTitle;
                    headerTitle.appendChild(originalTitleDiv);
                    console.log('Original title div created');
                }
            }
        } else {
            console.error('Cannot update title - element or title missing', { titleElement, newTranslatedTitle });
        }
    }

    // Initialize with existing translation if available
    if (isTranslated) {
        applyCharacterHighlights();
        if (translateBtn) translateBtn.textContent = '🔄 Re-translate';
        if (compareBtn) compareBtn.classList.remove('hidden');
        if (saveBtn) saveBtn.classList.add('hidden');  // Hide save button initially
        if (editBtn) editBtn.classList.remove('hidden');  // Show edit button if translated

        // Show thinking indicator if applicable
        if (thinkingIndicator && isThinkingModel(translationModel)) {
            thinkingIndicator.classList.remove('hidden');
            thinkingIndicator.title = `Translated with Thinking Mode (${translationModel})`;
        }
    }

    // Generic translate function
    async function performTranslation(useThinkingMode = false) {
        const activeBtn = useThinkingMode ? thinkBtn : translateBtn;
        const otherBtn = useThinkingMode ? thinkBtn : translateBtn;

        if (!activeBtn) {
            console.error('Translate button not found');
            return;
        }

        // Start translation immediately without confirmation
        activeBtn.disabled = true;
        if (otherBtn) otherBtn.disabled = true;

        const originalText = activeBtn.textContent;
        activeBtn.textContent = useThinkingMode ? '🧠 Thinking...' : '⏳ Translating...';

        if (saveBtn) saveBtn.classList.add('hidden');  // Hide save button during translation

        // Show translation status
        const statusDiv = document.getElementById('translation-status');
        if (statusDiv) {
            statusDiv.classList.remove('hidden');
            statusDiv.style.display = 'flex';
            statusDiv.innerHTML = '<span class="status-icon">⏳</span><span class="status-text">Chapter translating...</span>';
        }

        // Exit compare mode if active
        if (isCompareMode) {
            toggleCompareMode();
        }

        try {
            // Translate chapter content
            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: koreanText,
                    novel_id: window.chapterData.novelId,
                    chapter_id: window.chapterData.chapterId,
                    images: [],
                    use_thinking_mode: useThinkingMode
                })
            });

            const data = await response.json();

            if (data.success) {
                translatedText = data.translated_text;
                translationModel = data.model_used; // Backend should return this

                // Display token usage if available and setting is enabled
                if (data.token_usage) {
                    // Check setting before showing
                    try {
                        const settingsResp = await fetch('/api/settings');
                        if (settingsResp.ok) {
                            const settings = await settingsResp.json();
                            if (settings.show_translation_cost !== false) {
                                updateTokenUsageDisplay(data.token_usage, data.cost_info);
                            }
                        } else {
                            updateTokenUsageDisplay(data.token_usage, data.cost_info);
                        }
                    } catch (e) {
                        updateTokenUsageDisplay(data.token_usage, data.cost_info);
                    }
                } else {
                    // Try to fetch token usage for this chapter (already checks setting)
                    if (window.chapterData.chapterId) {
                        fetchChapterTokenUsage(window.chapterData.chapterId);
                    }
                }

                // Translate chapter title if it exists
                if (chapterTitle) {
                    try {
                        console.log('Translating chapter title:', chapterTitle);
                        const titleResponse = await fetch('/api/translate', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                text: chapterTitle,
                                novel_id: window.chapterData.novelId,
                                chapter_id: window.chapterData.chapterId,
                                images: [],
                                use_thinking_mode: useThinkingMode
                            })
                        });

                        const titleData = await titleResponse.json();
                        console.log('Title translation response:', titleData);
                        if (titleData.success && titleData.translated_text) {
                            translatedTitle = titleData.translated_text;
                            console.log('Updating title to:', translatedTitle);
                            updateChapterTitle(translatedTitle);
                        } else {
                            console.error('Title translation failed:', titleData.error || 'Unknown error');
                        }
                    } catch (titleError) {
                        console.error('Error translating title:', titleError);
                        // Don't fail the whole translation if title translation fails
                    }
                }

                // Update the display with translated text
                console.log('Updating text display with translation');
                isTranslated = true;

                // Ensure we're in single view mode and display is visible
                if (singleView) singleView.classList.remove('hidden');
                if (sideView) sideView.classList.remove('active');
                if (editArea) editArea.classList.add('hidden');
                if (textDisplay) textDisplay.classList.remove('hidden');

                applyCharacterHighlights();

                if (translateBtn) translateBtn.textContent = '🔄 Re-translate';
                if (compareBtn) compareBtn.classList.remove('hidden');
                if (saveBtn) saveBtn.classList.remove('hidden');  // Show save button after translation
                if (editBtn) editBtn.classList.remove('hidden');  // Show edit button

                // Hide status and show success
                if (statusDiv) {
                    statusDiv.innerHTML = '<span class="status-icon">✅</span><span class="status-text">Translation complete!</span>';
                    setTimeout(() => {
                        statusDiv.style.display = 'none';
                        statusDiv.classList.add('hidden');
                    }, 3000);
                }

                // Update indicator
                if (thinkingIndicator) {
                    if (useThinkingMode || isThinkingModel(translationModel)) {
                        thinkingIndicator.classList.remove('hidden');
                        thinkingIndicator.title = `Translated with Thinking Mode (${translationModel})`;
                    } else {
                        thinkingIndicator.classList.add('hidden');
                    }
                }

            } else {
                textDisplay.innerHTML = '<div style="color: #e53e3e; padding: 40px; text-align: center;">❌ Error: ' + (data.error || 'Translation failed') + '</div>';
                if (statusDiv) {
                    statusDiv.style.display = 'none';
                }
            }
        } catch (error) {
            textDisplay.innerHTML = '<div style="color: #e53e3e; padding: 40px; text-align: center;">❌ Error: ' + error.message + '</div>';
            if (statusDiv) {
                statusDiv.style.display = 'none';
            }
        } finally {
            if (activeBtn) {
                activeBtn.disabled = false;
                activeBtn.textContent = originalText;
            }
            if (otherBtn) otherBtn.disabled = false;
            if (isTranslated && activeBtn) {
                activeBtn.textContent = '🔄 Re-translate';
            }
        }
    }

    // Translate button
    if (translateBtn) {
        translateBtn.addEventListener('click', () => {
            performTranslation(false);
        });
    }

    // Think+ button
    if (thinkBtn) {
        thinkBtn.addEventListener('click', () => {
            performTranslation(true);
        });
    }




    // Compare side-by-side button
    if (compareBtn) {
        compareBtn.addEventListener('click', () => {
            toggleCompareMode();
        });
    }



    function toggleCompareMode() {
        isCompareMode = !isCompareMode;

        if (isCompareMode) {
            // Switch to side-by-side view
            singleView.classList.add('hidden');
            sideView.classList.add('active');
            compareBtn.textContent = '📄 Single View';

            // Prepare texts with sentence wrapping for highlighting
            prepareComparisonView();
        } else {
            // Switch to single view
            singleView.classList.remove('hidden');
            sideView.classList.remove('active');
            compareBtn.textContent = '⚖️ Compare Side-by-Side';

            // Show current text (Korean or English)
            if (isTranslated) {
                applyCharacterHighlights();
            } else {
                textDisplay.textContent = koreanText;
            }
        }
    }

    function prepareComparisonView() {
        // Split texts into sentences (keeping punctuation)
        const sentenceRegex = /([.!?]+|\n)/;  // Split on sentence endings or newlines
        const koreanSentences = koreanText.split(sentenceRegex).filter(s => s.trim().length > 0);
        const englishSentences = translatedText.split(sentenceRegex).filter(s => s.trim().length > 0);

        // Add images to Korean panel if they exist
        let koreanContent = '';
        if (window.chapterData.images && window.chapterData.images.length > 0) {
            koreanContent += '<div style="margin-bottom: 20px; text-align: center;">';
            window.chapterData.images.forEach(img => {
                koreanContent += `<div style="margin-bottom: 15px;"><img src="/images/${img.local_path}" alt="${img.alt || 'Chapter Image'}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"></div>`;
            });
            koreanContent += '</div>';
        }
        koreanContent += koreanSentences.map((sentence, idx) =>
            `<span data-idx="${idx}" style="cursor: pointer;">${sentence}</span>`
        ).join('');

        // Add images to English panel if they exist
        let englishContent = '';
        if (window.chapterData.images && window.chapterData.images.length > 0) {
            englishContent += '<div style="margin-bottom: 20px; text-align: center;">';
            window.chapterData.images.forEach(img => {
                englishContent += `<div style="margin-bottom: 15px;"><img src="/images/${img.local_path}" alt="${img.alt || 'Chapter Image'}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"></div>`;
            });
            englishContent += '</div>';
        }
        englishContent += englishSentences.map((sentence, idx) =>
            `<span data-idx="${idx}" style="cursor: pointer;">${sentence}</span>`
        ).join('');

        // Set the content
        koreanPanel.innerHTML = koreanContent;
        englishPanel.innerHTML = englishContent;

        // Add click handlers for synchronized highlighting
        addHighlightHandlers();

        // Add synchronized scrolling
        syncScroll(koreanPanel, englishPanel);
        syncScroll(englishPanel, koreanPanel);
    }

    function addHighlightHandlers() {
        const koreanSpans = koreanPanel.querySelectorAll('span[data-idx]');
        const englishSpans = englishPanel.querySelectorAll('span[data-idx]');

        // Clear previous highlights
        function clearHighlights() {
            koreanSpans.forEach(s => s.classList.remove('highlighted'));
            englishSpans.forEach(s => s.classList.remove('highlighted'));
        }

        // Korean panel clicks
        koreanSpans.forEach(span => {
            span.addEventListener('click', () => {
                clearHighlights();
                const idx = span.getAttribute('data-idx');
                span.classList.add('highlighted');
                const englishMatch = englishPanel.querySelector(`span[data-idx="${idx}"]`);
                if (englishMatch) {
                    englishMatch.classList.add('highlighted');
                    englishMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        });

        // English panel clicks
        englishSpans.forEach(span => {
            span.addEventListener('click', () => {
                clearHighlights();
                const idx = span.getAttribute('data-idx');
                span.classList.add('highlighted');
                const koreanMatch = koreanPanel.querySelector(`span[data-idx="${idx}"]`);
                if (koreanMatch) {
                    koreanMatch.classList.add('highlighted');
                    koreanMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        });
    }

    function syncScroll(source, target) {
        source.addEventListener('scroll', () => {
            target.scrollTop = source.scrollTop;
        });
    }

    // Edit button
    if (editBtn) {
        editBtn.addEventListener('click', () => {
            if (isCompareMode) toggleCompareMode();  // Exit compare mode
            if (textDisplay) textDisplay.classList.add('hidden');
            if (editArea) editArea.classList.remove('hidden');
            if (editTextarea) {
                editTextarea.value = translatedText;  // Pre-fill with current text
                editTextarea.focus();
                // Fix auto-scroll to bottom: reset cursor to start and scroll to top
                editTextarea.setSelectionRange(0, 0);
                editTextarea.scrollTop = 0;
            }
        });
    }

    // Save edit
    if (saveEditBtn) {
        saveEditBtn.addEventListener('click', async () => {
            const newText = editTextarea.value.trim();
            if (!newText) return alert('Text cannot be empty.');

            translatedText = newText;
            textDisplay.textContent = translatedText;
            textDisplay.classList.remove('hidden');
            editArea.classList.add('hidden');

            // Save via API
            try {
                const response = await fetch('/api/save-translation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        novel_id: window.chapterData.novelId,
                        chapter_index: window.chapterData.chapterIndex,
                        translated_text: translatedText,
                        translated_title: translatedTitle || undefined
                    })
                });
                const data = await response.json();
                if (!data.success) alert('Save failed: ' + (data.error || 'Unknown error'));
            } catch (error) {
                alert('Save error: ' + error.message);
            }
        });
    }

    // Cancel edit
    if (cancelEditBtn) {
        cancelEditBtn.addEventListener('click', () => {
            if (textDisplay) textDisplay.classList.remove('hidden');
            if (editArea) editArea.classList.add('hidden');
        });
    }

    // Save button
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            saveBtn.disabled = true;
            saveBtn.textContent = '💾 Saving...';

            try {
                const response = await fetch('/api/save-translation', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        novel_id: window.chapterData.novelId,
                        chapter_index: window.chapterData.chapterIndex,
                        translated_text: translatedText,
                        translated_title: translatedTitle || undefined
                    })
                });

                const data = await response.json();

                if (data.success) {
                    saveBtn.textContent = '✓ Saved!';
                    setTimeout(() => {
                        saveBtn.textContent = '💾 Save Translation';
                        saveBtn.disabled = false;
                        saveBtn.classList.add('hidden');  // Hide after save
                    }, 2000);
                } else {
                    alert('Error: ' + (data.error || 'Save failed'));
                    saveBtn.textContent = '💾 Save Translation';
                    saveBtn.disabled = false;
                }
            } catch (error) {
                alert('Error: ' + error.message);
                saveBtn.textContent = '💾 Save Translation';
                saveBtn.disabled = false;
            }
        });
    }


    // ============================================
    // Keyboard Shortcuts
    // ============================================
    document.addEventListener('keydown', (e) => {
        // Ignore if user is typing in input/textarea
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        // Ignore if any modifier keys (Ctrl, Alt, Meta)
        if (e.ctrlKey || e.altKey || e.metaKey) {
            return;
        }

        switch (e.key.toLowerCase()) {
            case 't':
                // Toggle Translate
                e.preventDefault();
                if (!translateBtn.disabled) {
                    translateBtn.click();
                }
                break;

            case 'e':
                // Enter Edit Mode
                e.preventDefault();
                if (!editBtn.classList.contains('hidden') && !editBtn.disabled) {
                    editBtn.click();
                }
                break;

            case 's':
                // Save Translation
                e.preventDefault();
                if (!saveBtn.classList.contains('hidden') && !saveBtn.disabled) {
                    saveBtn.click();
                }
                break;

            case 'c':
                // Toggle Compare Mode
                e.preventDefault();
                if (!compareBtn.classList.contains('hidden') && !compareBtn.disabled) {
                    compareBtn.click();
                }
                break;

            case 'escape':
                // Exit Edit Mode or Compare Mode
                e.preventDefault();
                if (!editArea.classList.contains('hidden')) {
                    // Exit edit mode
                    cancelEditBtn.click();
                } else if (isCompareMode) {
                    // Exit compare mode
                    compareBtn.click();
                }
                break;

            case '?':
                // Show keyboard shortcuts help
                e.preventDefault();
                toggleShortcutsHelp();
                break;
        }
    });

    // ============================================
    // Keyboard Shortcuts Help Modal
    // ============================================
    function toggleShortcutsHelp() {
        const modal = document.getElementById('shortcuts-modal');
        if (modal) {
            modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
        }
    }

    // Close modal when clicking outside
    document.addEventListener('click', (e) => {
        const modal = document.getElementById('shortcuts-modal');
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // Close modal with Escape key (when not in edit mode)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('shortcuts-modal');
            if (modal && modal.style.display === 'flex') {
                e.preventDefault();
                modal.style.display = 'none';
            }

            // Also close character popup
            const charPopup = document.getElementById('character-popup');
            if (charPopup && charPopup.style.display === 'flex') {
                e.preventDefault();
                charPopup.style.display = 'none';
            }
        }
    });

    // ============================================
    // Character Annotations Logic
    // ============================================

    // Initial highlight if translated text exists
    if (isTranslated && !isCompareMode) {
        applyCharacterHighlights();
    }

    function applyCharacterHighlights() {
        console.log('applyCharacterHighlights called, isTranslated:', isTranslated, 'translatedText length:', translatedText?.length);
        if (!textDisplay) return;
        if (!window.chapterData.glossary || Object.keys(window.chapterData.glossary).length === 0) {
            console.log('No glossary, displaying plain translated text');
            textDisplay.textContent = translatedText;  // ✅ Display plain text
            return;
        }

        // Use innerHTML to allow spans
        const highlightedText = highlightCharacters(translatedText);
        console.log('Setting textDisplay.innerHTML with highlighted text');
        textDisplay.innerHTML = highlightedText;

        // Add click handlers to new highlights
        addCharacterClickHandlers();
    }

    function highlightCharacters(text) {
        if (!text) return '';

        let processedText = text;
        const glossary = window.chapterData.glossary;

        // Filter to only characters with descriptions
        const charsWithDescriptions = Object.keys(glossary).filter(charId => {
            const charInfo = glossary[charId];
            return charInfo.description && charInfo.description.trim();
        });

        // Sort by length (descending) to handle substrings correctly
        const sortedCharIds = charsWithDescriptions.sort((a, b) => {
            const nameA = glossary[a].english_name || '';
            const nameB = glossary[b].english_name || '';
            return nameB.length - nameA.length;
        });

        // Create a temporary placeholder map to avoid nested replacements
        const placeholders = {};
        let placeholderCounter = 0;

        sortedCharIds.forEach(charId => {
            const charInfo = glossary[charId];
            const englishName = charInfo.english_name;

            if (englishName && englishName.trim().length > 0) {
                // Case-insensitive replacement, but preserve original casing
                const regex = new RegExp(`\\b${escapeRegExp(englishName)}\\b`, 'gi');

                processedText = processedText.replace(regex, (match) => {
                    const placeholder = `__CHAR_PLACEHOLDER_${placeholderCounter++}__`;
                    placeholders[placeholder] = `<span class="character-highlight has-description" data-char-id="${charId}">${match}</span>`;
                    return placeholder;
                });
            }
        });

        // Restore placeholders
        Object.keys(placeholders).forEach(placeholder => {
            processedText = processedText.replace(placeholder, placeholders[placeholder]);
        });

        return processedText;
    }

    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function addCharacterClickHandlers() {
        const highlights = textDisplay.querySelectorAll('.character-highlight');
        highlights.forEach(span => {
            const charId = span.getAttribute('data-char-id');
            const glossary = window.chapterData.glossary;
            const charInfo = glossary[charId];

            // Only make clickable if character has a description
            if (charInfo && charInfo.description && charInfo.description.trim()) {
                span.classList.add('has-description');
                span.addEventListener('click', (e) => {
                    e.stopPropagation();
                    showCharacterPopup(charId);
                });
            } else {
                // Remove cursor pointer for characters without descriptions
                span.style.cursor = 'default';
            }
        });
    }

    function showCharacterPopup(charId) {
        const glossary = window.chapterData.glossary;
        const charInfo = glossary[charId];

        if (!charInfo) return;

        // Don't show popup if no description
        if (!charInfo.description || !charInfo.description.trim()) {
            return;
        }

        const popup = document.getElementById('character-popup');
        const nameEl = document.getElementById('popup-name');
        const metaEl = document.getElementById('popup-meta');
        const descEl = document.getElementById('popup-description');

        // Set content
        nameEl.textContent = charInfo.english_name || charInfo.korean_name;

        // Meta info (Korean name, Gender)
        let metaHtml = `<span class="popup-korean">${charInfo.korean_name || ''}</span>`;

        if (charInfo.gender && charInfo.gender !== 'auto') {
            let genderLabel = charInfo.gender;
            if (charInfo.gender === 'male') genderLabel = 'Male (he/him)';
            if (charInfo.gender === 'female') genderLabel = 'Female (she/her)';
            if (charInfo.gender === 'other') genderLabel = 'Other (they/them)';

            metaHtml += `<span class="popup-gender gender-${charInfo.gender}">${genderLabel}</span>`;
        }
        metaEl.innerHTML = metaHtml;

        // Description with Markdown parsing
        const description = charInfo.description;
        descEl.innerHTML = parseMarkdown(description);

        // Show popup
        popup.style.display = 'flex';
    }

    // Close popup handlers
    const closePopupBtn = document.querySelector('.close-popup-btn');
    if (closePopupBtn) {
        closePopupBtn.addEventListener('click', () => {
            document.getElementById('character-popup').style.display = 'none';
        });
    }

    // Close when clicking outside content
    const charPopup = document.getElementById('character-popup');
    if (charPopup) {
        charPopup.addEventListener('click', (e) => {
            if (e.target === charPopup) {
                charPopup.style.display = 'none';
            }
        });
    }

    function parseMarkdown(text) {
        if (!text) return '';

        let html = text
            // Escape HTML first
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Bold: **text**
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic: *text*
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Lists: - item
            .replace(/^- (.*$)/gm, '<li>$1</li>')
            // Newlines to <br>
            .replace(/\n/g, '<br>');

        // Wrap lists
        if (html.includes('<li>')) {
            html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
        }

        return html;
    }

    // Hook into translation completion to apply highlights
    const originalTranslateBtnClick = translateBtn.onclick; // Note: we used addEventListener, so this might be null

    // We need to modify the existing translateBtn listener logic
    // Since we can't easily "hook" into the existing listener without rewriting it,
    // we'll rely on the fact that we're replacing the file content.
    // Ideally, we should update the translateBtn listener in the main block above.
    // For now, let's just make sure applyCharacterHighlights is called when translation finishes.
    // We can do this by observing the textDisplay for changes? 
    // Or better, let's just update the translateBtn listener in the next step if needed.
    // Actually, let's just add a MutationObserver to textDisplay to re-apply highlights if text changes?
    // No, that might cause infinite loops if we modify innerHTML.

    // Let's just expose applyCharacterHighlights globally so we can call it?
    // Or better, let's rewrite the translateBtn listener in a separate edit if needed.
    // For now, let's assume the user will reload or we can just re-apply highlights manually.

    // Wait! I can just overwrite the translateBtn listener logic in the previous block if I include it in the replacement range.
    // But I'm appending to the end.

    // Let's use a MutationObserver but be careful.
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList' && mutation.target === textDisplay) {
                // Only apply if it's plain text (not already highlighted)
                // and we have a glossary
                if (!textDisplay.querySelector('.character-highlight') &&
                    window.chapterData.glossary &&
                    Object.keys(window.chapterData.glossary).length > 0 &&
                    textDisplay.textContent.trim().length > 0 &&
                    !isCompareMode) {

                    // Disconnect to avoid loop
                    observer.disconnect();
                    applyCharacterHighlights();
                    // Reconnect
                    observer.observe(textDisplay, { childList: true });
                }
            }
        });
    });

    observer.observe(textDisplay, { childList: true });

    // Load token usage if chapter has an ID (may have historical data even if text was cleared)
    if (window.chapterData.chapterId) {
        fetchChapterTokenUsage(window.chapterData.chapterId);
    }

    (function checkTranslationStatus() {
        const chapterId = window.chapterData.chapterId;
        const hasTranslation = isTranslated;

        // If chapter has an ID but no translation, check if translation is in progress
        if (chapterId && !hasTranslation) {
            // FIRST: Check the actual translation status from the backend
            fetch(`/api/check-chapter-translation?novel_id=${encodeURIComponent(window.chapterData.novelId)}&chapter_index=${window.chapterData.chapterIndex}`)
                .then(response => response.json())
                .then(data => {
                    console.log('Initial translation status check:', data);

                    // Check for any active status (in_progress, queued, processing)
                    // 'pending' means not started yet, so don't include it
                    const activeStatuses = ['in_progress', 'queued', 'processing'];
                    const isActive = activeStatuses.includes(data.translation_status);

                    // Only show status indicator if translation is actually in progress/queued
                    if (isActive) {
                        const statusDiv = document.getElementById('translation-status');
                        if (statusDiv) {
                            statusDiv.classList.remove('hidden');
                            statusDiv.style.display = 'flex';

                            // Update text based on status
                            const statusText = statusDiv.querySelector('.status-text');
                            if (statusText) {
                                statusText.textContent = data.translation_status === 'queued' ? 'Translation queued...' : 'Chapter translating...';
                            }

                            // Poll for translation completion every 3 seconds
                            let pollCount = 0;
                            const maxPolls = 100; // 5 minutes max

                            const pollInterval = setInterval(async () => {
                                pollCount++;

                                try {
                                    const response = await fetch(`/api/check-chapter-translation?novel_id=${encodeURIComponent(window.chapterData.novelId)}&chapter_index=${window.chapterData.chapterIndex}`);
                                    if (response.ok) {
                                        const pollData = await response.json();
                                        console.log('Poll response:', pollData);

                                        // Check if translation is complete
                                        const hasContent = pollData.translated_content || pollData.translated_text;
                                        const isComplete = pollData.translated && hasContent;

                                        if (isComplete) {
                                            clearInterval(pollInterval);
                                            console.log('✅ Translation complete, refreshing page...');

                                            statusDiv.innerHTML = '<span class="status-icon">✅</span><span class="status-text">Translation complete! Refreshing...</span>';

                                            // Force refresh to load everything cleanly
                                            setTimeout(() => {
                                                window.location.reload();
                                            }, 1000);
                                            return;
                                        }

                                        // If status changed to inactive without completion, stop polling
                                        if (!activeStatuses.includes(pollData.translation_status) && !pollData.translated) {
                                            console.log('Translation status changed to inactive:', pollData.translation_status);
                                            clearInterval(pollInterval);
                                            statusDiv.innerHTML = '<span class="status-icon">❌</span><span class="status-text">Translation failed or stopped.</span>';
                                            return;
                                        }
                                    }
                                } catch (error) {
                                    console.error('Error checking translation status:', error);
                                }

                                // Stop polling after max attempts
                                if (pollCount >= maxPolls) {
                                    clearInterval(pollInterval);
                                    statusDiv.innerHTML = '<span class="status-icon">⚠️</span><span class="status-text">Translation taking longer than expected. Please refresh manually.</span>';
                                }
                            }, 3000);
                        }
                    }
                })
                .catch(error => {
                    console.error('Error checking initial translation status:', error);
                });
        }
    })();

});
