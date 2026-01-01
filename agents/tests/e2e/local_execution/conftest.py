"""Local executor fixtures."""
import subprocess
import pytest
import asyncio
import os


@pytest.fixture(scope="module")
async def executor_process():
    """Start local-executor for tests.

    Only starts if LOCAL_EXECUTOR_ENABLED env is set.
    """
    if not os.environ.get("LOCAL_EXECUTOR_ENABLED"):
        pytest.skip("Local executor not enabled (set LOCAL_EXECUTOR_ENABLED=1)")

    # Start executor
    proc = subprocess.Popen(
        ["python3", "agents/scripts/local-executor.py", "--poll", "--interval", "5"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for startup
    await asyncio.sleep(2)

    yield proc

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
