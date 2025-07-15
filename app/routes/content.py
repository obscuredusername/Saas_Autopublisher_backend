from fastapi import APIRouter, Request, BackgroundTasks, Depends
from app.services.blog_service import BlogService
from app.models.schemas import KeywordRequest, ScrapingResponse
from app.dependencies.auth import get_current_active_user
from app.models.schemas import User
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/content", tags=["Content"])

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return request.app.state.db

@router.post('/keywords', response_model=ScrapingResponse)
async def process_keywords(
    request: Request, 
    keyword_request: KeywordRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Process keywords and generate content.
    Requires authentication.
    """
    # Add user email to the request if not provided
    if not keyword_request.user_email or keyword_request.user_email == "default@user.com":
        keyword_request.user_email = current_user.email
    
    blog_service = BlogService(db)
    return await blog_service.process_keywords(keyword_request) 