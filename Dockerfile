# Базовый образ с Python 3.12
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями (на этом этапе кеширование лучше)
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код (кроме того, что исключено в .dockerignore)
COPY . .

# Создаём папки для логов и сессий (если их нет)
RUN mkdir -p /app/logs /app/sessions

# Открываем порты для health-check и дашборда
EXPOSE 8080 8081

# Указываем команду запуска
CMD ["python", "main.py"]