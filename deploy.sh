#!/bin/bash
set -e

echo "🚀 Starting Trading Leverage API Deployment..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required files exist
check_files() {
    print_status "Checking required files..."

    required_files=("trading_api.py" "requirements.txt" "docker-entrypoint.sh" "docker-compose.yml")
    missing_files=()

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done

    if [ ${#missing_files[@]} -gt 0 ]; then
        print_error "Missing required files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        print_error "Please ensure all required files are in the current directory."
        exit 1
    fi

    print_status "All required files found ✓"
}

# Create necessary directories
setup_directories() {
    print_status "Setting up directories..."
    directories=("data" "logs" "config")

    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_status "Created directory: $dir"
        fi
    done

    # Make entrypoint script executable
    chmod +x docker-entrypoint.sh
}

# Create .env file if it doesn't exist
create_env_file() {
    if [ ! -f ".env" ]; then
        print_status "Creating .env file..."
        cat > .env << 'EOF'
# Trading API Configuration
DATABASE_PATH=/app/data/trading_data.db
API_PORT=8079
EXCHANGE=binance
FLASK_ENV=production
LOG_LEVEL=INFO
WORKERS=2

# Security (CHANGE THESE IN PRODUCTION!)
SECRET_KEY=your-secret-key-change-this-in-production
API_KEY=your-api-key-change-this-in-production
API_KEY_REQUIRED=true

# CORS settings
CORS_ORIGINS=localhost,127.0.0.1

# Monitoring
ENABLE_METRICS=true

# Scheduler settings
UPDATE_INTERVAL_HOURS=48
UPDATE_HOUR=2
UPDATE_MINUTE=0
TIMEZONE=UTC
EOF
        print_warning "Created .env file with default values."
        print_warning "⚠️  IMPORTANT: Change SECRET_KEY and API_KEY before production use!"
    else
        print_status ".env file already exists ✓"
    fi
}

# Build and deploy with Docker Compose
deploy_services() {
    print_status "Building and deploying services..."

    # Stop any existing containers
    docker-compose down --remove-orphans 2>/dev/null || true

    # Build and start services
    docker-compose up --build -d

    if [ $? -eq 0 ]; then
        print_status "Services started successfully ✓"
    else
        print_error "Failed to start services"
        exit 1
    fi
}

# Wait for health check
wait_for_health() {
    print_status "Waiting for service health check..."

    max_attempts=24  # 2 minutes (24 * 5 seconds)
    attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s -f http://localhost:8079/health >/dev/null 2>&1; then
            print_status "Health check passed ✓"
            return 0
        fi

        echo -n "."
        sleep 5
        attempt=$((attempt + 1))
    done

    print_error "Health check failed after 2 minutes"
    print_status "Checking logs..."
    docker-compose logs trading-api
    return 1
}

# Show deployment status
show_status() {
    echo
    print_status "Deployment Status:"
    echo
    docker-compose ps
    echo

    print_status "Testing API..."
    if curl -s http://localhost:8079/health | grep -q "healthy"; then
        print_status "✅ API is responding correctly"
    else
        print_warning "⚠️  API health check returned unexpected response"
    fi

    echo
    print_status "Available endpoints:"
    echo "  • Health Check: http://localhost:8079/health"
    echo "  • API Endpoint: http://localhost:8079/leverage-adjustment"
    echo "  • Available Pairs: http://localhost:8079/pairs"
    echo

    print_status "Management commands:"
    echo "  • View logs: docker-compose logs -f trading-api"
    echo "  • Stop services: docker-compose down"
    echo "  • Restart: docker-compose restart"
    echo

    # Show API key from .env file
    if [ -f ".env" ] && grep -q "API_KEY=" .env; then
        api_key=$(grep "^API_KEY=" .env | cut -d= -f2)
        echo
        print_status "API Usage Example:"
        echo "curl -X POST http://localhost:8079/leverage-adjustment \\"
        echo "  -H 'Content-Type: application/json' \\"
        echo "  -H 'X-API-Key: $api_key' \\"
        echo "  -d '{\"pairs\": [\"BTC/USDT:USDT\", \"ETH/USDT:USDT\"]}'"
    fi
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy"|"")
        check_files
        setup_directories
        create_env_file
        deploy_services
        wait_for_health
        show_status
        print_status "🎉 Deployment completed successfully!"
        ;;
    "logs")
        docker-compose logs -f trading-api
        ;;
    "status")
        docker-compose ps
        echo
        curl -s http://localhost:8079/health 2>/dev/null | python3 -m json.tool || echo "API not responding"
        ;;
    "stop")
        docker-compose down
        print_status "Services stopped"
        ;;
    "restart")
        docker-compose restart
        print_status "Services restarted"
        ;;
    "clean")
        docker-compose down -v
        docker system prune -f
        print_status "Cleanup completed"
        ;;
    *)
        echo "Usage: $0 {deploy|logs|status|stop|restart|clean}"
        echo
        echo "Commands:"
        echo "  deploy   - Build and deploy the API (default)"
        echo "  logs     - Show real-time logs"
        echo "  status   - Show service status and health"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart services"
        echo "  clean    - Stop services and clean up Docker resources"
        exit 1
        ;;
esac