#!/bin/bash
set -e

# Wait for any dependencies if needed
echo "Starting Trading Leverage API..."

# Create necessary directories
mkdir -p /app/data /app/logs

# Run database migrations/initialization if needed
echo "Initializing database..."
python3 -c "
import sys
import os
sys.path.insert(0, '/app')
try:
    from trading_api import DatabaseManager
    db_path = os.getenv('DATABASE_PATH', '/app/data/trading_data.db')
    db = DatabaseManager(db_path)
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization warning: {e}')
    print('Database will be created on first API call')
"

# Start the application with Gunicorn for production
if [ "${FLASK_ENV:-production}" = "production" ]; then
    echo "Starting in production mode with Gunicorn..."
    exec gunicorn --bind 0.0.0.0:${API_PORT:-8079} \
                  --workers ${WORKERS:-4} \
                  --timeout 300 \
                  --keep-alive 2 \
                  --max-requests 1000 \
                  --max-requests-jitter 100 \
                  --access-logfile /app/logs/access.log \
                  --error-logfile /app/logs/error.log \
                  --log-level info \
                  --preload \
                  trading_api:app
else
    echo "Starting in development mode..."
    exec python3 trading_api.py
fi