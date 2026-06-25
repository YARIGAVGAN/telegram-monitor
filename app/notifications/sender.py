import aiohttp
import asyncio
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class NotificationSender:
    def __init__(self, bot_token, user_id):
        self.bot_token = bot_token
        self.user_id = user_id
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async def send(self, text, retries=5):
        data = {
            'chat_id': self.user_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.url, json=data, timeout=5) as resp:
                        if resp.status == 200:
                            logger.info("Notification sent successfully")
                            return True
                        else:
                            logger.warning(f"Bot API error {resp.status}, attempt {attempt+1}")
            except Exception as e:
                logger.error(f"Send attempt {attempt+1} failed: {e}")
            await asyncio.sleep(2 ** attempt)  # экспоненциальная задержка
        logger.error("Failed to send notification after all retries")
        return False