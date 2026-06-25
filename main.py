import asyncio
from app.config.loader import load_config, load_rules, load_chats
from app.utils.logger import setup_logger
from app.core.client import TelegramClientWrapper
from app.core.handlers import register_handlers
from app.core.processor import MessageProcessor
from app.filtering.rule_engine import RuleEngine
from app.security.dedup import Deduplicator
from app.security.ratelimit import RateLimiter
from app.notifications.queue import notification_queue
from app.notifications.sender import NotificationSender
from app.monitoring.health import start_health_server
from app.monitoring import metrics

logger = setup_logger(__name__)

async def worker_loop(queue, sender, rate_limiter):
    """Воркер очереди уведомлений (без метрик)"""
    while True:
        item = await queue.get()
        if rate_limiter.allow():
            await sender.send(item['text'])
        else:
            logger.warning("Rate limit exceeded, dropping notification")
        queue.task_done()

async def main():
    config = load_config()
    rules_data = load_rules()
    whitelist, blacklist = load_chats()

    rule_engine = RuleEngine(rules_data)
    deduplicator = Deduplicator()
    rate_limiter = RateLimiter(max_per_minute=config['limits']['notifications_per_minute'])
    sender = NotificationSender(
        bot_token=config['bot']['token'],
        user_id=config['notifications']['user_id']
    )
    processor = MessageProcessor(rule_engine, deduplicator, whitelist, blacklist, config['notifications']['user_id'])

    # Запуск health-сервера
    asyncio.create_task(start_health_server(port=config['health']['port']))

    # Запуск метрик (опционально, можно закомментировать, если не используется)
    # try:
    #     metrics.start_metrics_server(9090)
    # except Exception as e:
    #     logger.warning(f"Metrics server failed: {e}")

    # Запуск воркера очереди
    asyncio.create_task(worker_loop(notification_queue, sender, rate_limiter))

    # Подключение клиента Telethon
    client_wrapper = TelegramClientWrapper(
        api_id=config['telegram']['api_id'],
        api_hash=config['telegram']['api_hash'],
        session_name='sessions/user'
    )
    client = await client_wrapper.start()

    # Регистрация обработчика
    register_handlers(client, processor.process)

    logger.info("Service started, waiting for messages...")
    await client_wrapper.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")