from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from app.routes import router
from app.scheduler_service import SchedulerService
import asyncio
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Web Scraper API",
    description="API for scraping web content based on keywords",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
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
scheduler = None

@app.on_event("startup")
async def startup_db_client():
    global db, scheduler
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[SOURCE_DB]
    app.state.db = db
    
    # Initialize scheduler using global variables from routes
    from app.routes import TARGET_DB_URI, TARGET_DB
    scheduler = SchedulerService(
        MONGODB_URL, 
        SOURCE_DB, 
        SOURCE_COLLECTION,
        TARGET_DB_URI, 
        TARGET_DB, 
        TARGET_COLLECTION
    )
    app.state.scheduler = scheduler

    # Start scheduler in background
    asyncio.create_task(scheduler.start_scheduler())

@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.db.client.close()

# Include routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    print("🚀 Web Scraper API Server Starting...")
    print("📡 Available endpoint: POST /keywords")
    print("🌍 Server running at: http://localhost:8000")
    print("📖 API docs at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)