"""
Веб-дашборд для отображения состояния парсера и списка вакансий
"""
from aiohttp import web
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

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

MAX_VACANCIES = 500  # Максимальное количество хранимых вакансий


def add_vacancy(vacancy: Dict[str, Any]):
    """Добавить вакансию в хранилище"""
    global vacancies_store
    vacancy['received_at'] = datetime.now().isoformat()
    vacancies_store.insert(0, vacancy)
    # Ограничиваем размер хранилища
    if len(vacancies_store) > MAX_VACANCIES:
        vacancies_store = vacancies_store[:MAX_VACANCIES]


def update_parser_status(**kwargs):
    """Обновить статус парсера"""
    for key, value in kwargs.items():
        if key in parser_status:
            parser_status[key] = value


async def dashboard_handler(request):
    """Обработчик главной страницы дашборда"""
    html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Парсер вакансий - Дашборд</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .status-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .status-item {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border-left: 4px solid #667eea;
        }
        .status-item h3 {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .status-item .value {
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }
        .status-indicator {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 14px;
        }
        .status-running {
            background: #d4edda;
            color: #155724;
        }
        .status-stopped {
            background: #f8d7da;
            color: #721c24;
        }
        .status-starting {
            background: #fff3cd;
            color: #856404;
        }
        .vacancies-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .vacancies-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        .vacancies-header h2 {
            color: #333;
        }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s;
        }
        .refresh-btn:hover {
            background: #5a6fd6;
        }
        .vacancies-table {
            width: 100%;
            border-collapse: collapse;
        }
        .vacancies-table th,
        .vacancies-table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #f0f0f0;
        }
        .vacancies-table th {
            background: #f8f9fa;
            color: #666;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
        }
        .vacancies-table tr:hover {
            background: #f8f9fa;
        }
        .vacancy-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        .vacancy-link:hover {
            text-decoration: underline;
        }
        .chat-link {
            color: #28a745;
            text-decoration: none;
            font-weight: 500;
        }
        .vacancy-text {
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: #666;
            font-size: 14px;
        }
        .timestamp {
            color: #999;
            font-size: 13px;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }
        .empty-state svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        @media (max-width: 768px) {
            .status-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .vacancies-table {
                font-size: 14px;
            }
            .vacancies-table th,
            .vacancies-table td {
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Парсер вакансий - Мониторинг</h1>
        
        <div class="status-card">
            <h2 style="color: #333; margin-bottom: 15px;">Статус парсера</h2>
            <div style="margin-bottom: 20px;">
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
                <button class="refresh-btn" onclick="location.reload()">🔄 Обновить</button>
            </div>
            
            {{ vacancies_table }}
        </div>
    </div>
    
    <script>
        // Автообновление каждые 30 секунд
        setTimeout(() => location.reload(), 30000);
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
        for v in vacancies:
            chat_link = v.get('chat_link', '#')
            chat_title = v.get('chat_title', 'Неизвестно')
            sender_name = v.get('sender_name', 'Аноним')
            text = v.get('text', '')[:100].replace('"', '&quot;')
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
            <tr>
                <td><span class="timestamp">{received_at_fmt}</span></td>
                <td><a href="{chat_link}" class="chat-link" target="_blank">{chat_title}</a></td>
                <td>{sender_name}</td>
                <td class="vacancy-text" title="{text}">{text}...</td>
                <td><a href="{msg_link}" class="vacancy-link" target="_blank">Открыть →</a></td>
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
    """API endpoint для получения статуса в JSON"""
    return web.json_response({
        'status': parser_status,
        'vacancies_count': len(vacancies_store)
    })


async def api_vacancies_handler(request):
    """API endpoint для получения списка вакансий"""
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
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Dashboard server running on http://0.0.0.0:{port}")
    
    # Бесконечное ожидание
    await asyncio.Event().wait()
