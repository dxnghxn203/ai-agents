#!/bin/bash

# Video AI Agent System - Celery Worker Runner Script
# Giai đoạn 7: run_worker.sh

set -e

echo "🚀 Starting Video AI Agent Celery Worker..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating..."
    python3 -m venv venv
    echo "📦 Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
fi

# Activate virtual environment
source venv/bin/activate

echo "🔧 Environment activated: $(python --version)"
echo "📦 Python path: $(which python)"

# Set environment variables for Celery
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/0"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/0"}

echo "🔗 Celery Broker: $CELERY_BROKER_URL"
echo "💾 Celery Backend: $CELERY_RESULT_BACKEND"

# Check if Redis is running
echo "🔍 Checking Redis connection..."
if redis-cli -u "$CELERY_BROKER_URL" ping > /dev/null 2>&1; then
    echo "✅ Redis connection successful"
else
    echo "❌ Redis connection failed. Please start Redis server:"
    echo "   redis-server"
    echo "   or: brew services start redis (on macOS)"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Worker configuration
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:-4}
WORKER_LOGLEVEL=${WORKER_LOGLEVEL:-info}
WORKER_QUEUE=${WORKER_QUEUE:-"audio,visual,camera,merge"}

echo "⚙️  Worker Configuration:"
echo "   - Concurrency: $WORKER_CONCURRENCY"
echo "   - Log Level: $WORKER_LOGLEVEL"
echo "   - Queues: $WORKER_QUEUE"

# Get project root directory
PROJECT_ROOT=$(pwd)
echo "📁 Project Root: $PROJECT_ROOT"

# Kill any existing worker processes
echo "🛑 Stopping existing worker processes..."
pkill -f "celery worker" 2>/dev/null || true
sleep 2

# Start Celery worker
echo "🚀 Starting Celery worker..."
echo "   Command: celery -A celery_app worker --loglevel=$WORKER_LOGLEVEL --concurrency=$WORKER_CONCURRENCY -Q $WORKER_QUEUE --pidfile=celery_worker.pid --logfile=logs/celery_worker.log"

exec celery -A celery_app worker \
    --loglevel="$WORKER_LOGLEVEL" \
    --concurrency="$WORKER_CONCURRENCY" \
    -Q "$WORKER_QUEUE" \
    --pidfile="celery_worker.pid" \
    --logfile="logs/celery_worker.log"