#!/bin/bash

set -e

echo "🚀 Starting Video AI Agent Celery Worker..."

# Load .env - CHỈ load biến Celery thật sự cần
if [ -f ".env" ]; then
    echo "📄 Found .env file - loading Celery config only..."
    export $(grep -E '^(CELERY_BROKER_URL|CELERY_RESULT_BACKEND)[[:space:]]*=' .env | sed 's/=.*//' | xargs)
fi

# Virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
fi

source venv/bin/activate

echo "🔧 Activated: $(python --version)"

# Celery config fallback
CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://:password_redis@localhost:6379/0"}
CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://:password_redis@localhost:6379/0"}

export CELERY_BROKER_URL
export CELERY_RESULT_BACKEND

echo "🔗 Broker: $CELERY_BROKER_URL"
echo "💾 Backend: $CELERY_RESULT_BACKEND"

# Test Redis
echo "🔍 Testing Redis connection..."
if redis-cli -u "$CELERY_BROKER_URL" ping > /dev/null 2>&1; then
    echo "✅ Redis OK"
else
    echo "❌ Redis failed - start Redis server first!"
    exit 1
fi

# Worker config (KHÔNG export vào Python env)
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:-4}
WORKER_LOGLEVEL=${WORKER_LOGLEVEL:-info}
WORKER_QUEUE=${WORKER_QUEUE:-"audio,visual,camera,merge,workflow"}

echo "⚙️ Concurrency: $WORKER_CONCURRENCY | Log: $WORKER_LOGLEVEL | Queues: $WORKER_QUEUE"

mkdir -p logs

echo "🛑 Killing old workers..."
pkill -f "celery.*worker" 2>/dev/null || true
sleep 2

echo "🚀 Starting Celery worker..."
exec celery -A celery_app worker \
    --loglevel="$WORKER_LOGLEVEL" \
    --concurrency="$WORKER_CONCURRENCY" \
    -Q "$WORKER_QUEUE" \
    --pidfile=celery_worker.pid \
    --logfile=logs/celery_worker.log