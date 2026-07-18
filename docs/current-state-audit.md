# Current State Audit

Дата аудита: 2026-07-18.

Область аудита: структура проекта, запуск, зависимости, конфигурация, Telegram-клиент, `events.NewMessage`, движок правил, очередь и отправка уведомлений, дедупликация, логирование, health endpoint, Docker, секреты и пользовательские данные.

## 1. Текущая архитектура

Проект представляет собой небольшой async-сервис на Python с Telethon:

- `main.py` - точка запуска, собирает зависимости вручную, запускает health server, воркер уведомлений и Telethon-клиент.
- `app/config/loader.py` - загрузка YAML-конфигов из `config/` и частичная подмена значениями из переменных окружения.
- `app/core/client.py` - тонкая обертка над `telethon.TelegramClient`.
- `app/core/handlers.py` - регистрация `events.NewMessage`.
- `app/core/processor.py` - основной обработчик сообщения: фильтры чатов, дедупликация, правила, построение HTML-уведомления.
- `app/filtering/rule_engine.py` и `app/filtering/normalizer.py` - простой rule engine с `AND`/`OR` и нормализация текста.
- `app/notifications/queue.py` - глобальная `asyncio.Queue(maxsize=1000)`.
- `app/notifications/sender.py` - отправка в Telegram Bot API через `aiohttp`.
- `app/notifications/worker.py` - альтернативный воркер, но он не используется из `main.py`.
- `app/security/dedup.py` - in-memory LRU-дедупликация по `chat_id_message_id`.
- `app/security/ratelimit.py` - in-memory sliding window limiter на одну глобальную очередь.
- `app/monitoring/health.py` - `aiohttp` HTTP-сервер с `/health` и `/metrics`.
- `Dockerfile` и `docker-compose.yml` - контейнеризация, монтирование `sessions`, `logs`, `config`, `.env`.

В репозитории также присутствуют пользовательские и локальные артефакты: `.env`, `sessions/user.session`, `logs/app.log`, `.venv/`, `.idea/`, `Dockerfile.zip`, `telegram-monitor.zip`. По `git ls-files` отслеживаются `.idea/*` и `config/config.yaml`; `.env`, `logs/`, `*.session` игнорируются, но физически лежат в рабочей копии.

## 2. Основной поток обработки сообщения

1. `asyncio.run(main())` запускает приложение из `main.py`.
2. `load_config()`, `load_rules()`, `load_chats()` читают YAML-конфиги.
3. Создаются `RuleEngine`, `Deduplicator`, `RateLimiter`, `NotificationSender`, `MessageProcessor`.
4. `main.py` через `asyncio.create_task()` запускает `start_health_server()` и локальный `worker_loop()`.
5. `TelegramClientWrapper.start()` создает `TelegramClient('sessions/user', api_id, api_hash)` и вызывает `client.start()`.
6. `register_handlers(client, processor.process)` регистрирует `@client.on(events.NewMessage)`.
7. При новом входящем сообщении `handlers.py` пропускает `event.out`, затем `await process_message_callback(event.message)`.
8. `MessageProcessor.process()` берет `message.text`, нормализует текст, применяет whitelist/blacklist, проверяет дедупликацию, затем вызывает `RuleEngine.match()`.
9. При совпадении процессор запрашивает `chat_entity` и `sender_entity` через `message.client.get_entity()`, строит ссылки `t.me`, собирает HTML и вызывает `await push({'text': notif_text})`.
10. `worker_loop()` из `main.py` читает очередь, проверяет `RateLimiter.allow()`, отправляет уведомление через `NotificationSender.send()` или отбрасывает его.
11. `NotificationSender.send()` до 5 раз отправляет `sendMessage` в Bot API с `parse_mode='HTML'`.

## 3. Security-проблемы

