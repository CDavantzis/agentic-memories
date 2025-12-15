# Story 3.2: Portfolio POST Endpoint (Add Holding)

Status: done

## Story

As a **chatbot (Annie)**,
I want **to add a new stock holding for a user via API**,
so that **I can record purchases the user tells me about directly**.

## Acceptance Criteria

**AC1:** POST endpoint creates new holding
- **Given** a valid holding request
- **When** calling `POST /v1/portfolio/holding` with body:
  ```json
  {
    "user_id": "uuid",
    "ticker": "AAPL",
    "asset_name": "Apple Inc.",
    "shares": 100.0,
    "avg_price": 150.00,
    "intent": "hold"
  }
  ```
- **Then** the system creates a new holding in `portfolio_holdings` table
- **And** returns the created holding with 201 status

**AC2:** Ticker normalization
- **Given** a request with lowercase ticker (e.g., "aapl")
- **When** creating the holding
- **Then** ticker is normalized to uppercase ("AAPL")
- **And** stored in uppercase in database

**AC3:** Intent validation
- **Given** a request with invalid intent value
- **When** calling POST endpoint
- **Then** the system returns 400 Bad Request
- **And** error message lists valid intents: `hold`, `wants-to-buy`, `wants-to-sell`, `watch`

**AC4:** UPSERT behavior
- **Given** a holding already exists for user_id + ticker + intent combination
- **When** calling POST with same user_id + ticker + intent
- **Then** the system updates the existing holding (not creates duplicate)
- **And** returns the updated holding with 200 status

**AC5:** Request validation
- **Given** a request with missing required fields (user_id, ticker)
- **When** calling POST endpoint
- **Then** the system returns 422 Unprocessable Entity
- **And** error message indicates missing fields

## Tasks / Subtasks

- [x] **Task 1:** Create Pydantic request model (AC1, AC5)
  - [x] Create `AddHoldingRequest` model with fields: user_id (required), ticker (required), asset_name (optional), shares (optional), avg_price (optional), intent (default: "hold")
  - [x] Add field validators for ticker (non-empty string) and intent

- [x] **Task 2:** Implement ticker normalization (AC2)
  - [x] Use existing `normalize_ticker()` from `portfolio_service.py`
  - [x] Or implement inline uppercase + strip logic
  - [x] Validate ticker format (alphanumeric + dots, 1-10 chars)

- [x] **Task 3:** Implement intent validation (AC3)
  - [x] Use existing `VALID_INTENTS` set from `portfolio_service.py`
  - [x] Return 400 with clear error message if invalid

- [x] **Task 4:** Implement POST endpoint (AC1, AC4)
  - [x] Add `@router.post("/holding", status_code=201)` endpoint
  - [x] Accept `AddHoldingRequest` body
  - [x] Use INSERT ... ON CONFLICT for UPSERT behavior
  - [x] Return created/updated holding with appropriate status (201 for create, 200 for update)

- [x] **Task 5:** Create response model (AC1)
  - [x] Create `HoldingCreateResponse` model or reuse `HoldingResponse` from Story 3.1
  - [x] Include all holding fields plus `created` boolean flag

- [x] **Task 6:** Write unit tests (AC1, AC2, AC3, AC4, AC5)
  - [x] Test POST creates new holding with valid data
  - [x] Test ticker normalization (lowercase → uppercase)
  - [x] Test invalid intent returns 400
  - [x] Test UPSERT updates existing holding
  - [x] Test missing required fields returns 422

## Dev Notes

### Architecture Patterns

- **Router Pattern:** Extend `src/routers/portfolio.py` from Story 3.1
- **Database Connection:** Use existing `get_timescale_conn()` / `release_timescale_conn()` pattern
- **Validation:** Use existing helpers from `src/services/portfolio_service.py`

### Database Operation

UPSERT query pattern using PostgreSQL `ON CONFLICT`:

```sql
INSERT INTO portfolio_holdings (user_id, ticker, asset_name, shares, avg_price, intent, first_acquired, last_updated)
VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
ON CONFLICT (user_id, UPPER(ticker), intent)
DO UPDATE SET
    asset_name = EXCLUDED.asset_name,
    shares = EXCLUDED.shares,
    avg_price = EXCLUDED.avg_price,
    last_updated = NOW()
RETURNING id, ticker, asset_name, shares, avg_price, intent, first_acquired, last_updated;
```

