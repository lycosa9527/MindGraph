"""
Celery Application Configuration
Author: lycosa9527
Made by: MindSpring Team

Celery app for background task processing (document processing, etc.)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
from celery import Celery

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB = os.getenv('REDIS_CELERY_DB', '1')  # Use DB 1 for Celery (DB 0 for caching)

BROKER_URL = os.getenv('CELERY_BROKER_URL', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')
BACKEND_URL = os.getenv('CELERY_RESULT_BACKEND', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')

# Create Celery app
celery_app = Celery(
    'mindgraph',
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=['tasks.knowledge_space_tasks'],  # Register tasks
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes (reliability)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker (for long-running tasks)
    worker_concurrency=2,  # 2 concurrent tasks per worker
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Task queues (like Dify's queue isolation)
    task_routes={
        'knowledge_space.*': {'queue': 'knowledge'},
    },
    
    # Default queue
    task_default_queue='default',
)

# For running worker directly: celery -A celery_app worker --loglevel=info
if __name__ == '__main__':
    celery_app.start()
