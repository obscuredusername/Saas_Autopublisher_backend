from celery import Celery
from celery.schedules import crontab
import os

# Use MongoDB as broker (for consistency with data volume)
MONGODB_BROKER = 'mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/celery?retryWrites=true&w=majority&appName=celery'
MONGODB_BACKEND = 'mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/celery?retryWrites=true&w=majority&appName=celery'

print("BROKER:", MONGODB_BROKER)
print("BACKEND:", MONGODB_BACKEND)

celery_app = Celery(
    'tasks',
    broker=MONGODB_BROKER,
    backend=MONGODB_BACKEND
)

# (Removed custom beat_scheduler line to use default PersistentScheduler)

# Celery Beat Schedule Configuration
celery_app.conf.beat_schedule = {
    'publish-pending-posts-every-minute': {
        'task': 'app.services.tasks.publish_pending_posts_beat',
        'schedule': crontab(minute='*'),  # Every minute
    },
    'content-scheduler-every-150-minutes': {
        'task': 'app.services.tasks.content_scheduler_task',
        'schedule': 150 * 60,  # Every 150 minutes (2.5 hours) in seconds
    },
}

# Explicitly import tasks so Celery registers them
import app.services.tasks

# Example test task for debugging
@celery_app.task
def test_task(x, y):
    print(f"Running test_task with {x} and {y}")
    return x + y 