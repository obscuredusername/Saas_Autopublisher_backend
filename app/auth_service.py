from fastapi import HTTPException
from passlib.context import CryptContext
import jwt as PyJWT
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.models import User, UserCreate, LoginResponse

# Load environment variables
load_dotenv()

class AuthService:
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def create_user(self, db, user: UserCreate) -> User:
        # Check if user exists
        if await db.users.find_one({"email": user.email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        user_dict = {
            "email": user.email,
            "password": self.pwd_context.hash(user.password)
        }
        
        await db.users.insert_one(user_dict)
        return User(email=user.email)

    async def authenticate_user(self, db, email: str, password: str) -> LoginResponse:
        user = await db.users.find_one({"email": email})
        
        if not user or not self.pwd_context.verify(password, user["password"]):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        access_token = self._create_access_token(user["email"])
        return LoginResponse(access_token=access_token)

    def _create_access_token(self, email: str) -> str:
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        expire = datetime.utcnow() + expires_delta
        
        return PyJWT.encode(
            {"sub": email, "exp": expire},
            self.secret_key,
            algorithm=self.algorithm
        )

    async def verify_token(self, db, token: str) -> User:
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