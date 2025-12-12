-- Rollback PostgreSQL Migration: portfolio_holdings_unique
-- Description: Remove unique constraints from portfolio_holdings

-- Drop the unique indexes
DROP INDEX IF EXISTS idx_holdings_user_ticker_unique;
DROP INDEX IF EXISTS idx_holdings_user_asset_name_unique;
