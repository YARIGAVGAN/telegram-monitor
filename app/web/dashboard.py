"""
Веб-дашборд для отображения состояния парсера и списка вакансий
"""
from aiohttp import web
import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Set
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Базовая аутентификация для дашборда (опционально)
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'changeme123')  # Смените в production!

# Разрешённые origins для WebSocket (для production укажите свой домен)
ALLOWED_ORIGINS = os.getenv('DASHBOARD_ALLOWED_ORIGINS', 'http://localhost,http://127.0.0.1').split(',')

# Глобальное хранилище вакансий и статуса
vacancies_store: List[Dict[str, Any]] = []
parser_status = {
    "status": "starting",
    "started_at": None,
    "last_message_at": None,
    "messages_processed": 0,
    "messages_matched": 0,
    "restarts": 0,
    "last_restart_at": None,
    "last_error": None
}

# WebSocket подключения для realtime обновлений
websocket_connections: Set[web.WebSocketResponse] = set()

MAX_VACANCIES = 500  # Максимальное количество хранимых вакансий


def add_vacancy(vacancy: Dict[str, Any]):
    """Добавить вакансию в хранилище и уведомить WebSocket клиентов"""
    global vacancies_store
    vacancy['received_at'] = datetime.now().isoformat()
    vacancies_store.insert(0, vacancy)
    # Ограничиваем размер хранилища
    if len(vacancies_store) > MAX_VACANCIES:
        vacancies_store = vacancies_store[:MAX_VACANCIES]
    
    # Уведомляем все WebSocket подключения о новой вакансии
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(broadcast_vacancy(vacancy))
    except RuntimeError:
        # Нет запущенного event loop (например, при тестировании)
        pass


async def broadcast_vacancy(vacancy: Dict[str, Any]):
    """Отправить новую вакансию всем подключенным WebSocket клиентам"""
    if websocket_connections:
        message = json.dumps({
            'type': 'new_vacancy',
            'vacancy': vacancy
        })
        # Копируем множество, чтобы избежать изменения во время итерации
        disconnected = set()
        for ws in websocket_connections:
            try:
                await ws.send_str(message)
            except Exception:
                disconnected.add(ws)
        # Удаляем отключенные подключения
        websocket_connections.difference_update(disconnected)


def update_parser_status(**kwargs):
    """Обновить статус парсера"""
    for key, value in kwargs.items():
        if key in parser_status:
            parser_status[key] = value


async def websocket_handler(request):
    """WebSocket endpoint для realtime обновлений с проверкой Origin"""
    # Проверка Origin header для защиты от CSRF
    origin = request.headers.get('Origin', '')
    if origin and origin not in ALLOWED_ORIGINS:
        logger.warning(f"WebSocket connection rejected from origin: {origin}")
        return web.Response(status=403, text="Forbidden: Invalid Origin")
    
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    # Добавляем подключение к множеству
    websocket_connections.add(ws)
    logger.info(f"WebSocket client connected from {request.remote}. Total connections: {len(websocket_connections)}")
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Обрабатываем входящие сообщения (если нужно)
                data = json.loads(msg.data)
                if data.get('type') == 'ping':
                    await ws.send_str(json.dumps({'type': 'pong'}))
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f'WebSocket connection closed with exception: {ws.exception()}')
    finally:
        websocket_connections.discard(ws)
        logger.info(f"WebSocket client disconnected. Total connections: {len(websocket_connections)}")
    
    return ws


async def check_auth(request):
    """Проверка базовой аутентификации"""
    from aiohttp import web
    import base64
    
    # Если аутентификация не настроена (дефолтный пароль), пропускаем
    if DASHBOARD_PASSWORD == 'changeme123' and DASHBOARD_USERNAME == 'admin':
        return None
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return web.Response(
            status=401,
            text='Unauthorized',
            headers={'WWW-Authenticate': 'Basic realm="Dashboard"'}
        )
    
    try:
        auth_type, auth_string = auth_header.split()
        if auth_type.lower() != 'basic':
            raise ValueError("Invalid auth type")
        
        decoded = base64.b64decode(auth_string).decode('utf-8')
        username, password = decoded.split(':', 1)
        
        if username != DASHBOARD_USERNAME or password != DASHBOARD_PASSWORD:
            raise ValueError("Invalid credentials")
    except Exception:
        return web.Response(
            status=401,
            text='Unauthorized',
            headers={'WWW-Authenticate': 'Basic realm="Dashboard"'}
        )
    
    return None


