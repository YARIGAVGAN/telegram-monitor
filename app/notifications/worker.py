
from app.notifications.queue import notification_queue
from app.notifications.sender import NotificationSender
from app.security.ratelimit import RateLimiter
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

async def worker_loop(sender: NotificationSender, rate_limiter: RateLimiter):
    """Постоянно забирает уведомления из очереди и отправляет их"""
    while True:
        item = await notification_queue.get()
        try:
            if rate_limiter.allow():
                await sender.send(item['text'])
            else:
                logger.warning("Rate limit exceeded, notification dropped")
        except Exception as e:
            logger.error(f"Unexpected error in worker: {e}")
        finally:
            notification_queue.task_done()