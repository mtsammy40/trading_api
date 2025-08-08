#!/usr/bin/env python3
"""
Trading Leverage Adjustment REST API
Calculates leverage adjustments and indicators relative to ETH
"""

import os
import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
from logging.handlers import RotatingFileHandler

import ccxt
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from prometheus_flask_exporter import PrometheusMetrics

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# Configure logging for production
def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = os.getenv('LOG_FILE', 'logs/trading_api.log')

    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Add file handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=int(os.getenv('LOG_MAX_BYTES', 10485760)),
        backupCount=int(os.getenv('LOG_BACKUP_COUNT', 5))
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    logger = logging.getLogger(__name__)
    logger.addHandler(file_handler)
    return logger


logger = setup_logging()

# Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'trading_data.db')
EXCHANGE = os.getenv('EXCHANGE', 'binance')
API_PORT = int(os.getenv('API_PORT', 5000))
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
API_KEY_REQUIRED = os.getenv('API_KEY_REQUIRED', 'false').lower() == 'true'
API_KEY = os.getenv('API_KEY', '')
ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
DEFAULT_PAIRS = [
    'BTC/USDT:USDT',
    'ETH/USDT:USDT',
    'ADA/USDT:USDT',
    'SOL/USDT:USDT',
    'MATIC/USDT:USDT',
    'DOT/USDT:USDT',
    'LINK/USDT:USDT',
    'UNI/USDT:USDT'
]


@dataclass
class PairMetrics:
    """Data class for pair trading metrics"""
    pair: str
    leverage_adjustment: float
    volatility_ratio: float
    correlation_with_eth: float
    avg_daily_movement: float
    recommended_leverage: int
    last_updated: datetime


