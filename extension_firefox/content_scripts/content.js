const ext = (typeof browser !== 'undefined') ? browser : chrome;

// slugify that preserves Hangul
function slugifyKeepHangul(str) {
    if (!str) return 'unknown_novel';
    return str
        .toString()
        .normalize('NFKC')
        .replace(/[^\w\s\uac00-\ud7a3-]/g, ' ')
        .trim()
        .replace(/\s+/g, '_')
        .replace(/_+/g, '_') || 'unknown_novel';
}

// Helper function to detect Korean text
function hasKorean(text) {
    return text && /[\uac00-\ud7a3]/.test(text);
}

function extractNovelTitleFromPageTitle(pageTitle) {
    // Remove Novelpia branding
    let novelTitle = pageTitle.replace(/^Novelpia\s*-\s*/i, '');
    novelTitle = novelTitle.replace(/\s*-?\s*A World of Dreams Through Web Novels!?\s*-?\s*/gi, '');
    novelTitle = novelTitle.replace(/\s*-?\s*노벨피아\s*-?\s*/gi, '');
    novelTitle = novelTitle.replace(/\s*-?\s*웹소설로 꿈꾸는 세상\s*-?\s*/gi, '');
    novelTitle = novelTitle.replace(/\s*-\s*Novelpia\s*$/i, '');

    // Split by " - " to separate parts
    if (novelTitle.includes(' - ')) {
        const parts = novelTitle.split(' - ').map(p => p.trim()).filter(p => p.length > 0);

        // Filter out chapter indicators
        const nonChapterParts = [];
        const koreanParts = [];

        for (const part of parts) {
            // Skip EP indicators
            if (/^EP\.\d+/i.test(part)) continue;
            // Skip BONUS indicators
            if (/^BONUS/i.test(part)) continue;
            // Skip Korean chapter indicators
            if (/^제?\s*\d+\s*화/.test(part)) continue;

            nonChapterParts.push(part);

            // Collect parts with Korean text
            if (hasKorean(part)) {
                koreanParts.push(part);
            }
        }

        // Prefer Korean parts over English
        if (koreanParts.length > 0) {
            novelTitle = koreanParts[koreanParts.length - 1];
        } else if (nonChapterParts.length > 0) {
            novelTitle = nonChapterParts[nonChapterParts.length - 1];
        } else if (parts.length > 0) {
            novelTitle = parts[parts.length - 1];
        }
    }

    return novelTitle || 'Unknown Novel';
}

// Extract novel title - PRIORITIZE KOREAN TEXT
function extractNovelTitle() {
    // Priority 1: Try to extract from specific Korean title element (from novel page)
    const novelTitleEl = document.querySelector('div.ep-info-line.epnew-novel-title');
    if (novelTitleEl) {
        const titleText = novelTitleEl.textContent.trim();
        if (titleText && hasKorean(titleText)) {
            return titleText;
        }
    }

    // Priority 2: Look for novel links with Korean text
    const novelLinks = document.querySelectorAll('a[href*="/novel/"]');
    for (const link of novelLinks) {
        const linkText = link.textContent.trim();
        // Skip navigation/UI links
        if (/목록|list|back|돌아가기/i.test(linkText)) continue;
        // Must have Korean text and reasonable length
        if (linkText && linkText.length > 3 && hasKorean(linkText)) {
            return linkText;
        }
    }

    // Priority 3: Extract from page title, prioritizing Korean parts
    const pageTitle = document.title || '';
    const titleFromPage = extractNovelTitleFromPageTitle(pageTitle);

    // If we got Korean text from page title, use it
    if (hasKorean(titleFromPage)) {
        return titleFromPage;
    }

    // Priority 4: Try to find ANY element with Korean novel title
    // Look in common containers
    const possibleContainers = document.querySelectorAll('.novel-title, .book-title, .story-title, h1, h2');
    for (const container of possibleContainers) {
        const text = container.textContent.trim();
        if (text && text.length > 3 && text.length < 100 && hasKorean(text)) {
            // Make sure it's not a chapter title
            if (!/^(EP\.\d+|BONUS|제?\s*\d+\s*화)/i.test(text)) {
                return text;
            }
        }
    }

    // Fallback: Use what we extracted from page title (even if English)
    return titleFromPage || 'Unknown Novel';
}

