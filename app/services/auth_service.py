from fastapi import HTTPException
from passlib.context import CryptContext
import jwt as PyJWT
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.models.schemas import User, UserCreate, LoginResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

# Load environment variables
load_dotenv()

class AuthService:
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def create_user(self, db: AsyncIOMotorDatabase, user: UserCreate) -> User:
        # Check if user exists
        existing_user = await db.users.find_one({"email": user.email})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        user_dict = {
            "email": user.email,
            "password": self.pwd_context.hash(user.password),
            "created_at": datetime.utcnow(),
            "is_active": True
        }
        await db.users.insert_one(user_dict)
        return User(email=user.email)

    async def authenticate_user(self, db: AsyncIOMotorDatabase, email: str, password: str) -> LoginResponse:
        user = await db.users.find_one({"email": email})
        if not user or not self.pwd_context.verify(password, user["password"]):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="User account is deactivated")
        
        access_token = self._create_access_token(user["email"])
        return LoginResponse(access_token=access_token, token_type="bearer")

    def _create_access_token(self, email: str) -> str:
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        expire = datetime.utcnow() + expires_delta
        to_encode = {
            "sub": email, 
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        return PyJWT.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )

    async def verify_token(self, db: AsyncIOMotorDatabase, token: str) -> User:
        try:
            payload = PyJWT.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True}
            )
            email = payload.get("sub")
            if not email:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            
            user = await db.users.find_one({"email": email})
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            
            # Check if user is active
            if not user.get("is_active", True):
                raise HTTPException(status_code=401, detail="User account is deactivated")
            
            return User(email=user["email"])
            
        except PyJWT.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except PyJWT.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Authentication error: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )

    async def refresh_token(self, db: AsyncIOMotorDatabase, token: str) -> LoginResponse:
        """Refresh an access token"""
        try:
            payload = PyJWT.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Don't verify expiration for refresh
            )
            email = payload.get("sub")
            if not email:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            
            user = await db.users.find_one({"email": email})
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            
            # Create new access token
            new_access_token = self._create_access_token(email)
            return LoginResponse(access_token=new_access_token, token_type="bearer")
            
        except PyJWT.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Token refresh error: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            ) 