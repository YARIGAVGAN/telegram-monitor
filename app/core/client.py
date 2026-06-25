from telethon import TelegramClient
import asyncio
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class TelegramClientWrapper:
    def __init__(self, api_id, api_hash, session_name='sessions/user'):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
        self.is_running = False

    async def start(self):
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start()
        self.is_running = True
        logger.info("Telegram client started")
        return self.client

    async def stop(self):
        if self.client:
            await self.client.disconnect()
            self.is_running = False
            logger.info("Telegram client stopped")

    async def run_until_disconnected(self):
        try:
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Disconnected: {e}")
            self.is_running = False