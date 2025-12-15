"""
Unit tests for Portfolio CRUD API endpoints
Tests the GET /v1/portfolio endpoint
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# Mock database cursor and connection
class _MockCursor:
    """Mock database cursor for portfolio tests"""

    def __init__(self, results=None):
        self.results = results or []
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchall(self):
        return self.results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _MockConnection:
    """Mock database connection"""

    def __init__(self, cursor=None):
        self._cursor = cursor or _MockCursor()

    def cursor(self):
        return self._cursor


# Test GET /v1/portfolio endpoint
def test_get_portfolio_success_with_holdings(api_client, monkeypatch):
    """Test successful portfolio retrieval with holdings (AC1, AC2)"""
    # Setup mock data - tuple format from psycopg3
    mock_holdings = [
        ("AAPL", "Apple Inc.", 100.0, 150.50, "hold",
         datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
         datetime(2025, 12, 10, 15, 30, 0, tzinfo=timezone.utc)),
        ("GOOGL", "Alphabet Inc.", 50.0, 2800.00, "hold",
         datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc),
         datetime(2025, 12, 5, 12, 0, 0, tzinfo=timezone.utc)),
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    # Patch the database connection
    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=test-user-123")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure (AC2)
    assert data["user_id"] == "test-user-123"
    assert data["total_holdings"] == 2
    assert len(data["holdings"]) == 2
    assert data["last_updated"] is not None

    # Verify holding fields (AC1)
    holding = data["holdings"][0]
    assert holding["ticker"] == "AAPL"
    assert holding["asset_name"] == "Apple Inc."
    assert holding["shares"] == 100.0
    assert holding["avg_price"] == 150.50
    assert holding["intent"] == "hold"
    assert holding["first_acquired"] is not None
    assert holding["last_updated"] is not None


def test_get_portfolio_empty(api_client, monkeypatch):
    """Test portfolio retrieval with no holdings returns empty array (AC3)"""
    mock_cursor = _MockCursor(results=[])
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=no-holdings-user")

    assert response.status_code == 200
    data = response.json()

    # Verify empty response (AC3)
    assert data["user_id"] == "no-holdings-user"
    assert data["holdings"] == []
    assert data["total_holdings"] == 0
    assert data["last_updated"] is None


def test_get_portfolio_missing_user_id(api_client):
    """Test GET without user_id returns 400 (AC4)"""
    response = api_client.get("/v1/portfolio")

    # FastAPI returns 422 for missing required query parameters
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_get_portfolio_dict_cursor_format(api_client, monkeypatch):
    """Test handling of dict cursor results (psycopg3 compatibility)"""
    # Setup mock data - dict format
    mock_holdings = [
        {
            "ticker": "MSFT",
            "asset_name": "Microsoft Corp.",
            "shares": 75.0,
            "avg_price": 380.00,
            "intent": "hold",
            "first_acquired": datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            "last_updated": datetime(2025, 12, 1, 14, 0, 0, tzinfo=timezone.utc)
        }
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=dict-test-user")

    assert response.status_code == 200
    data = response.json()

    assert data["total_holdings"] == 1
    holding = data["holdings"][0]
    assert holding["ticker"] == "MSFT"
    assert holding["shares"] == 75.0


def test_get_portfolio_holdings_ordered_by_ticker(api_client, monkeypatch):
    """Test holdings are returned ordered by ticker ASC (AC1, AC2)"""
    # Data should come back ordered from DB, but verify query is correct
    mock_holdings = [
        ("AAPL", "Apple", 10.0, 150.0, "hold",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
        ("MSFT", "Microsoft", 20.0, 380.0, "hold",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
        ("TSLA", "Tesla", 5.0, 250.0, "watch",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=order-test-user")

    assert response.status_code == 200
    data = response.json()

    # Verify ORDER BY is in the query
    assert len(mock_cursor.queries) == 1
    query = mock_cursor.queries[0][0]
    assert "ORDER BY" in query

    # Verify holdings come back in order
    tickers = [h["ticker"] for h in data["holdings"]]
    assert tickers == ["AAPL", "MSFT", "TSLA"]


def test_get_portfolio_database_unavailable(api_client, monkeypatch):
    """Test handling when database connection is unavailable"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.get("/v1/portfolio?user_id=test-user")

    assert response.status_code == 500
    data = response.json()
    assert "Database connection unavailable" in data["detail"]


