from dotenv import load_dotenv
load_dotenv()

from app.celery_worker import celery_app
from app.services.blog_service import BlogService
from app.services.news_service import NewsService
from app.models.schemas import KeywordRequest
from pymongo import MongoClient
import os
import logging
import asyncio
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

@celery_app.task
def generate_content_task(keyword_request_dict):
    print(">>>> CELERY TASK STARTED <<<<")
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("celery.task")
    logger.info("[Celery] Task started: generate_content_task")
    try:
        mongodb_url = os.getenv('MONGODB_URL')
        source_db_name = os.getenv('SOURCE_DB', 'scraper_db')
        print(f"[DEBUG] Using MONGODB_URL: {mongodb_url}")
        print(f"[DEBUG] Using SOURCE_DB: {source_db_name}")
        source_db = MongoClient(mongodb_url)[source_db_name]
        target_db_name = keyword_request_dict.get('target_db_name')
        print(f"[DEBUG] Looking for db_configs with name: {target_db_name}")
        # Look up the config in the db_configs collection
        config = source_db["db_configs"].find_one({"name": target_db_name})
        if not config:
            print(f"[ERROR] No DB config found for name: {target_db_name} in db_configs collection of {mongodb_url}/{source_db_name}")
            # Try to fall back to a default config (e.g., the first one in the collection)
            fallback_config = source_db["db_configs"].find_one()
            if fallback_config:
                print(f"[WARNING] Falling back to first available config: {fallback_config.get('name')}")
                config = fallback_config
                target_db_name = config.get('name')
            else:
                error_msg = f"No DB config found for name: {target_db_name}. Please check your payload or add the config to db_configs."
                print(f"[FATAL] {error_msg}")
                raise Exception(error_msg)
        uri = config["target_db_uri"]
        dbname = config["target_db"]
        logger.info(f"Connecting to target DB: {uri}/{dbname}")
        logger.info("Creating BlogService instance...")
        target_db = MongoClient(uri)[dbname]
        service = BlogService(source_db, target_db=target_db, target_db_name=target_db_name)
        logger.info(f"Keyword request: {keyword_request_dict}")
        logger.info("Calling process_keywords...")
        # Actually run the content generation
        result = asyncio.run(service.process_keywords(KeywordRequest(**keyword_request_dict)))
        logger.info(f"process_keywords result: {result}")
        logger.info("[Celery] Task completed: generate_content_task")
    except Exception as e:
        logger.error(f"[Celery] Task failed: {e}")
        raise 

@celery_app.task
def publish_post_task(post_id_str):
    """Publish a post by setting its status to 'published' in broker.posts and also copy to backend.posts."""
    from pymongo import MongoClient
    mongo_url = 'mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/broker?retryWrites=true&w=majority'
    backend_url = 'mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/backend?retryWrites=true&w=majority'
    client = MongoClient(mongo_url)
    db = client['broker']
    collection = db['posts']
    from bson import ObjectId
    post_id = ObjectId(post_id_str)
    # Update status in broker.posts
    result = collection.update_one({'_id': post_id}, {'$set': {'status': 'published'}})
    if result.modified_count:
        print(f"✅ Post {post_id} published in broker.posts!")
        # Fetch the published document
        published_doc = collection.find_one({'_id': post_id})
        if published_doc:
            # Remove _id to avoid duplicate key error
            published_doc.pop('_id', None)
            # Insert or update in backend.posts by slug
            backend_client = MongoClient(backend_url)
            backend_db = backend_client['backend']
            backend_collection = backend_db['posts']
            slug = published_doc.get('slug')
            if slug:
                # Upsert by slug
                backend_collection.update_one(
                    {'slug': slug},
                    {'$set': published_doc},
                    upsert=True
                )
                print(f"✅ Post with slug '{slug}' published/copied to backend.posts!")
            else:
                print(f"⚠️ No slug found, skipping backend.posts copy.")
    else:
        print(f"⚠️ Post {post_id} not found or already published.") 

@celery_app.task
def generate_news_task(news_request_dict):
    print(">>>> CELERY NEWS TASK STARTED <<<<")
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("celery.task.news")
    logger.info("[Celery] Task started: generate_news_task")
    try:
        mongodb_url = os.getenv('MONGODB_URL')
        source_db_name = os.getenv('SOURCE_DB', 'scraper_db')
        client = MongoClient(mongodb_url)
        db = client[source_db_name]
        news_service = NewsService()
        logger.info(f"News request: {news_request_dict}")
        logger.info("Calling get_news_scrapped...")
        # Run the async news generation in a new event loop
        import asyncio
        result, status = asyncio.run(news_service.get_news_scrapped(
            news_request_dict['country'],
            news_request_dict['language'],
            news_request_dict['category'],
            db=db,
            user_email=news_request_dict.get('user_email', 'news@system.com')
        ))
        logger.info(f"get_news_scrapped result: {status}")
        logger.info("[Celery] Task completed: generate_news_task")
        return status
    except Exception as e:
        logger.error(f"[Celery] News Task failed: {e}")
        raise 