function extractChapterNumber() {
    const menuTitleWrapper = document.querySelector('.menu-title-wrapper');
    if (menuTitleWrapper) {
        const epTag = menuTitleWrapper.querySelector('.menu-top-tag');
        if (epTag) {
            const epText = epTag.textContent.trim();

            // Check if it's a BONUS chapter
            if (/BONUS/i.test(epText)) {
                return 'BONUS';
            }

            const match = epText.match(/EP\.?(\d+)/i);
            if (match) {
                return parseInt(match[1], 10);
            }
        }
    }

    const url = window.location.href;
    const urlPatterns = [
        /\/viewer\/(\d+)$/,
        /\/viewer\/\d+\/(\d+)/,
        /\/episode\/(\d+)/,
        /\/chapter[_-]?(\d+)/,
        /\/ep(\d+)/,
        /[?&]episode=(\d+)/,
        /[?&]chapter=(\d+)/,
        /[?&]ep=(\d+)/,
    ];

    for (const pattern of urlPatterns) {
        const match = url.match(pattern);
        if (match) {
            return parseInt(match[1], 10);
        }
    }

    const pageTitle = document.title;

    // Check for BONUS in page title
    if (/BONUS/i.test(pageTitle)) {
        return 'BONUS';
    }

    const titlePatterns = [
        /EP\.?(\d+)/i,
        /(?:chapter|ch\.?|ep\.?|episode)\s*[:#]?\s*(\d+)/i,
        /The\s*(\d+)(?:st|nd|rd|th)/i,
        /제\s*(\d+)\s*화/,
        /(\d+)\s*화/,
        /(\d+)회/,
        /^\s*(\d+)(?:[\.\s]|$)/, // Number at start
    ];

    for (const pattern of titlePatterns) {
        const match = pageTitle.match(pattern);
        if (match) {
            return parseInt(match[1], 10);
        }
    }

    return null;
}

function extractChapterTitle() {
    const menuTitleWrapper = document.querySelector('.menu-title-wrapper');
    if (menuTitleWrapper) {
        const titleDiv = menuTitleWrapper.querySelector('.menu-top-title');
        if (titleDiv) {
            const title = titleDiv.textContent.trim();
            return title;
        }
    }

    const viewerTitleSelectors = [
        '.episode_title',
        '.viewer_title',
        '#episode_title',
        '.episode-title-text'
    ];

    for (const sel of viewerTitleSelectors) {
        const el = document.querySelector(sel);
        if (el) {
            const text = el.textContent.trim();
            if (text && /[\uac00-\ud7a3]/.test(text)) {
                return text;
            }
        }
    }

    const selectors = [
        '.episode-title',
        '.chapter-title',
        '.menu-top-title',
        'h1.title',
        '.title'
    ];

    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
            const text = el.textContent.trim();
            if (text && /[\uac00-\ud7a3]/.test(text)) {
                return text;
            }
        }
    }

    const pageTitle = document.title;
    if (pageTitle) {
        const patterns = [
            /EP\.\d+\s+(.+?)\s+-\s+/i,
            /BONUS\s+(.+?)\s+-\s+/i,
            /\d+화\s+(.+?)\s+-\s+/,
            /제\s*\d+\s*화\s+(.+?)\s+-\s+/
        ];

        for (const pattern of patterns) {
            const match = pageTitle.match(pattern);
            if (match && match[1]) {
                return match[1].trim();
            }
        }
    }

    return null;
}