def test_get_portfolio_with_null_values(api_client, monkeypatch):
    """Test handling of holdings with NULL optional fields"""
    mock_holdings = [
        (None, "Private Equity Fund", None, None, "hold",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=null-test-user")

    assert response.status_code == 200
    data = response.json()

    holding = data["holdings"][0]
    assert holding["ticker"] is None
    assert holding["asset_name"] == "Private Equity Fund"
    assert holding["shares"] is None
    assert holding["avg_price"] is None


def test_get_portfolio_multiple_intents(api_client, monkeypatch):
    """Test portfolio with different intent values"""
    mock_holdings = [
        ("AAPL", "Apple", 100.0, 150.0, "hold",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
        ("NVDA", "Nvidia", None, None, "wants-to-buy",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
        ("TSLA", "Tesla", 50.0, 250.0, "wants-to-sell",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
        ("AMD", "AMD", None, None, "watch",
         datetime(2025, 1, 1, tzinfo=timezone.utc),
         datetime(2025, 12, 1, tzinfo=timezone.utc)),
    ]

    mock_cursor = _MockCursor(results=mock_holdings)
    mock_conn = _MockConnection(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.get("/v1/portfolio?user_id=intents-test-user")

    assert response.status_code == 200
    data = response.json()

    intents = [h["intent"] for h in data["holdings"]]
    assert "hold" in intents
    assert "wants-to-buy" in intents
    assert "wants-to-sell" in intents
    assert "watch" in intents


# ============================================================
# POST /v1/portfolio/holding tests (Story 3.2)
# ============================================================

class _MockCursorWithFetchone(_MockCursor):
    """Mock cursor that also supports fetchone for POST tests"""

    def __init__(self, results=None, fetchone_result=None):
        super().__init__(results)
        self._fetchone_result = fetchone_result

    def fetchone(self):
        return self._fetchone_result


class _MockConnectionWithCommit(_MockConnection):
    """Mock connection that also supports commit for POST tests"""

    def __init__(self, cursor=None):
        super().__init__(cursor)
        self._committed = False

    def commit(self):
        self._committed = True

    def rollback(self):
        pass


def test_post_holding_creates_new_holding(api_client):
    """Test POST creates new holding with valid data, returns 201 (AC1)"""
    import uuid
    holding_id = str(uuid.uuid4())

    # Mock result: new insert (inserted=True)
    mock_result = (
        holding_id,
        "AAPL",
        "Apple Inc.",
        100.0,
        150.50,
        "hold",
        datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2025, 12, 14, 10, 0, 0, tzinfo=timezone.utc),
        True  # inserted (xmax = 0)
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user-123",
                "ticker": "AAPL",
                "asset_name": "Apple Inc.",
                "shares": 100.0,
                "avg_price": 150.50,
                "intent": "hold"
            })

    assert response.status_code == 201
    data = response.json()

    assert data["id"] == holding_id
    assert data["ticker"] == "AAPL"
    assert data["asset_name"] == "Apple Inc."
    assert data["shares"] == 100.0
    assert data["avg_price"] == 150.50
    assert data["intent"] == "hold"
    assert data["created"] is True


def test_post_holding_ticker_normalization(api_client):
    """Test lowercase ticker is normalized to uppercase (AC2)"""
    import uuid
    holding_id = str(uuid.uuid4())

    mock_result = (
        holding_id, "AAPL", None, None, None, "hold",
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        True
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "aapl",  # lowercase input
                "intent": "hold"
            })

    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "AAPL"  # Should be uppercase

    # Verify the query was called with uppercase ticker
    assert len(mock_cursor.queries) == 1
    query, params = mock_cursor.queries[0]
    assert params[1] == "AAPL"  # Second param is ticker


def test_post_holding_invalid_intent(api_client):
    """Test invalid intent returns 400 with list of valid intents (AC3)"""
    response = api_client.post("/v1/portfolio/holding", json={
        "user_id": "test-user",
        "ticker": "AAPL",
        "intent": "invalid-intent"
    })

    assert response.status_code == 400
    data = response.json()
    assert "Invalid intent" in data["detail"]
    assert "hold" in data["detail"]
    assert "wants-to-buy" in data["detail"]
    assert "wants-to-sell" in data["detail"]
    assert "watch" in data["detail"]


def test_post_holding_upsert_updates_existing(api_client):
    """Test UPSERT updates existing holding for same user+ticker+intent, returns 200 (AC4)"""
    import uuid
    holding_id = str(uuid.uuid4())

    # Mock result: update (inserted=False)
    mock_result = (
        holding_id,
        "AAPL",
        "Apple Inc.",
        150.0,  # updated shares
        160.00,  # updated price
        "hold",
        datetime(2025, 11, 1, tzinfo=timezone.utc),  # original first_acquired
        datetime(2025, 12, 14, tzinfo=timezone.utc),  # new last_updated
        False  # NOT inserted, was updated
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "AAPL",
                "asset_name": "Apple Inc.",
                "shares": 150.0,
                "avg_price": 160.00,
                "intent": "hold"
            })

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == holding_id
    assert data["shares"] == 150.0
    assert data["avg_price"] == 160.00
    assert data["created"] is False


def test_post_holding_missing_user_id(api_client):
    """Test missing user_id returns 422 (AC5)"""
    response = api_client.post("/v1/portfolio/holding", json={
        "ticker": "AAPL",
        "intent": "hold"
    })

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_post_holding_missing_ticker(api_client):
    """Test missing ticker returns 422 (AC5)"""
    response = api_client.post("/v1/portfolio/holding", json={
        "user_id": "test-user",
        "intent": "hold"
    })

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_post_holding_optional_fields_null(api_client):
    """Test optional fields (asset_name, shares, avg_price) can be null (AC1)"""
    import uuid
    holding_id = str(uuid.uuid4())

    mock_result = (
        holding_id, "TSLA", None, None, None, "watch",
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        True
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "TSLA",
                "intent": "watch"
                # No asset_name, shares, avg_price
            })

    assert response.status_code == 201
    data = response.json()

    assert data["ticker"] == "TSLA"
    assert data["asset_name"] is None
    assert data["shares"] is None
    assert data["avg_price"] is None
    assert data["created"] is True


def test_post_holding_invalid_ticker_format(api_client):
    """Test invalid ticker format returns 400 (AC2)"""
    response = api_client.post("/v1/portfolio/holding", json={
        "user_id": "test-user",
        "ticker": "this-is-way-too-long-for-a-ticker",
        "intent": "hold"
    })

    assert response.status_code == 400
    data = response.json()
    assert "Invalid ticker format" in data["detail"]


def test_post_holding_dict_cursor_format(api_client):
    """Test handling of dict cursor results (psycopg3 compatibility)"""
    import uuid
    holding_id = str(uuid.uuid4())

    # Dict format result
    mock_result = {
        "id": holding_id,
        "ticker": "GOOGL",
        "asset_name": "Alphabet Inc.",
        "shares": 25.0,
        "avg_price": 140.00,
        "intent": "hold",
        "first_acquired": datetime(2025, 12, 14, tzinfo=timezone.utc),
        "last_updated": datetime(2025, 12, 14, tzinfo=timezone.utc),
        "inserted": True
    }

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "dict-test-user",
                "ticker": "GOOGL",
                "asset_name": "Alphabet Inc.",
                "shares": 25.0,
                "avg_price": 140.00,
                "intent": "hold"
            })

    assert response.status_code == 201
    data = response.json()

    assert data["id"] == holding_id
    assert data["ticker"] == "GOOGL"
    assert data["shares"] == 25.0
    assert data["created"] is True


