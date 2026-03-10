#!/bin/bash

# System Monitoring Script for Load Testing
# Run this in a separate terminal during load testing

echo "🔍 Starting System Monitoring for Load Testing"
echo "📊 Monitoring CPU, Memory, Redis, and Celery"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to get CPU usage
get_cpu_usage() {
    echo "$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
}

# Function to get memory usage
get_memory_usage() {
    free | grep Mem | awk '{printf "%.2f%%", $3/$2 * 100.0}'
}

# Function to get Redis memory usage
get_redis_memory() {
    redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r'
}

# Function to get Celery active tasks (if flower is running)
get_celery_active() {
    # This would need flower to be accessible via API
    # For now, we'll use celery inspect
    celery -A arc_backend inspect active 2>/dev/null | grep -c "OK" || echo "N/A"
}

# Function to get Redis connections
get_redis_connections() {
    redis-cli info clients | grep connected_clients | cut -d: -f2 | tr -d '\r'
}

echo "Time | CPU Usage | Memory Usage | Redis Memory | Redis Conns | Celery Active"
echo "-----|-----------|--------------|--------------|-------------|--------------"

# Monitor for specified duration (default 300 seconds = 5 minutes)
DURATION=${1:-300}
END_TIME=$((SECONDS + DURATION))

while [ $SECONDS -lt $END_TIME ]; do
    TIMESTAMP=$(date +"%H:%M:%S")
    CPU=$(get_cpu_usage)
    MEM=$(get_memory_usage)
    REDIS_MEM=$(get_redis_memory)
    REDIS_CONNS=$(get_redis_connections)
    CELERY_ACTIVE=$(get_celery_active)

    # Color coding based on thresholds
    if [[ $(echo "$CPU > 80" | bc -l) -eq 1 ]]; then
        CPU="${RED}${CPU}${NC}"
    elif [[ $(echo "$CPU > 60" | bc -l) -eq 1 ]]; then
        CPU="${YELLOW}${CPU}${NC}"
    else
        CPU="${GREEN}${CPU}${NC}"
    fi

    printf "%s | %s | %s | %s | %s | %s\\n" "$TIMESTAMP" "$CPU" "$MEM" "$REDIS_MEM" "$REDIS_CONNS" "$CELERY_ACTIVE"
    sleep 5
done

echo ""
echo "🏁 Monitoring completed!"
echo "💡 Analyze the data above for bottlenecks:"
echo "   - CPU > 80%: Consider increasing workers"
echo "   - Memory > 90%: Consider more RAM or optimization"
echo "   - Redis memory growing: Check for memory leaks"
echo "   - High Redis connections: Monitor connection pooling"
