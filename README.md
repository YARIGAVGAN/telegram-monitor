# Telegram Vacancy Parser

## 📋 Описание проекта

Автоматизированный парсер вакансий из Telegram-каналов с системой мониторинга, веб-дашбордом и автоматическим восстановлением при сбоях.

### Основные возможности

- **Мониторинг Telegram-каналов** - Автоматический перехват сообщений из заданных каналов
- **Фильтрация по правилам** - Гибкая система правил для отбора подходящих вакансий (белый/черный список ключевых слов)
- **Веб-дашборд** - Визуальный интерфейс для отслеживания статуса парсера и просмотра найденных вакансий
- **Health-check API** - Endpoint для проверки работоспособности сервиса
- **Авторестарт при крашах** - Автоматическое восстановление работы при сбоях
- **Уведомления о критических ошибках** - Отправка alert'ов в Telegram при невозможности восстановления
- **Deduplication** - Защита от дублирования вакансий
- **Rate limiting** - Ограничение частоты уведомлений

### Архитектура проекта

```
├── main.py                 # Точка входа приложения
├── app/
│   ├── config/            # Загрузчики конфигурации
│   ├── core/              # Ядро: клиент, обработчики, процессор, рестарт
│   ├── filtering/         # Движок правил фильтрации
│   ├── monitoring/        # Health-check и метрики
│   ├── notifications/     # Очередь и отправщик уведомлений
│   ├── security/          # Deduplicator и RateLimiter
│   ├── utils/             # Утилиты (логгер)
│   └── web/               # Веб-дашборд
├── config/                # YAML конфиги
├── logs/                  # Логи приложения
├── sessions/              # Сессии Telethon
├── Dockerfile             # Docker образ
└── docker-compose.yml     # Docker Compose конфигурация
```

---

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.12+
- Docker и Docker Compose (для контейнеризации)
- Telegram API credentials (api_id, api_hash)
- Telegram Bot Token

### Вариант 1: Запуск через Docker Compose (Рекомендуется)

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd <project-directory>

# 2. Настройте конфигурацию
# Отредактируйте файлы в папке config/:
# - config.yaml - основные настройки
# - keywords.yaml - ключевые слова для фильтрации
# - rules.yaml - правила фильтрации
# - chats.yaml - список каналов для мониторинга

# 3. Запустите сервис
docker-compose up -d

# 4. Проверьте логи
docker-compose logs -f monitor

# 5. Откройте веб-дашборд
# http://localhost:8081
```

### Вариант 2: Локальный запуск без Docker

```bash
# 1. Установите зависимости
pip install -r requirements.txt

# 2. Настройте конфигурацию (см. раздел "Конфигурация")

# 3. Запустите приложение
python main.py
```

---

## 📦 Сборка и деплой в Docker

### Пошаговая инструкция сборки

#### Шаг 1: Подготовка окружения

Убедитесь, что у вас установлены:
- Docker версии 20.10+
- Docker Compose версии 2.0+

Проверьте версии:
```bash
docker --version
docker-compose --version
```

#### Шаг 2: Настройка конфигурации

Отредактируйте файлы конфигурации в папке `config/`:

**config/config.yaml** - Основные настройки:
```yaml
telegram:
  api_id: YOUR_API_ID
  api_hash: "YOUR_API_HASH"

bot:
  token: "YOUR_BOT_TOKEN"

notifications:
  user_id: YOUR_USER_ID  # ID пользователя или чата для уведомлений

limits:
  notifications_per_minute: 20

health:
  port: 8080

dashboard:
  port: 8081
```

**config/keywords.yaml** - Ключевые слова для фильтрации:
```yaml
whitelist:
  - python
  - разработчик
  - vacancy
  
blacklist:
  - стажировка
  - бесплатно
```

**config/rules.yaml** - Правила фильтрации:
```yaml
rules:
  - name: "Python Developer"
    conditions:
      must_contain: ["python", "разработчик"]
      must_not_contain: ["стажировка", "junior"]
