from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Depends
from app.services.blog_service import BlogService
from app.models.schemas import KeywordRequest, ScrapingResponse, TaskQueuedResponse
from app.services.tasks import generate_content_task
from app.dependencies.auth import get_current_active_user
from app.models.schemas import User
from motor.motor_asyncio import AsyncIOMotorDatabase
from celery.result import AsyncResult
from app.celery_worker import celery_app
import os

router = APIRouter(prefix="/keywords", tags=["Keywords"])

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return request.app.state.db

@router.post("/", response_model=TaskQueuedResponse)
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
    Uses the currently selected database from the admin dashboard.
    """
    # Import the global variables from admin module
    from app.routes.admin import TARGET_DB, CURRENT_ACTIVE_DB
    
    # Use the currently selected database from admin dashboard
    selected_db = TARGET_DB
    print(f"📊 Using database selected on dashboard: {selected_db} (Active: {CURRENT_ACTIVE_DB})")
    
    # Add user email to the request if not provided
    if not keyword_request.user_email or keyword_request.user_email == "default@user.com":
        keyword_request.user_email = current_user.email
    
    # Create a copy of the request dict and add the selected database
    request_data = keyword_request.dict()
    # Only overwrite if not provided by the frontend
    if not request_data.get('target_db_name'):
        request_data['target_db_name'] = selected_db
    # Use Celery for background processing
    task = generate_content_task.delay(request_data)
    return TaskQueuedResponse(task_id=task.id, status="queued")

@router.get("/task-status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the status of a background task.
    Requires authentication.
    """
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": str(result.result)
    }

@router.get("/my-tasks")
async def get_my_tasks(
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get all tasks for the current user.
    Requires authentication.
    """
    # This would require storing task information with user association
    # For now, we'll return a placeholder
    return {
        "message": "User task history feature coming soon",
        "user_email": current_user.email
    } 