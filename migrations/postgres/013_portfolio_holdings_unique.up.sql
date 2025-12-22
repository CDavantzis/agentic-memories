-- PostgreSQL Migration: portfolio_holdings_unique
-- Description: Add unique constraints on portfolio_holdings to prevent duplicate entries
-- Fixes: Duplicate holdings created by race conditions in check-then-act pattern

-- First, clean up any existing duplicates before adding constraint
-- Keep only ONE record per (user_id, ticker) - the one with latest last_updated,
-- and if tied, the one with the largest id (UUID comparison as tiebreaker)
DELETE FROM portfolio_holdings
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY user_id, ticker
                   ORDER BY last_updated DESC, id DESC
               ) AS rn
        FROM portfolio_holdings
        WHERE ticker IS NOT NULL
    ) ranked
    WHERE rn > 1
);

-- Keep only ONE record per (user_id, asset_name) for non-ticker assets
-- Same logic: latest last_updated wins, id as tiebreaker
DELETE FROM portfolio_holdings
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY user_id, asset_name
                   ORDER BY last_updated DESC, id DESC
               ) AS rn
        FROM portfolio_holdings
        WHERE ticker IS NULL AND asset_name IS NOT NULL
    ) ranked
    WHERE rn > 1
);

-- Add unique constraint for ticker-based holdings
-- Partial index: only applies when ticker is NOT NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_user_ticker_unique
    ON portfolio_holdings (user_id, ticker)
    WHERE ticker IS NOT NULL;

-- Add unique constraint for asset_name-based holdings (private equity, etc.)
-- Partial index: only applies when asset_name is NOT NULL and ticker IS NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_user_asset_name_unique
    ON portfolio_holdings (user_id, asset_name)
    WHERE asset_name IS NOT NULL AND ticker IS NULL;

-- Add comments for documentation
COMMENT ON INDEX idx_holdings_user_ticker_unique IS 'Prevents duplicate holdings for same user+ticker';
COMMENT ON INDEX idx_holdings_user_asset_name_unique IS 'Prevents duplicate holdings for same user+asset_name (non-ticker assets)';
