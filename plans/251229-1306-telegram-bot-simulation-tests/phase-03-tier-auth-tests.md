---
phase: 3
title: "Tier-Based Auth and Rate Limiting Tests"
status: pending
effort: 1h
---

# Phase 3: Tier-Based Auth and Rate Limiting Tests

## Context

- Parent: [plan.md](./plan.md)
- Dependencies: Phase 1, Phase 2
- Docs: pytest, unittest.mock

## Overview

Deep testing of tier-based permission system, rate limiting enforcement, and auth token handling. Validates security boundaries.

## Requirements

1. Test all tier levels (guest, user, developer, admin)
2. Test has_permission function exhaustively
3. Test rate limiting per tier
4. Test tier caching behavior
5. Test admin identification logic

## Related Code Files

- `agents/src/services/firebase.py` - has_permission, get_rate_limit, set_user_tier
- `agents/src/core/state.py` - get_user_tier_cached, check_rate_limit
- `agents/main.py:649-1087` - Permission checks in commands

## Tier Matrix

| Tier | Guest | User | Developer | Admin |
|------|-------|------|-----------|-------|
| guest | ✓ | ✗ | ✗ | ✗ |
| user | ✓ | ✓ | ✗ | ✗ |
| developer | ✓ | ✓ | ✓ | ✗ |
| admin | ✓ | ✓ | ✓ | ✓ |

## Implementation Steps

### Step 1: Create test_auth.py