- Реальные Telegram API credentials и bot token лежат в `config/config.yaml:2-6`, а сам файл отслеживается Git. Это критическая утечка: токены нужно считать скомпрометированными и ротировать.
- `.env` физически присутствует в рабочем каталоге и содержит ключи `API_ID`, `API_HASH`, `BOT_TOKEN`, `USER_ID`. Он игнорируется Git, но монтируется в контейнер как файл в `docker-compose.yml:12`.
- `sessions/user.session` физически присутствует в репозитории. Telethon session дает доступ к пользовательскому Telegram-аккаунту и должна храниться как секрет.
- `logs/app.log` физически присутствует в репозитории и содержит chat_id, user_id/peer IDs и фрагменты пользовательских сообщений.
- `Dockerfile` делает `COPY . .` (`Dockerfile:14`). При ошибке `.dockerignore`, архивировании или альтернативной сборке в образ могут попасть секреты, `.session`, логи и локальные артефакты.
- `docker-compose.yml:13-14` публикует health/metrics порт наружу на `8080:8080`; health server слушает `0.0.0.0` в `app/monitoring/health.py:23`.
- `/metrics` открыт без аутентификации и может раскрывать операционные данные при добавлении метрик.
- В `NotificationSender` URL содержит bot token (`app/notifications/sender.py:11`). Сейчас URL не логируется, но любые debug-логи aiohttp/исключений вокруг URL могут раскрыть токен.
- HTML в уведомлениях собирается из пользовательского текста, имен и заголовков без escaping. Это может ломать доставку и создавать HTML/link injection в Telegram-сообщении.

## 4. Места возможной потери сообщений

- `handlers.py:11` вызывает `await process_message_callback(event.message)` прямо внутри Telethon handler. Долгая обработка, `get_entity()`, заполненная очередь или сетевые зависания замедляют прием следующих events.
- `notifications/queue.py:3` задает `maxsize=1000`; `push()` делает blocking `await put()`. При заполнении очереди обработчик сообщения зависает, Telethon backlog растет.
- `main.py:24` и `app/notifications/worker.py:17` отбрасывают уведомления при превышении rate limit без retry, delayed delivery или dead-letter storage.
- `NotificationSender.send()` возвращает `False` после 5 попыток, а `worker_loop()` все равно вызывает `queue.task_done()` и сообщение теряется.
- `NotificationSender.send()` не обрабатывает Telegram Bot API `429 retry_after`; текущие retry могут продолжать попадать в лимит.
- Дедупликация помечает сообщение как seen до успешного match/отправки (`processor.py:33-34`). Если дальше упадет построение уведомления, queue put, HTML или отправка, повторная обработка этого сообщения уже невозможна в рамках процесса.
- Дедупликация in-memory (`dedup.py`) теряется при рестарте; после рестарта возможны дубли, а не потеря, но при LRU eviction возможна повторная отправка старых сообщений.
- `run_until_disconnected()` в `client.py:29-33` только логирует исключение и не переподключает клиента.
- `asyncio.create_task()` для health и worker в `main.py:42` и `main.py:51` не сохраняются и не мониторятся. Если задача упадет, приложение может продолжить работу без health или без отправки уведомлений.
- `worker_loop()` в `main.py:17-25` не обернут в `try/finally`; неожиданный формат item, исключение sender или rate limiter могут убить воркер.
- Нет обработки `events.MessageEdited`, альбомов, deleted/read state, catch-up после downtime и исторического backfill.

## 5. Места, где блокируется event loop

Строго синхронных долгих блокировок немного, но есть операции, которые блокируют поток обработки events или создают backpressure:

- `processor.py:44-45` делает два последовательных network/cache вызова `get_entity()` внутри handler path.
- `notifications/queue.py:6` блокирует producer при заполненной очереди.
- `rule_engine.py:13-22` синхронно перебирает все правила и слова. Сейчас это дешево, но при росте rules.yaml будет CPU-bound в event loop.
- `normalizer.py:6-8` синхронно нормализует весь текст регулярным выражением.
- `logger.py:25` пишет RotatingFileHandler синхронно из event loop. При медленном диске или ротации это блокирует loop.
- `sender.py:21` создает новый `aiohttp.ClientSession` на каждую попытку отправки. Это не блокировка CPU, но лишняя синхронная/асинхронная overhead-нагрузка в единственном воркере.
- `sender.py:29` выполняет exponential sleep внутри единственного воркера; пока он спит после одной неудачной отправки, вся очередь стоит.

## 6. Где пользовательские данные могут попасть в логи

