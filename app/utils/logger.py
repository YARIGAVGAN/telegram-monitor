import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

def setup_logger(name=__name__, log_file='logs/app.log'):
    # Создаём папку для логов, если её нет
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Если уже есть обработчики, не добавляем повторно
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Консольный вывод
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # Файловый вывод с ротацией
    fh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger