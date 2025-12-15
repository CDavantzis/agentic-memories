# Story 1.6: Profile Completeness Tracking

Status: ready-for-dev

## Story

As a **system**,
I want **automatic tracking of profile completeness across all categories**,
so that **the system knows which profile gaps to prioritize for filling and can provide completeness metrics to users/companions**.

## Acceptance Criteria

**AC1:** Completeness recalculation on profile changes
- **Given** a user profile with some populated fields
- **When** profile data changes (via manual edit, extraction, or deletion)
- **Then** the system recalculates completeness_score for each category:
  - Basics: 5 expected fields (name, age, location, occupation, education)
  - Preferences: 5 expected fields (communication_style, likes, dislikes, favorites, style)
  - Goals: 5 expected fields (short_term, long_term, aspirations, plans, targets)
  - Interests: 5 expected fields (hobbies, topics, activities, passions, learning)
  - Background: 5 expected fields (history, experiences, skills, achievements, journey)
- **And** total_fields = 25 (5 categories × 5 fields)

**AC2:** Overall completeness calculation
- **Given** category-level completeness scores
- **When** calculating overall completeness
- **Then** overall_completeness = average of all category scores
- **And** stored in `user_profiles.completeness_pct` column
- **And** `populated_fields` and `total_fields` columns updated atomically

**AC3:** High-value gap identification
- **Given** a user profile with varying completeness
- **When** identifying gaps to fill
- **Then** the system identifies "high-value gaps" as:
  - Basics category fields (highest priority - foundational identity)
  - Fields with zero confidence (never extracted)
  - Fields relevant to user's stated goals (if goals category is populated)
- **And** gaps are prioritized: basics > zero-confidence > goal-relevant

**AC4:** Redis caching for gap prioritization
- **Given** computed high-value gaps
- **When** storing for companion access
- **Then** gap prioritization list is cached in Redis:
  - Key pattern: `profile_completeness:{user_id}`
  - TTL: 1 hour (3600 seconds)
  - Value structure: JSON with overall, categories breakdown, and high_value_gaps list
- **And** cache is invalidated on profile changes (namespace bump)

**AC5:** GET /v1/profile/completeness enhancement
- **Given** the existing completeness endpoint from Story 1.5
- **When** calling `GET /v1/profile/completeness?user_id={user_id}&details=true`
- **Then** the enhanced response includes:
  ```json
  {
    "overall_completeness_pct": 67.0,
    "populated_fields": 14,
    "total_fields": 21,
    "categories": {
      "basics": {"completeness_pct": 80, "populated": 4, "total": 5, "missing": ["education"]},
      "preferences": {"completeness_pct": 60, "populated": 3, "total": 5, "missing": ["favorites", "style"]},
      "goals": {"completeness_pct": 50, "populated": 2, "total": 4, "missing": ["aspirations", "plans"]},
      "interests": {"completeness_pct": 75, "populated": 3, "total": 4, "missing": ["learning"]},
      "background": {"completeness_pct": 67, "populated": 2, "total": 3, "missing": ["journey"]}
    },
    "high_value_gaps": ["education", "long_term_goals", "skills"]
  }
  ```
- **And** `details=false` (default) returns simple completeness metrics for backward compatibility

## Tasks / Subtasks

- [ ] **Task 1:** Define expected fields per category (AC1)
  - [ ] Create `EXPECTED_PROFILE_FIELDS` constant in `profile_storage.py`
  - [ ] Define 5 fields per category (25 total) based on architecture.md
  - [ ] Add docstring explaining field definitions

- [ ] **Task 2:** Enhance completeness calculation logic (AC1, AC2)
  - [ ] Update `ProfileStorageService._update_completeness()` method
  - [ ] Calculate per-category completeness: `(category_populated / category_expected) * 100`
  - [ ] Calculate overall completeness: `(total_populated / total_expected) * 100`
  - [ ] Store category breakdown in new `category_completeness` JSONB column (or separate query)

- [ ] **Task 3:** Implement high-value gap identification (AC3)
  - [ ] Create `ProfileStorageService.identify_high_value_gaps()` method
  - [ ] Priority 1: Missing basics fields (name, age, location, occupation, education)
  - [ ] Priority 2: Fields with zero confidence (never extracted)
  - [ ] Priority 3: Fields relevant to populated goals (if goals exist)
  - [ ] Return sorted list of field names by priority

- [ ] **Task 4:** Add Redis caching for completeness (AC4)
  - [ ] Create `ProfileCompletenessCache` class or extend existing service
  - [ ] Implement `cache_completeness(user_id, completeness_data)` method
  - [ ] Key: `profile_completeness:{user_id}`, TTL: 3600 seconds
  - [ ] Implement `get_cached_completeness(user_id)` method
  - [ ] Invalidate cache on profile changes (call in `upsert_profile_fields`)