- `processor.py:40` логирует `chat_id` и первые 50 символов нормализованного текста совпавшего сообщения.
- В существующем `logs/app.log` уже есть chat_id и фрагменты сообщений, включая русскоязычный текст.
- Старые строки в `logs/app.log` показывают, что ранее логировалась конфигурация и текст уведомлений. Даже если текущий код этого уже не делает, лог-файл сохраняет историческую утечку.
- `client.py:31`, `processor.py:47`, `sender.py:27` логируют exception text. Исключения Telethon/aiohttp могут содержать peer IDs, параметры запроса или детали HTML payload.
- `logger.py` пишет одновременно в stdout и `logs/app.log`; Docker также может собирать stdout, дублируя чувствительные данные в docker logs.

## 7. Проблемы lifecycle

- Нет централизованного application lifecycle: зависимости создаются в `main.py`, фоновые задачи запускаются без supervision.
- Health server task и worker task не отменяются и не await-ятся при shutdown.
- `KeyboardInterrupt` только логируется; `TelegramClientWrapper.stop()` не вызывается.
- Нет graceful drain очереди уведомлений перед остановкой.
- Нет readiness-состояния: `/health` всегда возвращает `ok`, даже если Telegram отключен или воркер умер.
- `TelegramClientWrapper.is_running` не используется health endpoint-ом.
- Нет обработки SIGTERM, что важно для Docker stop/redeploy.
- `docker-compose.yml` использует `restart: always`, но приложение само не умеет отличать recoverable disconnect от штатного shutdown.
- Дублируются две реализации worker loop: в `main.py` и `app/notifications/worker.py`; используется менее защищенная версия из `main.py`.

## 8. Проблемы с Telegram-ссылками

- Для приватных supergroup/channel ссылок используется `str(chat_id).replace('-', '')` (`processor.py:76-84`). Для `t.me/c/...` обычно нужен internal id без префикса `-100`, а не простое удаление минуса; ссылки могут быть неверными.
- `chat_link = https://t.me/c/{chat_id_abs}` без message id (`processor.py:77`) не является универсальной ссылкой на приватный чат.
- Для обычных private user chats и basic groups `t.me/c` может не работать.
- Ссылка на отправителя строится только по username (`processor.py:67-70`). Для пользователей без username ссылка отсутствует, хотя можно использовать `tg://user?id=...` с оговорками приватности.
- Username, title и names не escaping-ятся перед вставкой в HTML-ссылки.
- Нет обработки `message.sender_id is None`, anonymous admin, channel post, forwarded message, service message.
- Не учитываются topics/forum thread ids и replies; ссылка может открывать не тот контекст.

## 9. Проблемы с обработкой HTML

- `NotificationSender.send()` отправляет `parse_mode='HTML'` (`sender.py:17`), но `processor.py` вставляет `chat_title`, `sender_name`, `display_text`, fallback `text` без `html.escape`.
- Пользовательский текст с `<`, `>`, `&`, кавычками или незакрытыми тегами может вызвать Bot API `400 Bad Request` и потерю уведомления после retry.
- Пользовательский текст может внедрить собственные `<a href=...>` или визуально подменить структуру уведомления.
- Атрибуты `href='{chat_link}'` используют одинарные кавычки; если URL/username когда-либо будет загрязнен некорректным значением, HTML сломается.
- Обрезка `text[:MAX_TEXT_LENGTH]` идет по символам исходного текста до escaping. После escaping длина payload может стать больше лимита Telegram Bot API.
- Нет fallback на plain text при HTML parse error.

## 10. Проблемы текущего rate limiter

- `RateLimiter` глобальный, а не по destination/chat/rule; один шумный источник блокирует все уведомления.
- При лимите уведомление отбрасывается, а не откладывается.
- Используется `time.time()` (`ratelimit.py:10`), который чувствителен к изменениям системного времени; лучше `time.monotonic()`.
- Нет учета Bot API `429 retry_after`.
- Нет burst/steady-state модели, jitter и адаптивного backoff.
- Нет метрик dropped/delayed/rate_limited.
- Limiter не персистентный и не распределенный; при нескольких процессах/контейнерах лимиты не согласованы.
- Проверка лимита стоит после dequeue. Поэтому rate-limited сообщение уже извлечено из очереди и безвозвратно потеряно.

## 11. Недостающие тесты

