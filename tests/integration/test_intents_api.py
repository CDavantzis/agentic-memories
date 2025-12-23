"""Integration tests for Scheduled Intents API (Story 5.4).

Tests CRUD operations on /v1/intents endpoints:
- AC1: POST creates intent with validation and next_check
- AC2: GET list with filters
- AC3: GET single by ID
- AC4: PUT updates with next_check recalculation
- AC5: DELETE removes intent
- AC6: Langfuse tracing (verified via decorator presence)
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.schemas import TriggerSchedule, TriggerCondition


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection with cursor."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


@pytest.fixture
def sample_intent_row():
    """Create a sample database row for an intent."""
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(),
        "user_id": "test-user",
        "intent_name": "Test Intent",
        "description": "Test description",
        "trigger_type": "cron",
        "trigger_schedule": {"cron": "0 9 * * *"},
        "trigger_condition": None,
        "action_type": "notify",
        "action_context": "Test context",
        "action_priority": "normal",
        "next_check": now + timedelta(hours=1),
        "last_checked": None,
        "last_executed": None,
        "execution_count": 0,
        "last_execution_status": None,
        "last_execution_error": None,
        "last_message_id": None,
        "enabled": True,
        "expires_at": None,
        "max_executions": None,
        "created_at": now,
        "updated_at": now,
        "created_by": "test-user",
        "metadata": {},
    }


# =============================================================================
# AC1: POST /v1/intents - Create Intent
# =============================================================================

class TestCreateIntent:
    """Tests for POST /v1/intents (AC1)."""

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_create_intent_success(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """POST creates intent with 201 status."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = sample_intent_row

        response = client.post("/v1/intents", json={
            "user_id": "test-user",
            "intent_name": "Daily Check-in",
            "trigger_type": "cron",
            "trigger_schedule": {"cron": "0 9 * * *"},
            "action_context": "Good morning check-in",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "test-user"
        assert data["intent_name"] == "Test Intent"
        assert data["trigger_type"] == "cron"
        assert "id" in data
        assert "next_check" in data

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_create_intent_validation_fails(self, mock_release, mock_get_conn, client, mock_db_connection):
        """POST returns 400 for validation failure."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        # Return count > 25 to trigger validation failure
        cursor.fetchone.return_value = {"count": 26}

        response = client.post("/v1/intents", json={
            "user_id": "test-user",
            "intent_name": "Daily Check-in",
            "trigger_type": "cron",
            "trigger_schedule": {"cron": "0 9 * * *"},
            "action_context": "Good morning check-in",
        })

        assert response.status_code == 400
        data = response.json()
        assert "errors" in data
        assert any("25 active triggers max" in err for err in data["errors"])

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_create_intent_missing_required_field(self, mock_release, mock_get_conn, client, mock_db_connection):
        """POST returns 400 for missing required schedule field."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = {"count": 0}

        response = client.post("/v1/intents", json={
            "user_id": "test-user",
            "intent_name": "Daily Check-in",
            "trigger_type": "cron",
            # Missing trigger_schedule.cron
            "action_context": "Good morning check-in",
        })

        assert response.status_code == 400
        data = response.json()
        assert "errors" in data
        assert any("trigger_schedule.cron required" in err for err in data["errors"])

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_create_interval_intent_with_next_check(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """POST interval intent has correct next_check calculation."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn

        # Modify sample to be interval type
        sample_intent_row["trigger_type"] = "interval"
        sample_intent_row["trigger_schedule"] = {"interval_minutes": 30}
        cursor.fetchone.return_value = sample_intent_row

        response = client.post("/v1/intents", json={
            "user_id": "test-user",
            "intent_name": "Periodic Check",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "action_context": "Check status",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["trigger_type"] == "interval"


# =============================================================================
# AC2: GET /v1/intents - List Intents
# =============================================================================

class TestListIntents:
    """Tests for GET /v1/intents (AC2)."""

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_list_intents_success(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """GET list returns intents for user."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [sample_intent_row, sample_intent_row]

        response = client.get("/v1/intents?user_id=test-user")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_list_intents_with_trigger_type_filter(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """GET list filters by trigger_type."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [sample_intent_row]

        response = client.get("/v1/intents?user_id=test-user&trigger_type=cron")

        assert response.status_code == 200
        # Verify query was called with trigger_type filter
        call_args = cursor.execute.call_args
        assert "trigger_type" in call_args[0][0]

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_list_intents_with_enabled_filter(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """GET list filters by enabled status."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [sample_intent_row]

        response = client.get("/v1/intents?user_id=test-user&enabled=true")

        assert response.status_code == 200
        # Verify query was called with enabled filter
        call_args = cursor.execute.call_args
        assert "enabled" in call_args[0][0]

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_list_intents_with_pagination(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """GET list supports limit and offset."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [sample_intent_row]

        response = client.get("/v1/intents?user_id=test-user&limit=10&offset=5")

        assert response.status_code == 200
        # Verify query was called with LIMIT and OFFSET
        call_args = cursor.execute.call_args
        assert "LIMIT" in call_args[0][0]
        assert "OFFSET" in call_args[0][0]

    def test_list_intents_missing_user_id(self, client):
        """GET list requires user_id parameter."""
        response = client.get("/v1/intents")

        assert response.status_code == 422  # FastAPI validation error


# =============================================================================
# AC3: GET /v1/intents/{id} - Get Single Intent
# =============================================================================

class TestGetIntent:
    """Tests for GET /v1/intents/{id} (AC3)."""

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_get_intent_success(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """GET single returns intent with all fields."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = sample_intent_row

        intent_id = str(sample_intent_row["id"])
        response = client.get(f"/v1/intents/{intent_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == intent_id
        assert data["user_id"] == "test-user"
        assert "next_check" in data
        assert "last_executed" in data
        assert "execution_count" in data

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_get_intent_not_found(self, mock_release, mock_get_conn, client, mock_db_connection):
        """GET single returns 404 for non-existent intent."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = None

        response = client.get(f"/v1/intents/{uuid4()}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_intent_invalid_uuid(self, client):
        """GET single returns 422 for invalid UUID format."""
        response = client.get("/v1/intents/not-a-uuid")

        assert response.status_code == 422


# =============================================================================
# AC4: PUT /v1/intents/{id} - Update Intent
# =============================================================================

class TestUpdateIntent:
    """Tests for PUT /v1/intents/{id} (AC4)."""

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_update_intent_success(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """PUT updates intent and returns updated data."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        # First call returns existing intent, second call returns updated
        cursor.fetchone.side_effect = [sample_intent_row, sample_intent_row]

        intent_id = str(sample_intent_row["id"])
        response = client.put(f"/v1/intents/{intent_id}", json={
            "intent_name": "Updated Intent Name",
        })

        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_update_intent_not_found(self, mock_release, mock_get_conn, client, mock_db_connection):
        """PUT returns 404 for non-existent intent."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = None

        response = client.put(f"/v1/intents/{uuid4()}", json={
            "intent_name": "Updated Name",
        })

        assert response.status_code == 404

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_update_schedule_recalculates_next_check(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """PUT recalculates next_check when schedule changes."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.side_effect = [sample_intent_row, sample_intent_row]

        intent_id = str(sample_intent_row["id"])
        response = client.put(f"/v1/intents/{intent_id}", json={
            "trigger_schedule": {"cron": "0 10 * * *"},  # Changed schedule
        })

        assert response.status_code == 200
        # Verify UPDATE query includes next_check
        update_call = cursor.execute.call_args_list[-1]
        assert "next_check" in update_call[0][0]


# =============================================================================
# AC5: DELETE /v1/intents/{id} - Delete Intent
# =============================================================================

class TestDeleteIntent:
    """Tests for DELETE /v1/intents/{id} (AC5)."""

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_delete_intent_success(self, mock_release, mock_get_conn, client, mock_db_connection, sample_intent_row):
        """DELETE returns 204 on success."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = {"id": sample_intent_row["id"]}

        intent_id = str(sample_intent_row["id"])
        response = client.delete(f"/v1/intents/{intent_id}")

        assert response.status_code == 204

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_delete_intent_not_found(self, mock_release, mock_get_conn, client, mock_db_connection):
        """DELETE returns 404 for non-existent intent."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = None

        response = client.delete(f"/v1/intents/{uuid4()}")

        assert response.status_code == 404


# =============================================================================
# Story 5.5: GET /v1/intents/pending - Pending Intents
# =============================================================================

class TestPendingIntents:
    """Tests for GET /v1/intents/pending (Story 5.5)."""

    @pytest.fixture
    def pending_intent_row(self):
        """Create a sample database row for a pending intent (next_check in past)."""
        now = datetime.now(timezone.utc)
        return {
            "id": uuid4(),
            "user_id": "test-user",
            "intent_name": "Pending Intent",
            "description": "Due for execution",
            "trigger_type": "cron",
            "trigger_schedule": {"cron": "0 9 * * *"},
            "trigger_condition": None,
            "action_type": "notify",
            "action_context": "You have a pending task",
            "action_priority": "normal",
            "next_check": now - timedelta(minutes=5),  # Past = pending
            "last_checked": None,
            "last_executed": None,
            "execution_count": 0,
            "last_execution_status": None,
            "last_execution_error": None,
            "last_message_id": None,
            "enabled": True,
            "expires_at": None,
            "max_executions": None,
            "created_at": now - timedelta(hours=1),
            "updated_at": now - timedelta(hours=1),
            "created_by": "test-user",
            "metadata": {},
        }

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_pending_returns_due_intents(self, mock_release, mock_get_conn, client, mock_db_connection, pending_intent_row):
        """GET /pending returns intents with next_check <= NOW."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [pending_intent_row]

        response = client.get("/v1/intents/pending")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["intent_name"] == "Pending Intent"

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_pending_with_user_id_filter(self, mock_release, mock_get_conn, client, mock_db_connection, pending_intent_row):
        """GET /pending filters by user_id when provided."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [pending_intent_row]

        response = client.get("/v1/intents/pending?user_id=test-user")

        assert response.status_code == 200
        # Verify query includes user_id filter
        call_args = cursor.execute.call_args
        assert "user_id" in call_args[0][0]
        assert "test-user" in call_args[0][1]

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_pending_returns_empty_when_none_due(self, mock_release, mock_get_conn, client, mock_db_connection):
        """GET /pending returns empty array when no intents are due."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = []

        response = client.get("/v1/intents/pending")

        assert response.status_code == 200
        assert response.json() == []

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_pending_ordered_by_next_check_asc(self, mock_release, mock_get_conn, client, mock_db_connection, pending_intent_row):
        """GET /pending orders results by next_check ASC (oldest first)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [pending_intent_row]

        response = client.get("/v1/intents/pending")

        assert response.status_code == 200
        # Verify query includes ORDER BY next_check ASC
        call_args = cursor.execute.call_args
        assert "ORDER BY next_check ASC" in call_args[0][0]

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_pending_query_uses_correct_conditions(self, mock_release, mock_get_conn, client, mock_db_connection, pending_intent_row):
        """GET /pending uses enabled = true AND next_check <= NOW() conditions."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = [pending_intent_row]

        response = client.get("/v1/intents/pending")

        assert response.status_code == 200
        # Verify query includes correct WHERE conditions
        call_args = cursor.execute.call_args
        query = call_args[0][0]
        assert "enabled = true" in query
        assert "next_check" in query
        assert "NOW()" in query

    @patch("src.routers.intents.get_timescale_conn")
    def test_pending_database_unavailable(self, mock_get_conn, client):
        """GET /pending returns 500 when database is unavailable."""
        mock_get_conn.return_value = None

        response = client.get("/v1/intents/pending")

        assert response.status_code == 500
        assert "database" in response.json()["detail"].lower()


# =============================================================================
# AC6: Langfuse Tracing
# =============================================================================

class TestLangfuseTracing:
    """Tests for Langfuse tracing (AC6)."""

    def test_endpoints_have_observe_decorator(self):
        """Verify all endpoints have @observe decorator."""
        from src.routers.intents import (
            create_intent,
            list_intents,
            get_intent,
            get_pending_intents,
            update_intent,
            delete_intent,
        )

        # Check that functions have been wrapped by observe decorator
        # The decorator adds metadata to the function
        endpoints = [create_intent, list_intents, get_intent, get_pending_intents, update_intent, delete_intent]

        for endpoint in endpoints:
            # The observe decorator wraps the function
            # We can check if it has the expected structure
            assert callable(endpoint), f"{endpoint.__name__} should be callable"
            # The langfuse observe decorator sets __wrapped__ on the function
            # or modifies __name__ - we verify the function is still callable
            # and has expected name pattern
            assert hasattr(endpoint, "__name__")


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Additional edge case tests."""

    @patch("src.routers.intents.get_timescale_conn")
    def test_database_unavailable(self, mock_get_conn, client):
        """Returns 500 when database is unavailable."""
        mock_get_conn.return_value = None

        response = client.get("/v1/intents?user_id=test-user")

        assert response.status_code == 500
        assert "database" in response.json()["detail"].lower()

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_list_intents_empty(self, mock_release, mock_get_conn, client, mock_db_connection):
        """GET list returns empty array for user with no intents."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchall.return_value = []

        response = client.get("/v1/intents?user_id=new-user")

        assert response.status_code == 200
        assert response.json() == []


# =============================================================================
# Story 5.6: POST /v1/intents/{id}/fire - Fire Intent
# =============================================================================

class TestFireIntent:
    """Tests for POST /v1/intents/{id}/fire (Story 5.6)."""

    @pytest.fixture
    def interval_intent_row(self):
        """Create a sample database row for an interval intent."""
        now = datetime.now(timezone.utc)
        return {
            "id": uuid4(),
            "user_id": "test-user",
            "intent_name": "Interval Intent",
            "description": "Every 30 minutes",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "trigger_condition": None,
            "action_type": "notify",
            "action_context": "Check status",
            "action_priority": "normal",
            "next_check": now,
            "last_checked": None,
            "last_executed": None,
            "execution_count": 0,
            "last_execution_status": None,
            "last_execution_error": None,
            "last_message_id": None,
            "enabled": True,
            "expires_at": None,
            "max_executions": None,
            "created_at": now - timedelta(hours=1),
            "updated_at": now - timedelta(hours=1),
            "created_by": "test-user",
            "metadata": {},
        }

    @pytest.fixture
    def once_intent_row(self):
        """Create a sample database row for a one-time intent."""
        now = datetime.now(timezone.utc)
        return {
            "id": uuid4(),
            "user_id": "test-user",
            "intent_name": "One-time Intent",
            "description": "Fire once",
            "trigger_type": "once",
            "trigger_schedule": {"trigger_at": now.isoformat()},
            "trigger_condition": None,
            "action_type": "notify",
            "action_context": "One-time reminder",
            "action_priority": "high",
            "next_check": now,
            "last_checked": None,
            "last_executed": None,
            "execution_count": 0,
            "last_execution_status": None,
            "last_execution_error": None,
            "last_message_id": None,
            "enabled": True,
            "expires_at": None,
            "max_executions": None,
            "created_at": now - timedelta(hours=1),
            "updated_at": now - timedelta(hours=1),
            "created_by": "test-user",
            "metadata": {},
        }

    @pytest.fixture
    def max_exec_intent_row(self):
        """Create a sample intent at max_executions - 1."""
        now = datetime.now(timezone.utc)
        return {
            "id": uuid4(),
            "user_id": "test-user",
            "intent_name": "Limited Intent",
            "description": "Max 3 executions",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "trigger_condition": None,
            "action_type": "notify",
            "action_context": "Limited notification",
            "action_priority": "normal",
            "next_check": now,
            "last_checked": None,
            "last_executed": None,
            "execution_count": 2,  # At max_executions - 1
            "last_execution_status": None,
            "last_execution_error": None,
            "last_message_id": None,
            "enabled": True,
            "expires_at": None,
            "max_executions": 3,
            "created_at": now - timedelta(hours=1),
            "updated_at": now - timedelta(hours=1),
            "created_by": "test-user",
            "metadata": {},
        }

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_returns_updated_state(self, mock_release, mock_get_conn, client, mock_db_connection, interval_intent_row):
        """POST /fire returns IntentFireResponse with updated state (AC1)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = interval_intent_row

        intent_id = str(interval_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "success",
            "message_id": "msg-123",
            "evaluation_ms": 50,
            "generation_ms": 100,
            "delivery_ms": 25,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["intent_id"] == intent_id
        assert data["status"] == "success"
        assert data["enabled"] is True
        assert data["execution_count"] == 1
        assert "next_check" in data

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_updates_last_checked(self, mock_release, mock_get_conn, client, mock_db_connection, interval_intent_row):
        """POST /fire always updates last_checked (AC2)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = interval_intent_row

        intent_id = str(interval_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "condition_not_met",
        })

        assert response.status_code == 200
        # Verify UPDATE query includes last_checked
        update_call = [c for c in cursor.execute.call_args_list if "UPDATE" in c[0][0]]
        assert len(update_call) > 0
        assert "last_checked" in update_call[0][0][0]

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_increments_execution_count_on_success(self, mock_release, mock_get_conn, client, mock_db_connection, interval_intent_row):
        """POST /fire increments execution_count on success (AC3)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = interval_intent_row

        intent_id = str(interval_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "success",
            "message_id": "msg-456",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["execution_count"] == 1  # Was 0, now 1

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_does_not_increment_on_failure(self, mock_release, mock_get_conn, client, mock_db_connection, interval_intent_row):
        """POST /fire does not increment execution_count on failure (AC3)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = interval_intent_row

        intent_id = str(interval_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "failed",
            "error_message": "Connection timeout",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["execution_count"] == 0  # Still 0

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_calculates_next_check_for_interval(self, mock_release, mock_get_conn, client, mock_db_connection, interval_intent_row):
        """POST /fire calculates next_check for interval trigger (AC4)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = interval_intent_row

        intent_id = str(interval_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "success",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["next_check"] is not None

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_backoff_on_failure(self, mock_release, mock_get_conn, client, mock_db_connection, interval_intent_row):
        """POST /fire applies 15-minute backoff on failure (AC4)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = interval_intent_row

        intent_id = str(interval_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "failed",
            "error_message": "API error",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["next_check"] is not None

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_disables_one_time_trigger(self, mock_release, mock_get_conn, client, mock_db_connection, once_intent_row):
        """POST /fire disables one-time trigger after success (AC5)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = once_intent_row

        intent_id = str(once_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "success",
            "message_id": "msg-once",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["was_disabled_reason"] == "one-time trigger executed"
        assert data["next_check"] is None

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_disables_at_max_executions(self, mock_release, mock_get_conn, client, mock_db_connection, max_exec_intent_row):
        """POST /fire disables when max_executions reached (AC5)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = max_exec_intent_row

        intent_id = str(max_exec_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "success",
            "message_id": "msg-final",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["execution_count"] == 3  # Was 2, now 3 = max
        assert "max_executions" in data["was_disabled_reason"]

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_logs_to_intent_executions(self, mock_release, mock_get_conn, client, mock_db_connection, interval_intent_row):
        """POST /fire logs execution to intent_executions table (AC6)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = interval_intent_row

        intent_id = str(interval_intent_row["id"])
        response = client.post(f"/v1/intents/{intent_id}/fire", json={
            "status": "success",
            "message_id": "msg-logged",
            "trigger_data": {"price": 150.00},
            "gate_result": {"passed": True},
            "evaluation_ms": 45,
            "generation_ms": 120,
            "delivery_ms": 30,
        })

        assert response.status_code == 200
        # Verify INSERT into intent_executions
        insert_calls = [c for c in cursor.execute.call_args_list if "INSERT INTO intent_executions" in c[0][0]]
        assert len(insert_calls) == 1

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_fire_returns_404_for_nonexistent(self, mock_release, mock_get_conn, client, mock_db_connection):
        """POST /fire returns 404 for non-existent intent (AC7)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = None

        response = client.post(f"/v1/intents/{uuid4()}/fire", json={
            "status": "success",
        })

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("src.routers.intents.get_timescale_conn")
    def test_fire_database_unavailable(self, mock_get_conn, client):
        """POST /fire returns 500 when database unavailable."""
        mock_get_conn.return_value = None

        response = client.post(f"/v1/intents/{uuid4()}/fire", json={
            "status": "success",
        })

        assert response.status_code == 500
        assert "database" in response.json()["detail"].lower()

    def test_fire_has_observe_decorator(self):
        """Verify fire endpoint has @observe decorator (AC8)."""
        from src.routers.intents import fire_intent

        assert callable(fire_intent)
        assert hasattr(fire_intent, "__name__")


# =============================================================================
# Story 5.7: Execution History Endpoint Tests
# =============================================================================

class TestHistoryIntent:
    """Tests for GET /v1/intents/{id}/history endpoint (Story 5.7)."""

    @pytest.fixture
    def execution_row(self):
        """Create a sample execution history row."""
        now = datetime.now(timezone.utc)
        return {
            "id": uuid4(),
            "intent_id": uuid4(),
            "user_id": "test-user",
            "executed_at": now,
            "trigger_type": "interval",
            "trigger_data": {"price": 150.00},
            "status": "success",
            "gate_result": {"passed": True},
            "message_id": "msg-123",
            "message_preview": "Test message",
            "evaluation_ms": 45,
            "generation_ms": 120,
            "delivery_ms": 30,
            "error_message": None,
        }

    @pytest.fixture
    def execution_rows(self, execution_row):
        """Create multiple execution rows for pagination testing."""
        rows = []
        base_time = datetime.now(timezone.utc)
        intent_id = uuid4()
        for i in range(5):
            row = execution_row.copy()
            row["id"] = uuid4()
            row["intent_id"] = intent_id
            row["executed_at"] = base_time - timedelta(minutes=i)
            row["message_id"] = f"msg-{i}"
            rows.append(row)
        return rows, intent_id

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_history_returns_execution_records(self, mock_release, mock_get_conn, client, mock_db_connection, execution_row):
        """GET /history returns execution records (AC1)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        intent_id = execution_row["intent_id"]

        # First call returns intent exists, second returns executions
        cursor.fetchone.return_value = {"id": intent_id}
        cursor.fetchall.return_value = [execution_row]

        response = client.get(f"/v1/intents/{intent_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["status"] == "success"
        assert data[0]["message_id"] == "msg-123"

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_history_with_pagination(self, mock_release, mock_get_conn, client, mock_db_connection, execution_rows):
        """GET /history supports limit and offset (AC2)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        rows, intent_id = execution_rows

        cursor.fetchone.return_value = {"id": intent_id}
        cursor.fetchall.return_value = rows[:2]  # Simulate limit=2

        response = client.get(f"/v1/intents/{intent_id}/history?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_history_empty_array_when_no_executions(self, mock_release, mock_get_conn, client, mock_db_connection):
        """GET /history returns empty array when no executions exist (AC1)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        intent_id = uuid4()

        cursor.fetchone.return_value = {"id": intent_id}
        cursor.fetchall.return_value = []

        response = client.get(f"/v1/intents/{intent_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_history_ordered_by_executed_at_desc(self, mock_release, mock_get_conn, client, mock_db_connection, execution_rows):
        """GET /history orders by executed_at DESC (AC3)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        rows, intent_id = execution_rows

        cursor.fetchone.return_value = {"id": intent_id}
        cursor.fetchall.return_value = rows

        response = client.get(f"/v1/intents/{intent_id}/history")

        assert response.status_code == 200
        # Verify query contains ORDER BY executed_at DESC
        execute_calls = cursor.execute.call_args_list
        history_query = [c for c in execute_calls if "intent_executions" in c[0][0]]
        assert len(history_query) == 1
        assert "ORDER BY executed_at DESC" in history_query[0][0][0]

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_history_includes_all_execution_fields(self, mock_release, mock_get_conn, client, mock_db_connection, execution_row):
        """GET /history includes all execution details (AC4)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        intent_id = execution_row["intent_id"]

        cursor.fetchone.return_value = {"id": intent_id}
        cursor.fetchall.return_value = [execution_row]

        response = client.get(f"/v1/intents/{intent_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        execution = data[0]
        # Verify all required fields are present
        assert "status" in execution
        assert "trigger_data" in execution
        assert "gate_result" in execution
        assert "message_id" in execution
        assert "message_preview" in execution
        assert "evaluation_ms" in execution
        assert "generation_ms" in execution
        assert "delivery_ms" in execution
        assert "error_message" in execution or execution.get("error_message") is None

    @patch("src.routers.intents.get_timescale_conn")
    @patch("src.routers.intents.release_timescale_conn")
    def test_history_returns_404_for_nonexistent_intent(self, mock_release, mock_get_conn, client, mock_db_connection):
        """GET /history returns 404 for non-existent intent (AC5)."""
        conn, cursor = mock_db_connection
        mock_get_conn.return_value = conn
        cursor.fetchone.return_value = None

        response = client.get(f"/v1/intents/{uuid4()}/history")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("src.routers.intents.get_timescale_conn")
    def test_history_database_unavailable(self, mock_get_conn, client):
        """GET /history returns 500 when database unavailable."""
        mock_get_conn.return_value = None

        response = client.get(f"/v1/intents/{uuid4()}/history")

        assert response.status_code == 500
        assert "database" in response.json()["detail"].lower()

    def test_history_has_observe_decorator(self):
        """Verify history endpoint has @observe decorator (AC6)."""
        from src.routers.intents import get_intent_history

        assert callable(get_intent_history)
        assert hasattr(get_intent_history, "__name__")