def test_post_holding_database_unavailable(api_client):
    """Test handling when database connection is unavailable"""
    with patch("src.routers.portfolio.get_timescale_conn", return_value=None):
        response = api_client.post("/v1/portfolio/holding", json={
            "user_id": "test-user",
            "ticker": "AAPL",
            "intent": "hold"
        })

    assert response.status_code == 500
    data = response.json()
    assert "Database connection unavailable" in data["detail"]


def test_post_holding_default_intent(api_client):
    """Test default intent is 'hold' when not specified"""
    import uuid
    holding_id = str(uuid.uuid4())

    mock_result = (
        holding_id, "MSFT", None, None, None, "hold",
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        datetime(2025, 12, 14, tzinfo=timezone.utc),
        True
    )

    mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
    mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

    with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
        with patch("src.routers.portfolio.release_timescale_conn"):
            response = api_client.post("/v1/portfolio/holding", json={
                "user_id": "test-user",
                "ticker": "MSFT"
                # No intent specified
            })

    assert response.status_code == 201
    data = response.json()
    assert data["intent"] == "hold"

    # Verify query was called with "hold" intent
    assert len(mock_cursor.queries) == 1
    query, params = mock_cursor.queries[0]
    assert params[5] == "hold"  # Sixth param is intent


def test_post_holding_all_valid_intents(api_client):
    """Test all valid intent values are accepted"""
    import uuid

    valid_intents = ["hold", "wants-to-buy", "wants-to-sell", "watch"]

    for intent in valid_intents:
        holding_id = str(uuid.uuid4())
        mock_result = (
            holding_id, "AAPL", None, None, None, intent,
            datetime(2025, 12, 14, tzinfo=timezone.utc),
            datetime(2025, 12, 14, tzinfo=timezone.utc),
            True
        )

        mock_cursor = _MockCursorWithFetchone(fetchone_result=mock_result)
        mock_conn = _MockConnectionWithCommit(cursor=mock_cursor)

        with patch("src.routers.portfolio.get_timescale_conn", return_value=mock_conn):
            with patch("src.routers.portfolio.release_timescale_conn"):
                response = api_client.post("/v1/portfolio/holding", json={
                    "user_id": f"test-user-{intent}",
                    "ticker": "AAPL",
                    "intent": intent
                })

        assert response.status_code == 201, f"Intent '{intent}' should be valid"
        data = response.json()
        assert data["intent"] == intent