Папка `tests/` существует, но файлов тестов в ней не найдено. Нужны тесты:

- `normalizer`: Unicode NFKC, casefold, whitespace, пустые значения.
- `RuleEngine`: `AND`, `OR`, пустые words, неизвестный operator, дубли правил, регистронезависимость после normalize.
- `Deduplicator`: ключи по chat/message, eviction, повторная обработка после restart как ожидаемое поведение.
- `RateLimiter`: sliding window, boundary на 60 секунд, использование monotonic после исправления, отсутствие drop в целевом дизайне.
- `MessageProcessor`: whitelist/blacklist, empty text, dedup order, match/no match, ошибки `get_entity`, sender без username, channel post, anonymous sender.
- HTML escaping: текст, chat title, sender name, кавычки, `<>&`, длинные сообщения после escaping.
- Telegram links: public username, private `-100...`, basic group, user, missing sender, forum topic.
- Queue/worker: full queue, sender failure, retry, dead-letter/delay, `task_done` на исключениях.
- `NotificationSender`: reuse session, 200/400/429/5xx, timeout, payload limit, fallback parse mode.
- Lifecycle: SIGTERM, task cancellation, reconnect, health readiness при падении worker/client.
- Docker/config: env precedence, отсутствие секретов в config defaults, `.dockerignore`, volume assumptions.

## 12. Предлагаемая целевая структура проекта

```text
app/
  main.py
  settings/
    models.py
    loader.py
  telegram/
    client.py
    handlers.py
    links.py
    entities.py
  processing/
    message_processor.py
    models.py
  filtering/
    normalizer.py
    rule_engine.py
  notifications/
    queue.py
    sender.py
    worker.py
    html.py
    rate_limit.py
  storage/
    dedup_store.py
    sqlite.py
  monitoring/
    health.py
    metrics.py
    state.py
  logging/
    setup.py
  security/
    redaction.py
config/
  config.example.yaml
  rules.yaml
  chats.yaml
tests/
  unit/
  integration/
  fixtures/
docs/
```

Ключевая идея: оставить Telethon, aiohttp, YAML и текущий pipeline, но разделить построение ссылок, HTML, rate limiting, queue policy, lifecycle state и dedup storage на тестируемые модули.

## 13. План миграции без полного переписывания проекта

1. Секреты: ротировать Telegram credentials и bot token, убрать реальные значения из `config/config.yaml`, добавить `config.example.yaml`, проверить историю Git отдельно.
2. Логи: убрать пользовательский текст из info-логов, добавить redaction, удалить/заархивировать существующие локальные логи как секретный артефакт.
3. HTML: вынести сборку уведомления в `notifications/html.py`, ввести escaping всех пользовательских полей и fallback на plain text.
4. Telegram links: вынести построение ссылок в `telegram/links.py`, корректно обрабатывать public/private chats, `-100` ids, missing sender, channel posts.
5. Worker: использовать один воркер из `app/notifications/worker.py`, добавить supervision, try/finally, retry policy, delayed requeue или dead-letter.
6. Rate limiting: заменить drop-on-limit на отложенную отправку с monotonic clock и поддержкой `retry_after`.
7. Sender: переиспользовать один `aiohttp.ClientSession`, явно обрабатывать 400/429/5xx, timeouts и payload limits.
8. Processor: не помечать dedup как окончательно seen до успешной постановки в надежную очередь; добавить structured result и метрики.
9. Lifecycle: добавить `Application`/`ServiceContainer`, хранить task handles, graceful shutdown по SIGTERM/SIGINT, readiness state.
10. Health: `/health` оставить liveness, добавить `/ready` или расширить статус проверкой Telegram, worker и queue depth.
11. Dedup: перейти от in-memory LRU к SQLite/файловому TTL store либо явно задокументировать best-effort режим.
12. Docker: не копировать локальные секреты/артефакты, не монтировать `.env` как файл без необходимости, ограничить публикацию порта health.
13. Tests: сначала unit-тесты для pure-функций, затем async-тесты processor/worker/sender с mock Telethon/Bot API.

## Итоговая таблица

