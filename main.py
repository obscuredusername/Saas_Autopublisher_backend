from dotenv import load_dotenv
import os
# Explicitly load the .env from the parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from app.routes import router
from app.scheduler import start_scheduler_background, stop_scheduler_background
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Web Scraper API",
    description="API for scraping web content based on keywords with JWT authentication",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=False,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Get environment variables
MONGODB_URL = os.getenv('MONGODB_URL')
TARGET_DB_URI = os.getenv('TARGET_DB_URI')
SOURCE_DB = os.getenv('SOURCE_DB', 'scraper_db')
TARGET_DB = os.getenv('TARGET_DB', 'CRM')
SOURCE_COLLECTION = os.getenv('SOURCE_COLLECTION', 'generated_content')
TARGET_COLLECTION = os.getenv('TARGET_COLLECTION', 'posts')

db = None

@app.on_event("startup")
async def startup_db_client():
    global db
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[SOURCE_DB]
    app.state.db = db
    
    # Start the content scheduler in the background
    # try:
    #     await start_scheduler_background()
    #     logger.info("✅ Content scheduler started successfully")
    # except Exception as e:
    #     logger.error(f"❌ Failed to start content scheduler: {str(e)}")

@app.on_event("shutdown")
async def shutdown_db_client():
    # Stop the content scheduler
    try:
        await stop_scheduler_background()
        logger.info("✅ Content scheduler stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping content scheduler: {str(e)}")
    
    # Close database connection
    app.state.db.client.close()

# Database dependency for routes
@app.middleware("http")
async def add_db_to_request(request: Request, call_next):
    """Add database instance to request state for all routes"""
    request.state.db = app.state.db
    response = await call_next(request)
    return response

# Include routes
app.include_router(router)

print("FASTAPI CELERY BROKER:", MONGODB_URL)

if __name__ == "__main__":
    import uvicorn
    print("🚀 Web Scraper API Server Starting...")
    print("🔐 JWT Authentication enabled")
    print("📡 Available endpoints:")
    print("   POST /auth/signup - Create account")
    print("   POST /auth/login - Login")
    print("   POST /auth/refresh - Refresh token")
    print("   GET /auth/me - Get user info")
    print("   POST /keywords/ - Process keywords")
    print("   POST /news/ - Process news")
    print("   POST /admin/* - Admin operations")
    print("🌍 Server running at: http://localhost:8000")
    print("📖 API docs at: http://localhost:8000/docs")
    print("⏰ Content scheduler will run in background")
    print("⏰ please run man please======================================================")
    uvicorn.run(app, host="0.0.0.0", port=8000)