function extractNovelUrl() {
    // 1. Look for explicit novel links in the UI (breadcrumbs, title links, etc.)
    const selectors = [
        'a[href^="/novel/"]',
        'a[href*="/novel/"]',
        '.novel-title a',
        '.epnew-novel-title a'
    ];

    for (const selector of selectors) {
        const links = document.querySelectorAll(selector);
        for (const link of links) {
            const href = link.getAttribute('href');
            // Ensure it's a novel link, not a chapter viewer or something else
            // Novelpia novel links are usually /novel/12345
            if (href && /\/novel\/\d+/.test(href) && !href.includes('/viewer/')) {
                return link.href; // Returns absolute URL including domain
            }
        }
    }

    // 2. Try to parse from current URL if it contains novel ID
    // Some sites might have /novel/12345/viewer/67890
    const url = window.location.href;
    const match = url.match(/\/novel\/(\d+)/);
    if (match) {
        // Reconstruct the novel URL
        return new URL(`/novel/${match[1]}`, url).href;
    }

    // 3. Fallback to current URL (existing behavior)
    return window.location.href;
}

// Comprehensive content validation
function validateExtractedContent(content, metadata) {
    const errors = [];
    const warnings = [];

    // 1. Check content length
    if (!content || content.length < 200) {
        errors.push('Content too short (less than 200 characters)');
    }

    // 2. Check Korean character density
    const koreanChars = (content.match(/[\uac00-\ud7a3]/g) || []).length;
    if (koreanChars < 500) {
        errors.push(`Insufficient Korean content (${koreanChars} chars, need 500+)`);
    }

    // 3. Check for common error patterns
    const errorPatterns = [
        /구독이 필요합니다/,
        /로그인이 필요합니다/,
        /이용권.*필요/,
        /멤버십.*필요/,
        /코인.*부족/,
        /열람.*제한/,
        /페이지를 찾을 수 없습니다/,
        /오류가 발생했습니다/,
        /접근.*권한/,
        /잘못된.*요청/
    ];

    for (const pattern of errorPatterns) {
        if (pattern.test(content)) {
            errors.push(`Detected error message: ${pattern.source}`);
        }
    }

    // 4. Check metadata completeness
    if (!metadata.chapter_number && metadata.chapter_number !== 0) {
        warnings.push('Chapter number not detected');
    }

    if (!metadata.chapter_title) {
        warnings.push('Chapter title not detected');
    }

    if (!metadata.original_title) {
        warnings.push('Novel title not detected');
    }

    // 5. Check Korean density ratio
    const koreanDensity = koreanChars / content.length;
    if (koreanDensity < 0.3) {
        warnings.push(`Low Korean density (${(koreanDensity * 100).toFixed(1)}%)`);
    }

    return {
        valid: errors.length === 0,
        errors: errors,
        warnings: warnings,
        stats: {
            contentLength: content.length,
            koreanChars: koreanChars,
            koreanDensity: koreanDensity
        }
    };
}


function extractNovelInfo() {
    const pageTitle = document.title || '';
    const chapterTitle = extractChapterTitle();
    const chapterNumber = extractChapterNumber();

    const novelTitle = extractNovelTitleFromPageTitle(pageTitle);
    const novelUrl = extractNovelUrl();

    return {
        title: novelTitle || 'Unknown Title',
        slug: slugifyKeepHangul(novelTitle || 'unknown_novel'),
        source_url: novelUrl,
        chapter_number: chapterNumber,
        chapter_title: chapterTitle
    };
}

