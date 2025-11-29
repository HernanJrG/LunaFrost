/**
 * Reading Preferences Manager
 * Handles loading, saving, and applying user reading preferences
 * for the Enhanced Reading Modes feature.
 */

const ReadingPreferences = {
    // Default preference values
    defaults: {
        colorMode: 'light',
        fontSize: 16,
        lineHeight: '1.8',
        fontFamily: 'var(--font-serif)',
        readingWidth: '720px',
        textAlignment: 'left'
    },

    // Current preferences (loaded from API or defaults)
    current: null,

    /**
     * Initialize the reading preferences system
     */
    async init() {
        console.log('[ReadingPrefs] Initializing...');

        // Load preferences from API
        await this.load();

        // Apply preferences to the page
        this.apply(this.current);

        console.log('[ReadingPrefs] Initialized with:', this.current);
    },

    /**
     * Load preferences from API (with localStorage fallback)
     */
    async load() {
        try {
            // Try to load from API
            const response = await fetch('/api/reading-preferences');
            const data = await response.json();

            if (data.success && data.preferences) {
                this.current = data.preferences;
                // Cache in localStorage for faster subsequent loads
                this.saveToLocalStorage(this.current);
                return this.current;
            }
        } catch (error) {
            console.warn('[ReadingPrefs] Failed to load from API, using localStorage or defaults:', error);
        }

        // Fallback to localStorage
        const cached = this.loadFromLocalStorage();
        if (cached) {
            this.current = cached;
            return this.current;
        }

        // Final fallback to defaults
        this.current = { ...this.defaults };
        return this.current;
    },

    /**
     * Save preferences to API and localStorage
     */
    async save(prefs) {
        this.current = { ...this.current, ...prefs };

        // Save to localStorage immediately
        this.saveToLocalStorage(this.current);

        // Save to API in background
        try {
            const response = await fetch('/api/reading-preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.current)
            });

            const data = await response.json();
            if (!data.success) {
                console.error('[ReadingPrefs] Failed to save to API:', data.error);
            }
        } catch (error) {
            console.error('[ReadingPrefs] Error saving to API:', error);
        }
    },

    /**
     * Apply preferences to the page
     */
    apply(prefs) {
        if (!prefs) prefs = this.current || this.defaults;

        console.log('[ReadingPrefs] Applying preferences:', prefs);

        // Apply color mode
        this.applyColorMode(prefs.colorMode);

        // Apply text styles to all text-content elements
        const textElements = document.querySelectorAll('.text-content, .panel-content');
        textElements.forEach(element => {
            element.style.fontSize = `${prefs.fontSize}px`;
            element.style.lineHeight = prefs.lineHeight;
            element.style.fontFamily = prefs.fontFamily;
            element.style.maxWidth = prefs.readingWidth;
            element.style.textAlign = prefs.textAlignment;
        });
    },

    /**
     * Apply color mode to the page
     */
    applyColorMode(mode) {
        // Remove all mode classes
        document.documentElement.classList.remove('dark-mode', 'sepia-mode', 'high-contrast-mode');
        document.body.classList.remove('dark-mode', 'sepia-mode', 'high-contrast-mode');

        // Add the selected mode class
        if (mode === 'dark') {
            document.documentElement.classList.add('dark-mode');
            document.body.classList.add('dark-mode');
        } else if (mode === 'sepia') {
            document.documentElement.classList.add('sepia-mode');
            document.body.classList.add('sepia-mode');
        } else if (mode === 'high-contrast') {
            document.documentElement.classList.add('high-contrast-mode');
            document.body.classList.add('high-contrast-mode');
        }
        // 'light' mode requires no class (default styles)
    },

    /**
     * Save to localStorage
     */
    saveToLocalStorage(prefs) {
        try {
            localStorage.setItem('lf_reading_prefs', JSON.stringify(prefs));
        } catch (e) {
            console.warn('[ReadingPrefs] Failed to save to localStorage:', e);
        }
    },

    /**
     * Load from localStorage
     */
    loadFromLocalStorage() {
        try {
            const saved = localStorage.getItem('lf_reading_prefs');
            if (saved) {
                return { ...this.defaults, ...JSON.parse(saved) };
            }
        } catch (e) {
            console.warn('[ReadingPrefs] Failed to load from localStorage:', e);
        }
        return null;
    },

    /**
     * Reset to defaults
     */
    async reset() {
        this.current = { ...this.defaults };
        await this.save(this.current);
        this.apply(this.current);
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        ReadingPreferences.init();
    });
} else {
    ReadingPreferences.init();
}

// Export for use in other scripts
window.ReadingPreferences = ReadingPreferences;
