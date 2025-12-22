"""Celery application configuration for Video AI Agent System."""
import os
import logging
from celery import Celery
from kombu import Queue

from src.core.config import settings

logger = logging.getLogger(__name__)

# Configure Celery
app = Celery(
    'video_ai_agent',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['src.tasks.audio_task', 'src.tasks.visual_task', 'src.tasks.camera_task', 'src.tasks.merge_task']
)

# Celery configuration
app.conf.update(
    # Task configuration
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'src.tasks.audio_task.*': {'queue': 'audio'},
        'src.tasks.visual_task.*': {'queue': 'visual'},
        'src.tasks.camera_task.*': {'queue': 'camera'},
        'src.tasks.merge_task.*': {'queue': 'merge'},
    },

    # Queue configuration
    task_queues=(
        Queue('audio', routing_key='audio'),
        Queue('visual', routing_key='visual'),
        Queue('camera', routing_key='camera'),
        Queue('merge', routing_key='merge'),
    ),

    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,

    # Retry configuration
    task_reject_on_worker_lost=True,
    task_ignore_result=False,

    # Progress tracking
    task_track_started=True,
    task_send_sent_event=True,

    # Time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes

    # Result expiration
    result_expires=3600,       # 1 hour
)

# Optional: Configure specific task timeouts
app.conf.task_soft_time_limits = {
    'src.tasks.audio_task.generate_audio': 120,  # 2 minutes
    'src.tasks.visual_task.generate_images': 180,  # 3 minutes
    'src.tasks.camera_task.create_animations': 240,  # 4 minutes
    'src.tasks.merge_task.merge_video': 300,  # 5 minutes
}

if __name__ == '__main__':
    app.start()