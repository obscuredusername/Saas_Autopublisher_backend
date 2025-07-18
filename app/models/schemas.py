from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime, timezone

# Auth Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    email: EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Database Configuration Models
class TargetDBConfig(BaseModel):
    target_db_uri: str
    target_db: str

class TargetDBResponse(BaseModel):
    success: bool
    message: str
    target_db_uri: str
    target_db: str

class StoredDBConfig(BaseModel):
    name: str
    target_db_uri: str
    target_db: str
    description: Optional[str] = None

class StoredDBResponse(BaseModel):
    success: bool
    message: str
    name: str
    target_db_uri: str
    target_db: str
    description: Optional[str] = None

class SelectDBRequest(BaseModel):
    name: str

class ListDBResponse(BaseModel):
    success: bool
    message: str
    databases: List[StoredDBResponse]
    current_active: Optional[str] = None

# Scraping Models
class KeywordItem(BaseModel):
    text: str
    minLength: Optional[int] = None

class KeywordRequest(BaseModel):
    keywords: List[KeywordItem]
    country: str = "us"
    language: str = "en"
    user_email: str = "default@user.com"
    minutes: int = 150  # Default to 150 if not provided
    min_length: int = 0  # Global min_length for all keywords

class ScrapingResponse(BaseModel):
    success: bool
    message: str
    tasks: List[dict]
    country: str
    language: str
    status: str = "processing"
    unique_links: List[str] = []

class GeneratedContent(BaseModel):
    keyword: str
    content: str
    language: str
    content_type: str
    word_count: int
    user_email: str
    status: str = "pending"  # pending, published, failed
    created_at: datetime = datetime.now(timezone.utc)
    file_path: Optional[str]
    metadata: dict = {}  # Store additional info like sources, performance metrics

class TaskQueuedResponse(BaseModel):
    task_id: str
    status: str