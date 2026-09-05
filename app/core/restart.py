"""
Модуль авторестарта с уведомлениями о критических ошибках
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import Callable, Awaitable, Optional
from app.utils.logger import setup_logger
from app.web.dashboard import update_parser_status
import telethon

logger = setup_logger(__name__)

MAX_RESTART_ATTEMPTS = 3
RESTART_DELAY_SECONDS = 5


class RestartNotifier:
    """Отправляет уведомления о проблемах с рестартом"""
    
    def __init__(self, bot_token: str, user_id: int):
        self.bot_token = bot_token
        self.user_id = user_id
        self._client: Optional[telethon.TelegramClient] = None
    
    async def _get_client(self) -> telethon.TelegramClient:
        """Получить или создать клиента для отправки уведомлений"""
        if self._client is None or not self._client.is_connected():
            from app.core.client import TelegramClientWrapper
            wrapper = TelegramClientWrapper(
                api_id=int(os.getenv('API_ID', 36506376)),
                api_hash=os.getenv('API_HASH', 'd961313427bf4df9daf5b6970c6bc726'),
                session_name='sessions/restart_notifier'
            )
            try:
                self._client = await wrapper.start()
            except Exception as e:
                logger.error(f"Failed to create notification client: {e}")
                raise
        return self._client
    
    async def send_restart_failed_notification(self, error: str, attempts: int):
        """Отправить уведомление о невозможности рестарта"""
        message = (
            f"🚨 <b>КРИТИЧЕСКАЯ ОШИБКА: АВТОРЕСТАРТ НЕ УДАЛСЯ</b>\n\n"
            f"📊 <b>Попыток рестарта:</b> {attempts}\n"
            f"⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"❌ <b>Ошибка:</b>\n"
            f"<code>{error[:3000]}</code>\n\n"
            f"Требуется ручное вмешательство!"
        )
        
        try:
            client = await self._get_client()
            await client.send_message(self.user_id, message, parse_mode='html')
            logger.info("Sent restart failed notification to user")
        except Exception as e:
            logger.error(f"Failed to send restart notification: {e}")
    
    async def send_restart_attempt_notification(self, attempt: int, error: str):
        """Отправить уведомление о попытке рестарта"""
        message = (
            f"⚠️ <b>Попытка авторестарта #{attempt}</b>\n\n"
            f"⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"❌ <b>Причина:</b>\n"
            f"<code>{error[:500]}</code>"
        )
        
        try:
            client = await self._get_client()
            await client.send_message(self.user_id, message, parse_mode='html')
            logger.info(f"Sent restart attempt #{attempt} notification")
        except Exception as e:
            logger.error(f"Failed to send restart attempt notification: {e}")


class AutoRestarter:
    """Управляет авторестартом приложения при крашах"""
    
    def __init__(self, bot_token: str, user_id: int, max_attempts: int = MAX_RESTART_ATTEMPTS):
        self.notifier = RestartNotifier(bot_token, user_id)
        self.max_attempts = max_attempts
        self.current_attempt = 0
        self.last_start_time: Optional[datetime] = None
        self.rapid_restart_threshold = 60  # секунд - если рестарты чаще, считаем это проблемой
    
    async def run_with_restarts(self, main_func: Callable[[], Awaitable]):
        """
        Запускает main_func с автоматическим рестартом при падениях.
        Если рестарты происходят слишком часто или превышают лимит,
        отправляется уведомление и функция завершается.
        """
        while True:
            try:
                self.current_attempt = 0
                self.last_start_time = datetime.now()
                
                # Обновляем статус парсера
                update_parser_status(
                    status='running',
                    started_at=self.last_start_time.isoformat(),
                    last_error=None
                )
                
                logger.info("Starting parser...")
                await main_func()
                
                # Если main_func завершилась без исключения, это нормально (пользователь нажал Ctrl+C)
                logger.info("Parser stopped gracefully")
                update_parser_status(status='stopped')
                break
                
            except Exception as e:
                error_str = str(e)
                logger.exception(f"Parser crashed: {e}")
                
                self.current_attempt += 1
                
                # Проверяем, не слишком ли частые рестарты
                now = datetime.now()
                if self.last_start_time:
                    time_since_start = (now - self.last_start_time).total_seconds()
                    if time_since_start < self.rapid_restart_threshold:
                        logger.warning(f"Rapid restart detected ({time_since_start:.1f}s since start)")
                
                # Обновляем статус
                update_parser_status(
                    status='restarting',
                    last_error=error_str,
                    restarts=self.current_attempt,
                    last_restart_at=now.isoformat()
                )
                
                if self.current_attempt >= self.max_attempts:
                    # Превышено максимальное количество попыток
                    logger.error(f"Max restart attempts ({self.max_attempts}) reached, giving up")
                    
                    # Отправляем уведомление
                    try:
                        await self.notifier.send_restart_failed_notification(error_str, self.current_attempt)
                    except Exception as notif_error:
                        logger.error(f"Failed to send notification: {notif_error}")
                    
                    update_parser_status(status='stopped')
                    raise  # Пробрасываем исключение дальше
                    
                else:
                    # Пытаемся сделать рестарт
                    logger.info(f"Attempting restart #{self.current_attempt}/{self.max_attempts} in {RESTART_DELAY_SECONDS}s...")
                    
                    # Отправляем уведомление о попытке рестарта (опционально, можно закомментировать)
                    try:
                        await self.notifier.send_restart_attempt_notification(self.current_attempt, error_str)
                    except Exception as notif_error:
                        logger.error(f"Failed to send attempt notification: {notif_error}")
                    
                    update_parser_status(status='restarting')
                    
                    # Ждём перед рестартом
                    await asyncio.sleep(RESTART_DELAY_SECONDS)
                    
                    # Сбрасываем счётчик если прошло достаточно времени
                    if self.last_start_time:
                        time_since_start = (now - self.last_start_time).total_seconds()
                        if time_since_start > 300:  # 5 минут
                            logger.info("Resetting restart counter (enough time passed)")
                            self.current_attempt = 0


async def run_with_auto_restart(main_func: Callable[[], Awaitable], bot_token: str, user_id: int):
    """
    Обёртка для запуска основного приложения с авторестартом.
    
    Usage:
        async def main():
            # ваш код
        
        await run_with_auto_restart(main, bot_token, user_id)
    """
    restarter = AutoRestarter(bot_token, user_id)
    await restarter.run_with_restarts(main_func)