class DatabaseManager:
    """Manages SQLite database operations"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pair_metrics (
                    pair TEXT PRIMARY KEY,
                    leverage_adjustment REAL,
                    volatility_ratio REAL,
                    correlation_with_eth REAL,
                    avg_daily_movement REAL,
                    recommended_leverage INTEGER,
                    last_updated TIMESTAMP
                )
            ''')
            conn.commit()

    def save_metrics(self, metrics: PairMetrics):
        """Save pair metrics to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO pair_metrics 
                (pair, leverage_adjustment, volatility_ratio, correlation_with_eth, 
                 avg_daily_movement, recommended_leverage, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics.pair,
                metrics.leverage_adjustment,
                metrics.volatility_ratio,
                metrics.correlation_with_eth,
                metrics.avg_daily_movement,
                metrics.recommended_leverage,
                metrics.last_updated
            ))
            conn.commit()

    def get_metrics(self, pairs: List[str]) -> Dict[str, PairMetrics]:
        """Retrieve metrics for specified pairs"""
        placeholders = ','.join('?' * len(pairs))
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f'''
                SELECT * FROM pair_metrics 
                WHERE pair IN ({placeholders})
            ''', pairs)

            results = {}
            for row in cursor.fetchall():
                metrics = PairMetrics(
                    pair=row[0],
                    leverage_adjustment=row[1],
                    volatility_ratio=row[2],
                    correlation_with_eth=row[3],
                    avg_daily_movement=row[4],
                    recommended_leverage=row[5],
                    last_updated=datetime.fromisoformat(row[6])
                )
                results[row[0]] = metrics

            return results

    def get_all_pairs(self) -> List[str]:
        """Get all pairs in database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT pair FROM pair_metrics')
            return [row[0] for row in cursor.fetchall()]


class TradingAnalyzer:
    """Analyzes trading pairs and calculates metrics"""

    def __init__(self, exchange_name: str = EXCHANGE):
        self.exchange = getattr(ccxt, exchange_name)({
            'sandbox': False,
            'enableRateLimit': True,
        })

    def get_ohlcv_data(self, symbol: str, timeframe: str = '1d', days: int = 28) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol"""
        try:
            since = self.exchange.milliseconds() - days * 24 * 60 * 60 * 1000
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since)

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_daily_returns(self, df: pd.DataFrame) -> pd.Series:
        """Calculate daily returns from OHLCV data"""
        return df['close'].pct_change().dropna()

    def calculate_volatility(self, returns: pd.Series) -> float:
        """Calculate annualized volatility"""
        return returns.std() * np.sqrt(365)

    def calculate_avg_daily_movement(self, df: pd.DataFrame) -> float:
        """Calculate average daily price movement (high-low)/close"""
        daily_movement = (df['high'] - df['low']) / df['close']
        return daily_movement.mean()

    def calculate_leverage_adjustment(self, pair_volatility: float, eth_volatility: float,
                                      pair_avg_movement: float, eth_avg_movement: float) -> float:
        """
        Calculate leverage adjustment relative to ETH
        Higher volatility = lower leverage multiplier
        """
        volatility_ratio = pair_volatility / eth_volatility if eth_volatility > 0 else 1.0
        movement_ratio = pair_avg_movement / eth_avg_movement if eth_avg_movement > 0 else 1.0

        # Combine volatility and movement ratios
        risk_ratio = (volatility_ratio + movement_ratio) / 2

        # Inverse relationship: higher risk = lower leverage
        leverage_adjustment = 1.0 / risk_ratio if risk_ratio > 0 else 1.0

        # Clamp between 0.1 and 2.0
        return max(0.1, min(2.0, leverage_adjustment))

    def calculate_correlation(self, returns1: pd.Series, returns2: pd.Series) -> float:
        """Calculate correlation between two return series"""
        aligned_data = pd.concat([returns1, returns2], axis=1).dropna()
        if len(aligned_data) < 10:
            return 0.0
        return aligned_data.iloc[:, 0].corr(aligned_data.iloc[:, 1])

    def recommend_leverage(self, leverage_adjustment: float, volatility_ratio: float) -> int:
        """Recommend leverage level based on adjustments"""
        base_leverage = 10

        # Adjust based on volatility and leverage adjustment
        adjusted_leverage = base_leverage * leverage_adjustment

        # Apply volatility penalty
        if volatility_ratio > 1.5:
            adjusted_leverage *= 0.6
        elif volatility_ratio > 1.2:
            adjusted_leverage *= 0.8

        # Round to common leverage levels
        leverage_levels = [1, 2, 3, 5, 10, 20, 25, 50]
        recommended = min(leverage_levels, key=lambda x: abs(x - adjusted_leverage))

        return max(1, min(25, recommended))  # Cap at 25x for safety

    def analyze_pair(self, pair: str, eth_data: Dict) -> Optional[PairMetrics]:
        """Analyze a single trading pair"""
        try:
            logger.info(f"Analyzing pair: {pair}")

            # Get pair data
            pair_df = self.get_ohlcv_data(pair)
            if pair_df.empty:
                logger.warning(f"No data available for {pair}")
                return None

            # Calculate pair metrics
            pair_returns = self.calculate_daily_returns(pair_df)
            pair_volatility = self.calculate_volatility(pair_returns)
            pair_avg_movement = self.calculate_avg_daily_movement(pair_df)

            # Calculate relative metrics to ETH
            volatility_ratio = pair_volatility / eth_data['volatility'] if eth_data['volatility'] > 0 else 1.0
            leverage_adjustment = self.calculate_leverage_adjustment(
                pair_volatility, eth_data['volatility'],
                pair_avg_movement, eth_data['avg_movement']
            )
            correlation = self.calculate_correlation(pair_returns, eth_data['returns'])
            recommended_leverage = self.recommend_leverage(leverage_adjustment, volatility_ratio)

            return PairMetrics(
                pair=pair,
                leverage_adjustment=leverage_adjustment,
                volatility_ratio=volatility_ratio,
                correlation_with_eth=correlation,
                avg_daily_movement=pair_avg_movement,
                recommended_leverage=recommended_leverage,
                last_updated=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error analyzing pair {pair}: {e}")
            return None

    def analyze_all_pairs(self, pairs: List[str]) -> Dict[str, PairMetrics]:
        """Analyze all pairs relative to ETH"""
        results = {}

        # First, analyze ETH as the reference
        logger.info("Analyzing ETH as reference...")
        eth_df = self.get_ohlcv_data('ETH/USDT:USDT')
        if eth_df.empty:
            logger.error("Could not fetch ETH data - using defaults")
            eth_data = {
                'volatility': 0.8,  # Default ETH volatility
                'avg_movement': 0.05,  # Default ETH daily movement
                'returns': pd.Series([0])  # Dummy returns
            }
        else:
            eth_returns = self.calculate_daily_returns(eth_df)
            eth_data = {
                'volatility': self.calculate_volatility(eth_returns),
                'avg_movement': self.calculate_avg_daily_movement(eth_df),
                'returns': eth_returns
            }

        logger.info(
            f"ETH reference metrics - Volatility: {eth_data['volatility']:.3f}, Avg Movement: {eth_data['avg_movement']:.3f}")

        # Analyze each pair
        for pair in pairs:
            metrics = self.analyze_pair(pair, eth_data)
            if metrics:
                results[pair] = metrics
                logger.info(f"{pair}: Leverage Adj: {metrics.leverage_adjustment:.3f}, "
                            f"Volatility Ratio: {metrics.volatility_ratio:.3f}, "
                            f"Recommended Leverage: {metrics.recommended_leverage}x")

        return results


# Initialize components
db_manager = DatabaseManager(DATABASE_PATH)
analyzer = TradingAnalyzer()

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Enable CORS for cross-origin requests
CORS(app, origins=os.getenv('CORS_ORIGINS', '*').split(','))

# Initialize Prometheus metrics if enabled
if ENABLE_METRICS:
    metrics = PrometheusMetrics(app)
    metrics.info('trading_api_info', 'Trading API Info', version='1.0.0')


def require_api_key(f):
    """Decorator to require API key authentication"""

    def decorated_function(*args, **kwargs):
        if API_KEY_REQUIRED:
            provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
            if not provided_key or provided_key != API_KEY:
                return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "Request payload too large"}), 413


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        pairs_count = len(db_manager.get_all_pairs())

        # Test exchange connection
        exchange_status = "connected"
        try:
            analyzer.exchange.fetch_ticker('BTC/USDT')
        except:
            exchange_status = "disconnected"

        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database_pairs": pairs_count,
            "exchange_status": exchange_status,
            "scheduler_running": scheduler.running if 'scheduler' in globals() else False
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503