function extractNovelContent() {
    const hasKorean = (text) => /[\uac00-\ud7a3]/.test(text);

    // Try specific selectors first (faster)
    const prioritySelectors = [
        '#novel_body',
        '#novel_content',
        '.novel_body',
        '.novel_content',
        '#episode_body'
    ];

    let best = null;
    let bestScore = 0;

    // Try priority selectors first
    for (const selector of prioritySelectors) {
        const el = document.querySelector(selector);
        if (el) {
            const text = (el.innerText || el.textContent || '').trim();
            if (text.length >= 500) {
                const koreanChars = (text.match(/[\uac00-\ud7a3]/g) || []).length;
                if (koreanChars >= 500) {
                    const koreanDensity = koreanChars / text.length;
                    const score = koreanChars * koreanDensity;

                    if (score > 1000) {
                        best = el;
                        bestScore = score;
                        break;
                    }
                }
            }
        }
    }

    // If no good match found, do broader search
    if (!best || bestScore < 1000) {
        const allElements = document.querySelectorAll('div, article, section, main');

        // Limit search to first 100 elements
        const elementsToCheck = Array.from(allElements).slice(0, 100);

        for (const el of elementsToCheck) {
            try {
                const text = (el.innerText || el.textContent || '').trim();

                if (text.length < 500) continue;

                const koreanChars = (text.match(/[\uac00-\ud7a3]/g) || []).length;
                if (koreanChars < 500) continue;

                const koreanDensity = koreanChars / text.length;
                const score = koreanChars * koreanDensity;

                // Skip navigation/UI elements early
                const className = el.className || '';
                const id = el.id || '';
                const combined = (className + ' ' + id).toLowerCase();

                if (/nav|menu|header|footer|sidebar|comment|button|modal|popup|alert|notice|coupon|membership|banner|ad/i.test(combined)) {
                    continue;
                }

                if (score > bestScore) {
                    bestScore = score;
                    best = el;
                }
            } catch (e) {
                continue;
            }
        }
    }

    if (!best) {
        return {
            error: 'Could not find content on page. Make sure you are on a chapter page and the content has loaded.'
        };
    }

    // Extract images (only first cover)
    const images = [];
    const imgElements = best.querySelectorAll('img');
    for (const img of imgElements) {
        const src = img.src || img.getAttribute('data-src') || img.getAttribute('data-original');
        if (src && src.includes('images.novelpia.com/imagebox/cover/')) {
            images.push({
                url: src,
                alt: img.alt || 'Chapter Image'
            });
            break;
        }
    }

    let content = (best.innerText || best.textContent || '').trim();

    // Clean content
    content = content
        .replace(/^커버접기\s*/g, '')
        .replace(/\d+일 무료 쿠폰이 적용되었습니다\..*?예고없이 종료될 수 있습니다\./gs, '')
        .replace(/회원님께서는.*?이용하실 수 있습니다\./g, '')
        .replace(/다양한 컨텐츠를 즐겨보세요!/g, '')
        .replace(/※\s*일부 작품 및 회차는 열람에 제한될 수 있습니다\./g, '')
        .replace(/※\s*모든 회차를 자유롭게 열람하시기 위해서는 플러스 멤버십 구독이 필요합니다\./g, '')
        .replace(/※\s*이용권 기간 중 결제 시 이용권의 남은기간은 소멸됩니다\./g, '')
        .replace(/※\s*해당 혜택은 본사 사정에 의해 예고없이 종료될 수 있습니다\./g, '')
        .replace(/[A-Za-z0-9+/]{40,}={0,2}/g, '')
        .replace(/data:image\/[^;]+;base64,[A-Za-z0-9+/=]+/gi, '')
        .replace(/\n{3,}/g, '\n\n')
        .replace(/  +/g, ' ')
        .trim();

    if (content.length < 200) {
        return {
            error: 'Could not find chapter content - only found promotional messages or UI elements'
        };
    }

    // Extract metadata
    const chapterTitle = extractChapterTitle();
    const chapterNumber = extractChapterNumber();
    const novelTitle = extractNovelTitle();

    let cover_url = '';
    let author = '';
    let tags = [];
    let synopsis = '';

    const coverImg = document.querySelector('img.cover_img.s_inv');
    if (coverImg) {
        cover_url = coverImg.src || coverImg.getAttribute('data-src') || '';
        if (cover_url.startsWith('//')) {
            cover_url = 'https:' + cover_url;
        }
    }

    const authorEl = document.querySelector('.writer-tag, .author-name');
    if (authorEl) {
        const authorText = authorEl.textContent.trim();
        const match = authorText.match(/작가명\[([^\]]+)\]/);
        author = match ? match[1].trim() : authorText;
    }

    const tagEls = document.querySelectorAll('.ep-info-line .tag');
    for (const el of tagEls) {
        const tag = el.textContent.trim().replace(/^#/, '');
        if (tag && tag !== '+나만의태그 추가' && tag !== '나만의태그 추가') {
            tags.push(tag);
        }
    }

    const synopsisEl = document.querySelector('.synopsis');
    if (synopsisEl) {
        synopsis = synopsisEl.textContent.trim();
    }

    const novelUrl = extractNovelUrl();

    const result = {
        title: chapterTitle || document.title,
        original_title: novelTitle,
        content,
        url: window.location.href,
        selector: best ? `${best.tagName}.${best.className}#${best.id}` : null,
        images: images,
        chapter_number: chapterNumber,
        chapter_title: chapterTitle,
        cover_url: cover_url,
        author: author,
        tags: tags,
        synopsis: synopsis,
        novel_source_url: novelUrl
    };

    // Validate extracted content before returning
    const validation = validateExtractedContent(content, {
        chapter_number: chapterNumber,
        chapter_title: chapterTitle,
        original_title: novelTitle
    });

    // If validation fails, return error with details
    if (!validation.valid) {
        return {
            error: 'Content validation failed',
            validation_errors: validation.errors,
            validation_warnings: validation.warnings,
            validation_stats: validation.stats
        };
    }

    // If validation passes but has warnings, add them to result
    if (validation.warnings.length > 0) {
        result.validation_warnings = validation.warnings;
    }

    // Add validation stats for debugging
    result.validation_stats = validation.stats;

    return result;
}


