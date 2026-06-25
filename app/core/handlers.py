from telethon import events
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

def register_handlers(client, process_message_callback):
    @client.on(events.NewMessage)
    async def handler(event):
        if event.out:
            return
        await process_message_callback(event.message)
    logger.info("Handlers registered")