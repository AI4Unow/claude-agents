#!/usr/bin/env python3
"""One-time authentication script for Telethon E2E tests.

Run this interactively to create the session file:
    python3 tests/e2e/auth_session.py

After authentication, the session file is saved and tests can run non-interactively.
"""
import asyncio
import os
from pathlib import Path

async def main():
    from telethon import TelegramClient

    api_id = int(os.environ.get("TELEGRAM_API_ID", "37530910"))
    api_hash = os.environ.get("TELEGRAM_API_HASH", "e24392516d50e9694aac8febb7b2a396")
    phone = os.environ.get("TELEGRAM_PHONE", "+84934461188")

    session_file = Path(__file__).parent / "test_session"

    print(f"Creating Telethon session...")
    print(f"  API ID: {api_id}")
    print(f"  Phone: {phone}")
    print(f"  Session: {session_file}")

    client = TelegramClient(str(session_file), api_id, api_hash)

    await client.start(phone=phone)

    me = await client.get_me()
    print(f"\n✅ Authenticated as: {me.first_name} (@{me.username})")
    print(f"Session saved to: {session_file}.session")
    print("\nYou can now run E2E tests without entering the code again.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