- [ ] **Task 5:** Enhance GET /v1/profile/completeness endpoint (AC5)
  - [ ] Add `details: bool = Query(False)` parameter
  - [ ] When `details=true`: return full breakdown with categories and high_value_gaps
  - [ ] When `details=false`: return existing simple response (backward compatible)
  - [ ] Check Redis cache first, fallback to database calculation

- [ ] **Task 6:** Trigger completeness recalculation (AC1)
  - [ ] Ensure `_update_completeness()` is called in all profile modification paths:
    - `upsert_profile_fields()` - already exists
    - `update_profile_field()` (manual edit) - verify
    - `delete_profile()` - verify/add
  - [ ] Add cache invalidation after each completeness update

- [ ] **Task 7:** Write unit tests
  - [ ] Test completeness calculation with various field counts
  - [ ] Test per-category breakdown accuracy
  - [ ] Test high-value gap identification priority ordering
  - [ ] Test Redis caching and invalidation
  - [ ] Test enhanced endpoint with details=true and details=false

- [ ] **Task 8:** Integration testing
  - [ ] Test full flow: add fields → verify completeness updates
  - [ ] Test cache hit/miss scenarios
  - [ ] Test backward compatibility (existing callers still work)

## Dev Notes

### Architecture Patterns

- **Service Layer:** Extend existing `ProfileStorageService` in `src/services/profile_storage.py`
- **Caching Pattern:** Follow existing Redis namespace pattern from architecture.md (AD-007)
- **API Pattern:** Extend existing router in `src/routers/profile.py`

### Database Schema Context

From architecture.md and Story 1.1:
- `user_profiles`: Contains `completeness_pct`, `populated_fields`, `total_fields` columns
- `profile_fields`: Key-value storage with `category` and `field_name`
- `profile_confidence_scores`: Has `overall_confidence` for gap detection

### Expected Profile Fields (from architecture.md)

```python
EXPECTED_PROFILE_FIELDS = {
    'basics': ['name', 'age', 'location', 'occupation', 'education'],
    'preferences': ['communication_style', 'likes', 'dislikes', 'favorites', 'style'],
    'goals': ['short_term', 'long_term', 'aspirations', 'plans', 'targets'],
    'interests': ['hobbies', 'topics', 'activities', 'passions', 'learning'],
    'background': ['history', 'experiences', 'skills', 'achievements', 'journey']
}
# Total: 25 fields (5 categories × 5 fields)
```

**Note:** Current implementation uses 21 total fields. Verify with existing code and adjust if needed.

### Learnings from Previous Story

**From Story 1.5: Profile CRUD API Endpoints (Status: done)**

- **Files Created**: `src/routers/profile.py`, `src/routers/__init__.py`, `tests/unit/test_profile_api.py`
- **Files Modified**: `src/app.py`, `src/services/profile_storage.py`
- **Key Patterns**:
  - Cursor results can be dict or tuple - handle both: `result['field'] if isinstance(result, dict) else result[0]`
  - Manual edits set all confidence scores to 100 (explicit source type)
  - FastAPI routing: specific routes (`/completeness`) before parameterized routes (`/{category}`)
  - source_type valid values: `explicit`, `implicit`, `inferred` (NOT `manual`)
- **Existing Method**: `_update_profile_metadata(cursor, user_id)` already calculates completeness
- **Completeness Calculation**: Currently `(populated_fields / 21 total) * 100`

**Reuse Patterns:**
- Extend existing `_update_profile_metadata()` or `_update_completeness()` method
- Use existing `get_redis_client()` from `src/dependencies/redis_client`
- Follow existing cache key pattern: `profile:{user_id}:v{namespace}`

[Source: docs/sprint-artifacts/1-5-profile-crud-api-endpoints.md#Dev-Agent-Record]

### Redis Caching Schema (from architecture.md AD-007)

```python
# Completeness cache
key = f"profile_completeness:{user_id}"
value = {
    "overall": 67.0,
    "categories": {
        "basics": {"pct": 80, "populated": 4, "total": 5, "missing": ["education"]},
        # ... other categories
    },
    "high_value_gaps": ["education", "long_term_goals", "skills"],
    "cached_at": "2025-12-12T10:00:00Z"
}
ttl = 3600  # 1 hour
```

### Testing Standards

- Unit tests for completeness calculation logic
- Unit tests for gap identification priority
- Integration tests with actual database (Docker environment)
- Test backward compatibility for existing `/v1/profile/completeness` callers
- Test Redis cache operations (set, get, invalidate)

### References

- [Source: docs/epics.md#Story-1.6]
- [Source: docs/architecture.md#AD-007-Profile-Caching]
- [Source: docs/architecture.md#Pattern-Profile-Storage-Service]
- [Source: src/services/profile_storage.py - Existing service]
- [Source: src/routers/profile.py - Existing router]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/1-6-profile-completeness-tracking.context.xml`

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

---

**Story Created:** 2025-12-12
**Epic:** 1 (Profile Foundation)
**Depends On:** Stories 1.1 (Database Schema), 1.5 (Profile CRUD API)
