from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, Header
from typing import List
from app.models import (
    UserCreate, 
    User, 
    LoginRequest, 
    LoginResponse,
    KeywordRequest,
    ScrapingResponse
)
from app.auth_service import AuthService
from app.content_service import ContentService
from motor.motor_asyncio import AsyncIOMotorClient
import os

router = APIRouter()
auth_service = AuthService()

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