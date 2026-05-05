"""Quick check: are API_ID / API_HASH valid?

Connects to Telegram without logging in.
Valid credentials → "OK".
Wrong credentials → ApiIdInvalidError.
"""
import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import ApiIdInvalidError

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]


async def main() -> None:
    client = TelegramClient("check_session", API_ID, API_HASH)
    try:
        await client.connect()
        print("✓ API_ID / API_HASH valid — connected to Telegram")
    except ApiIdInvalidError:
        print("✗ Invalid API_ID or API_HASH")
    finally:
        await client.disconnect()
        # Remove the temp session file
        for f in ("check_session.session", "check_session.session-journal"):
            if os.path.exists(f):
                os.remove(f)


asyncio.run(main())
