# config/production.py
import os
from datetime import timedelta


class ProductionConfig:
    """Production configuration"""

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    DEBUG = False
    TESTING = False

    # Database settings
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/data/trading_data.db')
    DATABASE_BACKUP_PATH = os.getenv('DATABASE_BACKUP_PATH', '/app/data/backups')

    # API settings
    API_PORT = int(os.getenv('API_PORT', 8079))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size

    # Exchange settings
    EXCHANGE = os.getenv('EXCHANGE', 'binance')
    EXCHANGE_SANDBOX = os.getenv('EXCHANGE_SANDBOX', 'false').lower() == 'true'
    RATE_LIMIT = True

    # Scheduler settings
    SCHEDULER_TIMEZONE = os.getenv('TIMEZONE', 'UTC')
    UPDATE_INTERVAL_HOURS = int(os.getenv('UPDATE_INTERVAL_HOURS', 48))
    UPDATE_HOUR = int(os.getenv('UPDATE_HOUR', 2))
    UPDATE_MINUTE = int(os.getenv('UPDATE_MINUTE', 0))

    # Logging settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', '/app/logs/trading_api.log')
    LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 10485760))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))

    # Cache settings
    CACHE_TIMEOUT = int(os.getenv('CACHE_TIMEOUT', 300))  # 5 minutes

    # Security settings
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'localhost,127.0.0.1').split(',')
    API_KEY_REQUIRED = os.getenv('API_KEY_REQUIRED', 'false').lower() == 'true'
    API_KEY = os.getenv('API_KEY', '')

    # Monitoring settings
    ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    METRICS_PORT = int(os.getenv('METRICS_PORT', 9090))
