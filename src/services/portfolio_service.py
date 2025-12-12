"""
Portfolio Service

Manages structured portfolio holdings, transactions, and preferences
with time-series snapshots and graph relationships.
"""

from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass

from psycopg import Connection

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.dependencies.neo4j_client import get_neo4j_driver

logger = logging.getLogger(__name__)

# Valid enum values - must match database CHECK constraints
# Intent semantics:
#   hold = user OWNS this asset (completed purchase or stated ownership)
#   wants-to-buy = user WANTS to acquire (future intent, not owned yet)
#   wants-to-sell = user WANTS to dispose (planning to sell)
#   watch = user is MONITORING (no ownership, no immediate intent)
VALID_INTENTS: Set[str] = {'hold', 'wants-to-buy', 'wants-to-sell', 'watch'}
# Intents that indicate speculative/future interest, NOT actual ownership
# These should be filtered out from portfolio_holdings storage
SPECULATIVE_INTENTS: Set[str] = {'wants-to-buy', 'wants-to-sell', 'watch'}
VALID_POSITIONS: Set[str] = {'long', 'short'}
VALID_ASSET_TYPES: Set[str] = {'public_equity', 'private_equity', 'etf', 'mutual_fund', 'cash', 'bond', 'crypto', 'other'}
VALID_TIME_HORIZONS: Set[str] = {'days', 'weeks', 'months', 'years'}

# Ticker validation: 1-10 uppercase alphanumeric + dots (for BRK.B style)
TICKER_PATTERN = re.compile(r'^[A-Z0-9\.]{1,10}$')


def normalize_ticker(ticker: Optional[str]) -> Optional[str]:
    """Normalize ticker to uppercase and validate format."""
    if not ticker:
        return None

    normalized = ticker.upper().strip()

    if not normalized:
        return None

    if not TICKER_PATTERN.match(normalized):
        logger.warning("Invalid ticker format rejected: %s", ticker)
        return None

    return normalized


def validate_enum(value: Optional[str], valid_values: Set[str], field_name: str) -> Optional[str]:
    """Validate enum field against allowed values."""
    if value is None:
        return None

    normalized = value.lower().strip()

    if normalized in valid_values:
        return normalized

    logger.warning("Invalid %s value rejected: %s (allowed: %s)", field_name, value, valid_values)
    return None


def validate_positive_float(value: Any, field_name: str, allow_zero: bool = False) -> Optional[float]:
    """Validate and convert numeric field to positive float."""
    if value is None:
        return None

    try:
        float_val = float(value)

        if allow_zero and float_val >= 0:
            return float_val
        elif not allow_zero and float_val > 0:
            return float_val
        else:
            logger.warning("Non-positive %s value rejected: %s", field_name, value)
            return None
    except (ValueError, TypeError):
        logger.warning("Invalid numeric %s value rejected: %s", field_name, value)
        return None


def validate_percentage(value: Any, field_name: str) -> Optional[float]:
    """Validate percentage field (0-100)."""
    if value is None:
        return None

    try:
        float_val = float(value)

        if 0 <= float_val <= 100:
            return float_val
        else:
            logger.warning("Invalid percentage %s value rejected: %s (must be 0-100)", field_name, value)
            return None
    except (ValueError, TypeError):
        logger.warning("Invalid numeric %s value rejected: %s", field_name, value)
        return None


@dataclass
class PortfolioHolding:
    """Portfolio holding model"""
    user_id: str
    ticker: Optional[str]
    asset_name: Optional[str]
    asset_type: str
    shares: Optional[float] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    cost_basis: Optional[float] = None
    ownership_pct: Optional[float] = None
    position: Optional[str] = None
    intent: Optional[str] = None
    time_horizon: Optional[str] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None
    source_memory_id: Optional[str] = None
    id: Optional[str] = None


