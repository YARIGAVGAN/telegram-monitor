from telethon import events
from app.utils.logger import setup_logger
from app.web.dashboard import update_parser_status, parser_status

logger = setup_logger(__name__)

def register_handlers(client, process_message_callback):
    @client.on(events.NewMessage)
    async def handler(event):
        if event.out:
            return
        
        # Обновляем счётчик обработанных сообщений
        current_processed = parser_status.get('messages_processed', 0)
        update_parser_status(messages_processed=current_processed + 1)
        
        await process_message_callback(event.message)
    logger.info("Handlers registered")