| Проблема | Критичность | Затронутые файлы | Рекомендуемое исправление | Этап реализации |
|---|---:|---|---|---|
| Реальные Telegram credentials и bot token в отслеживаемом YAML | Critical | `config/config.yaml`, Git history | Ротировать секреты, заменить на placeholders, использовать env/secrets manager | 1 |
| Session-файл Telegram лежит в рабочей копии | Critical | `sessions/user.session` | Хранить вне репозитория/в secret volume, ограничить доступ, считать артефакт чувствительным | 1 |
| Логи содержат пользовательский текст и chat IDs | High | `logs/app.log`, `app/core/processor.py`, `app/utils/logger.py` | Redaction, убрать message snippets из info, очистить существующие логи | 2 |
| HTML не escaping-ится перед `parse_mode=HTML` | High | `app/core/processor.py`, `app/notifications/sender.py` | `html.escape` для всех пользовательских полей, fallback plain text | 3 |
| Уведомления теряются при rate limit | High | `main.py`, `app/notifications/worker.py`, `app/security/ratelimit.py` | Delayed retry/requeue, no drop policy, метрики | 6 |
| Уведомления теряются после исчерпания retries | High | `app/notifications/sender.py`, `main.py` | Dead-letter или persistent retry queue | 5 |
| Handler блокируется обработкой и заполненной очередью | High | `app/core/handlers.py`, `app/core/processor.py`, `app/notifications/queue.py` | Быстрый enqueue events, bounded worker pool, backpressure policy | 5 |
| Дедуп помечается до успешной доставки | Medium | `app/core/processor.py`, `app/security/dedup.py` | Разделить seen/processed/enqueued/sent или помечать после надежного enqueue | 8 |
| Дедуп in-memory и теряется при рестарте | Medium | `app/security/dedup.py` | TTL store на SQLite/Redis/file | 11 |
| Неверные `t.me/c` ссылки для `-100...` и private/basic chats | Medium | `app/core/processor.py` | Выделить link builder и корректную нормализацию peer id | 4 |
| Не обработаны missing sender, anonymous admin, channel posts | Medium | `app/core/processor.py` | Defensive entity handling и тестовые fixtures | 4 |
| Единственный worker спит на retry и блокирует всю очередь | Medium | `app/notifications/sender.py`, `main.py` | Пул воркеров или scheduler retry без блокировки очереди | 5 |
| Создается новый `aiohttp.ClientSession` на каждую попытку | Medium | `app/notifications/sender.py` | Lifecycle-managed shared session | 7 |
| Фоновые tasks не мониторятся | Medium | `main.py` | Хранить task handles, supervision, fail-fast или restart | 9 |
| Нет graceful shutdown и drain очереди | Medium | `main.py`, `app/core/client.py` | Обработка SIGTERM/SIGINT, cancel/drain/close session/client | 9 |
| `/health` всегда `ok` | Medium | `app/monitoring/health.py` | Разделить liveness/readiness, проверять client/worker/queue | 10 |
| Health/metrics слушают `0.0.0.0` и публикуются наружу | Medium | `app/monitoring/health.py`, `docker-compose.yml` | Bind localhost/internal network или закрыть auth/firewall | 12 |
| `COPY . .` зависит от корректности `.dockerignore` | Medium | `Dockerfile`, `.dockerignore` | Копировать только нужные пути, исключить архивы/.venv/.idea | 12 |
| `.dockerignore` игнорирует `venv/`, но не `.venv/` | Medium | `.dockerignore` | Добавить `.venv/`, `.idea/`, `*.zip`, `sessions/`, `config/config.yaml` при необходимости | 12 |
| `.gitignore` игнорирует `venv/`, но не `.venv/`; `.idea` отслеживается | Low | `.gitignore`, `.idea/*` | Добавить `.venv/`, `.idea/`, удалить IDE-файлы из индекса | 12 |
| `app/notifications/worker.py` не используется | Low | `main.py`, `app/notifications/worker.py` | Оставить одну реализацию worker и подключить ее | 5 |
| Metrics объявлены, но не инкрементируются | Low | `app/monitoring/health.py`, `app/monitoring/metrics.py`, `main.py` | Единый модуль metrics и инкременты в pipeline | 10 |
| Тесты отсутствуют | High | `tests/`, весь pipeline | Добавить unit/integration tests по списку выше | 13 |