@app.route('/leverage-adjustment', methods=['POST'])
@require_api_key
def get_leverage_adjustment():
    """Main endpoint for getting leverage adjustments"""
    try:
        data = request.get_json()
        pairs = data.get('pairs', [])

        if not pairs:
            return jsonify({"error": "No pairs provided"}), 400

        # Get metrics from database
        metrics = db_manager.get_metrics(pairs)

        # Prepare response
        response = {}
        for pair in pairs:
            if pair in metrics:
                m = metrics[pair]
                response[pair] = {
                    "leverage_adjustment": round(m.leverage_adjustment, 4),
                    "volatility_ratio": round(m.volatility_ratio, 4),
                    "correlation_with_eth": round(m.correlation_with_eth, 4),
                    "avg_daily_movement": round(m.avg_daily_movement, 4),
                    "recommended_leverage": m.recommended_leverage,
                    "last_updated": m.last_updated.isoformat()
                }
            else:
                response[pair] = {
                    "error": "Pair not found in database",
                    "leverage_adjustment": 1.0,  # Default
                    "recommended_leverage": 5  # Conservative default
                }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in leverage_adjustment endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/pairs', methods=['GET'])
def get_available_pairs():
    """Get all available pairs in database"""
    try:
        pairs = db_manager.get_all_pairs()
        return jsonify({"pairs": pairs, "count": len(pairs)})
    except Exception as e:
        logger.error(f"Error getting pairs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/update-metrics', methods=['POST'])
@require_api_key
def manual_update():
    """Manually trigger metrics update"""
    try:
        data = request.get_json() or {}
        pairs = data.get('pairs', DEFAULT_PAIRS)

        update_metrics(pairs)
        return jsonify({"status": "Update completed", "pairs_updated": len(pairs)})
    except Exception as e:
        logger.error(f"Error in manual update: {e}")
        return jsonify({"error": str(e)}), 500


def update_metrics(pairs: List[str] = None):
    """Update metrics for specified pairs"""
    if pairs is None:
        pairs = DEFAULT_PAIRS

    logger.info(f"Starting metrics update for {len(pairs)} pairs...")

    try:
        results = analyzer.analyze_all_pairs(pairs)

        # Save results to database
        for pair, metrics in results.items():
            db_manager.save_metrics(metrics)
            logger.info(f"Saved metrics for {pair}")

        logger.info(f"Metrics update completed. Updated {len(results)} pairs.")

    except Exception as e:
        logger.error(f"Error during metrics update: {e}")
        raise


# Scheduler setup
scheduler = BackgroundScheduler()


def scheduled_update():
    """Scheduled metrics update"""
    logger.info("Running scheduled metrics update...")
    try:
        update_metrics()
    except Exception as e:
        logger.error(f"Scheduled update failed: {e}")


if __name__ == '__main__':
    # Initial data update
    logger.info("Starting initial metrics calculation...")
    try:
        update_metrics()
        logger.info("Initial metrics calculation completed")
    except Exception as e:
        logger.error(f"Initial update failed: {e}")

    # Schedule updates every 48 hours
    scheduler.add_job(
        func=scheduled_update,
        trigger=CronTrigger(hour=2, minute=0),  # Run at 2:00 AM every day
        id='metrics_update',
        name='Update trading metrics every 48 hours',
        replace_existing=True
    )

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started - metrics will update every 48 hours at 2:00 AM")

    # Start Flask app
    logger.info(f"Starting Flask API server on port {API_PORT}...")
    app.run(host='0.0.0.0', port=API_PORT, debug=False)