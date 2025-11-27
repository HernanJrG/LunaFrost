document.addEventListener('DOMContentLoaded', function () {
    const charactersContainer = document.getElementById('characters-container');
    const addCharacterBtn = document.getElementById('add-character-btn');
    const autoDetectBtn = document.getElementById('auto-detect-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const alertContainer = document.getElementById('alert-container');
    const loadingOverlay = document.getElementById('loading-overlay');

    let charCounter = window.novelSettingsData.glossaryLength;

    // Toggle character entry expansion
    document.addEventListener('click', function (e) {
        const header = e.target.closest('.character-header');
        if (header && !e.target.closest('.btn-remove-char')) {
            const entry = header.closest('.character-entry');
            entry.classList.toggle('collapsed');
            entry.classList.toggle('expanded');
        }
    });

    // Add character entry manually
    addCharacterBtn.addEventListener('click', function () {
        charCounter++;
        const newEntry = createCharacterEntry('', '', 'auto', true);
        charactersContainer.appendChild(newEntry);
        removeEmptyMessage();
    });

    // Auto-detect characters with name translation AND gender detection
    autoDetectBtn.addEventListener('click', async function () {
        loadingOverlay.style.display = 'flex';

        try {
            const novelId = window.novelSettingsData.novelId;
            const response = await fetch('/api/novel/' + encodeURIComponent(novelId) + '/auto-detect-characters', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();

            if (data.success && data.characters) {
                // Get existing Korean names to avoid duplicates
                const existingNames = new Set();
                charactersContainer.querySelectorAll('.char-korean').forEach(input => {
                    if (input.value.trim()) {
                        existingNames.add(input.value.trim());
                    }
                });

                let addedCount = 0;
                let skippedCount = 0;

                // Add detected characters with auto-translated English names and AI-detected genders
                data.characters.forEach(function (koreanName) {
                    if (existingNames.has(koreanName)) {
                        skippedCount++;
                        return;
                    }

                    const englishName = data.translations && data.translations[koreanName]
                        ? data.translations[koreanName]
                        : '';

                    const gender = data.genders && data.genders[koreanName]
                        ? data.genders[koreanName]
                        : 'auto';

                    const entry = createCharacterEntry(koreanName, englishName, gender, false);
                    charactersContainer.appendChild(entry);
                    charCounter++;
                    addedCount++;
                });

                removeEmptyMessage();

                let message = '✓ Auto-detected ' + addedCount + ' new character(s)!';
                if (skippedCount > 0) {
                    message += ' (Skipped ' + skippedCount + ' duplicate(s))';
                }
                showAlert(message, 'success');
            } else {
                showAlert('Error: ' + (data.error || 'Failed to detect characters'), 'error');
            }
        } catch (error) {
            showAlert('Error: ' + error.message, 'error');
        } finally {
            loadingOverlay.style.display = 'none';
        }
    });

    // Remove character entries
    document.addEventListener('click', function (e) {
        const removeBtn = e.target.closest('.btn-remove-char');
        if (removeBtn) {
            e.stopPropagation();
            const entry = removeBtn.closest('.character-entry');
            if (entry) {
                entry.remove();

                // Show empty message if no characters left
                if (charactersContainer.querySelectorAll('.character-entry').length === 0) {
                    showEmptyMessage();
                }
            }
        }
    });

    // Update character summary when fields change
    document.addEventListener('input', function (e) {
        if (e.target.classList.contains('char-korean') ||
            e.target.classList.contains('char-english') ||
            e.target.classList.contains('char-gender')) {

            const entry = e.target.closest('.character-entry');
            updateCharacterSummary(entry);
        }
    });

    // Save settings (glossary only, sort order is auto-saved)
    saveSettingsBtn.addEventListener('click', async function () {
        const glossary = {};
        const entries = charactersContainer.querySelectorAll('.character-entry');

        entries.forEach(function (entry, index) {
            const koreanName = entry.querySelector('.char-korean').value.trim();
            const englishName = entry.querySelector('.char-english').value.trim();
            const gender = entry.querySelector('.char-gender').value;
            const description = entry.querySelector('.char-description').value.trim();

            if (koreanName || englishName) {
                glossary['char_' + index] = {
                    korean_name: koreanName,
                    english_name: englishName,
                    gender: gender,
                    description: description
                };
            }
        });

        try {
            // Save glossary only
            const novelId = window.novelSettingsData.novelId;
            let response = await fetch('/api/novel/' + encodeURIComponent(novelId) + '/glossary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ glossary: glossary })
            });

            let data = await response.json();

            if (data.success) {
                showAlert('✓ Character glossary saved! (' + Object.keys(glossary).length + ' characters)', 'success');

                // Reload the page after a short delay
                setTimeout(function () {
                    location.reload();
                }, 1500);
            } else {
                showAlert('Error: ' + (data.error || 'Failed to save glossary'), 'error');
            }
        } catch (error) {
            showAlert('Error: ' + error.message, 'error');
        }
    });


    function createCharacterEntry(koreanName, englishName, gender, expanded) {
        const entry = document.createElement('div');
        entry.className = 'character-entry ' + (expanded ? 'expanded' : 'collapsed');

        // Escape HTML in values
        const escapeHtml = function (text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        };

        const safeKoreanName = escapeHtml(koreanName);
        const safeEnglishName = escapeHtml(englishName);

        const displayKoreanName = koreanName || '(Empty)';
        const displayEnglishName = englishName || '(Not set)';

        // Default to 'auto' if not specified
        if (!gender) gender = 'auto';

        let genderBadgeHtml = '';
        let genderDisplayText = '';

        if (gender === 'auto') {
            genderBadgeHtml = '<span class="gender-badge gender-auto">AI Auto-select</span>';
            genderDisplayText = 'AI Auto-select';
        } else if (gender === 'male') {
            genderBadgeHtml = '<span class="gender-badge gender-male">he/him</span>';
            genderDisplayText = 'he/him';
        } else if (gender === 'female') {
            genderBadgeHtml = '<span class="gender-badge gender-female">she/her</span>';
            genderDisplayText = 'she/her';
        } else if (gender === 'other') {
            genderBadgeHtml = '<span class="gender-badge gender-other">they/them</span>';
            genderDisplayText = 'they/them';
        } else {
            genderBadgeHtml = '<span class="gender-badge gender-auto">AI Auto-select</span>';
            genderDisplayText = 'AI Auto-select';
        }

        const headerHtml =
            '<div class="character-header">' +
            '<div class="character-summary">' +
            '<span class="korean-name">' + displayKoreanName + '</span>' +
            '<span class="arrow">→</span>' +
            '<span class="english-name">' + displayEnglishName + '</span>' +
            genderBadgeHtml +
            '</div>' +
            '<div class="character-actions">' +
            '<button class="btn btn-danger btn-remove-char">✕</button>' +
            '<span class="expand-icon">▼</span>' +
            '</div>' +
            '</div>';

        const detailsHtml =
            '<div class="character-details">' +
            '<div class="form-group">' +
            '<label>Korean Name (Original)</label>' +
            '<input type="text" class="char-korean" placeholder="e.g., 김철수" value="' + safeKoreanName + '">' +
            '</div>' +
            '<div class="form-group">' +
            '<label>English Name (Translation)</label>' +
            '<input type="text" class="char-english" placeholder="e.g., John Kim" value="' + safeEnglishName + '">' +
            '</div>' +
            '<div class="form-group">' +
            '<label>Gender / Pronouns</label>' +
            '<select class="char-gender">' +
            '<option value="auto"' + (gender === 'auto' ? ' selected' : '') + '>AI Auto-select (recommended)</option>' +
            '<option value="male"' + (gender === 'male' ? ' selected' : '') + '>Male (he/him)</option>' +
            '<option value="female"' + (gender === 'female' ? ' selected' : '') + '>Female (she/her)</option>' +
            '<option value="other"' + (gender === 'other' ? ' selected' : '') + '>Other (they/them)</option>' +
            '</select>' +
            '<p class="help-text">AI Auto-select lets the translator determine the best pronouns based on context</p>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>Description (Optional)</label>' +
            '<textarea class="char-description" placeholder="e.g., Main protagonist, skilled swordsman, age 25"></textarea>' +
            '<p class="help-text">Additional context to help the AI translate consistently. Supports <strong>Markdown</strong> (e.g., **bold**, *italic*).</p>' +
            '</div>' +
            '</div>';

        entry.innerHTML = headerHtml + detailsHtml;
        return entry;
    }

    function updateCharacterSummary(entry) {
        const koreanName = entry.querySelector('.char-korean').value.trim() || '(Empty)';
        const englishName = entry.querySelector('.char-english').value.trim() || '(Not set)';
        const gender = entry.querySelector('.char-gender').value;

        const summary = entry.querySelector('.character-summary');

        let genderBadgeClass = 'gender-auto';
        let genderBadgeText = 'AI Auto-select';

        if (gender === 'auto') {
            genderBadgeClass = 'gender-auto';
            genderBadgeText = 'AI Auto-select';
        } else if (gender === 'male') {
            genderBadgeClass = 'gender-male';
            genderBadgeText = 'he/him';
        } else if (gender === 'female') {
            genderBadgeClass = 'gender-female';
            genderBadgeText = 'she/her';
        } else if (gender === 'other') {
            genderBadgeClass = 'gender-other';
            genderBadgeText = 'they/them';
        }

        summary.innerHTML =
            '<span class="korean-name">' + koreanName + '</span>' +
            '<span class="arrow">→</span>' +
            '<span class="english-name">' + englishName + '</span>' +
            '<span class="gender-badge ' + genderBadgeClass + '">' + genderBadgeText + '</span>';
    }

    function removeEmptyMessage() {
        const emptyMessage = document.getElementById('empty-message');
        if (emptyMessage) {
            emptyMessage.remove();
        }
    }

    function showEmptyMessage() {
        charactersContainer.innerHTML = '<p id="empty-message" style="text-align: center; color: #718096; padding: 40px;">No characters added yet. Click "Add Character Manually" or "Auto-Detect Characters" to get started.</p>';
    }

    function showAlert(message, type) {
        alertContainer.innerHTML =
            '<div class="alert alert-' + type + '">' +
            message +
            '</div>';

        window.scrollTo({ top: 0, behavior: 'smooth' });

        setTimeout(function () {
            alertContainer.innerHTML = '';
        }, 5000);
    }
});
