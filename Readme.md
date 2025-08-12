# Trading Leverage API - Setup Instructions

## 📁 Required Project Structure

Create the following files in your project directory:

```
trading-leverage-api/
├── trading_api.py              # Main API application
├── requirements.txt            # Python dependencies
├── docker-entrypoint.sh        # Docker startup script
├── docker-compose.yml          # Docker Compose configuration
├── Dockerfile                  # Docker build configuration
├── deploy.sh                   # Deployment script
├── .env                        # Environment variables (auto-created)
├── data/                       # Database storage (auto-created)
├── logs/                       # Log files (auto-created)
└── README.md                   # This file
```

## 🚀 Quick Setup

### Step 1: Create Project Directory
```bash
mkdir trading-leverage-api
cd trading-leverage-api
```

### Step 2: Copy Required Files
Copy these files from the artifacts to your project directory:
- `trading_api.py` - Main application code
- `requirements.txt` - Python dependencies 
- `docker-entrypoint.sh` - Docker startup script
- `docker-compose.yml` - Container orchestration
- `Dockerfile` - Container build instructions
- `deploy.sh` - Deployment automation

### Step 3: Make Scripts Executable
```bash
chmod +x deploy.sh
chmod +x docker-entrypoint.sh
```

### Step 4: Deploy
```bash
./deploy.sh
```

## 📋 File Contents Quick Reference

### requirements.txt
```
flask==3.0.0
flask-cors==4.0.0
gunicorn==21.2.0
ccxt==4.1.92
pandas==2.1.4
numpy==1.26.2
apscheduler==3.10.4
python-dotenv==1.0.0
requests==2.31.0
prometheus-flask-exporter==0.23.0
```

### Environment Variables (.env)
The deploy script will create this automatically:
```env
DATABASE_PATH=/app/data/trading_data.db
API_PORT=8079
EXCHANGE=binance
FLASK_ENV=production
LOG_LEVEL=INFO
WORKERS=4
SECRET_KEY=your-secret-key-change-this-in-production
API_KEY=your-api-key-change-this-in-production
API_KEY_REQUIRED=true
CORS_ORIGINS=localhost,127.0.0.1
ENABLE_METRICS=true
UPDATE_INTERVAL_HOURS=48
UPDATE_HOUR=2
UPDATE_MINUTE=0
TIMEZONE=UTC
```

## 🐳 Docker Commands

### Basic Operations
```bash
# Deploy everything
./deploy.sh

# View logs
./deploy.sh logs

# Check status
./deploy.sh status

# Stop services
./deploy.sh stop

# Restart services  
./deploy.sh restart

# Clean up everything
./deploy.sh clean
```

### Manual Docker Commands
```bash
# Build image
docker build -t trading-leverage-api .

# Run container
docker run -d \
  --name trading-api \
  -p 8079:8079 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  trading-leverage-api

# Check logs
docker logs -f trading-api

# Stop container
docker stop trading-api
```

## 🔧 Configuration

### API Authentication
The API uses header-based authentication. Get your API key from the `.env` file:
```bash
# Test with authentication
API_KEY=$(grep "^API_KEY=" .env | cut -d= -f2)
curl -X POST http://localhost:8079/leverage-adjustment \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"pairs": ["BTC/USDT:USDT"]}'
```

### Exchange Configuration
Supported exchanges (via CCXT):
- binance (default)
- coinbase
- kraken  
- bybit
- okx

Change in `.env` file:
```env
EXCHANGE=binance
```

## 🔍 Monitoring

### Health Checks
```bash
# Basic health check
curl http://localhost:8079/health

# Detailed status with auth
curl -H "X-API-Key: $API_KEY" http://localhost:8079/pairs
```

### Logs
```bash
# Real-time application logs
docker-compose logs -f trading-api

# Access log files directly
tail -f logs/access.log
tail -f logs/error.log
```

### Database
```bash
# Check database size
du -h data/trading_data.db

# View database contents
sqlite3 data/trading_data.db "SELECT * FROM pair_metrics LIMIT 5;"
```

## 📊 API Usage

### Get Leverage Adjustments
```bash
curl -X POST http://localhost:8079/leverage-adjustment \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "pairs": [
      "BTC/USDT:USDT",
      "ETH/USDT:USDT", 
      "ADA/USDT:USDT"
    ]
  }'
```

### Response Format
```json
{
  "BTC/USDT:USDT": {
    "leverage_adjustment": 0.8500,
    "volatility_ratio": 1.1750,
    "correlation_with_eth": 0.7234,
    "avg_daily_movement": 0.0456,
    "recommended_leverage": 5,
    "last_updated": "2025-08-07T10:30:00"
  }
}
```

## 🚨 Troubleshooting

### Common Issues

**Build fails with missing files:**
```bash
# Ensure all required files are present
ls -la
# Should show: trading_api.py, requirements.txt, docker-entrypoint.sh, etc.
```

**Permission denied on scripts:**
```bash
chmod +x deploy.sh docker-entrypoint.sh
```

**API not responding:**
```bash
# Check container status
docker-compose ps

# View logs for errors
docker-compose logs trading-api

# Restart services
docker-compose restart
```

**Database errors:**
```bash
# Check database file permissions
ls -la data/

# Recreate database
rm data/trading_data.db
docker-compose restart trading-api
```

### Port Conflicts
If port 8079 is already in use:
```bash
# Change port in docker-compose.yml
ports:
  - "8079:8079"  # Use port 8079 instead
```

## 🔒 Security Notes

### Production Checklist
- [ ] Change default API_KEY and SECRET_KEY
- [ ] Configure CORS_ORIGINS for your domain
- [ ] Set up HTTPS with SSL certificates
- [ ] Configure firewall rules
- [ ] Enable log monitoring
- [ ] Regular security updates

### Generate Secure Keys
```bash
# Generate secure API key
openssl rand -base64 32

# Update .env file with new keys
```

## 📈 Performance

### Resource Requirements
- **Minimum**: 1GB RAM, 1 CPU core, 5GB disk
- **Recommended**: 2GB RAM, 2 CPU cores, 20GB disk
- **High-load**: 4GB RAM, 4 CPU cores, 50GB disk

### Scaling
```bash
# Increase workers for higher load
# Edit .env file:
WORKERS=8

# Restart to apply changes
docker-compose restart
```

## 📞 Support

### Health Endpoints
- `GET /health` - Service health status
- `GET /pairs` - Available trading pairs  
- `POST /leverage-adjustment` - Main API endpoint

### Log Files
- `logs/access.log` - HTTP access logs
- `logs/error.log` - Application errors
- `logs/trading_api.log` - Application logs

Ready to deploy! 🚀