async def dashboard_handler(request):
    """Обработчик главной страницы дашборда с проверкой аутентификации"""
    # Проверка аутентификации (если настроена)
    auth_response = await check_auth(request)
    if auth_response:
        return auth_response
    
    html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Парсер вакансий - Дашборд</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --success-gradient: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            --bg-gradient: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            --card-bg: rgba(255, 255, 255, 0.95);
            --card-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            --text-primary: #1a1a2e;
            --text-secondary: #666;
            --accent-color: #667eea;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --border-radius: 16px;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-gradient);
            min-height: 100vh;
            padding: 20px;
            color: var(--text-primary);
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: clamp(1.5rem, 4vw, 2.5rem);
            font-weight: 700;
            text-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        h1 .emoji {
            font-size: 1.2em;
        }

        /* Status Card */
        .status-card {
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border-radius: var(--border-radius);
            padding: clamp(20px, 4vw, 30px);
            margin-bottom: 30px;
            box-shadow: var(--card-shadow);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .status-card h2 {
            color: var(--text-primary);
            margin-bottom: 20px;
            font-size: clamp(1.2rem, 3vw, 1.5rem);
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-badge-container {
            margin-bottom: 25px;
        }

        .status-indicator {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border-radius: 50px;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 14px;
            letter-spacing: 0.5px;
            transition: var(--transition);
        }

        .status-indicator::before {
            content: '';
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse-dot 2s infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }

        .status-running {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            color: #155724;
        }

        .status-running::before {
            background: #28a745;
        }

        .status-stopped {
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
            color: #721c24;
        }

        .status-stopped::before {
            background: #dc3545;
            animation: none;
        }

        .status-starting, .status-restarting {
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            color: #856404;
        }

        .status-starting::before, .status-restarting::before {
            background: #ffc107;
        }

        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(250px, 100%), 1fr));
            gap: clamp(15px, 3vw, 20px);
            margin-top: 20px;
        }

        .status-item {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: clamp(15px, 3vw, 20px);
            border-radius: 12px;
            text-align: center;
            border-left: 4px solid var(--accent-color);
            transition: var(--transition);
            position: relative;
            overflow: hidden;
        }

        .status-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, transparent 100%);
            opacity: 0;
            transition: var(--transition);
        }

        .status-item:hover::before {
            opacity: 1;
        }

        .status-item:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 24px rgba(102, 126, 234, 0.2);
        }

        .status-item h3 {
            color: var(--text-secondary);
            font-size: 12px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        .status-item .value {
            font-size: clamp(1.5rem, 4vw, 1.75rem);
            font-weight: 700;
            color: var(--text-primary);
            word-break: break-word;
        }

        /* Vacancies Card */
        .vacancies-card {
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border-radius: var(--border-radius);
            padding: clamp(20px, 4vw, 30px);
            box-shadow: var(--card-shadow);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .vacancies-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
            flex-wrap: wrap;
            gap: 15px;
        }

        .vacancies-header h2 {
            color: var(--text-primary);
            font-size: clamp(1.2rem, 3vw, 1.5rem);
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .live-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 20px;
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            border-radius: 50px;
            font-size: 14px;
            color: #155724;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.2);
        }

        .live-dot {
            width: 10px;
            height: 10px;
            background: #28a745;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.4); }
            50% { opacity: 1; transform: scale(1.3); box-shadow: 0 0 0 10px rgba(40, 167, 69, 0); }
            100% { opacity: 1; transform: scale(1); box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); }
        }

        /* Table Styles */
        .table-container {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border-radius: 12px;
            border: 1px solid #e0e0e0;
        }

        .vacancies-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 800px;
        }

        .vacancies-table th,
        .vacancies-table td {
            padding: clamp(12px, 2vw, 15px);
            text-align: left;
            border-bottom: 1px solid #f0f0f0;
        }

        .vacancies-table th {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 1px;
            white-space: nowrap;
        }

        .vacancies-table tr {
            transition: var(--transition);
        }

        .vacancies-table tbody tr:hover {
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
        }

        .vacancies-table tr.new-row {
            animation: highlight 2.5s ease-out;
        }

        @keyframes highlight {
            0% { background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); }
            100% { background: transparent; }
        }

        .vacancy-link, .chat-link {
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 500;
            transition: var(--transition);
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .vacancy-link:hover, .chat-link:hover {
            color: #764ba2;
            text-decoration: underline;
        }

        .vacancy-text {
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-secondary);
            font-size: 14px;
        }

        .timestamp {
            color: #999;
            font-size: 13px;
            font-weight: 500;
        }

        .empty-state {
            text-align: center;
            padding: clamp(40px, 8vw, 60px) 20px;
            color: var(--text-secondary);
        }

        .empty-state svg {
            width: clamp(60px, 15vw, 80px);
            height: clamp(60px, 15vw, 80px);
            margin-bottom: 20px;
            opacity: 0.5;
            color: var(--accent-color);
        }

        .empty-state p {
            font-size: 16px;
            margin-top: 10px;
        }

        .empty-state p:last-child {
            font-size: 14px;
            opacity: 0.8;
        }

        /* Notification Toast */
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(16, 185, 129, 0.4);
            transform: translateX(calc(100% + 40px));
            transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 500;
            max-width: calc(100vw - 40px);
        }

        .notification.show {
            transform: translateX(0);
        }

        .notification-icon {
            font-size: 20px;
        }

        /* Modal Styles */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(5px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 2000;
            opacity: 0;
            transition: opacity 0.3s ease;
            padding: 20px;
        }

        .modal-overlay.active {
            display: flex;
            opacity: 1;
        }

        .modal-content {
            background: white;
            border-radius: 20px;
            width: 100%;
            max-width: 700px;
            max-height: 85vh;
            overflow: hidden;
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
            transform: translateY(-30px) scale(0.95);
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            flex-direction: column;
        }

        .modal-overlay.active .modal-content {
            transform: translateY(0) scale(1);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 25px;
            border-bottom: 2px solid #f0f0f0;
            background: var(--primary-gradient);
            color: white;
            flex-shrink: 0;
        }

        .modal-header h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            padding-right: 15px;
        }

        .modal-close {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition);
            flex-shrink: 0;
        }

        .modal-close:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: rotate(90deg);
        }

        .modal-body {
            padding: 25px;
            overflow-y: auto;
            line-height: 1.8;
            color: #333;
            font-size: 15px;
            flex: 1;
        }

        .modal-body::-webkit-scrollbar {
            width: 8px;
        }

        .modal-body::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }

        .modal-body::-webkit-scrollbar-thumb {
            background: var(--accent-color);
            border-radius: 4px;
        }

        .modal-body::-webkit-scrollbar-thumb:hover {
            background: #764ba2;
        }

        .show-text-btn {
            background: var(--primary-gradient);
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: var(--transition);
            white-space: nowrap;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }

        .show-text-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
        }

        .show-text-btn:active {
            transform: translateY(0);
        }

        /* Connection Status */
        .connection-status {
            position: fixed;
            bottom: 20px;
            left: 20px;
            padding: 10px 16px;
            background: var(--card-bg);
            border-radius: 50px;
            box-shadow: var(--card-shadow);
            font-size: 13px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
            z-index: 900;
            transition: var(--transition);
        }

        .connection-status.connected {
            color: var(--success-color);
        }

        .connection-status.disconnected {
            color: var(--danger-color);
        }

        .connection-status .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: currentColor;
        }

        .connection-status.connected .dot {
            animation: pulse-dot 2s infinite;
        }

        /* Responsive Design */
        @media (max-width: 1024px) {
            .status-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 768px) {
            body {
                padding: 10px;
            }

            .status-card, .vacancies-card {
                padding: 15px;
            }

            .status-grid {
                grid-template-columns: 1fr;
            }

            .vacancies-header {
                flex-direction: column;
                align-items: flex-start;
            }

            .live-indicator {
                align-self: flex-start;
            }

            .table-container {
                margin: 0 -15px;
                border-radius: 0;
                border: none;
            }

            .vacancies-table th,
            .vacancies-table td {
                padding: 10px 8px;
                font-size: 13px;
            }

            .vacancy-text {
                max-width: 150px;
            }

            .modal-content {
                max-height: 90vh;
                margin: 10px;
            }

            .modal-header {
                padding: 15px 20px;
            }

            .modal-body {
                padding: 20px;
            }

            .notification {
                left: 10px;
                right: 10px;
                top: 10px;
            }

            .connection-status {
                bottom: 10px;
                left: 10px;
                font-size: 12px;
                padding: 8px 12px;
            }
        }

        @media (max-width: 480px) {
            h1 {
                font-size: 1.3rem;
            }

            .status-item .value {
                font-size: 1.25rem;
            }

            .vacancies-table {
                font-size: 12px;
            }

            .show-text-btn {
                padding: 8px 12px;
                font-size: 12px;
            }
        }

        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
            :root {
                --card-bg: rgba(30, 30, 50, 0.95);
                --text-primary: #f0f0f0;
                --text-secondary: #aaa;
            }

            .status-item {
                background: linear-gradient(135deg, #2a2a4a 0%, #1a1a3a 100%);
            }

            .vacancies-table th {
                background: linear-gradient(135deg, #2a2a4a 0%, #1a1a3a 100%);
            }

            .vacancies-table td {
                border-bottom-color: #3a3a5a;
            }

            .vacancies-table tbody tr:hover {
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            }
        }

        /* Loading skeleton */
        .skeleton {
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: loading 1.5s infinite;
            border-radius: 4px;
        }

        @keyframes loading {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        /* Print styles */
        @media print {
            body {
                background: white;
                padding: 0;
            }

            .status-card, .vacancies-card {
                box-shadow: none;
                border: 1px solid #ddd;
            }

            .notification, .connection-status, .live-indicator {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Парсер вакансий - Мониторинг</h1>
        
        <div class="status-card">
            <h2>📊 Статус парсера</h2>
            <div class="status-badge-container">
                <span id="status-indicator" class="status-indicator status-{{ status }}">
                    {{ status_display }}
                </span>
            </div>
            <div class="status-grid">
                <div class="status-item">
                    <h3>Запущен</h3>
                    <div class="value" id="started-at">{{ started_at }}</div>
                </div>
                <div class="status-item">
                    <h3>Сообщений обработано</h3>
                    <div class="value" id="messages-processed">{{ messages_processed }}</div>
                </div>
                <div class="status-item">
                    <h3>Вакансий найдено</h3>
                    <div class="value" id="messages-matched">{{ messages_matched }}</div>
                </div>
                <div class="status-item">
                    <h3>Перезапусков</h3>
                    <div class="value" id="restarts">{{ restarts }}</div>
                </div>
                <div class="status-item">
                    <h3>Последнее сообщение</h3>
                    <div class="value" id="last-message-at" style="font-size: 18px;">{{ last_message_at }}</div>
                </div>
                <div class="status-item">
                    <h3>Последняя ошибка</h3>
                    <div class="value" id="last-error" style="font-size: 16px;">{{ last_error }}</div>
                </div>
            </div>
        </div>
        
        <div class="vacancies-card">
            <div class="vacancies-header">
                <h2>📋 Последние вакансии</h2>
                <div class="live-indicator">
                    <span class="live-dot"></span>
                    <span>Live обновление</span>
                </div>
            </div>
            
            {{ vacancies_table }}
        </div>
    </div>
    
    <div id="notification" class="notification">
        <span class="notification-icon">✨</span>
        <span>Новая вакансия найдена!</span>
    </div>
    
    <!-- Connection Status Indicator -->
    <div id="connection-status" class="connection-status disconnected">
        <span class="dot"></span>
        <span id="connection-text">Отключено</span>
    </div>
    
    <!-- Modal for full vacancy text -->
    <div id="modal-overlay" class="modal-overlay" onclick="if(event.target === this) closeModal()">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">Текст вакансии</h3>
                <button class="modal-close" onclick="closeModal()" aria-label="Закрыть">&times;</button>
            </div>
            <div class="modal-body" id="modal-body">
                <!-- Full text will be inserted here -->
            </div>
        </div>
    </div>
    
    <script>
        // WebSocket для realtime обновлений
        let ws = null;
        let reconnectAttempts = 0;
        const MAX_RECONNECT_ATTEMPTS = 10;
        let connectionCheckInterval = null;
        let isConnecting = false;
        
        // Обновление статуса подключения
        function updateConnectionStatus(connected) {
            const statusEl = document.getElementById('connection-status');
            const textEl = document.getElementById('connection-text');
            
            if (connected) {
                statusEl.className = 'connection-status connected';
                textEl.textContent = 'Live подключено';
            } else {
                statusEl.className = 'connection-status disconnected';
                textEl.textContent = isConnecting ? 'Подключение...' : 'Отключено';
            }
        }
        
        function connectWebSocket() {
            if (isConnecting || (ws && ws.readyState === WebSocket.OPEN)) {
                return;
            }
            
            isConnecting = true;
            updateConnectionStatus(false);
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            console.log('Connecting to WebSocket:', wsUrl);
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket connected');
                reconnectAttempts = 0;
                isConnecting = false;
                updateConnectionStatus(true);
                
                // Запускаем периодический ping
                if (connectionCheckInterval) {
                    clearInterval(connectionCheckInterval);
                }
                connectionCheckInterval = setInterval(() => {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({ type: 'ping' }));
                    }
                }, 30000);
            };
            
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'new_vacancy') {
                        addNewVacancy(data.vacancy);
                        showNotification();
                    } else if (data.type === 'pong') {
                        // Ответ на ping - соединение активно
                        console.log('WebSocket heartbeat OK');
                    }
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };
            
            ws.onclose = function(event) {
                console.log('WebSocket disconnected', event.code, event.reason);
                isConnecting = false;
                updateConnectionStatus(false);
                
                // Очищаем интервал ping
                if (connectionCheckInterval) {
                    clearInterval(connectionCheckInterval);
                    connectionCheckInterval = null;
                }
                
                // Попытка переподключения с экспоненциальной задержкой
                if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    reconnectAttempts++;
                    const delay = Math.min(2000 * reconnectAttempts, 30000);
                    console.log(`Reconnecting... (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}, delay: ${delay}ms)`);
                    setTimeout(connectWebSocket, delay);
                } else {
                    console.error('Max reconnection attempts reached');
                }
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                isConnecting = false;
                updateConnectionStatus(false);
            };
        }
        
        function addNewVacancy(vacancy) {
            const tbody = document.querySelector('.vacancies-table tbody');
            if (!tbody) return;
            
            // Проверяем, нет ли уже такой вакансии (защита от дубликатов)
            const existingRows = tbody.querySelectorAll('tr');
            for (let row of existingRows) {
                const msgLink = row.querySelector('.vacancy-link');
                if (msgLink && msgLink.href === vacancy.msg_link) {
                    console.log('Duplicate vacancy detected, skipping');
                    return;
                }
            }
            
            // Форматируем дату
            const receivedAt = new Date(vacancy.received_at);
            const dateStr = receivedAt.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            // Обрезаем текст для превью
            const textPreview = vacancy.text.substring(0, 100).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            
            // Создаём новую строку, сохраняя полные данные в объекте DOM элемента
            const row = document.createElement('tr');
            row.className = 'new-row';
            // Сохраняем полные данные вакансии прямо в элементе DOM
            row.vacancyData = {
                title: vacancy.chat_title || 'Вакансия',
                text: vacancy.text
            };
            row.innerHTML = `
                <td><span class="timestamp">${dateStr}</span></td>
                <td><a href="${vacancy.chat_link || '#'}" class="chat-link" target="_blank" rel="noopener noreferrer">${vacancy.chat_title || 'Неизвестно'}</a></td>
                <td>${vacancy.sender_name || 'Аноним'}</td>
                <td class="vacancy-text" title="${textPreview}">${textPreview}...</td>
                <td style="display: flex; gap: 8px; align-items: center;">
                    <button class="show-text-btn" onclick="showModalByRow(this)">Показать текст</button>
                    <a href="${vacancy.msg_link || '#'}" class="vacancy-link" target="_blank" rel="noopener noreferrer">Открыть →</a>
                </td>
            `;
            
            // Вставляем в начало таблицы
            tbody.insertBefore(row, tbody.firstChild);
            
            // Удаляем лишние строки если их больше 100
            while (tbody.children.length > 100) {
                tbody.removeChild(tbody.lastChild);
            }
            
            // Обновляем счётчик вакансий
            const matchedEl = document.getElementById('messages-matched');
            if (matchedEl) {
                matchedEl.textContent = parseInt(matchedEl.textContent) + 1;
            }
        }
        
        // Показать модальное окно с полным текстом вакансии (по кнопке)
        function showModalByRow(btn) {
            const row = btn.closest('tr');
            
            // Пробуем получить данные из объекта DOM (для динамически добавленных строк)
            let vacancyData = row.vacancyData;
            
            // Если нет, пробуем получить из data-атрибутов (для строк, загруженных при инициализации)
            if (!vacancyData) {
                const title = row.getAttribute('data-vacancy-title');
                const fullText = row.getAttribute('data-vacancy-text');
                if (title && fullText) {
                    vacancyData = { title: title, text: fullText };
                }
            }
            
            if (!vacancyData) return;
            
            const modalOverlay = document.getElementById('modal-overlay');
            const modalTitle = document.getElementById('modal-title');
            const modalBody = document.getElementById('modal-body');
            
            modalTitle.textContent = vacancyData.title;
            // Преобразуем переносы строк в <br> для отображения, экранируем HTML
            const escapedText = escapeHtml(vacancyData.text);
            modalBody.innerHTML = escapedText.replace(/\\n/g, '<br>').replace(/\n/g, '<br>');
            modalOverlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        // Закрытие модального окна
        function closeModal() {
            const modalOverlay = document.getElementById('modal-overlay');
            modalOverlay.classList.remove('active');
            document.body.style.overflow = '';
        }
        
        // Функция для экранирования HTML (защита от XSS)
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function showNotification() {
            const notification = document.getElementById('notification');
            notification.classList.add('show');
            
            // Воспроизводим тихий звук уведомления (опционально)
            try {
                const audio = new Audio('data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU');
                audio.volume = 0.1;
                audio.play().catch(() => {});
            } catch (e) {}
            
            setTimeout(() => {
                notification.classList.remove('show');
            }, 3000);
        }
        
        // Обработка закрытия страницы
        window.addEventListener('beforeunload', () => {
            if (ws) {
                ws.close();
            }
            if (connectionCheckInterval) {
                clearInterval(connectionCheckInterval);
            }
        });
        
        // Подключаемся при загрузке страницы
        document.addEventListener('DOMContentLoaded', connectWebSocket);
    </script>
</body>
</html>
"""
    
    # Определяем статус
    status = parser_status.get('status', 'starting')
    status_display_map = {
        'running': '🟢 Работает',
        'stopped': '🔴 Остановлен',
        'starting': '🟡 Запуск',
        'restarting': '🟠 Перезапуск'
    }
    status_display = status_display_map.get(status, status)
    
    # Форматируем дату запуска
    started_at = parser_status.get('started_at')
    if started_at:
        try:
            started_at_dt = datetime.fromisoformat(started_at)
            started_at_fmt = started_at_dt.strftime('%d.%m.%Y %H:%M')
        except:
            started_at_fmt = started_at
    else:
        started_at_fmt = 'Неизвестно'
    
    # Форматируем последнее сообщение
    last_message_at = parser_status.get('last_message_at')
    if last_message_at:
        try:
            last_message_at_dt = datetime.fromisoformat(last_message_at)
            last_message_at_fmt = last_message_at_dt.strftime('%d.%m.%Y %H:%M:%S')
        except:
            last_message_at_fmt = last_message_at
    else:
        last_message_at_fmt = 'Нет данных'
    
    # Последняя ошибка
    last_error = parser_status.get('last_error', 'Нет ошибок')
    if last_error and len(last_error) > 30:
        last_error = last_error[:30] + '...'
    
    # Генерируем таблицу вакансий
    vacancies = vacancies_store[:100]  # Показываем последние 100
    if vacancies:
        rows = []
        for idx, v in enumerate(vacancies):
            chat_link = v.get('chat_link', '#')
            chat_title = v.get('chat_title', 'Неизвестно')
            sender_name = v.get('sender_name', 'Аноним')
            text_preview = v.get('text', '')[:100].replace('"', '&quot;')
            # Экранируем для data-атрибутов (JS строка)
            full_text_js = v.get('text', '').replace('\\', '\\\\').replace("'", "\\''").replace('\n', '\\n').replace('\r', '\\r')
            title_js = chat_title.replace('\\', '\\\\').replace("'", "\\''")
            received_at = v.get('received_at', '')
            msg_link = v.get('msg_link', '#')
            
            if received_at:
                try:
                    received_at_dt = datetime.fromisoformat(received_at)
                    received_at_fmt = received_at_dt.strftime('%d.%m.%Y %H:%M')
                except:
                    received_at_fmt = received_at
            else:
                received_at_fmt = 'Неизвестно'
            
            row = f"""
            <tr data-vacancy-title="{title_js}" data-vacancy-text="{full_text_js}">
                <td><span class="timestamp">{received_at_fmt}</span></td>
                <td><a href="{chat_link}" class="chat-link" target="_blank">{chat_title}</a></td>
                <td>{sender_name}</td>
                <td class="vacancy-text" title="{text_preview}">{text_preview}...</td>
                <td style="display: flex; gap: 8px; align-items: center;">
                    <button class="show-text-btn" onclick="showModalByRow(this)">Показать текст</button>
                    <a href="{msg_link}" class="vacancy-link" target="_blank">Открыть →</a>
                </td>
            </tr>
            """
            rows.append(row)
        
        vacancies_table = f"""
        <table class="vacancies-table">
            <thead>
                <tr>
                    <th>Время</th>
                    <th>Чат</th>
                    <th>Отправитель</th>
                    <th>Текст</th>
                    <th>Ссылка</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        """
    else:
        vacancies_table = """
        <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <p>Пока нет найденных вакансий</p>
            <p style="font-size: 14px; margin-top: 10px;">Как только парсер найдёт подходящую вакансию, она появится здесь</p>
        </div>
        """
    
    # Подставляем значения в шаблон
    html = html.replace('{{ status }}', status)
    html = html.replace('{{ status_display }}', status_display)
    html = html.replace('{{ started_at }}', started_at_fmt)
    html = html.replace('{{ messages_processed }}', str(parser_status.get('messages_processed', 0)))
    html = html.replace('{{ messages_matched }}', str(parser_status.get('messages_matched', 0)))
    html = html.replace('{{ restarts }}', str(parser_status.get('restarts', 0)))
    html = html.replace('{{ last_message_at }}', last_message_at_fmt)
    html = html.replace('{{ last_error }}', last_error or 'Нет ошибок')
    html = html.replace('{{ vacancies_table }}', vacancies_table)
    
    return web.Response(text=html, content_type='text/html')


async def api_status_handler(request):
    """API endpoint для получения статуса в JSON с проверкой аутентификации"""
    auth_response = await check_auth(request)
    if auth_response:
        return auth_response
    
    return web.json_response({
        'status': parser_status,
        'vacancies_count': len(vacancies_store)
    })


async def api_vacancies_handler(request):
    """API endpoint для получения списка вакансий с проверкой аутентификации"""
    auth_response = await check_auth(request)
    if auth_response:
        return auth_response
    
    limit = int(request.query.get('limit', 100))
    return web.json_response({
        'vacancies': vacancies_store[:limit],
        'total': len(vacancies_store)
    })


async def start_dashboard_server(port: int = 8081):
    """Запуск веб-сервера дашборда"""
    app = web.Application()
    app.router.add_get('/', dashboard_handler)
    app.router.add_get('/api/status', api_status_handler)
    app.router.add_get('/api/vacancies', api_vacancies_handler)
    app.router.add_get('/ws', websocket_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Dashboard server running on http://0.0.0.0:{port}")
    logger.info(f"WebSocket endpoint available at ws://0.0.0.0:{port}/ws")
    
    # Бесконечное ожидание
    await asyncio.Event().wait()
