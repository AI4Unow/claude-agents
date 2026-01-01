#!/usr/bin/env python3
"""Export Modal secrets to local environment for E2E testing.

Usage:
    eval $(modal run agents/tests/e2e/export_secrets.py)
    pytest agents/tests/e2e/ -v
"""
import modal

app = modal.App("export-secrets")


@app.function(
    secrets=[
        modal.Secret.from_name("telegram-e2e-test"),
        modal.Secret.from_name("admin-credentials"),
    ],
)
def fetch_env() -> dict:
    """Fetch environment variables from Modal secrets."""
    import os
    return {
        "TELEGRAM_API_ID": os.environ.get("TELEGRAM_API_ID", ""),
        "TELEGRAM_API_HASH": os.environ.get("TELEGRAM_API_HASH", ""),
        "TELEGRAM_PHONE": os.environ.get("TELEGRAM_PHONE", ""),
        "TELEGRAM_BOT_USERNAME": os.environ.get("TELEGRAM_BOT_USERNAME", ""),
        # admin-credentials uses ADMIN_TOKEN, we export as ADMIN_API_TOKEN for tests
        "ADMIN_API_TOKEN": os.environ.get("ADMIN_TOKEN", ""),
    }


@app.local_entrypoint()
def main():
    """Export secrets as shell export commands."""
    secrets = fetch_env.remote()
    for key, val in secrets.items():
        if val:
            print(f"export {key}='{val}'")
    # Also print API base URL
    print("export API_BASE_URL='https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run'")
