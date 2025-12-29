"""Tests for tier-based authentication and rate limiting."""
import pytest
from unittest.mock import AsyncMock, patch
import time

pytestmark = pytest.mark.asyncio


class TestHasPermission:
    """Test has_permission function."""

    def test_guest_has_guest(self):
        """Guest can access guest-level resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "guest") is True

    def test_guest_lacks_user(self):
        """Guest cannot access user-level resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "user") is False

    def test_guest_lacks_developer(self):
        """Guest cannot access developer resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "developer") is False

    def test_guest_lacks_admin(self):
        """Guest cannot access admin resources."""
        from src.services.firebase import has_permission
        assert has_permission("guest", "admin") is False

    def test_user_has_guest(self):
        """User can access guest resources."""
        from src.services.firebase import has_permission
        assert has_permission("user", "guest") is True

    def test_user_has_user(self):
        """User can access user resources."""
        from src.services.firebase import has_permission
        assert has_permission("user", "user") is True

    def test_user_lacks_developer(self):
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

    def test_admin_has_all(self):
        """Admin has all permissions."""
        from src.services.firebase import has_permission
        assert has_permission("admin", "guest") is True
        assert has_permission("admin", "user") is True
        assert has_permission("admin", "developer") is True
        assert has_permission("admin", "admin") is True


class TestGetRateLimit:
    """Test rate limit per tier."""

    def test_guest_rate_limit(self):
        """Guest has 5 req/min."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("guest") == 5

    def test_user_rate_limit(self):
        """User has 20 req/min."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("user") == 20

    def test_developer_rate_limit(self):
        """Developer has 50 req/min."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("developer") == 50

    def test_admin_rate_limit(self):
        """Admin has 1000 req/min."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("admin") == 1000

    def test_unknown_tier_gets_guest(self):
        """Unknown tier defaults to guest limit."""
        from src.services.firebase import get_rate_limit
        assert get_rate_limit("unknown") == 5


class TestRateLimiting:
    """Test rate limit enforcement."""

    def test_allows_under_limit(self, mock_state):
        """Requests under limit are allowed."""
        mock_state.set_tier(123, "guest")  # 10/min

        for i in range(5):
            allowed, _ = mock_state.check_rate_limit(123, "guest")
            assert allowed is True

    def test_rate_limit_clears_old(self, mock_state):
        """Old timestamps cleared from counter."""
        user_id = 789

        # Add old timestamps
        mock_state._rate_counters[user_id] = [time.time() - 120] * 20

        # New request allowed
        allowed, _ = mock_state.check_rate_limit(user_id, "guest")
        assert allowed is True


class TestTierCaching:
    """Test tier caching in StateManager."""

    async def test_tier_cache_hit(self, mock_state):
        """Cached tier returned without Firebase call."""
        mock_state.set_tier(123, "developer")
        tier = await mock_state.get_user_tier_cached(123)
        assert tier == "developer"

    async def test_tier_cache_miss(self, mock_state):
        """Missing tier returns guest."""
        tier = await mock_state.get_user_tier_cached(999)
        assert tier == "guest"

    async def test_tier_invalidation(self, mock_state):
        """Invalidated tier cleared."""
        mock_state.set_tier(123, "developer")
        await mock_state.invalidate_user_tier(123)
        tier = await mock_state.get_user_tier_cached(123)
        assert tier == "guest"


class TestAdminIdentification:
    """Test admin identification via ADMIN_TELEGRAM_ID."""

    async def test_admin_id_matches(self, mock_env, mock_state, admin_user):
        """User matching ADMIN_TELEGRAM_ID sees admin commands."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/help", user_dict, admin_user.id)

        assert "/grant" in result

    async def test_non_admin_denied(self, mock_env, mock_state, regular_user):
        """Non-admin denied admin commands."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/remind 1h test", user_dict, regular_user.id)

        assert "admin only" in result.lower()


class TestTierTransitions:
    """Test tier grant/revoke operations."""

    async def test_grant_tier_success(self, mock_env, mock_state, admin_user):
        """Admin can grant tier."""
        from main import handle_command

        with patch("src.services.firebase.set_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/grant 123456 developer", user_dict, admin_user.id)

        assert "developer" in result.lower() or "Granted" in result

    async def test_grant_invalid_id(self, mock_env, mock_state, admin_user):
        """Grant with invalid user ID fails."""
        from main import handle_command

        user_dict = {"id": admin_user.id}
        result = await handle_command("/grant not-a-number developer", user_dict, admin_user.id)

        assert "Invalid" in result

    async def test_revoke_tier_success(self, mock_env, mock_state, admin_user):
        """Admin can revoke tier."""
        from main import handle_command

        with patch("src.services.firebase.remove_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/revoke 123456", user_dict, admin_user.id)

        assert "Revoked" in result or "guest" in result.lower()


class TestPermissionBoundaries:
    """Test permission enforcement at boundaries."""

    async def test_traces_user_denied(self, mock_env, mock_state, regular_user):
        """/traces requires developer, user denied."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/traces", user_dict, regular_user.id)

        assert "denied" in result.lower() or "developer" in result.lower()

    async def test_task_guest_denied(self, mock_env, mock_state, guest_user):
        """/task requires user tier, guest denied."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": guest_user.id}
            result = await handle_command("/task abc123", user_dict, guest_user.id)

        assert "denied" in result.lower() or "tier" in result.lower()
