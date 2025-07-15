from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.models.schemas import User
from motor.motor_asyncio import AsyncIOMotorDatabase

# Security scheme for JWT tokens
security = HTTPBearer()

# Auth service instance
auth_service = AuthService()

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return request.app.state.db

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    This will be used to protect API endpoints.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify the JWT token and get user
        user = await auth_service.verify_token(db, credentials.credentials)
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get the current active user.
    You can add additional checks here (e.g., user is not banned, etc.)
    """
    # Add any additional user validation here
    # For example, check if user is active, not banned, etc.
    return current_user

# Optional: Admin user dependency
async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get the current admin user.
    You can add admin role checks here.
    """
    # Add admin role validation here
    # For now, we'll just return the user
    # You can add role-based checks later
    return current_user 