
# monitoring.sh - Monitoring and alerting script

#!/bin/bash

# Configuration
API_URL="http://localhost:8079"
WEBHOOK_URL=""  # Slack/Discord webhook URL
LOG_FILE="logs/monitoring.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

check_api_health() {
    local response=$(curl -s -w "%{http_code}" -o /tmp/health_response "$API_URL/health")
    local http_code="${response: -3}"

    if [ "$http_code" = "200" ]; then
        log "✅ API Health Check: OK"
        return 0
    else
        log "❌ API Health Check: FAILED (HTTP $http_code)"
        return 1
    fi
}

check_database_size() {
    local db_file="data/trading_data.db"
    if [ -f "$db_file" ]; then
        local size=$(du -h "$db_file" | cut -f1)
        log "📊 Database Size: $size"

        # Alert if database is over 100MB
        local size_mb=$(du -m "$db_file" | cut -f1)
        if [ "$size_mb" -gt 100 ]; then
            log "⚠️  Warning: Database size is over 100MB"
            send_alert "Database size warning: ${size}B"
        fi
    else
        log "❌ Database file not found"
        return 1
    fi
}

check_log_files() {
    local log_dir="logs"
    local total_size=$(du -sh "$log_dir" 2>/dev/null | cut -f1 || echo "0")
    log "📋 Log Files Size: $total_size"

    # Clean old logs (older than 30 days)
    find "$log_dir" -name "*.log*" -mtime +30 -delete 2>/dev/null || true
}

check_container_stats() {
    if command -v docker &> /dev/null; then
        local stats=$(docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep trading)
        if [ ! -z "$stats" ]; then
            log "🐳 Container Stats:"
            log "$stats"
        fi
    fi
}

send_alert() {
    local message="$1"

    if [ ! -z "$WEBHOOK_URL" ]; then
        curl -X POST -H 'Content-type: application/json' \
             --data "{\"text\":\"Trading API Alert: $message\"}" \
             "$WEBHOOK_URL" &>/dev/null
    fi

    log "🚨 ALERT: $message"
}

# Main monitoring function
run_monitoring() {
    log "🔍 Starting monitoring checks..."

    local checks_failed=0

    # Health check
    if ! check_api_health; then
        checks_failed=$((checks_failed + 1))
        send_alert "API health check failed"
    fi

    # Database checks
    check_database_size

    # Log file maintenance
    check_log_files

    # Container stats
    check_container_stats

    # Check API response time
    local response_time=$(curl -o /dev/null -s -w '%{time_total}\n' "$API_URL/health")
    log "⏱️  API Response Time: ${response_time}s"

    # Alert if response time is over 5 seconds
    if (( $(echo "$response_time > 5.0" | bc -l) )); then
        send_alert "API response time is slow: ${response_time}s"
    fi

    # Check disk space
    local disk_usage=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    log "💾 Disk Usage: ${disk_usage}%"

    if [ "$disk_usage" -gt 85 ]; then
        send_alert "High disk usage: ${disk_usage}%"
    fi

    # Check memory usage
    local mem_usage=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
    log "🧠 Memory Usage: ${mem_usage}%"

    if (( $(echo "$mem_usage > 85.0" | bc -l) )); then
        send_alert "High memory usage: ${mem_usage}%"
    fi

    log "✅ Monitoring checks completed (Failed: $checks_failed)"

    if [ "$checks_failed" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# Performance testing function
run_performance_test() {
    log "🚀 Running performance test..."

    local test_payload='{"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT", "ADA/USDT:USDT"]}'
    local start_time=$(date +%s.%3N)

    # Test API endpoint
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d "$test_payload" \
        -w "%{http_code}" \
        "$API_URL/leverage-adjustment")

    local end_time=$(date +%s.%3N)
    local duration=$(echo "$end_time - $start_time" | bc)
    local http_code="${response: -3}"

    if [ "$http_code" = "200" ]; then
        log "✅ Performance Test: OK (${duration}s)"
    else
        log "❌ Performance Test: FAILED (HTTP $http_code, ${duration}s)"
        send_alert "Performance test failed: HTTP $http_code"
        return 1
    fi
}

# Backup function
backup_database() {
    log "💾 Creating database backup..."

    local backup_dir="backups/$(date +%Y%m%d)"
    local backup_file="$backup_dir/trading_data_$(date +%H%M%S).db"

    mkdir -p "$backup_dir"

    if [ -f "data/trading_data.db" ]; then
        cp "data/trading_data.db" "$backup_file"
        gzip "$backup_file"
        log "✅ Database backed up to: ${backup_file}.gz"

        # Clean old backups (keep last 7 days)
        find backups -name "*.db.gz" -mtime +7 -delete 2>/dev/null || true

        return 0
    else
        log "❌ Database file not found for backup"
        return 1
    fi
}

# Log rotation function
rotate_logs() {
    log "🔄 Rotating log files..."

    # Rotate application logs
    if [ -f "logs/trading_api.log" ]; then
        local timestamp=$(date +%Y%m%d_%H%M%S)
        mv "logs/trading_api.log" "logs/trading_api_${timestamp}.log"
        gzip "logs/trading_api_${timestamp}.log"
        log "✅ Application log rotated"
    fi

    # Clean old rotated logs (keep last 30 days)
    find logs -name "*.log.gz" -mtime +30 -delete 2>/dev/null || true

    # Restart the API to start fresh log file
    docker-compose restart trading-api
    log "✅ API restarted for log rotation"
}

# Cleanup function
cleanup_system() {
    log "🧹 Running system cleanup..."

    # Clean Docker system
    if command -v docker &> /dev/null; then
        docker system prune -f >/dev/null 2>&1
        log "✅ Docker system cleaned"
    fi

    # Clean temporary files
    rm -rf /tmp/trading_api_* 2>/dev/null || true
    rm -rf /tmp/health_response 2>/dev/null || true

    # Clean old backup files
    find backups -type f -mtime +30 -delete 2>/dev/null || true

    log "✅ System cleanup completed"
}

# Main function with argument handling
case "${1:-monitor}" in
    "monitor")
        run_monitoring
        ;;
    "performance")
        run_performance_test
        ;;
    "backup")
        backup_database
        ;;
    "rotate-logs")
        rotate_logs
        ;;
    "cleanup")
        cleanup_system
        ;;
    "full")
        log "🔍 Running full monitoring suite..."
        run_monitoring
        run_performance_test
        backup_database
        cleanup_system
        log "✅ Full monitoring suite completed"
        ;;
    *)
        echo "Usage: $0 {monitor|performance|backup|rotate-logs|cleanup|full}"
        echo ""
        echo "Commands:"
        echo "  monitor      - Run basic health and system checks"
        echo "  performance  - Run API performance test"
        echo "  backup       - Backup database"
        echo "  rotate-logs  - Rotate and compress log files"
        echo "  cleanup      - Clean temporary files and Docker cache"
        echo "  full         - Run all monitoring tasks"
        exit 1
        ;;
esac