-- Emotional Patterns (PostgreSQL)
-- Stores learned emotional patterns detected over time
-- Not a time-series table, so stored in regular PostgreSQL

CREATE TABLE IF NOT EXISTS emotional_patterns (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    pattern_type VARCHAR(32) NOT NULL,  -- "daily", "weekly", "seasonal", "triggered"
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    dominant_emotion VARCHAR(64) NOT NULL,
    average_valence FLOAT NOT NULL,
    average_arousal FLOAT NOT NULL,
    frequency INT NOT NULL DEFAULT 1,  -- How many times this pattern occurred
    confidence FLOAT NOT NULL DEFAULT 0.0,  -- 0.0 to 1.0
    triggers TEXT[],  -- List of trigger events
    metadata JSONB
);

-- Add constraints
ALTER TABLE emotional_patterns
  ADD CONSTRAINT chk_pattern_valence_range 
    CHECK (average_valence BETWEEN -1.0 AND 1.0),
  ADD CONSTRAINT chk_pattern_arousal_range 
    CHECK (average_arousal BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_pattern_confidence_range 
    CHECK (confidence BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_pattern_frequency_positive 
    CHECK (frequency > 0);

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_emotional_patterns_user_id 
  ON emotional_patterns (user_id);

CREATE INDEX IF NOT EXISTS idx_emotional_patterns_type 
  ON emotional_patterns (pattern_type);

CREATE INDEX IF NOT EXISTS idx_emotional_patterns_emotion 
  ON emotional_patterns (dominant_emotion);

CREATE INDEX IF NOT EXISTS idx_emotional_patterns_time_range 
  ON emotional_patterns (user_id, start_time DESC, end_time DESC);

CREATE INDEX IF NOT EXISTS idx_emotional_patterns_confidence 
  ON emotional_patterns (user_id, confidence DESC, frequency DESC);

