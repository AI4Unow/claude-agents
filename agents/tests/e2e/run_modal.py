#!/usr/bin/env python3
"""Run E2E tests on Modal with secrets.

Usage:
    modal run agents/tests/e2e/run_modal.py
    modal run agents/tests/e2e/run_modal.py --test-filter "circuit"
"""
import modal
import subprocess
import sys

app = modal.App("e2e-test-runner")

# Image with test dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "telethon>=1.34",
)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("telegram-e2e-test"),
        modal.Secret.from_name("admin-credentials"),
    ],
    timeout=600,
)
def run_e2e_tests(test_filter: str = None, verbose: bool = True) -> dict:
    """Run E2E tests with Modal secrets injected."""
    import os

    # Log available env vars (masked)
    env_vars = [
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "TELEGRAM_PHONE",
        "TELEGRAM_BOT_USERNAME",
        "ADMIN_API_TOKEN",
    ]

    print("Environment check:")
    for var in env_vars:
        val = os.environ.get(var)
        if val:
            print(f"  {var}: {'*' * min(len(val), 8)}...")
        else:
            print(f"  {var}: NOT SET")

    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        "agents/tests/e2e/",
        "-v" if verbose else "-q",
        "--tb=short",
    ]

    if test_filter:
        cmd.extend(["-k", test_filter])

    print(f"\nRunning: {' '.join(cmd)}")
    print("-" * 50)

    result = subprocess.run(cmd, capture_output=True, text=True)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@app.function(
    secrets=[
        modal.Secret.from_name("telegram-e2e-test"),
        modal.Secret.from_name("admin-credentials"),
    ],
)
def print_env_vars() -> dict:
    """Print available environment variables for debugging."""
    import os

    env_vars = {
        "TELEGRAM_API_ID": os.environ.get("TELEGRAM_API_ID", "NOT SET"),
        "TELEGRAM_API_HASH": os.environ.get("TELEGRAM_API_HASH", "NOT SET")[:8] + "..." if os.environ.get("TELEGRAM_API_HASH") else "NOT SET",
        "TELEGRAM_PHONE": os.environ.get("TELEGRAM_PHONE", "NOT SET"),
        "TELEGRAM_BOT_USERNAME": os.environ.get("TELEGRAM_BOT_USERNAME", "NOT SET"),
        "ADMIN_API_TOKEN": "SET" if os.environ.get("ADMIN_API_TOKEN") else "NOT SET",
    }

    return env_vars


@app.local_entrypoint()
def main(test_filter: str = None, check_env: bool = False):
    """Run E2E tests or check environment."""
    if check_env:
        print("Checking Modal secrets...")
        env_vars = print_env_vars.remote()
        print("\nEnvironment variables:")
        for key, val in env_vars.items():
            print(f"  {key}: {val}")
        return

    print("Running E2E tests on Modal...")
    result = run_e2e_tests.remote(test_filter=test_filter)

    print(result["stdout"])
    if result["stderr"]:
        print("STDERR:", result["stderr"])

    print(f"\nExit code: {result['returncode']}")
    sys.exit(result["returncode"])
