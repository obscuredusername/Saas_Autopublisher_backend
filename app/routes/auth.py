from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.models.schemas import UserCreate, LoginRequest, LoginResponse, User
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_service = AuthService()

# Security scheme for refresh tokens
refresh_security = HTTPBearer()

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return request.app.state.db

@router.post('/signup', response_model=User, status_code=status.HTTP_201_CREATED)
async def signup(
    user: UserCreate, 
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Create a new user account.
    """
    return await auth_service.create_user(db, user)

@router.post('/login', response_model=LoginResponse)
async def login(
    login_data: LoginRequest, 
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Authenticate user and return JWT access token.
    """
    return await auth_service.authenticate_user(db, login_data.email, login_data.password)

@router.post('/refresh', response_model=LoginResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(refresh_security),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Refresh an access token using a valid refresh token.
    """
    return await auth_service.refresh_token(db, credentials.credentials)

@router.get('/me', response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get current user information.
    """
    return current_user 