// popup/popup.js - CONCURRENT VERSION

document.addEventListener('DOMContentLoaded', () => {
  console.log('🔧 Extension popup loaded');

  // Element references
  const serverUrlInput = document.getElementById('server-url');
  const maxConcurrentTabsInput = document.getElementById('max-concurrent-tabs');
  const saveSettingsBtn = document.getElementById('save-settings');
  const importNovelBtn = document.getElementById('import-novel');
  const importChapterBtn = document.getElementById('import-chapter');
  const getChapterRangeBtn = document.getElementById('get-chapter-range');
  const batchImportBtn = document.getElementById('batch-import');
  const cancelBatchBtn = document.getElementById('cancel-batch');
  const statusDiv = document.getElementById('status');
  const chapterRangeInfo = document.getElementById('chapter-range-info');
  const progressContainer = document.getElementById('progress-container');
  const progressFill = document.getElementById('progress-fill');
  const progressText = document.getElementById('progress-text');
  const progressSuccess = document.getElementById('progress-success');
  const progressFailed = document.getElementById('progress-failed');

  // Section elements
  const singleChapterSection = document.getElementById('single-chapter-section');
  const batchImportSection = document.getElementById('batch-import-section');

  // Collapsible sections
  const settingsToggle = document.getElementById('settings-toggle');
  const settingsContent = document.getElementById('settings-content');
  const autoTranslateTitleCheckbox = document.getElementById('auto-translate-title');
  const autoTranslateContentCheckbox = document.getElementById('auto-translate-content');
  const autoTranslateContentContainer = document.getElementById('auto-translate-content-container');

  // Tab elements
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  let batchImportInProgress = false;
  let batchImportCancelled = false;
  let detectedChapterInfo = null;

  // Load saved settings
  chrome.storage.sync.get([
    'serverUrl',
    'maxConcurrentTabs',
    'auto_translate_title',
    'auto_translate_content',
    'autoTranslateEnabled' // For backward compatibility
  ], (result) => {
    const savedUrl = result.serverUrl || 'https://lunafrost.moe';
    const savedMaxTabs = result.maxConcurrentTabs || 1;

    serverUrlInput.value = savedUrl;
    if (maxConcurrentTabsInput) {
      maxConcurrentTabsInput.value = savedMaxTabs;
    }

    // Backward compatibility: if old setting exists but new ones don't, migrate
    if (result.autoTranslateEnabled !== undefined &&
      result.auto_translate_title === undefined) {
      result.auto_translate_title = result.autoTranslateEnabled;
      result.auto_translate_content = result.autoTranslateEnabled;
      // Save the new settings
      chrome.storage.sync.set({
        auto_translate_title: result.autoTranslateEnabled,
        auto_translate_content: result.autoTranslateEnabled
      });
    }

    const autoTranslateTitle = result.auto_translate_title || false;
    const autoTranslateContent = result.auto_translate_content || false;

    console.log('📂 Loaded settings:', {
      savedUrl,
      savedMaxTabs,
      autoTranslateTitle,
      autoTranslateContent
    });

    // Set checkbox states
    if (autoTranslateTitleCheckbox) {
      autoTranslateTitleCheckbox.checked = autoTranslateTitle;
    }
    if (autoTranslateContentCheckbox) {
      autoTranslateContentCheckbox.checked = autoTranslateContent;
    }

    // Initial visibility check
    if (autoTranslateTitleCheckbox && autoTranslateContentContainer) {
      if (autoTranslateTitleCheckbox.checked) {
        autoTranslateContentContainer.classList.remove('hidden');
      } else {
        autoTranslateContentContainer.classList.add('hidden');
      }
    }
  });

  // Tab switching logic
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      // Remove active class from all buttons and contents
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      // Add active class to clicked button
      btn.classList.add('active');

      // Show corresponding content
      const tabId = btn.getAttribute('data-tab');
      document.getElementById(`tab-${tabId}`).classList.add('active');
    });
  });

  // Save auto-translate preferences when checkboxes change
  if (autoTranslateTitleCheckbox) {
    autoTranslateTitleCheckbox.addEventListener('change', function () {
      chrome.storage.sync.set({ auto_translate_title: this.checked });

      // Toggle content option visibility
      if (autoTranslateContentContainer) {
        if (this.checked) {
          autoTranslateContentContainer.classList.remove('hidden');
        } else {
          autoTranslateContentContainer.classList.add('hidden');
          // Also uncheck content if title is unchecked
          if (autoTranslateContentCheckbox && autoTranslateContentCheckbox.checked) {
            autoTranslateContentCheckbox.checked = false;
            // Trigger change event to save content setting
            const event = new Event('change');
            autoTranslateContentCheckbox.dispatchEvent(event);
          }
        }
      }
    });
  }
  if (autoTranslateContentCheckbox) {
    autoTranslateContentCheckbox.addEventListener('change', function () {
      chrome.storage.sync.set({ auto_translate_content: this.checked });

      // If content is checked, automatically check title as well
      if (this.checked && autoTranslateTitleCheckbox && !autoTranslateTitleCheckbox.checked) {
        autoTranslateTitleCheckbox.checked = true;
        // Trigger change event to save title setting
        const event = new Event('change');
        autoTranslateTitleCheckbox.dispatchEvent(event);
      }
    });
  }

  // Detect current page type and show/hide sections accordingly
  function detectPageType() {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;

      const url = tabs[0].url;
      console.log('📍 Current URL:', url);

      // Check if on chapter page
      const isChapterPage = url.includes('/viewer/');

      // Check if on novel page
      const isNovelPage = url.includes('/novel/') && !isChapterPage;

      console.log('📄 Page type - Chapter:', isChapterPage, 'Novel:', isNovelPage);

      // Show/hide sections based on page type
      if (isChapterPage) {
        singleChapterSection.classList.remove('hidden');
        batchImportSection.classList.add('hidden');
      } else if (isNovelPage) {
        singleChapterSection.classList.add('hidden');
        batchImportSection.classList.remove('hidden');
      } else {
        singleChapterSection.classList.add('hidden');
        batchImportSection.classList.add('hidden');
        showStatus('Please navigate to a Novelpia novel or chapter page', 'info');
      }
    });
  }

  // Detect page type on load
  detectPageType();

  // Helper function to get server URL
  function getServerUrl() {
    return serverUrlInput.value.trim() || 'https://lunafrost.moe';
  }

  // Helper function to check authentication
  async function checkAuthentication(serverUrl) {
    console.log('🔐 Checking authentication with:', serverUrl);

    try {
      const response = await fetch(`${serverUrl}/api/check-auth`, {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return {
        success: true,
        authenticated: data.authenticated,
        user: data.user,
        data: data
      };

    } catch (error) {
      console.error('🔐 Auth check failed:', error);
      return {
        success: false,
        authenticated: false,
        error: error.message
      };
    }
  }

  // Save settings
  saveSettingsBtn.addEventListener('click', () => {
    const serverUrl = serverUrlInput.value.trim();
    let maxTabs = 1;

    if (maxConcurrentTabsInput) {
      maxTabs = parseInt(maxConcurrentTabsInput.value);
      if (isNaN(maxTabs) || maxTabs < 1) maxTabs = 1;
      if (maxTabs > 10) maxTabs = 10;
      maxConcurrentTabsInput.value = maxTabs;
    }

    if (!serverUrl) {
      showStatus('Please enter a server URL', 'error');
      return;
    }

    try {
      new URL(serverUrl);
    } catch (e) {
      showStatus('Invalid URL format.', 'error');
      return;
    }

    console.log('💾 Saving settings:', { serverUrl, maxTabs });

    chrome.storage.sync.set({ serverUrl, maxConcurrentTabs: maxTabs }, () => {
      if (chrome.runtime.lastError) {
        showStatus('Error saving settings: ' + chrome.runtime.lastError.message, 'error');
        return;
      }

      showStatus('✅ Settings saved successfully!', 'success');
    });
  });

  // Import novel metadata
  importNovelBtn.addEventListener('click', async () => {
    importNovelBtn.disabled = true;
    showStatus('Extracting novel metadata...', 'info');

    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      if (!tabs[0]) {
        showStatus('Error: No active tab found', 'error');
        importNovelBtn.disabled = false;
        return;
      }

      try {
        const response = await new Promise((resolve, reject) => {
          chrome.tabs.sendMessage(tabs[0].id, { action: 'extractNovelMetadata' }, (resp) => {
            if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
            else resolve(resp);
          });
        });

        if (!response || response.error) throw new Error(response?.error || 'No response from content script');

        const serverUrl = getServerUrl();
        const authResult = await checkAuthentication(serverUrl);

        if (!authResult.success) throw new Error('Cannot connect to server: ' + authResult.error);
        if (!authResult.authenticated) throw new Error('Not logged in. Please log in at ' + serverUrl);

        const payload = {
          original_title: response.original_title || response.title || 'Unknown',
          title: response.title || 'Unknown',
          chapter_title: '',
          content: '',
          source_url: tabs[0].url,
          novel_source_url: tabs[0].url,
          images: [],
          cover_url: response.cover_url || '',
          author: response.author || '',
          tags: response.tags || [],
          synopsis: response.synopsis || ''
        };

        const res = await fetch(`${serverUrl}/api/import-chapter`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`Server error ${res.status}: ${errorText}`);
        }

        const data = await res.json();
        if (data.success) {
          showStatus('✅ Novel metadata imported successfully!', 'success');
        } else {
          throw new Error(data.error || 'Import failed');
        }

      } catch (error) {
        showStatus('Error: ' + error.message, 'error');
      } finally {
        importNovelBtn.disabled = false;
      }
    });
  });

  // Import single chapter
  importChapterBtn.addEventListener('click', async () => {
    importChapterBtn.disabled = true;
    showStatus('Extracting chapter...', 'info');

    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      if (!tabs[0]) {
        showStatus('Error: No active tab found', 'error');
        importChapterBtn.disabled = false;
        return;
      }

      const currentTab = tabs[0];
      const currentUrl = currentTab.url;

      try {
        // Use retry utility for robust extraction
        const response = await RetryUtils.withRetry(async () => {
          return await new Promise((resolve, reject) => {
            chrome.tabs.sendMessage(currentTab.id, { action: 'extractChapter' }, (resp) => {
              if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
              } else if (!resp) {
                reject(new Error('No response from content script'));
              } else if (resp.error) {
                // Check if it's a validation error that should be retried
                if (resp.error === 'Content validation failed') {
                  const err = new Error(resp.error);
                  err.validation_errors = resp.validation_errors;
                  reject(err);
                } else {
                  reject(new Error(resp.error));
                }
              } else {
                resolve(resp);
              }
            });
          });
        }, {
          maxAttempts: 3,
          baseDelay: 1000,
          shouldRetry: (error) => {
            // Retry on validation failures or network/communication errors
            return RetryUtils.isRetriableError(error);
          },
          onRetry: (attempt, max, error) => {
            showStatus(`⚠️ Extraction failed (Attempt ${attempt}/${max}). Retrying...`, 'warning');
          }
        });

        const serverUrl = getServerUrl();

        const chapterNumber = response.chapter_number;
        const isBonus = chapterNumber === 'BONUS';

        const autoTranslateTitle = autoTranslateTitleCheckbox ? autoTranslateTitleCheckbox.checked : false;
        const autoTranslateContent = autoTranslateContentCheckbox ? autoTranslateContentCheckbox.checked : false;

        const payload = {
          original_title: response.original_title || 'Unknown Novel',
          title: response.chapter_title || response.title,
          chapter_title: response.chapter_title || response.title,
          chapter_number: chapterNumber,
          content: response.content,
          source_url: currentUrl,
          novel_source_url: response.novel_source_url || currentUrl,
          images: response.images || [],
          cover_url: response.cover_url || '',
          author: response.author || '',
          tags: response.tags || [],
          synopsis: response.synopsis || '',
          is_bonus: isBonus,
          position: null,
          auto_translate_title: autoTranslateTitle,
          auto_translate_content: autoTranslateContent,
          skip_translation: false
        };

        const res = await fetch(`${serverUrl}/api/import-chapter`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`Server error ${res.status}: ${errorText}`);
        }

        const data = await res.json();
        if (data.success) {
          showStatus('✅ Chapter imported successfully!', 'success');
        } else {
          throw new Error(data.error || 'Import failed');
        }

      } catch (error) {
        showStatus('Error: ' + error.message, 'error');
      } finally {
        importChapterBtn.disabled = false;
      }
    });
  });

  // Get chapter range
  getChapterRangeBtn.addEventListener('click', () => {
    getChapterRangeBtn.disabled = true;
    getChapterRangeBtn.style.display = 'none';
    showStatus('Detecting chapter information...', 'info');

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) {
        showStatus('Error: No active tab found', 'error');
        getChapterRangeBtn.disabled = false;
        getChapterRangeBtn.style.display = 'block';
        return;
      }

      chrome.tabs.sendMessage(tabs[0].id, { action: 'getChapterRange' }, (response) => {
        if (chrome.runtime.lastError) {
          showStatus('Error: ' + chrome.runtime.lastError.message + '\n\nMake sure you are on a Novelpia novel page.', 'error');
          getChapterRangeBtn.disabled = false;
          getChapterRangeBtn.style.display = 'block';
          return;
        }

        if (!response || response.error) {
          showStatus('Error: ' + (response?.error || 'No response'), 'error');
          getChapterRangeBtn.disabled = false;
          getChapterRangeBtn.style.display = 'block';
          return;
        }

        detectedChapterInfo = response;
        document.getElementById('chapter-start').value = response.visibleMin;
        document.getElementById('chapter-end').value = response.visibleMax;

        showStatus('🔍 Scanning all pages for chapters...\n\n(Page 1 of ' + response.totalPages + ')', 'info');

        chrome.tabs.sendMessage(
          tabs[0].id,
          {
            action: 'getAllChapterIds',
            novelId: response.novelId,
            totalPages: response.totalPages
          },
          (collectionResponse) => {
            if (chrome.runtime.lastError) {
              showStatus('⚠️ Error during collection: ' + chrome.runtime.lastError.message + '\n\nUsing detected range only', 'warning');
              return;
            }

            if (!collectionResponse || !collectionResponse.success) {
              showStatus('⚠️ Collection failed: ' + (collectionResponse?.error || 'Unknown error'), 'warning');
              return;
            }

            detectedChapterInfo.allCollectedChapters = collectionResponse.chapters;

            let minChapterNum = Infinity;
            let maxChapterNum = -Infinity;

            collectionResponse.chapters.forEach(ch => {
              if (!ch.isBonus && typeof ch.chapterNumber === 'number') {
                minChapterNum = Math.min(minChapterNum, ch.chapterNumber);
                maxChapterNum = Math.max(maxChapterNum, ch.chapterNumber);
              }
            });

            if (minChapterNum === Infinity) {
              minChapterNum = 1;
              maxChapterNum = 1;
            }

            document.getElementById('chapter-start').value = minChapterNum;
            document.getElementById('chapter-end').value = maxChapterNum;

            const bonusCount = collectionResponse.chapters.filter(ch => ch.isBonus).length;
            const regularCount = collectionResponse.chapters.length - bonusCount;

            chapterRangeInfo.style.display = 'block';
            showStatus(`✅ Finished scanning!\n\nFound ${collectionResponse.chapters.length} chapters (${regularCount} regular + ${bonusCount} bonus)\nRange: ${minChapterNum} to ${maxChapterNum}`, 'success');
          }
        );
      });
    });
  });

  // Batch import - CONCURRENT VERSION
  batchImportBtn.addEventListener('click', async () => {
    if (!detectedChapterInfo || !detectedChapterInfo.allCollectedChapters) {
      showStatus('Please detect chapters first by clicking "Detect Chapters"', 'error');
      return;
    }

    const startChapter = parseInt(document.getElementById('chapter-start').value);
    const endChapter = parseInt(document.getElementById('chapter-end').value);

    if (isNaN(startChapter) || isNaN(endChapter) || startChapter > endChapter) {
      showStatus('Please enter valid chapter numbers', 'error');
      return;
    }

    const selectedRegularChapters = detectedChapterInfo.allCollectedChapters.filter(ch => {
      return !ch.isBonus && typeof ch.chapterNumber === 'number'
        && ch.chapterNumber >= startChapter && ch.chapterNumber <= endChapter;
    });

    if (selectedRegularChapters.length === 0) {
      showStatus('Error: No chapters found in the specified range', 'error');
      return;
    }

    const minPosition = Math.min(...selectedRegularChapters.map(ch => ch.position));
    const maxPosition = Math.max(...selectedRegularChapters.map(ch => ch.position));

    let chapters = detectedChapterInfo.allCollectedChapters.filter(ch => {
      return ch.position >= minPosition && ch.position <= maxPosition;
    });

    chapters.sort((a, b) => a.position - b.position);

    // Recalculate positions
    chapters = chapters.map((ch, index) => ({
      ...ch,
      position: index,
      originalPosition: ch.position
    }));

    const bonusCount = chapters.filter(ch => ch.isBonus).length;
    const regularCount = chapters.length - bonusCount;

    // Get concurrency limit
    const maxConcurrentTabs = parseInt(maxConcurrentTabsInput ? maxConcurrentTabsInput.value : 1) || 1;

    if (!confirm(`Import ${chapters.length} chapters (${regularCount} regular, ${bonusCount} bonus)?\n\nConcurrency: ${maxConcurrentTabs} tabs`)) {
      return;
    }

    batchImportBtn.disabled = true;
    batchImportBtn.style.display = 'none';
    cancelBatchBtn.style.display = 'block';
    getChapterRangeBtn.disabled = true;

    batchImportInProgress = true;
    batchImportCancelled = false;
    progressContainer.style.display = 'block';

    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      if (!tabs[0]) {
        showStatus('Error: No active tab found', 'error');
        resetBatchImportUI();
        return;
      }

      const mainTab = tabs[0];
      const serverUrl = getServerUrl();

      try {
        const authResult = await checkAuthentication(serverUrl);
        if (!authResult.success || !authResult.authenticated) {
          throw new Error('Authentication failed. Please log in.');
        }

        // Import metadata first
        try {
          const metadataResponse = await new Promise((resolve, reject) => {
            chrome.tabs.sendMessage(mainTab.id, { action: 'extractNovelMetadata' }, (resp) => {
              if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
              else resolve(resp);
            });
          });

          if (metadataResponse && !metadataResponse.error) {
            const metadataPayload = {
              original_title: metadataResponse.original_title || metadataResponse.title || 'Unknown',
              title: metadataResponse.title || 'Unknown',
              chapter_title: '', content: '', source_url: mainTab.url, novel_source_url: mainTab.url,
              images: [], cover_url: metadataResponse.cover_url || '', author: metadataResponse.author || '',
              tags: metadataResponse.tags || [], synopsis: metadataResponse.synopsis || ''
            };
            await fetch(`${serverUrl}/api/import-chapter`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
              credentials: 'include',
              body: JSON.stringify(metadataPayload)
            });
          }
        } catch (e) { console.warn('Metadata import failed', e); }

        progressFill.style.width = '0%';
        progressFill.textContent = '0%';
        progressText.textContent = 'Starting batch import...';
        progressSuccess.textContent = '✓ Success: 0';
        progressFailed.textContent = '✗ Failed: 0';
        document.getElementById('progress-skipped').style.display = 'inline-block';
        document.getElementById('progress-skipped').textContent = '⭐️ Skipped: 0';

        // Clear failed list
        const failedList = document.getElementById('failed-chapters-content');
        const failedContainer = document.getElementById('failed-chapters-list');
        if (failedList) failedList.innerHTML = '';
        if (failedContainer) failedContainer.style.display = 'none';

        const results = {
          success: 0, failed: 0, skipped: 0, errors: [], total: chapters.length, novelId: null
        };
        const importedEpisodeIds = new Set();
        const failedChapters = [];

        // Helper function to process a single chapter
        const processChapter = async (chapter, index) => {
          if (batchImportCancelled) return;

          const episodeNo = chapter.episodeNo;
          const chapterNum = chapter.chapterNumber;
          const isBonus = chapter.isBonus;
          const chapterUrl = `https://novelpia.com/viewer/${episodeNo}`;

          if (importedEpisodeIds.has(episodeNo)) {
            results.skipped++;
            return;
          }

          let chapterTab = null;
          try {
            chapterTab = await new Promise((resolve, reject) => {
              chrome.tabs.create({ url: chapterUrl, active: false }, (tab) => {
                if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
                else resolve(tab);
              });
            });

            await new Promise(resolve => setTimeout(resolve, 3000)); // Wait for load

            // Check content loaded
            let contentLoaded = false;
            for (let check = 0; check < 10; check++) {
              if (batchImportCancelled) throw new Error('Cancelled');
              try {
                const checkResp = await new Promise((resolve) => {
                  chrome.tabs.sendMessage(chapterTab.id, { action: 'checkContentLoaded' }, resolve);
                });
                if (checkResp && checkResp.loaded) { contentLoaded = true; break; }
              } catch (e) { }
              if (check < 9) await new Promise(resolve => setTimeout(resolve, 1000));
            }
            if (!contentLoaded) await new Promise(resolve => setTimeout(resolve, 2000));

            // Extract with retry
            const extractResp = await RetryUtils.withRetry(async () => {
              return await new Promise((resolve, reject) => {
                chrome.tabs.sendMessage(chapterTab.id, { action: 'extractChapter' }, (resp) => {
                  if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                  } else if (!resp) {
                    reject(new Error('No response from content script'));
                  } else if (resp.error) {
                    // Check if it's a validation error that should be retried
                    if (resp.error === 'Content validation failed') {
                      const err = new Error(resp.error);
                      err.validation_errors = resp.validation_errors;
                      reject(err);
                    } else {
                      reject(new Error(resp.error));
                    }
                  } else {
                    resolve(resp);
                  }
                });
              });
            }, {
              maxAttempts: 3,
              baseDelay: 1000,
              shouldRetry: (error) => RetryUtils.isRetriableError(error)
            });

            if (!extractResp || extractResp.error) throw new Error(extractResp?.error || 'Extraction failed');

            const autoTranslateTitle = autoTranslateTitleCheckbox ? autoTranslateTitleCheckbox.checked : false;
            const autoTranslateContent = autoTranslateContentCheckbox ? autoTranslateContentCheckbox.checked : false;

            const payload = {
              original_title: extractResp.original_title || 'Unknown Novel',
              title: extractResp.chapter_title || extractResp.title,
              chapter_title: extractResp.chapter_title || extractResp.title,
              chapter_number: chapterNum,
              content: extractResp.content,
              source_url: chapterUrl,
              novel_source_url: extractResp.novel_source_url || chapterUrl,
              images: extractResp.images || [],
              cover_url: extractResp.cover_url || '',
              author: extractResp.author || '',
              tags: extractResp.tags || [],
              synopsis: extractResp.synopsis || '',
              is_bonus: isBonus,
              position: chapter.position,
              auto_translate_title: autoTranslateTitle,
              auto_translate_content: autoTranslateContent,
              skip_translation: false
            };

            const res = await fetch(`${serverUrl}/api/import-chapter`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error(`Server error ${res.status}`);

            const data = await res.json();
            if (data.success) {
              if (data.already_exists) results.skipped++;
              else results.success++;
              importedEpisodeIds.add(episodeNo);
              if (data.novel_id) results.novelId = data.novel_id;
            } else {
              throw new Error(data.error || 'Import failed');
            }

          } catch (error) {
            results.failed++;
            results.errors.push(`Ch ${chapterNum}: ${error.message}`);
            failedChapters.push(chapter);

            // Add to persistent failed list immediately
            const failedList = document.getElementById('failed-chapters-content');
            const failedContainer = document.getElementById('failed-chapters-list');
            if (failedList && failedContainer) {
              failedContainer.style.display = 'block';
              const errorItem = document.createElement('div');
              errorItem.style.marginBottom = '4px';
              errorItem.style.borderBottom = '1px solid rgba(0,0,0,0.1)';
              errorItem.style.paddingBottom = '2px';
              errorItem.textContent = `Ch ${chapterNum}: ${error.message}`;
              failedList.appendChild(errorItem);
            }
          } finally {
            if (chapterTab) chrome.tabs.remove(chapterTab.id).catch(() => { });

            const completed = results.success + results.failed + results.skipped;
            const percent = Math.round((completed / results.total) * 100);
            progressFill.style.width = percent + '%';
            progressFill.textContent = percent + '%';
            progressText.textContent = `Processing... (${completed}/${results.total})`;
            progressSuccess.textContent = `✓ Success: ${results.success}`;
            progressFailed.textContent = `✗ Failed: ${results.failed}`;
            document.getElementById('progress-skipped').textContent = `⭐️ Skipped: ${results.skipped}`;
          }
        };

        // Concurrency Queue Manager
        let currentIndex = 0;
        const startWorker = async () => {
          while (currentIndex < chapters.length && !batchImportCancelled) {
            const index = currentIndex++;
            await processChapter(chapters[index], index);
          }
        };

        const workers = [];
        for (let i = 0; i < maxConcurrentTabs; i++) {
          workers.push(startWorker());
        }
        await Promise.all(workers);

        // Retry failed chapters (up to 2 additional attempts)
        // Retry failed chapters (up to 2 additional attempts)
        let retryAttempt = 0;
        const maxRetries = 2;
        const originalTotal = results.total;  // SAVE ORIGINAL TOTAL

        while (failedChapters.length > 0 && retryAttempt < maxRetries && !batchImportCancelled) {
          retryAttempt++;
          const retryCount = failedChapters.length;

          showStatus(`🔄 Retrying ${retryCount} failed chapters (Attempt ${retryAttempt}/${maxRetries})...`, 'info');

          const chaptersToRetry = [...failedChapters];
          failedChapters.length = 0;

          results.failed = 0;

          currentIndex = 0;
          chapters = chaptersToRetry;

          const retryWorkers = [];
          for (let i = 0; i < maxConcurrentTabs; i++) {
            retryWorkers.push(startWorker());
          }
          await Promise.all(retryWorkers);

          if (failedChapters.length > 0) {
            results.failed = failedChapters.length;
          }
        }

        results.total = originalTotal;  // RESTORE ORIGINAL TOTAL

        // Final re-sort: ensure chapters are in correct position order
        if (!batchImportCancelled && results.novelId) {
          try {
            await fetch(`${serverUrl}/api/resort-chapters`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({ novel_id: results.novelId })
            });
          } catch (e) { console.warn('Resort failed:', e); }
        }

        // Final Status
        let message = batchImportCancelled ? '⏹️ Batch import cancelled\n\n' : '✅ Batch import complete!\n\n';
        message += `Total: ${results.total}\nSuccess: ${results.success}\nSkipped: ${results.skipped}\nFailed: ${results.failed}`;
        showStatus(message, results.failed === 0 ? 'success' : 'warning');

        // Trigger translation if needed
        if ((results.success > 0 || results.skipped > 0) && !batchImportCancelled && results.novelId) {
          try {
            await fetch(`${serverUrl}/api/translate-novel-title-sync`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({ novel_id: results.novelId })
            });
          } catch (e) { }
        }

      } catch (error) {
        showStatus('Fatal Error: ' + error.message, 'error');
      } finally {
        resetBatchImportUI();
      }
    });
  });

  // Cancel batch import
  cancelBatchBtn.addEventListener('click', () => {
    if (confirm('Are you sure you want to cancel?')) {
      batchImportCancelled = true;
      showStatus('Cancelling...', 'warning');
      cancelBatchBtn.disabled = true;
    }
  });

  function resetBatchImportUI() {
    batchImportBtn.disabled = false;
    batchImportBtn.style.display = 'block';
    cancelBatchBtn.style.display = 'none';
    cancelBatchBtn.disabled = false;
    getChapterRangeBtn.disabled = false;
    getChapterRangeBtn.style.display = 'block';
    progressContainer.style.display = 'none';
    document.getElementById('progress-skipped').style.display = 'none';
    chapterRangeInfo.style.display = 'none';
  }

  function showStatus(message, type) {
    statusDiv.innerHTML = '';
    const statusElement = document.createElement('div');
    statusElement.className = `status ${type}`;
    statusElement.textContent = message;
    statusDiv.appendChild(statusElement);
    if (type === 'success') {
      setTimeout(() => {
        if (statusDiv.contains(statusElement)) {
          statusElement.style.opacity = '0';
          setTimeout(() => statusDiv.removeChild(statusElement), 500);
        }
      }, 5000);
    }
  }
});
