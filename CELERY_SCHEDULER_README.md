# Celery Content Scheduler Integration

This document explains how to use the new content scheduler as a Celery background task, integrated with your existing Celery setup.

## 🎯 What's New

I've added a new Celery task called `content_scheduler_task` that implements the same scheduler logic as the standalone version, but runs as a Celery background task.

## 📁 Files Modified/Added

### 1. **`app/services/tasks.py`** - Added New Task
- **`content_scheduler_task()`**: New Celery task that runs the scheduler logic
- **`run_scheduler_logic()`**: Async function implementing the scheduler logic
- **`check_and_publish_content()`**: Core logic to find and publish pending content
- **`publish_content_to_target()`**: Logic to publish content to target database

### 2. **`app/celery_worker.py`** - Updated Beat Schedule
- Added new scheduled task: `content-scheduler-every-150-minutes`
- Runs every 150 minutes (2.5 hours) by default

### 3. **`test_celery_scheduler.py`** - Test Script
- Manual testing script for the new scheduler task

## 🚀 How to Use

### Option 1: Run with Existing Celery Setup

```bash
# Terminal 1: Start Celery worker
celery -A app.celery_worker worker --loglevel=info

# Terminal 2: Start Celery beat (scheduler)
celery -A app.celery_worker beat --loglevel=info

# Terminal 3: Run your FastAPI app
python main.py
```

### Option 2: Test the Scheduler Task Manually

```bash
# Make sure Celery worker is running first, then:
python test_celery_scheduler.py
```

## ⚙️ Configuration

### Environment Variables

Make sure your `.env` file has these variables:

```env
# Database Configuration
MONGODB_URL=mongodb://localhost:27017
TARGET_DB_URI=mongodb://localhost:27017
SOURCE_DB=scraper_db
TARGET_DB=CRM
SOURCE_COLLECTION=generated_content
TARGET_COLLECTION=posts
```

### Schedule Configuration

The scheduler runs every 150 minutes by default. To change this, modify `app/celery_worker.py`:

```python
'content-scheduler-every-150-minutes': {
    'task': 'app.services.tasks.content_scheduler_task',
    'schedule': 150 * 60,  # Change this number (in seconds)
},
```

## 🔄 How It Works

1. **Celery Beat** triggers `content_scheduler_task` every 150 minutes
2. **Task Execution**: The task runs the async scheduler logic
3. **Content Check**: Finds the oldest pending post in source database
4. **Publishing**: Moves content to target database and updates status
5. **Logging**: Provides detailed logs for monitoring

## 📊 Monitoring

### Check Task Status

```bash
# View Celery worker logs
celery -A app.celery_worker worker --loglevel=info

# View Celery beat logs
celery -A app.celery_worker beat --loglevel=info

# Check task results
celery -A app.celery_worker inspect active
```

### Database Queries

```javascript
// Check pending content
db.generated_content.find({status: "pending"}).sort({createdAt: 1})

// Check published content
db.posts.find({status: "published"}).sort({createdAt: -1})
```

## 🧪 Testing

### Manual Test

```bash
# Start Celery worker first
celery -A app.celery_worker worker --loglevel=info

# In another terminal, run the test
python test_celery_scheduler.py
```

### Expected Output

```
🧪 Testing Celery Content Scheduler Task...
==================================================
✅ Task submitted to Celery with ID: abc123...
⏳ Task status: PENDING
⏳ Waiting for task completion...
📊 [SCHEDULER] Connecting to databases...
✅ [SCHEDULER] READY TO PUBLISH: Your content title...
✅ Task completed successfully!
📋 Result: Published content: Your content title
```

## 🔧 Troubleshooting

### Common Issues

1. **Task Not Running**
   - Check if Celery worker is running
   - Check if Celery beat is running
   - Verify task is registered: `celery -A app.celery_worker inspect registered`

2. **Database Connection Errors**
   - Verify MongoDB connection strings
   - Check network connectivity
   - Ensure databases exist

3. **No Content Being Published**
   - Check for pending content in source database
   - Verify task is running on schedule
   - Check logs for errors

### Debug Mode

To enable more detailed logging, modify the task:

```python
@celery_app.task
def content_scheduler_task():
    print("🕐 [SCHEDULER TASK] Starting content scheduler task...")
    # Add more debug prints here
    try:
        result = asyncio.run(run_scheduler_logic())
        print(f"✅ [SCHEDULER TASK] Task completed: {result}")
        return result
    except Exception as e:
        print(f"❌ [SCHEDULER TASK] Task failed: {e}")
        import traceback
        traceback.print_exc()  # Add this for detailed error info
        raise
```

## 🔄 Integration with Existing Code

The new scheduler task works alongside your existing Celery tasks:

- **`generate_content_task`**: Creates content with `status: "pending"`
- **`publish_pending_posts_beat`**: Your existing publishing task
- **`content_scheduler_task`**: New scheduler task (alternative approach)

Both publishing tasks can run simultaneously - they won't conflict with each other.

## 📈 Performance

- **Lightweight**: Minimal resource usage
- **Non-blocking**: Runs as background task
- **Scalable**: Can run multiple workers
- **Reliable**: Built-in error handling and retries

## 🎉 Benefits

✅ **Integrated**: Works with your existing Celery setup  
✅ **Configurable**: Easy to adjust schedule  
✅ **Monitorable**: Full logging and status tracking  
✅ **Testable**: Manual testing capabilities  
✅ **Reliable**: Error handling and retry logic  
✅ **Scalable**: Can run on multiple workers  

Your existing Celery setup remains unchanged, and you now have an additional scheduler option that integrates seamlessly with your current infrastructure! 