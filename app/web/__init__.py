"""
Веб-модуль для дашборда
"""
from app.web.dashboard import (
    start_dashboard_server,
    add_vacancy,
    update_parser_status,
    vacancies_store,
    parser_status
)

__all__ = [
    'start_dashboard_server',
    'add_vacancy',
    'update_parser_status',
    'vacancies_store',
    'parser_status'
]