### Intent Values (from Migration 014)

- `hold` - User owns this stock (default)
- `wants-to-buy` - User is interested in buying
- `wants-to-sell` - User wants to sell
- `watch` - User is watching this stock

### Unique Constraint

The database has unique constraint: `(user_id, UPPER(ticker), intent)`

This means a user can have:
- AAPL with intent "hold" (owns it)
- AAPL with intent "watch" (also watching it)

Both are valid - different intents.

### Learnings from Story 3.1

**From Dev Agent Record:**
- Actual DB columns: `first_acquired` and `last_updated` (not `created_at`/`updated_at`)
- Use `get_timescale_conn()` / `release_timescale_conn()` pattern
- Handle dict/tuple cursor results for psycopg3 compatibility
- FastAPI returns 422 (not 400) for missing required params

**Files Created in Story 3.1:**
- `src/routers/portfolio.py` - Add POST endpoint here
- `tests/unit/test_portfolio_api.py` - Add POST tests here

**Existing Helpers in portfolio_service.py:**
- `normalize_ticker(ticker: str) -> Optional[str]` - Uppercase + validate format
- `validate_enum(value, valid_values, field_name)` - Validate against set
- `VALID_INTENTS` - Set of valid intent values

### References

- [Source: docs/epic-portfolio-crud-api.md#Story-3.2]
- [Source: docs/epic-portfolio-crud-api.md#FR-PC2]
- [Source: src/services/portfolio_service.py - normalize_ticker, VALID_INTENTS]
- [Source: src/routers/portfolio.py - Existing GET endpoint patterns]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/3-2-portfolio-post-endpoint.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Used existing `normalize_ticker()` and `VALID_INTENTS` from `portfolio_service.py` for validation
- Implemented UPSERT using PostgreSQL `ON CONFLICT (user_id, UPPER(ticker), intent)` with `RETURNING (xmax = 0) AS inserted` to detect insert vs update
- Returns JSONResponse with dynamic status code (201 for insert, 200 for update) since FastAPI default status_code decorator is fixed
- Handle both dict and tuple cursor results for psycopg3 compatibility (same pattern as Story 3.1)

### Completion Notes List

- ✅ Created `AddHoldingRequest` Pydantic model with required user_id, ticker and optional asset_name, shares, avg_price, intent (default: "hold")
- ✅ Created `HoldingCreateResponse` model with `created` boolean flag to indicate insert vs update
- ✅ Implemented POST /v1/portfolio/holding endpoint with full UPSERT behavior
- ✅ Ticker normalization via `normalize_ticker()` with 400 error for invalid format
- ✅ Intent validation against `VALID_INTENTS` set with 400 error listing valid values
- ✅ 12 unit tests added covering all 5 ACs plus edge cases (dict cursor, database unavailable, default intent, all valid intents)
- ✅ All 20 portfolio API tests pass (8 GET + 12 POST)

### File List

**Modified Files:**
- `src/routers/portfolio.py` - Added AddHoldingRequest, HoldingCreateResponse models and POST /holding endpoint

**Test Files:**
- `tests/unit/test_portfolio_api.py` - Added 12 POST endpoint tests (test_post_holding_*)

---

**Story Created:** 2025-12-14
**Epic:** 3 (Portfolio Direct CRUD API)
**Depends On:** Story 3.1 (Portfolio GET Endpoint - done)

---

## Senior Developer Review (AI)

### Reviewer
Ankit (via Claude Opus 4.5)

### Date
2025-12-14

### Outcome
**✅ APPROVE**

All acceptance criteria are implemented with evidence. All completed tasks have been verified. Implementation follows established patterns from Story 3.1 and uses existing validation helpers from portfolio_service.py.

### Summary

Story 3.2 implements a clean POST endpoint for adding/updating portfolio holdings at `/v1/portfolio/holding`. The implementation properly handles:
- UPSERT via PostgreSQL `ON CONFLICT` with dynamic status codes (201/200)
- Ticker normalization using existing `normalize_ticker()` helper
- Intent validation against `VALID_INTENTS` set with clear error messages
- Required field validation via Pydantic (422 for missing user_id/ticker)

### Key Findings

**No blocking issues found.**

**LOW Severity:**
- Note: The endpoint uses `JSONResponse` with `model_dump(mode='json')` for dynamic status codes. This works correctly but is slightly non-standard compared to returning Pydantic models directly. Acceptable trade-off for the 201/200 status code requirement.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | POST endpoint creates new holding | ✅ IMPLEMENTED | `src/routers/portfolio.py:147-247` |
| AC2 | Ticker normalization | ✅ IMPLEMENTED | `src/routers/portfolio.py:159-165` |
| AC3 | Intent validation | ✅ IMPLEMENTED | `src/routers/portfolio.py:167-173` |
| AC4 | UPSERT behavior | ✅ IMPLEMENTED | `src/routers/portfolio.py:185-195,243` |
| AC5 | Request validation | ✅ IMPLEMENTED | `src/routers/portfolio.py:42-49` (Pydantic) |

**Summary:** 5 of 5 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| Task 1: Create Pydantic request model | [x] | ✅ | Lines 42-49: AddHoldingRequest with required user_id, ticker |
| Task 2: Implement ticker normalization | [x] | ✅ | Lines 159-165: normalize_ticker() with 400 error |
| Task 3: Implement intent validation | [x] | ✅ | Lines 167-173: VALID_INTENTS check with 400 error |
| Task 4: Implement POST endpoint | [x] | ✅ | Lines 147-259: Full UPSERT with 201/200 status |
| Task 5: Create response model | [x] | ✅ | Lines 52-62: HoldingCreateResponse with created flag |
| Task 6: Write unit tests | [x] | ✅ | 12 tests covering all ACs |

**Summary:** 6 of 6 completed tasks verified, 0 questionable, 0 falsely marked complete

### Test Coverage and Gaps

**Tests Present:**
- ✅ AC1: `test_post_holding_creates_new_holding` (201 status)
- ✅ AC1: `test_post_holding_optional_fields_null`
- ✅ AC2: `test_post_holding_ticker_normalization` (lowercase → uppercase)
- ✅ AC2: `test_post_holding_invalid_ticker_format` (400 error)
- ✅ AC3: `test_post_holding_invalid_intent` (400 with valid list)
- ✅ AC3: `test_post_holding_all_valid_intents`
- ✅ AC4: `test_post_holding_upsert_updates_existing` (200 status)
- ✅ AC5: `test_post_holding_missing_user_id` (422)
- ✅ AC5: `test_post_holding_missing_ticker` (422)
- ✅ Edge: `test_post_holding_dict_cursor_format`
- ✅ Edge: `test_post_holding_database_unavailable`
- ✅ Edge: `test_post_holding_default_intent`

**Gaps:** None identified. All ACs have comprehensive test coverage.

### Architectural Alignment

- ✅ Follows FastAPI router pattern from portfolio.py (Story 3.1)
- ✅ Uses `get_timescale_conn()` / `release_timescale_conn()` pattern
- ✅ Reuses existing helpers (`normalize_ticker`, `VALID_INTENTS`)
- ✅ Proper try/except/finally for connection cleanup
- ✅ Logging follows established format `[portfolio.api.post] user_id=%s`
- ✅ UPSERT uses correct unique constraint `(user_id, UPPER(ticker), intent)`

### Security Notes

- ✅ No SQL injection risk (parameterized query with %s placeholders)
- ✅ Input validation via Pydantic models
- ✅ Ticker format validated (rejects invalid patterns)
- ✅ Intent validated against whitelist
- ⚠️ Note: No authentication/authorization on endpoint (matches existing pattern - auth handled elsewhere)

### Best-Practices and References

- FastAPI POST endpoints: https://fastapi.tiangolo.com/tutorial/body/
- PostgreSQL UPSERT: https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT
- Pydantic models: https://docs.pydantic.dev/latest/concepts/models/
- psycopg3 cursor handling: https://www.psycopg.org/psycopg3/docs/

### Action Items

**Code Changes Required:**
- None. All acceptance criteria implemented correctly.

**Advisory Notes:**
- Note: Consider adding explicit UUID validation for user_id in future stories if needed
- Note: The JSONResponse approach for dynamic status codes is acceptable but could be abstracted into a helper for consistency across future endpoints
