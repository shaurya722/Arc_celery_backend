#!/bin/bash

# Arc Backend - Project Startup Script
# This script starts all required services for the Arc Backend application:
# - Redis (message broker)
# - Django development server
# - Celery workers (background task processing)
# - Celery Beat (task scheduler)

set -e  # Exit on any error

echo "=== Arc Backend Startup Script ==="
echo "Starting all services..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment 'venv' not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required commands
if ! command_exists redis-server; then
    echo "Error: redis-server not found. Please install Redis."
    exit 1
fi

if ! command_exists celery; then
    echo "Error: celery not found. Please install with: pip install celery"
    exit 1
fi

# Kill any existing processes on ports we need
echo "Cleaning up existing processes..."
pkill -f "redis-server" || true
pkill -f "runserver" || true
pkill -f "celery.*worker" || true
pkill -f "celery.*beat" || true
sleep 2

# Start Redis in background
echo "Starting Redis server..."
redis-server --daemonize yes --port 6379
sleep 1

# Verify Redis is running
if ! redis-cli ping >/dev/null 2>&1; then
    echo "Error: Redis failed to start"
    exit 1
fi
echo "✓ Redis started successfully"

# Start Django development server
echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000 &
DJANGO_PID=$!
sleep 2

# Check if Django started
if ! kill -0 $DJANGO_PID 2>/dev/null; then
    echo "Error: Django server failed to start"
    exit 1
fi
echo "✓ Django server started on http://127.0.0.1:8000"

# Start Celery Workers (multiple for load balancing)
echo "Starting Celery workers..."
celery -A arc_backend worker --loglevel=info --hostname=worker1@%h --concurrency=2 --logfile=celery_worker1.log &
WORKER1_PID=$!

celery -A arc_backend worker --loglevel=info --hostname=worker2@%h --concurrency=2 --logfile=celery_worker2.log &
WORKER2_PID=$!

celery -A arc_backend worker --loglevel=info --hostname=worker3@%h --concurrency=2 --logfile=celery_worker3.log &
WORKER3_PID=$!

celery -A arc_backend worker --loglevel=info --hostname=worker4@%h --concurrency=2 --logfile=celery_worker4.log &
WORKER4_PID=$!

sleep 3

# Verify workers are running
WORKER_COUNT=$(ps aux | grep "celery.*worker" | grep -v grep | wc -l)
if [ "$WORKER_COUNT" -lt 4 ]; then
    echo "Warning: Only $WORKER_COUNT Celery workers started (expected 4)"
else
    echo "✓ Celery workers started successfully"
fi

# Start Celery Beat (scheduler)
echo "Starting Celery Beat scheduler..."
celery -A arc_backend beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler --logfile=celery_beat.log &
BEAT_PID=$!
sleep 2

if ! kill -0 $BEAT_PID 2>/dev/null; then
    echo "Warning: Celery Beat failed to start"
else
    echo "✓ Celery Beat started successfully"
fi

echo ""
echo "=== All Services Started Successfully! ==="
echo "Django Server:     http://127.0.0.1:8000"
echo "API Documentation: http://127.0.0.1:8000/api/schema/swagger-ui/"
echo "Admin Panel:       http://127.0.0.1:8000/admin/"
echo ""
echo "Optional Monitoring:"
echo "Celery Flower:     celery -A arc_backend flower (then visit http://127.0.0.0:5555)"
echo ""
echo "Log files:"
echo "- celery_worker1.log, celery_worker2.log, celery_worker3.log, celery_worker4.log"
echo "- celery_beat.log"
echo ""
echo "To stop all services, press Ctrl+C or run: pkill -f 'redis\|runserver\|celery'"
echo ""
echo "Process IDs:"
echo "Django: $DJANGO_PID"
echo "Workers: $WORKER1_PID, $WORKER2_PID, $WORKER3_PID, $WORKER4_PID"
echo "Beat: $BEAT_PID"

# Wait for user interrupt to stop all services
trap 'echo ""; echo "Stopping all services..."; pkill -P $$; exit 0' INT TERM

# Keep script running
wait
