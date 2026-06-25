from aiohttp import web
import asyncio
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

# Определяем метрики
messages_received = Counter('messages_received_total', 'Total messages received')
messages_matched = Counter('messages_matched_total', 'Total messages matched keywords')
notifications_sent = Counter('notifications_sent_total', 'Total notifications sent')

async def health_handler(request):
    return web.json_response({"status": "ok"})

async def metrics_handler(request):
    # Возвращаем все метрики в формате Prometheus
    return web.Response(body=generate_latest(), content_type=CONTENT_TYPE_LATEST)

async def start_health_server(port=8080):
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/metrics', metrics_handler)  # эндпоинт для сбора метрик
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Health and metrics server running on port {port}")
    # Бесконечное ожидание
    await asyncio.Event().wait()