function tryMeta(selector) {
    try {
        const el = document.querySelector(selector);
        return el ? el.getAttribute('content') : null;
    } catch (e) {
        return null;
    }
}

// ========== BATCH IMPORT FUNCTIONS ==========

function getChapterRange() {
    const url = window.location.href;

    const novelIdMatch = url.match(/\/novel\/(\d+)/);
    if (!novelIdMatch) {
        return { success: false, error: 'Could not determine novel ID from URL.' };
    }
    const novelId = novelIdMatch[1];

    // Get episode rows visible on CURRENT page only
    const episodeRows = document.querySelectorAll('tr[data-episode-no]');

    if (episodeRows.length === 0) {
        return { success: false, error: 'No chapters found on current page. Try loading more chapters.' };
    }

    const chapterNumbers = [];
    episodeRows.forEach(row => {
        const episodeNo = row.getAttribute('data-episode-no');
        if (episodeNo) {
            let epNumber = null;
            let isBonus = false;

            const spans = row.querySelectorAll('span');
            for (const span of spans) {
                const spanText = span.textContent.trim();

                // Robust extraction logic
                // spanText is already declared above

                // Check for BONUS first
                if (/BONUS/i.test(spanText)) {
                    isBonus = true;
                    epNumber = 'BONUS';
                    break;
                }

                // Extract EP number
                let epMatch = spanText.match(/EP\.?(\d+)/i);
                if (!epMatch) {
                    epMatch = spanText.match(/The\s*(\d+)(?:st|nd|rd|th)/i);
                }
                if (!epMatch) {
                    epMatch = spanText.match(/(?:Episode|Chapter|Ch)\.?\s*(\d+)/i);
                }
                if (!epMatch) {
                    // Fallback: look for just a number at the start of the string if it's followed by a dot or space
                    epMatch = spanText.match(/^\s*(\d+)(?:[\.\s]|$)/);
                }

                if (epMatch) {
                    epNumber = parseInt(epMatch[1]);
                    break;
                }
            }

            if (epNumber) {
                chapterNumbers.push({ epNumber, isBonus, episodeNo });
            }
        }
    });

    if (chapterNumbers.length === 0) {
        return { success: false, error: 'Could not extract EP numbers from current page. Please check if chapter titles follow supported formats (EP.1, The 1st, Chapter 1, etc.).' };
    }

    chapterNumbers.sort((a, b) => {
        if (a.isBonus) return 1;
        if (b.isBonus) return -1;
        return a.epNumber - b.epNumber;
    });

    const minEp = chapterNumbers[0].epNumber;
    const maxEp = chapterNumbers[chapterNumbers.length - 1].epNumber;

    // Determine pagination info
    let totalPages = 1;
    let currentPage = 1;

    const paginationItems = document.querySelectorAll('.pagination .page-item');
    paginationItems.forEach(item => {
        const pageLink = item.querySelector('.page-link');
        if (pageLink) {
            const text = pageLink.textContent.trim();

            // Check if active
            if (item.classList.contains('active')) {
                const pageNum = parseInt(text);
                if (!isNaN(pageNum)) {
                    currentPage = pageNum;
                }
            }

            // Check onclick to find max page
            const onclick = pageLink.getAttribute('onclick');
            if (onclick) {
                const pageMatch = onclick.match(/localStorage\['novel_page_\d+'\]\s*=\s*'(\d+)'/);
                if (pageMatch) {
                    const pageIdx = parseInt(pageMatch[1]);
                    totalPages = Math.max(totalPages, pageIdx + 1);
                }
            }

            // Fallback: Check text content for max page
            if (/^\d+$/.test(text)) {
                const p = parseInt(text);
                if (!isNaN(p)) {
                    totalPages = Math.max(totalPages, p);
                }
            }
        }
    });

    const chaptersPerPage = chapterNumbers.length;

    return {
        success: true,
        novelId: novelId,
        minEp: typeof minEp === 'number' ? minEp : 0,
        maxEp: typeof maxEp === 'number' ? maxEp : 0,
        visibleMin: typeof minEp === 'number' ? minEp : 0,
        visibleMax: typeof maxEp === 'number' ? maxEp : 0,
        currentPage: currentPage,
        totalPages: totalPages,
        chaptersPerPage: chaptersPerPage,
        totalVisible: chapterNumbers.length,
        estimatedTotalChapters: totalPages * chaptersPerPage
    };
}

