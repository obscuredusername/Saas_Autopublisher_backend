from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, Header
from typing import List
from app.models import (
    UserCreate, 
    User, 
    LoginRequest, 
    LoginResponse,
    KeywordRequest,
    ScrapingResponse,
    TargetDBConfig,
    TargetDBResponse,
    StoredDBConfig,
    StoredDBResponse,
    SelectDBRequest,
    ListDBResponse
)
from app.auth_service import AuthService
from app.content_service import ContentService
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json

router = APIRouter()
auth_service = AuthService()

TARGET_DB_URI = os.getenv('TARGET_DB_URI')
TARGET_DB = os.getenv('TARGET_DB', 'CRM')
CURRENT_ACTIVE_DB = "default"

# Helper to get db config collection
async def get_db_config_collection(request: Request):
    return request.app.state.db["db_configs"]

@router.post("/store-db-config", response_model=StoredDBResponse)
async def store_database_config(config: StoredDBConfig, request: Request):
    try:
        test_client = AsyncIOMotorClient(config.target_db_uri)
        await test_client.admin.command('ping')
        test_client.close()
        db_configs = await get_db_config_collection(request)
        # Upsert config by name
        await db_configs.update_one(
            {"name": config.name},
            {"$set": {
                "target_db_uri": config.target_db_uri,
                "target_db": config.target_db,
                "description": config.description or f"Database configuration for {config.name}"
            }},
            upsert=True
        )
        return StoredDBResponse(
            success=True,
            message=f"Database configuration '{config.name}' stored successfully",
            name=config.name,
            target_db_uri=config.target_db_uri,
            target_db=config.target_db,
            description=config.description
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {str(e)}")

@router.post("/select-db", response_model=TargetDBResponse)
async def select_database(request: Request, select_request: SelectDBRequest):
    global TARGET_DB_URI, TARGET_DB, CURRENT_ACTIVE_DB
    db_configs = await get_db_config_collection(request)
    db_config = await db_configs.find_one({"name": select_request.name})
    if not db_config:
        raise HTTPException(status_code=404, detail=f"Database configuration '{select_request.name}' not found")
    try:
        test_client = AsyncIOMotorClient(db_config["target_db_uri"])
        await test_client.admin.command('ping')
        test_client.close()
        TARGET_DB_URI = db_config["target_db_uri"]
        TARGET_DB = db_config["target_db"]
        CURRENT_ACTIVE_DB = select_request.name
        os.environ['TARGET_DB_URI'] = db_config["target_db_uri"]
        os.environ['TARGET_DB'] = db_config["target_db"]
        scheduler = request.app.state.scheduler
        if scheduler:
            scheduler.update_target_connection(db_config["target_db_uri"], db_config["target_db"])
        return TargetDBResponse(
            success=True,
            message=f"Database '{select_request.name}' activated successfully. All operations will now use {db_config['target_db']}",
            target_db_uri=db_config["target_db_uri"],
            target_db=db_config["target_db"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to database '{select_request.name}': {str(e)}")

@router.get("/list-db-configs", response_model=ListDBResponse)
async def list_database_configs(request: Request):
    db_configs = await get_db_config_collection(request)
    configs = db_configs.find()
    databases = []
    async for config in configs:
        databases.append(StoredDBResponse(
            success=True,
            message="",
            name=config["name"],
            target_db_uri=config["target_db_uri"],
            target_db=config["target_db"],
            description=config.get("description")
        ))
    return ListDBResponse(
        success=True,
        message=f"Found {len(databases)} database configurations",
        databases=databases,
        current_active=CURRENT_ACTIVE_DB
    )

@router.delete("/delete-db-config/{name}")
async def delete_database_config(name: str, request: Request):
    global CURRENT_ACTIVE_DB
    db_configs = await get_db_config_collection(request)
    db_config = await db_configs.find_one({"name": name})
    if not db_config:
        raise HTTPException(status_code=404, detail=f"Database configuration '{name}' not found")
    if name == "default":
        raise HTTPException(status_code=400, detail="Cannot delete the default database configuration")
    if name == CURRENT_ACTIVE_DB:
        CURRENT_ACTIVE_DB = "default"
        default_config = await db_configs.find_one({"name": "default"})
        if default_config:
            TARGET_DB_URI = default_config["target_db_uri"]
            TARGET_DB = default_config["target_db"]
    await db_configs.delete_one({"name": name})
    return {"success": True, "message": f"Database configuration '{name}' deleted successfully"}

@router.post("/set-target-db", response_model=TargetDBResponse)
async def set_target_database(config: TargetDBConfig, request: Request):
    """
    Set target MongoDB URI and database name as global variables (legacy endpoint)
    """
    global TARGET_DB_URI, TARGET_DB
    
    try:
        # Test the connection to ensure it's valid
        test_client = AsyncIOMotorClient(config.target_db_uri)
        await test_client.admin.command('ping')
        test_client.close()
        
        # Set global variables
        TARGET_DB_URI = config.target_db_uri
        TARGET_DB = config.target_db
        
        # Update environment variables
        os.environ['TARGET_DB_URI'] = config.target_db_uri
        os.environ['TARGET_DB'] = config.target_db
        
        # Update scheduler's target connection
        scheduler = request.app.state.scheduler
        if scheduler:
            scheduler.update_target_connection(config.target_db_uri, config.target_db)
        
        return TargetDBResponse(
            success=True,
            message=f"Target database configuration updated successfully. All operations will now use {config.target_db}",
            target_db_uri=config.target_db_uri,
            target_db=config.target_db
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect to target database: {str(e)}"
        )

@router.get("/get-target-db", response_model=TargetDBResponse)
async def get_target_database():
    """
    Get current target database configuration
    """
    return TargetDBResponse(
        success=True,
        message="Current target database configuration",
        target_db_uri=TARGET_DB_URI,
        target_db=TARGET_DB
    )

# Auth endpoints
@router.post("/signup", response_model=User)
async def signup(request: Request, user: UserCreate):
    return await auth_service.create_user(request.app.state.db, user)

@router.post("/login", response_model=LoginResponse)
async def login(request: Request, login_data: LoginRequest):
    return await auth_service.authenticate_user(request.app.state.db, login_data.email, login_data.password)

# Auth middleware
async def get_current_user(request: Request, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="No authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = authorization.split(" ")[1]
    return await auth_service.verify_token(request.app.state.db, token)

# Protected route example
@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/keywords", response_model=ScrapingResponse)
async def scrape_keywords(request: Request, keyword_request: KeywordRequest, background_tasks: BackgroundTasks):
    """
    Get unique links immediately and schedule content generation
    """
    content_service = ContentService(request.app.state.db)
    
    # Check if scheduler is running and restart if needed
    scheduler = request.app.state.scheduler
    if not scheduler.is_scheduler_running():
        print("🔄 Restarting scheduler...")
        scheduler.resume_scheduler()
    
    response = await content_service.process_keywords(keyword_request)
    
    # Schedule background tasks for content generation
    for keyword_item in keyword_request.keywords:
        if response.unique_links:
            # Determine content type based on keyword
            content_type = "biography"  # Default to biography for person names
            if any(tech_term in keyword_item.text.lower() for tech_term in ["how to", "guide", "tutorial", "learn", "using"]):
                content_type = "how_to"
            elif any(company_term in keyword_item.text.lower() for company_term in ["company", "corporation", "inc", "ltd"]):
                content_type = "company"
            
            background_tasks.add_task(
                content_service.scrape_and_generate_content,
                response.unique_links,
                keyword_item.text,
                keyword_request.country.lower(),
                keyword_request.language.lower(),
                keyword_item.minLength,
                keyword_request.user_email,  # Pass email separately
                keyword_item.scheduledDate,
                keyword_item.scheduledTime,
                content_type  # Pass the determined content type
            )
    
    return response

@router.get("/scheduled-content")
async def get_scheduled_content(
    request: Request,
    status: str = None,
    date: str = None
):
    """Get scheduled content"""
    content_service = ContentService(request.app.state.db)
    return await content_service.get_scheduled_content(status, date)

@router.get("/published-content")
async def get_published_content(
    request: Request,
    date: str = None
):
    """Get published content"""
    try:
        target_client = AsyncIOMotorClient(os.getenv("TARGET_DB_URI"))
        target_db = target_client.get_default_database()
        
        query = {"status": "published"}
        if date:
            query["scheduled_date"] = date
            
        cursor = target_db.published_content.find(query)
        content_list = await cursor.to_list(length=None)
        
        return {
            "success": True,
            "published_count": len(content_list),
            "content": content_list
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def root():
    """
    Root endpoint with API information
    """
    return {
        "message": "Web Scraper API with Intelligent AI Blog Generation",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "POST /keywords": "Get unique links instantly + auto-generate AI blog (biography/company/how-to)"
        },
        "ai_features": {
            "auto_detection": "AI automatically detects content type based on keyword",
            "biography": "For people (e.g., 'elon musk', 'bill gates')",
            "company": "For businesses (e.g., 'tesla', 'pinterest', 'google')", 
            "how_to": "For tutorials (e.g., 'powerbi', 'excel', 'python')"
        }
    }