```

**config/chats.yaml** - Каналы для мониторинга:
```yaml
chats:
  - id: -1001234567890
    title: "IT Jobs"
  - id: -1009876543210
    title: "Python Jobs"
```

#### Шаг 3: Сборка Docker образа

```bash
# Сборка образа
docker build -t telegram-vacancy-parser:latest .

# Проверка образа
docker images | grep telegram-vacancy-parser
```

#### Шаг 4: Запуск через Docker Compose

```bash
# Запуск в фоновом режиме
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f monitor

# Остановка сервиса
docker-compose down

# Остановка с удалением томов (данные будут потеряны)
docker-compose down -v
```

#### Шаг 5: Запуск отдельным контейнером

```bash
# Создание сети (если нужна изоляция)
docker network create telegram-parser-net

# Запуск контейнера
docker run -d \
  --name telegram-monitor \
  --restart always \
  -p 8080:8080 \
  -p 8081:8081 \
  -v $(pwd)/sessions:/app/sessions \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/.env:/app/.env \
  -e TZ=Europe/Moscow \
  telegram-vacancy-parser:latest
```

### Деплой на сервер (DigitalOcean, AWS, etc.)

#### Шаг 1: Подготовка сервера

```bash
# Подключение к серверу
ssh user@your-server-ip

# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
# Перелогиньтесь для применения изменений
```

#### Шаг 2: Развёртывание проекта

```bash
# Клонирование репозитория
git clone <repository-url> /opt/telegram-parser
cd /opt/telegram-parser

# Настройка конфигурации
nano config/config.yaml
# Внесите необходимые изменения

# Настройка прав доступа
chmod -R 755 config/
mkdir -p sessions logs
chmod -R 777 sessions logs

# Запуск сервиса
docker-compose up -d

# Проверка статуса
docker-compose ps
docker-compose logs -f
```

#### Шаг 3: Настройка автозапуска

Docker Compose уже настроен с `restart: always`, но можно дополнительно создать systemd сервис:

```bash
sudo nano /etc/systemd/system/telegram-parser.service
```

Содержимое файла:
```ini
[Unit]
Description=Telegram Vacancy Parser
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/telegram-parser
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down

[Install]
WantedBy=multi-user.target
```

Активация сервиса:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-parser
sudo systemctl start telegram-parser
sudo systemctl status telegram-parser
```

---

## 🌐 Веб-дашборд

### Доступ к дашборду

После запуска сервиса веб-дашборд доступен по адресу:
```
http://your-server-ip:8081
```

### Функционал дашборда

- **Статус парсера** - Текущее состояние (работает/остановлен/запуск/перезапуск)
- **Статистика** - Количество обработанных сообщений, найденных вакансий, перезапусков
- **Список вакансий** - Таблица последних 100 найденных вакансий с ссылками на оригиналы
- **Live обновление через WebSocket** - Мгновенное добавление новых вакансий без перезагрузки страницы
- **Визуальные уведомления** - Всплывающее сообщение при появлении новой вакансии
- **Анимация новых строк** - Подсветка вновь добавленных вакансий
- **Индикатор live-режима** - Пульсирующая точка, показывающая активное соединение
- **Авто-переподключение** - При разрыве соединения попытка переподключения до 10 раз

### API endpoints

Дашборд предоставляет JSON API и WebSocket для интеграции:

```bash
# Получить статус парсера
curl http://localhost:8081/api/status

# Получить список вакансий
curl http://localhost:8081/api/vacancies?limit=50

# WebSocket endpoint для realtime обновлений
# ws://localhost:8081/ws
```

**WebSocket сообщения:**

Сервер отправляет клиенту:
```json
{
  "type": "new_vacancy",
  "vacancy": {
    "chat_id": -1001234567890,
    "chat_title": "IT Jobs",
    "chat_link": "https://t.me/itjobs",
    "sender_name": "HR Manager",
    "text": "Требуется Python разработчик...",
    "msg_link": "https://t.me/itjobs/12345",
    "received_at": "2024-01-15T10:30:00"
  }
}
```