@celery_app.task
def publish_pending_posts_beat():
    """Celery Beat task: Find and publish all pending posts that are due for publishing"""
    print("🕐 [BEAT] Checking for pending posts to publish...")
    
    from pymongo import MongoClient
    from datetime import timedelta
    mongo_url = 'mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/broker?retryWrites=true&w=majority'
    client = MongoClient(mongo_url)
    db = client['broker']
    collection = db['posts']
    
    # Find all pending posts where scheduledAt <= now
    now = datetime.now(timezone.utc)
    all_pending_posts = list(collection.find({
        'status': 'pending',
        'scheduledAt': {'$lte': now}
    }).sort('scheduledAt', 1))
    
    print(f"📋 [BEAT] Found {len(all_pending_posts)} posts ready for publishing")
    
    # If there are too many posts (more than 5), add 30-minute delay to the rest
    if len(all_pending_posts) > 5:
        print(f"⚠️ [BEAT] Too many posts ({len(all_pending_posts)}), limiting to 5 and adding 30-minute delay to rest")
        
        # Take first 5 posts to publish now
        posts_to_publish = all_pending_posts[:5]
        
        # Add 30-minute delay to the remaining posts
        remaining_posts = all_pending_posts[5:]
        new_scheduled_time = now + timedelta(minutes=30)
        
        for post in remaining_posts:
            collection.update_one(
                {'_id': post['_id']},
                {'$set': {'scheduledAt': new_scheduled_time}}
            )
            print(f"⏰ [BEAT] Delayed post '{post.get('title', 'No title')[:30]}...' to {new_scheduled_time.strftime('%H:%M:%S UTC')}")
        
        print(f"📅 [BEAT] Delayed {len(remaining_posts)} posts by 30 minutes")
    else:
        posts_to_publish = all_pending_posts
    
    published_count = 0
    for post in posts_to_publish:
        try:
            post_id = str(post['_id'])
            target_db = post.get('target_db', 'backend')  # Default to 'backend' if not specified
            target_collection = post.get('target_collection', 'posts')  # Default to 'posts' if not specified
            
            print(f"🚀 [BEAT] Publishing post {post_id} to {target_db}.{target_collection}")
            
            # Remove _id to avoid duplicate key error when inserting to target
            post_copy = post.copy()
            post_copy.pop('_id', None)
            
            # Add publishedAt timestamp
            post_copy['publishedAt'] = now
            post_copy['status'] = 'published'
            
            # Connect to target database
            target_url = post.get('target_url')
            if not target_url:
                # Use environment variables for target URLs
                if target_db == 'news':
                    target_url = os.getenv('NEWS_TARGET_DB_URI', 'mongodb+srv://cryptoanalysis45:Zz5e0HLdDoF9SJXA@cluster0.zqdhkxn.mongodb.net/news?retryWrites=true&w=majority')
                elif target_db == 'keywords':
                    target_url = os.getenv('KEYWORDS_TARGET_DB_URI', 'mongodb+srv://cryptoanalysis45:Zz5e0HLdDoF9SJXA@cluster0.zqdhkxn.mongodb.net/keywords?retryWrites=true&w=majority')
                else:
                    # Fallback to default URL pattern
                    target_url = f'mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/{target_db}?retryWrites=true&w=majority'
            
            target_client = MongoClient(target_url)
            target_db_instance = target_client[target_db]
            target_collection_instance = target_db_instance[target_collection]
            
            # Insert or update in target collection (upsert by slug if available)
            slug = post_copy.get('slug')
            if slug:
                # Upsert by slug
                result = target_collection_instance.update_one(
                    {'slug': slug},
                    {'$set': post_copy},
                    upsert=True
                )
                print(f"✅ [BEAT] Upserted post with slug '{slug}' to {target_db}.{target_collection}")
            else:
                # Insert new document
                result = target_collection_instance.insert_one(post_copy)
                print(f"✅ [BEAT] Inserted post to {target_db}.{target_collection} with ID: {result.inserted_id}")
            
            # Update status in broker.posts
            collection.update_one(
                {'_id': post['_id']},
                {
                    '$set': {
                        'status': 'published',
                        'publishedAt': now,
                        'target_db_published': target_db,
                        'target_collection_published': target_collection
                    }
                }
            )
            
            published_count += 1
            target_client.close()
            
        except Exception as e:
            print(f"❌ [BEAT] Error publishing post {post.get('_id', 'unknown')}: {e}")
            continue
    
    print(f"🎉 [BEAT] Successfully published {published_count} posts")
    client.close()
    return f"Published {published_count} posts" 

