from fastapi import APIRouter, Query, Request, HTTPException, Depends
from app.services.news_service import NewsService
from app.services.tasks import generate_news_task
from app.dependencies.auth import get_current_active_user
from app.models.schemas import User
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Optional
import os

router = APIRouter(prefix="/news", tags=["News"])

class NewsRequest(BaseModel):
    country: str = "us"
    language: str = "en"
    category: str = "technology"
    user_email: str = "news@system.com"

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return request.app.state.db

@router.post('/')
async def process_news(
    request: Request, 
    news_request: NewsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Process news articles via POST request.
    Requires authentication.
    Uses the currently selected database from the admin dashboard.
    """
    # Import the global variables from admin module
    from app.routes.admin import TARGET_DB, CURRENT_ACTIVE_DB
    
    # Use the currently selected database from admin dashboard
    selected_db = TARGET_DB
    print(f"📊 Using database selected on dashboard: {selected_db} (Active: {CURRENT_ACTIVE_DB})")
    
    # Use current user's email if not provided
    if not news_request.user_email or news_request.user_email == "news@system.com":
        news_request.user_email = current_user.email
    
    # Submit a Celery task for news processing
    payload = {
        'country': news_request.country,
        'language': news_request.language,
        'category': news_request.category,
        'target_db_name': selected_db,
        'user_email': news_request.user_email
    }
    task = generate_news_task.delay(payload)
    return {
        "task_id": task.id,
        "status": "queued",
        "country": news_request.country,
        "language": news_request.language,
        "category": news_request.category,
        "target_db_name": selected_db,
        "user_email": news_request.user_email
    }

@router.get('/')
async def get_news(
    request: Request,
    country: str = Query(default='us', description="Country code (e.g., 'us', 'gb', 'in')"),
    language: str = Query(default='en', description="Language code (e.g., 'en', 'es', 'fr')"),
    category: str = Query(default='technology', description="News category (e.g., 'technology', 'business', 'sports')"),
    user_email: str = Query(default='news@system.com', description="User email for blog generation"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get news articles, scrape content from up to 5 working links, and generate blog posts.
    Returns scraped content saved to JSON file and creates 5 new blog posts.
    Requires authentication.
    Uses the currently selected database from the admin dashboard.
    """
    # Import the global variables from admin module
    from app.routes.admin import TARGET_DB, CURRENT_ACTIVE_DB
    
    # Use the currently selected database from admin dashboard
    selected_db = TARGET_DB
    print(f"📊 Using database selected on dashboard: {selected_db} (Active: {CURRENT_ACTIVE_DB})")
    
    # Use current user's email if not provided
    if not user_email or user_email == "news@system.com":
        user_email = current_user.email
    
    # Submit a Celery task for news processing
    payload = {
        'country': country,
        'language': language,
        'category': category,
        'target_db_name': selected_db,
        'user_email': user_email
    }
    task = generate_news_task.delay(payload)
    return {
        "task_id": task.id,
        "status": "queued",
        "country": country,
        "language": language,
        "category": category,
        "target_db_name": selected_db,
        "user_email": user_email
    }

@router.get('/supported-countries')
async def get_supported_countries():
    """
    Get list of supported countries and their names for NewsAPI.
    This helps users understand what country codes are valid.
    """
    news_service = NewsService()
    return {
        "supported_countries": news_service.get_supported_countries(),
        "country_info": news_service.get_country_info(),
        "total_countries": len(news_service.get_supported_countries())
    }

@router.get('/my-news')
async def get_my_news(
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get news articles generated for the current user.
    Requires authentication.
    """
    # This would require storing news generation history with user association
    # For now, we'll return a placeholder
    return {
        "message": "User news history feature coming soon",
        "user_email": current_user.email
    } 