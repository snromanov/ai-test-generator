# src/utils/logger.py

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
        name: str = __name__,
        log_level: str = None,
        log_file: str = None
) -> logging.Logger:
    """
    Настраивает и возвращает logger для модуля

    Args:
        name: имя logger'а (обычно __name__ модуля)
        log_level: уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: путь к файлу логов (опционально)

    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)

    # Избегаем дублирования handlers при повторных вызовах
    if logger.handlers:
        return logger

    # Уровень логирования из переменной окружения или параметра
    level = log_level or os.getenv('LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, level.upper()))

    # Формат логов
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (с ротацией)
    if log_file or os.getenv('LOG_FILE'):
        file_path = log_file or os.getenv('LOG_FILE')
        log_dir = Path(file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger для быстрого использования
logger = setup_logger('req_to_code')