async function getAllChapterIds(novelId, totalPages) {
    const allChapters = [];
    const seenEpisodeNos = new Set();
    const currentPageKey = `novel_page_${novelId}`;
    const originalPage = localStorage.getItem(currentPageKey) || '0';

    let globalPosition = 0;

    try {
        for (let pageIndex = 0; pageIndex < totalPages; pageIndex++) {
            // Set the page in localStorage
            localStorage.setItem(currentPageKey, pageIndex.toString());

            // Find and click the page button
            // Robust finding: Try onclick first, then text content
            let pageButton = document.querySelector(`.pagination .page-link[onclick*="'${pageIndex}'"]`);

            if (!pageButton) {
                // Fallback: find by text content (pageIndex + 1)
                const targetPageNum = pageIndex + 1;
                const links = document.querySelectorAll('.pagination .page-link');
                for (const link of links) {
                    if (link.textContent.trim() === String(targetPageNum)) {
                        pageButton = link;
                        break;
                    }
                }
            }

            if (pageButton) {
                pageButton.click();

                // Wait for page to actually change
                let pageLoaded = false;
                let attempts = 0;
                const maxAttempts = 15;

                // Get current episode numbers before clicking
                const oldEpisodeNos = new Set();
                document.querySelectorAll('tr[data-episode-no]').forEach(row => {
                    oldEpisodeNos.add(row.getAttribute('data-episode-no'));
                });

                while (!pageLoaded && attempts < maxAttempts) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                    attempts++;

                    // Check if content has changed
                    const currentEpisodeRows = document.querySelectorAll('tr[data-episode-no]');

                    if (currentEpisodeRows.length === 0) {
                        continue;
                    }

                    // Check if we have new episode numbers
                    const newEpisodeNos = new Set();
                    currentEpisodeRows.forEach(row => {
                        newEpisodeNos.add(row.getAttribute('data-episode-no'));
                    });

                    // If we're on page 0, just check if we have content
                    if (pageIndex === 0) {
                        if (currentEpisodeRows.length > 0) {
                            pageLoaded = true;
                            break;
                        }
                    } else {
                        // For other pages, check if content has changed
                        let hasNewContent = false;
                        for (const episodeNo of newEpisodeNos) {
                            if (!oldEpisodeNos.has(episodeNo)) {
                                hasNewContent = true;
                                break;
                            }
                        }

                        if (hasNewContent && currentEpisodeRows.length > 0) {
                            pageLoaded = true;
                            break;
                        }
                    }
                }

                // Additional small wait to ensure DOM is stable
                await new Promise(resolve => setTimeout(resolve, 300));
            } else {
                // If we can't find the button, we might be on a single-page novel
                if (pageIndex > 0) {
                    console.warn(`Could not find button for page ${pageIndex + 1}`);
                }
            }

            // Extract episodes from the current page
            const episodeRows = document.querySelectorAll('tr[data-episode-no]');

            if (episodeRows.length === 0) {
                continue;
            }

            // Process rows in DOM order
            episodeRows.forEach((row, rowIndex) => {
                const episodeNo = row.getAttribute('data-episode-no');

                if (episodeNo && !seenEpisodeNos.has(episodeNo)) {
                    let isBonus = false;
                    let chapterNumber = null;

                    // Extract chapter info
                    const rowText = row.textContent;

                    // Check for BONUS first
                    if (/BONUS/i.test(rowText)) {
                        isBonus = true;
                        chapterNumber = 'BONUS';
                    } else {
                        // Extract EP number
                        let epMatch = rowText.match(/EP\.?(\d+)/i);
                        if (!epMatch) {
                            epMatch = rowText.match(/The\s*(\d+)(?:st|nd|rd|th)/i);
                        }
                        if (!epMatch) {
                            epMatch = rowText.match(/(?:Episode|Chapter|Ch)\.?\s*(\d+)/i);
                        }
                        if (!epMatch) {
                            // Fallback: look for just a number at the start of the string if it's followed by a dot or space
                            epMatch = rowText.match(/^\s*(\d+)(?:[\.\s]|$)/);
                        }

                        if (epMatch) {
                            chapterNumber = parseInt(epMatch[1]);
                        } else {
                            console.warn('Could not extract chapter number from row:', rowText);
                        }
                    }

                    if (chapterNumber !== null) {
                        allChapters.push({
                            episodeNo: parseInt(episodeNo),
                            chapterNumber: chapterNumber,
                            isBonus: isBonus,
                            position: globalPosition,
                            pageIndex: pageIndex,
                            rowIndex: rowIndex
                        });

                        seenEpisodeNos.add(episodeNo);
                        globalPosition++;
                    }
                }
            });
        }


        // Restore original page
        localStorage.setItem(currentPageKey, originalPage);

        // Try to find original button with robust logic too
        let originalButton = document.querySelector(`.pagination .page-link[onclick*="'${originalPage}'"]`);
        if (!originalButton) {
            const targetPageNum = parseInt(originalPage) + 1;
            const links = document.querySelectorAll('.pagination .page-link');
            for (const link of links) {
                if (link.textContent.trim() === String(targetPageNum)) {
                    originalButton = link;
                    break;
                }
            }
        }

        if (originalButton) {
            originalButton.click();
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        return {
            success: true,
            chapters: allChapters,
            chapterIds: allChapters.map(ch => ch.chapterNumber),
            totalChapters: allChapters.length
        };

    } catch (error) {
        // Restore on error
        localStorage.setItem(currentPageKey, originalPage);
        return { success: false, error: error.message };
    }
}

