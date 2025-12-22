-- Rollback: Revert intent values to original schema
-- New values: hold, wants-to-buy, wants-to-sell, watch
-- Old values: buy, sell, hold, watch

-- Step 1: Migrate back to old values
UPDATE portfolio_holdings
SET intent = CASE
    WHEN intent = 'wants-to-buy' THEN 'buy'
    WHEN intent = 'wants-to-sell' THEN 'sell'
    ELSE intent
END
WHERE intent IN ('wants-to-buy', 'wants-to-sell');

-- Step 2: Drop the new CHECK constraint
ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS chk_intent;

-- Step 3: Add old CHECK constraint
ALTER TABLE portfolio_holdings ADD CONSTRAINT chk_intent
    CHECK (intent IS NULL OR intent IN ('buy', 'sell', 'hold', 'watch'));

-- Step 4: Restore original index
DROP INDEX IF EXISTS idx_holdings_user_intent;
CREATE INDEX idx_holdings_user_intent ON portfolio_holdings (user_id, intent)
    WHERE intent IN ('buy', 'watch');
