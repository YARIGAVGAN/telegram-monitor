# Руководство по безопасности

## 🔐 Критические меры безопасности

### 1. Защита чувствительных данных

#### Никогда не коммитьте следующие данные в репозиторий:
- **Telegram API credentials** (`api_id`, `api_hash`)
- **Bot Token** от @BotFather
- **User ID** для уведомлений
- **Session файлы** Telethon (*.session)
- **Файлы .env** с паролями и токенами

#### Правильное хранение секретов:

```bash
# 1. Создайте файл .env (не коммитить!)
cp .env.example .env

# 2. Отредактируйте .env, добавив свои данные
nano .env

# 3. Убедитесь, что .env в .gitignore
cat .gitignore | grep env
```

### 2. Конфигурация через переменные окружения

Измените `config/config.yaml` для использования переменных окружения:

```yaml
telegram:
  api_id: ${API_ID}
  api_hash: "${API_HASH}"

bot:
  token: "${BOT_TOKEN}"

notifications:
  user_id: ${USER_ID}
```

Загрузка из `.env`:
```python
from dotenv import load_dotenv
load_dotenv()  # Загружает переменные из .env
```

### 3. Защита сессий Telethon

Файлы сессий (`*.session`) содержат данные для аутентификации в Telegram:

```bash
# Установите строгие права доступа
chmod 600 sessions/*.session
chown -R $USER:$USER sessions/

# В production используйте зашифрованное хранилище
```

### 4. Безопасность веб-дашборда

#### Текущие уязвимости и исправления:

| Уязвимость | Статус | Решение |
|------------|--------|---------|
| XSS через текст вакансии | ✅ Исправлено | Экранирование HTML через `escapeHtml()` |
| CSRF | ⚠️ Требуется | Добавить CSRF токены |
| Отсутствие аутентификации | ⚠️ Требуется | Добавить базовую auth или JWT |
| WebSocket без проверки origin | ⚠️ Требуется | Проверять Origin header |

#### Рекомендации по усилению безопасности дашборда:

```python
# Добавить middleware для проверки Origin
async def check_origin_middleware(app, handler):
    async def middleware(request):
        origin = request.headers.get('Origin')
        allowed_origins = ['https://your-domain.com']
        if origin and origin not in allowed_origins:
            return web.Response(status=403)
        return await handler(request)
    return middleware

# Добавить базовую аутентификацию
from aiohttp_basicauth import BasicAuthMiddleware
auth = BasicAuthMiddleware(username='admin', password='secure_password')
app.middlewares.append(auth)
```

### 5. Rate Limiting и защита от DoS

Текущий rate limiter защищает только уведомления. Добавьте защиту для веб-сервера:

```python
from aiohttp_limiter import RateLimitMiddleware

app.middlewares.append(
    RateLimitMiddleware(
        rate=100,  # запросов в минуту
        per=60,
        key_func=lambda r: r.remote
    )
)
```

### 6. HTTPS для production

Никогда не запускайте дашборд на публичном IP без HTTPS:

```nginx
# Пример конфигурации Nginx reverse proxy
server {
    listen 443 ssl http2;
    server_name dashboard.your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://localhost:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 7. Firewall правила

```bash
# Разрешить только необходимые порты
sudo ufw default deny incoming
sudo ufw allow from 192.168.1.0/24 to any port 8081  # Дашборд из локальной сети
sudo ufw allow from 127.0.0.1 to any port 8080       # Health check локально
sudo ufw enable
```

### 8. Мониторинг безопасности

Добавьте логирование подозрительной активности:

```python
import logging
security_logger = logging.getLogger('security')

# Логировать неудачные попытки подключения
security_logger.warning(f"Failed connection attempt from {request.remote}")

# Логировать необычные паттерны запросов
```

### 9. Регулярные обновления

```bash
# Проверяйте зависимости на уязвимости
pip install pip-audit
pip-audit -r requirements.txt

# Обновляйте зависимости регулярно
pip install --upgrade telethon aiohttp pyyaml
```

### 10. Checklist перед деплоем

- [ ] Все секреты вынесены в `.env` или secrets manager
- [ ] `.env` добавлен в `.gitignore`
- [ ] Session файлы защищены (chmod 600)
- [ ] Дашборд доступен только по HTTPS
- [ ] Настроен firewall
- [ ] Включён rate limiting
- [ ] Настроено логирование безопасности
- [ ] Проведён аудит зависимостей

## 📞 Экстренные действия при компрометации

Если вы подозреваете утечку данных:

1. **Немедленно отзовите bot token** через @BotFather
2. **Завершите все сессии Telethon** (удалите *.session файлы)
3. **Смените API credentials** на https://my.telegram.org
4. **Проверьте логи** на предмет несанкционированного доступа
5. **Уведомите пользователей** если были затронуты их данные

## 🔗 Полезные ресурсы

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Telegram API Security](https://core.telegram.org/api/security)
- [Python Security Best Practices](https://docs.python.org/3/library/security.html)
