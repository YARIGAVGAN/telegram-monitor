from app.filtering.normalizer import normalize
from app.filtering.rule_engine import RuleEngine
from app.security.dedup import Deduplicator
from app.notifications.queue import push
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

MAX_TEXT_LENGTH = 3800

class MessageProcessor:
    def __init__(self, rule_engine: RuleEngine, deduplicator: Deduplicator,
                 whitelist: list, blacklist: list, user_id: int):
        self.rule_engine= rule_engine
        self.deduplicator = deduplicator
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.user_id = user_id

    async def process(self, message):
        text = message.text or ''
        if not text:
            return

        normalized = normalize(text)

        chat_id = message.chat_id
        if chat_id in self.blacklist:
            return
        if self.whitelist and chat_id not in self.whitelist:
            return

        if self.deduplicator.is_seen(chat_id, message.id):
            return
        self.deduplicator.mark_seen(chat_id, message.id)

        if not self.rule_engine.match(normalized):
            return

        logger.info(f"Match found in chat {chat_id}: {normalized[:50]}...")

        # ---------- Получаем сущности для ссылок ----------
        try:
            chat_entity = await message.client.get_entity(chat_id)
            sender_entity = await message.client.get_entity(message.sender_id)
        except Exception as e:
            logger.error(f"Error getting entities: {e}")
            notif_text = (
                f"🔔 <b>Найдено ключевое слово</b>\n"
                f"📌 <b>Чат:</b> {chat_id}\n"
                f"👤 <b>Отправитель:</b> {message.sender_id}\n"
                f"📝 <b>Текст:</b>\n"
                f"{text[:MAX_TEXT_LENGTH]}{'…' if len(text) > MAX_TEXT_LENGTH else ''}"
            )
            await push({'text': notif_text})
            return

        # ---------- Определяем имя и ссылку на отправителя ----------
        # Для пользователей (User) используем first_name, для каналов (Channel) — title
        if hasattr(sender_entity, 'first_name'):
            sender_name = sender_entity.first_name or sender_entity.username or str(message.sender_id)
        elif hasattr(sender_entity, 'title'):
            sender_name = sender_entity.title or sender_entity.username or str(message.sender_id)
        else:
            sender_name = str(message.sender_id)

        if hasattr(sender_entity, 'username') and sender_entity.username:
            sender_link = f"https://t.me/{sender_entity.username}"
        else:
            sender_link = None

        # ---------- Ссылка на чат ----------
        if hasattr(chat_entity, 'username') and chat_entity.username:
            chat_link = f"https://t.me/{chat_entity.username}"
        else:
            chat_id_abs = str(chat_id).replace('-', '')
            chat_link = f"https://t.me/c/{chat_id_abs}"

        # ---------- Ссылка на конкретное сообщение ----------
        if hasattr(chat_entity, 'username') and chat_entity.username:
            msg_link = f"https://t.me/{chat_entity.username}/{message.id}"
        else:
            chat_id_abs = str(chat_id).replace('-', '')
            msg_link = f"https://t.me/c/{chat_id_abs}/{message.id}"

        chat_title = chat_entity.title if hasattr(chat_entity, 'title') else str(chat_id)

        # ---------- Подготовка текста сообщения с обрезкой ----------
        if len(text) > MAX_TEXT_LENGTH:
            display_text = text[:MAX_TEXT_LENGTH] + "\n\n… (сообщение обрезано, слишком длинное)"
        else:
            display_text = text

        # ---------- Сборка уведомления ----------
        notif_text = (
            f"🔔 <b>Найдено ключевое слово</b>\n"
            f"📌 <b>Чат:</b> <a href='{chat_link}'>{chat_title}</a>\n"
            f"👤 <b>Отправитель:</b> "
        )
        if sender_link:
            notif_text += f"<a href='{sender_link}'>{sender_name}</a>\n"
        else:
            notif_text += f"{sender_name}\n"
        notif_text += f"🔗 <b>Ссылка на сообщение:</b> <a href='{msg_link}'>перейти</a>\n"
        notif_text += f"📝 <b>Текст:</b>\n{display_text}"

        # ---------- Отправка через бота ----------
        await push({'text': notif_text})