// ========== MESSAGE LISTENER ==========

ext.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (!msg || !msg.action) {
        sendResponse({ success: false, error: 'no action specified' });
        return;
    }

    if (msg.action === 'extractChapter' || msg.action === 'extractContent') {
        try {
            const data = extractNovelContent();
            sendResponse(data);
        } catch (err) {
            sendResponse({ error: err.message });
        }
        return true;
    }

    if (msg.action === 'extractNovelMetadata') {
        try {
            let title = '';
            let author = '';
            let tags = [];
            let synopsis = '';
            let cover_url = '';

            // Try to find novel title from page
            const titleEl = document.querySelector('div.ep-info-line.epnew-novel-title');
            if (titleEl) {
                title = titleEl.textContent.trim();
            }

            if (!title || title === 'Unknown Novel') {
                title = extractNovelTitleFromPageTitle(document.title) || 'Unknown Novel';
            }

            // Author
            let authorEl = document.querySelector('a.writer-name');
            if (authorEl) {
                author = authorEl.textContent.trim();
            }

            // Tags
            const tagEls = document.querySelectorAll('.writer-tag .tag');
            tagEls.forEach(el => {
                const tag = el.textContent.trim().replace(/^#/, '');
                if (tag && tag !== '+나만의태그 추가' && tag !== '나만의태그 추가') {
                    tags.push(tag);
                }
            });

            // Synopsis
            const synopsisEl = document.querySelector('.synopsis');
            if (synopsisEl) {
                synopsis = synopsisEl.textContent.trim();
            }

            // Cover image - IMPROVED SELECTORS
            const coverSelectors = [
                'img.cover_img.s_inv',
                'img.cover_img',
                '.cover img',
                '.ep-cover img',
                '.novel-cover img',
                '.book-cover img',
                'img[src*="cover"]',
                'img[alt*="표지"]',
                'meta[property="og:image"]',
                'link[rel="image_src"]'
            ];

            for (const selector of coverSelectors) {
                const el = document.querySelector(selector);
                if (el) {
                    if (selector.startsWith('meta')) {
                        cover_url = el.getAttribute('content') || '';
                    } else if (selector.startsWith('link')) {
                        cover_url = el.getAttribute('href') || '';
                    } else {
                        cover_url = el.src || el.getAttribute('data-src') || el.getAttribute('data-lazy-src') || '';
                    }

                    if (cover_url) {
                        if (cover_url.startsWith('//')) {
                            cover_url = 'https:' + cover_url;
                        }
                        // Filter out generic placeholder images if possible
                        if (!cover_url.includes('no_cover') && !cover_url.includes('blank')) {
                            break; // Found a good candidate
                        }
                    }
                }
            }

            const responseData = {
                success: true,
                original_title: title,
                title: title,
                author: author,
                tags: tags,
                synopsis: synopsis,
                cover_url: cover_url,
                novel_source_url: window.location.href
            };

            console.log('Extracted Metadata:', responseData);

            sendResponse(responseData);
        } catch (err) {
            console.error('Metadata extraction error:', err);
            sendResponse({
                error: err.message,
                stack: err.stack
            });
        }
        return true;
    }

    if (msg.action === 'checkContentLoaded') {
        try {
            const bodyText = document.body.textContent || '';
            const koreanChars = (bodyText.match(/[\uac00-\ud7a3]/g) || []).length;

            if (koreanChars > 300) {
                sendResponse({ success: true, loaded: true, error: false });
                return true;
            }

            const contentSelectors = [
                '#novel_body',
                '#novel_content',
                '.novel_body',
                '.novel_content',
                '#episode_body',
                '.viewer-content',
                '[class*="content"]',
                '[id*="content"]'
            ];

            for (const selector of contentSelectors) {
                const container = document.querySelector(selector);
                if (container) {
                    const containerText = (container.textContent || '').trim();
                    const containerKorean = (containerText.match(/[\uac00-\ud7a3]/g) || []).length;

                    if (containerKorean > 100) {
                        sendResponse({ success: true, loaded: true, error: false });
                        return true;
                    }
                }
            }

            sendResponse({ success: true, loaded: false, error: false });

        } catch (err) {
            sendResponse({ success: false, loaded: false, error: false });
        }
        return true;
    }

    if (msg.action === 'getChapterRange') {
        try {
            const result = getChapterRange();
            sendResponse(result);
        } catch (err) {
            sendResponse({ success: false, error: err.message });
        }
        return true;
    }

    if (msg.action === 'getAllChapterIds') {
        (async () => {
            try {
                const result = await getAllChapterIds(msg.novelId, msg.totalPages);
                sendResponse(result);
            } catch (err) {
                sendResponse({ success: false, error: err.message });
            }
        })();
        return true;
    }

    sendResponse({ success: false, error: 'unknown action' });
    return true;
});
