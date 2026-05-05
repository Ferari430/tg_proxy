"""One-time script to authorize a Telegram account and save the session file.

Usage:
    python authorize.py                   # authorizes sessions/account1.session
    python authorize.py account2.session  # authorizes sessions/account2.session
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

session_name = sys.argv[1] if len(sys.argv) > 1 else "account1.session"
session_path = Path("sessions") / session_name


async def main() -> None:
    session_path.parent.mkdir(exist_ok=True)
    client = TelegramClient(str(session_path), API_ID, API_HASH)

    # start() handles the full auth flow interactively:
    # phone number → SMS/app code → 2FA password (if set)
    await client.start()

    me = await client.get_me()
    print(f"✓ Authorized as: {me.first_name} (@{me.username}), id={me.id}")
    print(f"  Session saved to: {session_path}")

    await client.disconnect()


asyncio.run(main())
