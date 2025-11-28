from celery import Celery
import os

def make_celery():
    """Create and configure Celery application"""
    # Default to localhost for non-Docker environments, redis:6379 for Docker
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    celery = Celery(
        'lunafrost',
        broker=redis_url,
        backend=redis_url
    )
    
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=300,  # 5 minutes max
        task_soft_time_limit=240,  # 4 minutes soft limit
        broker_connection_retry_on_startup=True,
    )
    
    return celery

celery = make_celery()

# Import tasks AFTER creating celery instance (avoid circular import)
import tasks.translation_tasks  # This registers the tasks