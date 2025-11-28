-- Migration: Add translation_token_usage table
-- Date: 2024
-- Description: Creates table to track token usage for translations

-- Create the translation_token_usage table
CREATE TABLE IF NOT EXISTS translation_token_usage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    chapter_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    translation_type VARCHAR(20) DEFAULT 'content',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT fk_translation_token_usage_chapter 
        FOREIGN KEY (chapter_id) 
        REFERENCES chapters(id) 
        ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_token_usage_user_date 
    ON translation_token_usage(user_id, created_at);
    
CREATE INDEX IF NOT EXISTS idx_token_usage_chapter 
    ON translation_token_usage(chapter_id);
    
CREATE INDEX IF NOT EXISTS idx_token_usage_user_id 
    ON translation_token_usage(user_id);

-- Add comment to table
COMMENT ON TABLE translation_token_usage IS 'Tracks token usage for each translation operation';
COMMENT ON COLUMN translation_token_usage.translation_type IS 'Type of translation: content, title, or both';

