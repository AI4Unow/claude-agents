"""Integration test fixtures."""
import pytest


@pytest.fixture(scope="module")
def integration_cleanup():
    """Cleanup fixture for integration tests.

    Ensures test state is cleaned up between test modules.
    """
    # Setup - nothing needed
    yield

    # Teardown - clean any test artifacts
    # (Add specific cleanup as needed)
    pass
