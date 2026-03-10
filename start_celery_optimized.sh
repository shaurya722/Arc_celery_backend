#!/bin/bash
# Optimized Celery worker configuration for SQLite
# Reduces concurrency to minimize database locking issues

echo "Starting Celery worker with optimized settings for SQLite..."
echo "Configuration:"
echo "  - Concurrency: 4 workers (reduced from 12)"
echo "  - Pool: prefork"
echo "  - Max tasks per child: 100 (prevents memory leaks)"
echo ""

celery -A arc_backend worker \
  --loglevel=info \
  --concurrency=4 \
  --max-tasks-per-child=100 \
  --hostname=worker1@%h
