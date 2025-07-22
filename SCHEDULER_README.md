# Content Scheduler Documentation

This project now includes a standalone content scheduler that can run independently of Celery, publishing content from the source database to the target database at regular intervals.

## Features

- **Standalone Operation**: Runs without Celery dependency
- **Background Integration**: Can run alongside the FastAPI application
- **Configurable Intervals**: Set publish interval via environment variable
- **Comprehensive Logging**: Detailed logs for monitoring and debugging
- **Error Handling**: Robust error handling with automatic retries
- **Duplicate Detection**: Handles duplicate content gracefully

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Database Configuration
MONGODB_URL=mongodb://localhost:27017
TARGET_DB_URI=mongodb://localhost:27017
SOURCE_DB=scraper_db
TARGET_DB=CRM
SOURCE_COLLECTION=generated_content
TARGET_COLLECTION=posts

# Scheduler Configuration
PUBLISH_INTERVAL_MINUTES=150  # Default: 150 minutes (2.5 hours)
```

## Usage

### Option 1: Run with FastAPI Application (Recommended)

The scheduler is automatically started when you run the main FastAPI application:

```bash
python main.py
```

This will:
- Start the FastAPI server on port 8000
- Start the content scheduler in the background
- Both will run simultaneously

### Option 2: Run Scheduler Standalone

If you want to run only the scheduler without the FastAPI application:

```bash
python run_scheduler.py
```

This is useful for:
- Testing the scheduler independently
- Running the scheduler on a separate server
- Debugging scheduler issues

## How It Works

1. **Initialization**: The scheduler connects to both source and target databases
2. **Content Check**: Every `PUBLISH_INTERVAL_MINUTES`, it checks for pending content
3. **Content Selection**: Finds the oldest pending post (by `createdAt` timestamp)
4. **Publishing**: 
   - Removes MongoDB `_id` to avoid duplicate key errors
   - Sets status to "published"
   - Inserts into target database
   - Updates status in source database
5. **Error Handling**: Handles duplicate slugs and other errors gracefully

## Logging

The scheduler provides comprehensive logging:

- **File Logging**: Logs are saved to `scheduler.log`
- **Console Logging**: Logs are also displayed in the console
- **Log Levels**: INFO, WARNING, ERROR levels for different types of events

### Log Examples

```
2024-01-15 10:30:00 - INFO - 🚀 Starting scheduler (150 min interval)...
2024-01-15 10:30:00 - INFO - ✅ Database connections initialized
2024-01-15 10:30:00 - INFO - ✅ READY TO PUBLISH: How to Improve Your SEO...
2024-01-15 10:30:01 - INFO - ✅ Content saved with ID: 507f1f77bcf86cd799439011
2024-01-15 10:30:01 - INFO - ✅ Published content (status updated in source DB)
```

## Monitoring

### Check Scheduler Status

The scheduler logs its activity. You can monitor it by:

```bash
# View real-time logs
tail -f scheduler.log

# Check if scheduler is running
ps aux | grep python
```

### Database Queries

You can check the status of content in your databases:

```javascript
// Check pending content in source database
db.generated_content.find({status: "pending"}).sort({createdAt: 1})

// Check published content in target database
db.posts.find({status: "published"}).sort({createdAt: -1})
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check your MongoDB connection strings
   - Ensure MongoDB is running
   - Verify network connectivity

2. **No Content Being Published**
   - Check if there's pending content: `db.generated_content.find({status: "pending"})`
   - Verify the scheduler is running: check logs
   - Check if the publish interval is too long

3. **Duplicate Key Errors**
   - The scheduler handles these automatically
   - Content is marked as published even if it's a duplicate
   - Check your slug generation logic

### Debug Mode

To enable more detailed logging, modify the logging level in `app/scheduler.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    # ... rest of config
)
```

## Integration with Existing Code

The scheduler integrates seamlessly with your existing content generation pipeline:

1. **Content Generation**: Your existing content generation creates posts with `status: "pending"`
2. **Scheduling**: The scheduler automatically picks up pending content
3. **Publishing**: Content is moved to the target database with `status: "published"`

No changes needed to your existing content generation code!

## Performance Considerations

- **Memory Usage**: The scheduler is lightweight and uses minimal memory
- **Database Load**: Only one query per interval, very low impact
- **Network**: Minimal network usage for database operations
- **CPU**: Negligible CPU usage

## Security

- Uses environment variables for sensitive configuration
- No hardcoded credentials
- Database connections are properly closed on shutdown
- Error messages don't expose sensitive information 