Клиент может отправить ping для поддержания соединения:
```json
{
  "type": "ping"
}
```

Сервер ответит pong:
```json
{
  "type": "pong"
}
```

---

## 🔍 Health Check

Сервис предоставляет endpoint для проверки работоспособности:

```bash
# Проверка статуса
curl http://localhost:8080/health

# Ответ: {"status": "healthy"}
```

Используется для мониторинга и оркестрации (Kubernetes, Docker Swarm, etc.).

---

## 🔔 Система уведомлений

### Авторестарт при крашах

Приложение автоматически пытается перезапуститься при возникновении ошибок:
- Максимум 3 попытки перезапуска
- Задержка между попытками: 5 секунд
- Сброс счётчика попыток после 5 минут стабильной работы

### Уведомления о критических ошибках

Если авторестарт не удался (превышено максимальное количество попыток), система отправляет уведомление в Telegram с деталями ошибки.

### Уведомления о попытках рестарта

При каждой попытке перезапуска отправляется информативное сообщение с причиной сбоя.

---

## 📁 Структура конфигурационных файлов

### config/config.yaml

Основные настройки приложения:
- Telegram API credentials
- Bot token для уведомлений
- ID пользователя/чата для уведомлений
- Лимиты (уведомлений в минуту)
- Порты health-check и дашборда

### config/keywords.yaml

Ключевые слова для фильтрации:
- `whitelist` - слова, которые должны присутствовать
- `blacklist` - слова, которые исключают вакансию

### config/rules.yaml

Продвинутые правила фильтрации:
- Именованные правила
- Комбинации условий
- Логические операторы

### config/chats.yaml

Список каналов для мониторинга:
- ID каналов
- Названия (для отображения в дашборде)

---

## 🛠️ Troubleshooting

### Проблема: Контейнер не запускается

**Решение:**
```bash
# Проверьте логи
docker-compose logs monitor

# Убедитесь, что порты свободны
sudo lsof -i :8080
sudo lsof -i :8081

# Проверьте права доступа к томам
ls -la sessions/ logs/ config/
```

### Проблема: Нет найденных вакансий

**Решение:**
1. Проверьте конфигурацию ключевых слов в `config/keywords.yaml`
2. Убедитесь, что каналы добавлены в `config/chats.yaml`
3. Проверьте логи на наличие ошибок подключения
4. Убедитесь, что сессия Telethon успешно создана

### Проблема: Уведомления не приходят

**Решение:**
1. Проверьте правильность bot token в `config/config.yaml`
2. Убедитесь, что user_id указан верно (для личного чата это ваш ID)
3. Проверьте, что бот добавлен в нужные чаты (если требуется)

### Проблема: Дашборд недоступен

**Решение:**
```bash
# Проверьте, что контейнер запущен
docker-compose ps

# Проверьте маппинг портов
docker-compose port monitor 8081

# Попробуйте перезапустить
docker-compose restart monitor
```

---

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Логи в реальном времени
docker-compose logs -f monitor

# Последние 100 строк
docker-compose logs --tail=100 monitor

# Логи за определённый период
docker-compose logs --since="2024-01-01" monitor
```

### Логи сохраняются в:
- Внутри контейнера: `/app/logs/app.log`
- На хосте: `./logs/app.log`

---

## 🔒 Безопасность

### Рекомендации

1. **Не коммитьте чувствительные данные** - Используйте `.env` файл для секретов
2. **Ограничьте доступ к портам** - Используйте firewall для ограничения доступа к 8080/8081
3. **Регулярно обновляйте зависимости** - Проверяйте `requirements.txt` на уязвимости
4. **Используйте HTTPS** - Для продакшена настройте reverse proxy с SSL

### Пример настройки firewall (UFW)

```bash
# Разрешить только с определённых IP
sudo ufw allow from 192.168.1.0/24 to any port 8081
sudo ufw allow from 192.168.1.0/24 to any port 8080
```

---

## 📝 Лицензия

MIT License

---

## 🤝 Поддержка

Для вопросов и предложений создавайте Issues в репозитории.