class PortfolioService:
    """Service for managing portfolio holdings and financial tracking"""

    def __init__(self):
        self.neo4j_driver = get_neo4j_driver()

    def upsert_holding_from_memory(self, user_id: str, portfolio_metadata: Dict[str, Any], memory_id: str) -> Optional[str]:
        """
        Upsert portfolio holding from memory metadata
        
        Args:
            user_id: User ID
            portfolio_metadata: Portfolio dict from memory extraction
            memory_id: Source memory ID
            
        Returns:
            Holding ID if successful, None otherwise
        """
        from src.services.tracing import start_span, end_span
        
        span = start_span("portfolio_upsert", 
                         input={"ticker": portfolio_metadata.get("ticker") if portfolio_metadata else None})
        
        if not portfolio_metadata or not isinstance(portfolio_metadata, dict):
            end_span(output={"success": False, "reason": "invalid_metadata"})
            return None
        
        conn = get_timescale_conn()
        if not conn:
            end_span(output={"success": False, "reason": "timescale_unavailable"})
            return None

        try:
            # Check if this is a holdings array (portfolio snapshot)
            holdings_array = portfolio_metadata.get('holdings')
            if holdings_array and isinstance(holdings_array, list):
                # Process each holding in the snapshot
                for holding_data in holdings_array:
                    self._upsert_single_holding(conn, user_id, holding_data, memory_id)
                end_span(output={"holding_id": None, "success": True, "processed_multiple": True})
                return None  # Multiple holdings processed

            # Extract and validate base portfolio data
            ticker = normalize_ticker(portfolio_metadata.get('ticker'))
            asset_name = portfolio_metadata.get('name') or portfolio_metadata.get('asset_name')
            if asset_name:
                asset_name = str(asset_name).strip() or None

            # Must have either ticker or asset_name
            if not ticker and not asset_name:
                logger.warning("Portfolio holding rejected: missing both ticker and asset_name")
                end_span(output={"success": False, "reason": "missing_identifier"})
                return None

            # Validate and normalize enum fields
            intent = validate_enum(portfolio_metadata.get('intent'), VALID_INTENTS, 'intent')
            position = validate_enum(portfolio_metadata.get('position'), VALID_POSITIONS, 'position')
            time_horizon = validate_enum(portfolio_metadata.get('time_horizon'), VALID_TIME_HORIZONS, 'time_horizon')

            # Validate asset_type with default fallback
            raw_asset_type = portfolio_metadata.get('asset_type')
            asset_type = validate_enum(raw_asset_type, VALID_ASSET_TYPES, 'asset_type')
            if not asset_type:
                asset_type = 'public_equity' if ticker else 'other'

            # Validate numeric fields (handle alternate field names from extraction)
            shares = validate_positive_float(
                portfolio_metadata.get('shares') or portfolio_metadata.get('quantity'),
                'shares'
            )
            avg_price = validate_positive_float(
                portfolio_metadata.get('avg_price') or portfolio_metadata.get('price'),
                'avg_price'
            )
            current_value = validate_positive_float(portfolio_metadata.get('current_value'), 'current_value', allow_zero=True)
            cost_basis = validate_positive_float(portfolio_metadata.get('cost_basis'), 'cost_basis', allow_zero=True)
            ownership_pct = validate_percentage(portfolio_metadata.get('ownership_pct'), 'ownership_pct')
            target_price = validate_positive_float(portfolio_metadata.get('target_price'), 'target_price')
            stop_loss = validate_positive_float(portfolio_metadata.get('stop_loss'), 'stop_loss')

            # OWNERSHIP GATE: Only store actual holdings, not watchlist/speculative entries
            # Only 'hold' intent (or None for neutral statements) represents actual ownership
            # 'wants-to-buy', 'wants-to-sell', 'watch' are all speculative/future intent
            if intent in SPECULATIVE_INTENTS:
                logger.info(
                    "Skipping speculative/watchlist entry for user %s: ticker=%s, intent=%s",
                    user_id, ticker or asset_name, intent
                )
                end_span(output={"success": False, "reason": "speculative_entry_filtered"})
                return None

            # Build notes from various fields
            notes = portfolio_metadata.get('notes') or portfolio_metadata.get('concern') or portfolio_metadata.get('goal')
            if notes:
                notes = str(notes).strip() or None

            # Single holding case
            holding = PortfolioHolding(
                user_id=user_id,
                ticker=ticker,
                asset_name=asset_name,
                asset_type=asset_type,
                shares=shares,
                avg_price=avg_price,
                current_value=current_value,
                cost_basis=cost_basis,
                ownership_pct=ownership_pct,
                position=position,
                intent=intent,
                time_horizon=time_horizon,
                target_price=target_price,
                stop_loss=stop_loss,
                notes=notes,
                source_memory_id=memory_id
            )

            result = self._upsert_single_holding(conn, user_id, holding.__dict__, memory_id)
            end_span(output={"holding_id": result, "success": bool(result)})
            return result

        except Exception as e:
            logger.error("Error upserting portfolio holding: %s", e)
            end_span(output={"success": False, "error": str(e)}, level="ERROR")
            return None
        finally:
            release_timescale_conn(conn)

    def _upsert_single_holding(self, conn: Connection, user_id: str, holding_data: Dict[str, Any], memory_id: str) -> Optional[str]:
        """Insert or update a single holding with validation"""
        if not conn:
            return None

        try:
            # Validate and normalize ticker
            ticker = normalize_ticker(holding_data.get('ticker'))
            asset_name = holding_data.get('asset_name') or holding_data.get('name')
            if asset_name:
                asset_name = str(asset_name).strip() or None

            # Must have either ticker or asset_name
            if not ticker and not asset_name:
                logger.warning("Holding rejected in _upsert_single_holding: missing identifier")
                return None

            # Validate enum fields
            intent = validate_enum(holding_data.get('intent'), VALID_INTENTS, 'intent')
            position = validate_enum(holding_data.get('position'), VALID_POSITIONS, 'position')
            time_horizon = validate_enum(holding_data.get('time_horizon'), VALID_TIME_HORIZONS, 'time_horizon')

            # Validate asset_type with default fallback
            raw_asset_type = holding_data.get('asset_type')
            asset_type = validate_enum(raw_asset_type, VALID_ASSET_TYPES, 'asset_type')
            if not asset_type:
                asset_type = 'public_equity' if ticker else 'other'

            # Validate numeric fields (handle alternate field names from extraction)
            shares = validate_positive_float(
                holding_data.get('shares') or holding_data.get('quantity'),
                'shares'
            )
            avg_price = validate_positive_float(
                holding_data.get('avg_price') or holding_data.get('price'),
                'avg_price'
            )
            current_price = validate_positive_float(holding_data.get('current_price'), 'current_price')
            current_value = validate_positive_float(holding_data.get('current_value'), 'current_value', allow_zero=True)
            cost_basis = validate_positive_float(holding_data.get('cost_basis'), 'cost_basis', allow_zero=True)
            ownership_pct = validate_percentage(holding_data.get('ownership_pct'), 'ownership_pct')
            target_price = validate_positive_float(holding_data.get('target_price'), 'target_price')
            stop_loss = validate_positive_float(holding_data.get('stop_loss'), 'stop_loss')

            # OWNERSHIP GATE: Only store actual holdings, not watchlist/speculative entries
            # Only 'hold' intent (or None for neutral statements) represents actual ownership
            # 'wants-to-buy', 'wants-to-sell', 'watch' are all speculative/future intent
            if intent in SPECULATIVE_INTENTS:
                logger.info(
                    "Skipping speculative/watchlist entry in batch for user %s: ticker=%s, intent=%s",
                    user_id, ticker or asset_name, intent
                )
                return None

            notes = holding_data.get('notes')
            if notes:
                notes = str(notes).strip() or None

            with conn.cursor() as cur:
                # Check if holding exists (by user_id + ticker/asset_name)
                if ticker:
                    cur.execute("""
                        SELECT id FROM portfolio_holdings
                        WHERE user_id = %s AND ticker = %s
                        LIMIT 1
                    """, (user_id, ticker))
                else:
                    cur.execute("""
                        SELECT id FROM portfolio_holdings
                        WHERE user_id = %s AND asset_name = %s AND ticker IS NULL
                        LIMIT 1
                    """, (user_id, asset_name))

                existing = cur.fetchone()

                if existing:
                    # Update existing holding - use COALESCE to preserve existing values
                    holding_id = existing['id']
                    cur.execute("""
                        UPDATE portfolio_holdings
                        SET
                            shares = COALESCE(%s, shares),
                            avg_price = COALESCE(%s, avg_price),
                            current_price = COALESCE(%s, current_price),
                            current_value = COALESCE(%s, current_value),
                            cost_basis = COALESCE(%s, cost_basis),
                            ownership_pct = COALESCE(%s, ownership_pct),
                            position = COALESCE(%s, position),
                            intent = COALESCE(%s, intent),
                            time_horizon = COALESCE(%s, time_horizon),
                            target_price = COALESCE(%s, target_price),
                            stop_loss = COALESCE(%s, stop_loss),
                            notes = COALESCE(%s, notes),
                            last_updated = NOW(),
                            source_memory_id = %s
                        WHERE id = %s
                    """, (
                        shares,
                        avg_price,
                        current_price,
                        current_value,
                        cost_basis,
                        ownership_pct,
                        position,
                        intent,
                        time_horizon,
                        target_price,
                        stop_loss,
                        notes,
                        memory_id,
                        holding_id
                    ))
                    logger.debug("Updated holding %s for user %s ticker=%s", holding_id, user_id, ticker or asset_name)
                else:
                    # Insert new holding
                    holding_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO portfolio_holdings (
                            id, user_id, ticker, asset_name, asset_type,
                            shares, avg_price, current_price, current_value, cost_basis,
                            ownership_pct, position, intent, time_horizon,
                            target_price, stop_loss, notes, source_memory_id,
                            first_acquired, last_updated
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            NOW(), NOW()
                        )
                    """, (
                        holding_id, user_id,
                        ticker, asset_name,
                        asset_type,
                        shares,
                        avg_price,
                        current_price,
                        current_value,
                        cost_basis,
                        ownership_pct,
                        position,
                        intent,
                        time_horizon,
                        target_price,
                        stop_loss,
                        notes,
                        memory_id
                    ))
                    logger.debug("Inserted holding %s for user %s ticker=%s", holding_id, user_id, ticker or asset_name)

                # Commit the transaction
                conn.commit()

                # Create Neo4j node and relationships (async, fire-and-forget)
                self._create_holding_graph_node(holding_id, user_id, ticker, asset_name)

                return holding_id

        except Exception as e:
            # Rollback on error
            if conn:
                conn.rollback()
            logger.error("Error in _upsert_single_holding: %s", e)
            return None

    def _create_holding_graph_node(self, holding_id: str, user_id: str, ticker: Optional[str], asset_name: Optional[str]) -> None:
        """Create Neo4j node for holding (non-blocking)"""
        if not self.neo4j_driver or not (ticker or asset_name):
            return
        
        try:
            with self.neo4j_driver.session() as session:
                session.run("""
                    MERGE (h:Holding {id: $holding_id})
                    SET h.user_id = $user_id,
                        h.ticker = $ticker,
                        h.asset_name = $asset_name,
                        h.updated_at = datetime()
                """, {
                    "holding_id": holding_id,
                    "user_id": user_id,
                    "ticker": ticker,
                    "asset_name": asset_name
                })
        except Exception as e:
            print(f"Error creating holding graph node: {e}")
    
    def get_holdings(self, user_id: str, intent_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve current holdings for a user
        
        Args:
            user_id: User ID
            intent_filter: Optional filter by intent ('buy', 'sell', 'hold', 'watch')
            
        Returns:
            List of holding dictionaries
        """
        conn = get_timescale_conn()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                if intent_filter:
                    cur.execute("""
                        SELECT * FROM portfolio_holdings
                        WHERE user_id = %s AND intent = %s
                        ORDER BY last_updated DESC
                    """, (user_id, intent_filter))
                else:
                    cur.execute("""
                        SELECT * FROM portfolio_holdings
                        WHERE user_id = %s
                        ORDER BY last_updated DESC
                    """, (user_id,))
                
                rows = cur.fetchall()
                conn.commit()
                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error retrieving holdings: {e}")
            if conn:
                conn.rollback()
            return []
        finally:
            release_timescale_conn(conn)

    def create_snapshot(self, user_id: str) -> bool:
        """
        Create a portfolio value snapshot
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        conn = get_timescale_conn()
        if not conn:
            return False

        try:
            holdings = self.get_holdings(user_id)
            
            total_value = sum(h.get('current_value', 0) or 0 for h in holdings)
            cash_value = sum(h.get('current_value', 0) or 0 for h in holdings if h.get('asset_type') == 'cash')
            equity_value = sum(h.get('current_value', 0) or 0 for h in holdings if h.get('asset_type') in ('public_equity', 'private_equity', 'etf', 'mutual_fund'))
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO portfolio_snapshots (
                        user_id, snapshot_timestamp, total_value,
                        cash_value, equity_value, holdings_snapshot
                    ) VALUES (%s, NOW(), %s, %s, %s, %s)
                """, (
                    user_id, total_value, cash_value, equity_value,
                    holdings  # Store full holdings JSON
                ))

            # Commit the transaction
            conn.commit()
            return True

        except Exception as e:
            print(f"Error creating portfolio snapshot: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            release_timescale_conn(conn)

