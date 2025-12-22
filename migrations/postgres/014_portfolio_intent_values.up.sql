-- Migration: Update intent CHECK constraint for clearer ownership semantics
-- Old values: buy, sell, hold, watch
-- New values: hold, wants-to-buy, wants-to-sell, watch
--
-- Semantic meanings:
--   hold = user OWNS the asset (completed purchase or stated ownership)
--   wants-to-buy = user WANTS to acquire (future intent, not owned yet)
--   wants-to-sell = user WANTS to dispose (planning to sell)
--   watch = user is MONITORING only (no ownership, no immediate intent)

-- Step 1: Drop the old CHECK constraint FIRST (so we can update to new values)
ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS chk_intent;

-- Step 2: Migrate existing 'buy' entries to 'wants-to-buy' (if no shares, it was speculative)
-- and to 'hold' (if has shares, it was a completed purchase)
UPDATE portfolio_holdings
SET intent = CASE
    WHEN intent = 'buy' AND shares IS NOT NULL AND shares > 0 THEN 'hold'
    WHEN intent = 'buy' THEN 'wants-to-buy'
    WHEN intent = 'sell' THEN 'wants-to-sell'
    ELSE intent
END
WHERE intent IN ('buy', 'sell');

-- Step 3: Add new CHECK constraint with updated values
ALTER TABLE portfolio_holdings ADD CONSTRAINT chk_intent
    CHECK (intent IS NULL OR intent IN ('hold', 'wants-to-buy', 'wants-to-sell', 'watch'));

-- Step 4: Update the index for watchlist/speculative entries (used for filtering)
DROP INDEX IF EXISTS idx_holdings_user_intent;
CREATE INDEX idx_holdings_user_intent ON portfolio_holdings (user_id, intent)
    WHERE intent IN ('wants-to-buy', 'wants-to-sell', 'watch');
