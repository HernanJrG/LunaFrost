/**
 * Retry Utility for LunaFrost Extension
 * Implements exponential backoff for robust operations
 */

/**
 * Wait for a specified duration
 * @param {number} ms - Duration in milliseconds
 * @returns {Promise<void>}
 */
const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Retry configuration options
 * @typedef {Object} RetryOptions
 * @property {number} maxAttempts - Maximum number of attempts (default: 3)
 * @property {number} baseDelay - Base delay in ms for exponential backoff (default: 1000)
 * @property {number} maxDelay - Maximum delay in ms (default: 10000)
 * @property {function} shouldRetry - Optional callback to determine if error is retriable
 * @property {function} onRetry - Optional callback called on each retry attempt
 */

/**
 * Execute a function with exponential backoff retry logic
 * @param {function} fn - Async function to execute
 * @param {RetryOptions} options - Retry configuration
 * @returns {Promise<any>} - Result of the function
 */
async function withRetry(fn, options = {}) {
    const maxAttempts = options.maxAttempts || 3;
    const baseDelay = options.baseDelay || 1000;
    const maxDelay = options.maxDelay || 10000;

    let lastError;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            return await fn();
        } catch (error) {
            lastError = error;

            // Check if we should stop retrying based on error type
            if (options.shouldRetry && !options.shouldRetry(error)) {
                throw error;
            }

            // If this was the last attempt, throw the error
            if (attempt === maxAttempts) {
                throw error;
            }

            // Calculate delay with exponential backoff and jitter
            // delay = baseDelay * 2^(attempt-1) + random_jitter
            const exponentialDelay = baseDelay * Math.pow(2, attempt - 1);
            const cappedDelay = Math.min(exponentialDelay, maxDelay);
            const jitter = Math.random() * 0.1 * cappedDelay; // 10% jitter
            const actualDelay = cappedDelay + jitter;

            // Notify retry callback
            if (options.onRetry) {
                options.onRetry(attempt, maxAttempts, error, actualDelay);
            }

            console.log(`Attempt ${attempt} failed. Retrying in ${Math.round(actualDelay)}ms...`, error);
            await wait(actualDelay);
        }
    }

    throw lastError;
}

/**
 * Check if an error indicates a temporary failure that should be retried
 * @param {Error} error - The error to check
 * @returns {boolean} - True if retriable
 */
function isRetriableError(error) {
    const message = error.message || '';

    // Network errors are usually retriable
    if (message.includes('NetworkError') ||
        message.includes('fetch') ||
        message.includes('timeout') ||
        message.includes('aborted')) {
        return true;
    }

    // Content validation errors might be retriable (page loading)
    if (message.includes('Content validation failed') ||
        message.includes('Could not find content')) {
        return true;
    }

    // Server errors (5xx) are retriable
    if (message.includes('500') ||
        message.includes('502') ||
        message.includes('503') ||
        message.includes('504')) {
        return true;
    }

    return false;
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { wait, withRetry, isRetriableError };
} else {
    // For browser extension context
    window.RetryUtils = { wait, withRetry, isRetriableError };
}