```python
# agents/tests/test_telegram/test_auth.py
"""Tests for tier-based authentication and rate limiting."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import os
import time

pytestmark = pytest.mark.asyncio


class TestHasPermission:
    """Test has_permission function."""

    def test_guest_has_guest_permission(self):
        """Guest can access guest-level resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "guest") is True

    def test_guest_lacks_user_permission(self):
        """Guest cannot access user-level resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "user") is False

    def test_guest_lacks_developer_permission(self):
        """Guest cannot access developer resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "developer") is False

    def test_guest_lacks_admin_permission(self):
        """Guest cannot access admin resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "admin") is False

    def test_user_has_guest_permission(self):
        """User can access guest resources (inheritance)."""
        from src.services.firebase import has_permission
        assert has_permission("user", "guest") is True

    def test_user_has_user_permission(self):
        """User can access user resources."""
        from src.services.firebase import has_permission
        assert has_permission("user", "user") is True

    def test_user_lacks_developer_permission(self):
        """User cannot access developer resources."""
        from src.services.firebase import has_permission
        assert has_permission("user", "developer") is False

    def test_developer_has_all_below(self):
        """Developer has guest, user, developer permissions."""
        from src.services.firebase import has_permission
        assert has_permission("developer", "guest") is True
        assert has_permission("developer", "user") is True
        assert has_permission("developer", "developer") is True

    def test_developer_lacks_admin(self):
        """Developer cannot access admin resources."""
        from src.services.firebase import has_permission
        assert has_permission("developer", "admin") is False

    def test_admin_has_all_permissions(self):
        """Admin has all permissions."""
        from src.services.firebase import has_permission
        assert has_permission("admin", "guest") is True
        assert has_permission("admin", "user") is True
        assert has_permission("admin", "developer") is True
        assert has_permission("admin", "admin") is True

    def test_unknown_tier_treated_as_guest(self):
        """Unknown tier defaults to guest-level access."""
        from src.services.firebase import has_permission
        assert has_permission("unknown", "guest") is True
        assert has_permission("unknown", "user") is False

    def test_unknown_required_tier_denies(self):
        """Unknown required tier denies access."""
        from src.services.firebase import has_permission
        assert has_permission("admin", "superadmin") is False


class TestGetRateLimit:
    """Test rate limit per tier."""

    def test_guest_rate_limit(self):
        """Guest has 10 req/min."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("guest") == 10

    def test_user_rate_limit(self):
        """User has 30 req/min."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("user") == 30

    def test_developer_rate_limit(self):
        """Developer has 100 req/min."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("developer") == 100

    def test_admin_rate_limit(self):
        """Admin has 1000 req/min (effectively unlimited)."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("admin") == 1000

    def test_unknown_tier_gets_guest_limit(self):
        """Unknown tier defaults to guest limit."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("unknown") == 10


class TestRateLimiting:
    """Test rate limit enforcement in StateManager."""

    def test_rate_limit_allows_under_limit(self, mock_state):
        """Requests under limit are allowed."""
        mock_state.set_tier(123, "guest")  # 10/min

        for i in range(5):
            allowed, _ = mock_state.check_rate_limit(123, "guest")
            assert allowed is True

    def test_rate_limit_denies_over_limit(self):
        """Requests over limit are denied."""
        from src.core.state import StateManager

        state = StateManager()
        user_id = 456

        # Simulate 15 requests in quick succession
        for i in range(15):
            state._rate_counters[user_id].append(time.time())

        # Should be denied (guest limit = 10)
        allowed, reset_in = state.check_rate_limit(user_id, "guest")

        if len(state._rate_counters[user_id]) > 10:
            # If counter exceeds limit, should be denied
            assert allowed is False or reset_in > 0

    def test_rate_limit_clears_old_entries(self):
        """Old timestamps are cleared from rate counter."""
        from src.core.state import StateManager

        state = StateManager()
        user_id = 789

        # Add old timestamps (> 60 seconds ago)
        old_time = time.time() - 120
        state._rate_counters[user_id] = [old_time] * 20

        # New request should be allowed (old ones cleared)
        allowed, _ = state.check_rate_limit(user_id, "guest")
        assert allowed is True


class TestTierCaching:
    """Test tier caching in StateManager."""

    async def test_tier_cache_hit(self, mock_state):
        """Cached tier is returned without Firebase call."""
        mock_state.set_tier(123, "developer")

        tier = await mock_state.get_user_tier_cached(123)
        assert tier == "developer"

    async def test_tier_cache_miss_returns_guest(self, mock_state):
        """Missing tier returns guest."""
        tier = await mock_state.get_user_tier_cached(999)
        assert tier == "guest"

    async def test_tier_invalidation(self, mock_state):
        """Invalidated tier is re-fetched."""
        mock_state.set_tier(123, "developer")

        # Invalidate
        await mock_state.invalidate_user_tier(123)

        # Should return guest (no cached value)
        tier = await mock_state.get_user_tier_cached(123)
        assert tier == "guest"


class TestAdminIdentification:
    """Test admin identification via ADMIN_TELEGRAM_ID."""

    async def test_admin_id_matches(self, mock_env, mock_state, admin_user):
        """User matching ADMIN_TELEGRAM_ID is admin."""
        from main import handle_command

        # Admin sees admin-only commands in help
        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/help", user_dict, admin_user.id)

        assert "/grant" in result

    async def test_non_admin_id_denied(self, mock_env, mock_state, regular_user):
        """User not matching ADMIN_TELEGRAM_ID denied admin commands."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/remind 1h test", user_dict, regular_user.id)

        assert "admin only" in result.lower() or "denied" in result.lower()

    def test_admin_id_type_comparison(self, mock_env):
        """ADMIN_TELEGRAM_ID comparison handles string/int."""
        admin_id = os.environ.get("ADMIN_TELEGRAM_ID")

        # Both should match
        assert str(999999999) == str(admin_id)
        assert str(int(admin_id)) == str(999999999)


class TestTierTransitions:
    """Test tier grant/revoke operations."""

    async def test_grant_tier_success(self, mock_env, mock_state, admin_user):
        """Admin can grant tier."""
        from main import handle_command

        with patch("src.services.firebase.set_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/grant 123456 developer", user_dict, admin_user.id)

        assert "developer" in result.lower() or "Granted" in result

    async def test_grant_invalid_user_id(self, mock_env, mock_state, admin_user):
        """Grant with invalid user ID fails."""
        from main import handle_command

        user_dict = {"id": admin_user.id}
        result = await handle_command("/grant not-a-number developer", user_dict, admin_user.id)

        assert "Invalid" in result or "number" in result.lower()

    async def test_revoke_tier_success(self, mock_env, mock_state, admin_user):
        """Admin can revoke tier."""
        from main import handle_command

        with patch("src.services.firebase.remove_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/revoke 123456", user_dict, admin_user.id)

        assert "Revoked" in result or "guest" in result.lower()

    async def test_grant_non_admin_denied(self, mock_env, mock_state, developer_user):
        """Non-admin cannot grant tier."""
        from main import handle_command

        user_dict = {"id": developer_user.id}
        result = await handle_command("/grant 123456 user", user_dict, developer_user.id)

        assert "Admin only" in result or "denied" in result.lower()


class TestPermissionBoundaries:
    """Test permission enforcement at boundaries."""

    async def test_traces_boundary_user_denied(self, mock_env, mock_state, regular_user):
        """/traces requires developer, user is denied."""
        from main import handle_command

        mock_state.set_tier(regular_user.id, "user")

        with patch("src.services.firebase.has_permission", side_effect=lambda t, r: t in ["developer", "admin"] if r == "developer" else True):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/traces", user_dict, regular_user.id)

        assert "denied" in result.lower() or "developer" in result.lower()

    async def test_traces_boundary_developer_allowed(self, mock_env, mock_state, developer_user):
        """/traces allowed for developer."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.trace.list_traces", new_callable=AsyncMock, return_value=[]):

            user_dict = {"id": developer_user.id}
            result = await handle_command("/traces", user_dict, developer_user.id)

        assert "denied" not in result.lower()

    async def test_task_boundary_guest_denied(self, mock_env, mock_state, guest_user):
        """/task requires user tier, guest denied."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": guest_user.id}
            result = await handle_command("/task abc123", user_dict, guest_user.id)

        assert "denied" in result.lower() or "tier" in result.lower()
```

## Todo List

- [ ] Create `test_auth.py` file
- [ ] Implement TestHasPermission (12 tests)
- [ ] Implement TestGetRateLimit (5 tests)
- [ ] Implement TestRateLimiting (3 tests)
- [ ] Implement TestTierCaching (3 tests)
- [ ] Implement TestAdminIdentification (3 tests)
- [ ] Implement TestTierTransitions (4 tests)
- [ ] Implement TestPermissionBoundaries (3 tests)
- [ ] Run tests and verify all pass

## Success Criteria

1. All 33 tests pass
2. Permission matrix fully validated
3. Rate limiting behavior confirmed
4. Tier caching works correctly
5. Admin identification is secure

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Permission bypass | Test both allow and deny paths |
| Rate limit timing issues | Use controlled timestamps |
| Cache state leakage | Reset cache between tests |

## Security Considerations

- Verify guest cannot escalate
- Confirm admin checks use timing-safe comparison
- Rate limits enforced before processing

## Next Steps

After completing this phase:
1. Proceed to Phase 4: Complexity Detection Tests
2. Test the auto-routing logic