@celery_app.task
def content_scheduler_task():
    """
    Celery task that runs the content scheduler logic.
    This task can be scheduled to run periodically using Celery Beat.
    """
    print("🕐 [SCHEDULER TASK] Starting content scheduler task...")
    
    try:
        # Run the async scheduler logic
        result = asyncio.run(run_scheduler_logic())
        print(f"✅ [SCHEDULER TASK] Task completed: {result}")
        return result
    except Exception as e:
        print(f"❌ [SCHEDULER TASK] Task failed: {e}")
        raise

async def run_scheduler_logic():
    """
    Async function that implements the scheduler logic.
    This is the same logic from the standalone scheduler but adapted for Celery.
    """
    try:
        # Get configuration from environment
        source_uri = os.getenv('MONGODB_URL')
        target_uri = os.getenv('TARGET_DB_URI')
        source_db = os.getenv('SOURCE_DB', 'scraper_db')
        target_db = os.getenv('TARGET_DB', 'CRM')
        source_collection = os.getenv('SOURCE_COLLECTION', 'generated_content')
        target_collection = os.getenv('TARGET_COLLECTION', 'posts')
        
        print(f"📊 [SCHEDULER] Connecting to databases...")
        print(f"📊 [SCHEDULER] Source: {source_db}.{source_collection}")
        print(f"📊 [SCHEDULER] Target: {target_db}.{target_collection}")
        
        # Initialize database connections
        source_client = AsyncIOMotorClient(source_uri)
        target_client = AsyncIOMotorClient(target_uri)
        
        source_db_instance = source_client[source_db]
        target_db_instance = target_client[target_db]
        
        try:
            # Check for scheduled content
            await check_and_publish_content(
                source_db_instance, 
                source_collection, 
                target_db_instance, 
                target_collection
            )
            
            return "Scheduler task completed successfully"
            
        finally:
            # Close connections
            source_client.close()
            target_client.close()
            
    except Exception as e:
        print(f"❌ [SCHEDULER] Error in scheduler logic: {str(e)}")
        raise

async def check_and_publish_content(source_db, source_collection, target_db, target_collection):
    """
    Check for pending content and publish the oldest one.
    This is the core logic from the standalone scheduler.
    """
    try:
        # Find the oldest pending post
        content = await source_db[source_collection].find_one(
            {"status": "pending"},
            sort=[("createdAt", 1)]  # Use createdAt to determine order
        )
        
        if content:
            print(f"✅ [SCHEDULER] READY TO PUBLISH: {content.get('title', content.get('content', '')[:30])}...")
            await publish_content_to_target(content, source_db, source_collection, target_db, target_collection)
            return f"Published content: {content.get('title', 'No title')}"
        else:
            print(f"ℹ️ [SCHEDULER] No pending content found")
            return "No pending content found"
            
    except Exception as e:
        print(f"❌ [SCHEDULER] Error in check_and_publish_content: {str(e)}")
        raise

async def publish_content_to_target(content: dict, source_db, source_collection, target_db, target_collection):
    """
    Publish content to target database.
    This is the same logic from the standalone scheduler.
    """
    try:
        # Remove MongoDB _id to avoid duplicate key error
        content_to_publish = dict(content)
        content_to_publish.pop("_id", None)
        # Set status to published
        content_to_publish["status"] = "published"

        # Log the publish attempt with timestamp
        publish_time = datetime.now(timezone.utc)
        print(f"[PUBLISH LOG] {publish_time.strftime('%Y-%m-%d %H:%M:%S %Z')} - Attempting to publish: {content_to_publish.get('title', str(content_to_publish)[:30])}")

        print("\n📤 [SCHEDULER] CONTENT BEING PUSHED TO DATABASE:")
        print("=" * 80)
        print(f"Content: {str(content_to_publish)[:200]}{'...' if len(str(content_to_publish)) > 200 else ''}")
        print("=" * 80)

        duplicate = False
        try:
            result = await target_db[target_collection].insert_one(content_to_publish)
            if result.inserted_id:
                print(f"✅ [SCHEDULER] Content saved with ID: {result.inserted_id}")
        except Exception as e:
            # Check for duplicate key error (slug)
            if hasattr(e, 'details') and e.details and e.details.get('code') == 11000:
                print(f"⚠️ [SCHEDULER] Duplicate slug detected. Marking as published without inserting.")
                duplicate = True
            else:
                print(f"❌ [SCHEDULER] Error publishing content: {e}")
                # Still update status below

        # Update status in source collection regardless of duplicate or other errors
        utc_timestamp = publish_time.timestamp()

        await source_db[source_collection].update_one(
            {"_id": content["_id"]},
            {"$set": {
                "status": "published",
                "createdAt": utc_timestamp,
                "updatedAt": utc_timestamp
            }}
        )
        print(f"✅ [SCHEDULER] Published content (status updated in source DB).{' (Duplicate slug)' if duplicate else ''} (Used UTC now) [PUBLISHED AT: {publish_time.strftime('%Y-%m-%d %H:%M:%S %Z')}]\n")

    except Exception as e:
        print(f"❌ [SCHEDULER] Error publishing content: {str(e)}")
        raise 