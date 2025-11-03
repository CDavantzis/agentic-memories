-- Down: Drop emotional_patterns table

DROP INDEX IF EXISTS idx_emotional_patterns_confidence;
DROP INDEX IF EXISTS idx_emotional_patterns_time_range;
DROP INDEX IF EXISTS idx_emotional_patterns_emotion;
DROP INDEX IF EXISTS idx_emotional_patterns_type;
DROP INDEX IF EXISTS idx_emotional_patterns_user_id;

DROP TABLE IF EXISTS emotional_patterns CASCADE;

