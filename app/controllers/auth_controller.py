from app.services.auth_service import AuthService
from app.models.schemas import UserCreate, LoginRequest, User, LoginResponse

class AuthController:
    def __init__(self):
        self.auth_service = AuthService()

    async def signup(self, db, user: UserCreate) -> User:
        return await self.auth_service.create_user(db, user)

    async def login(self, db, login_data: LoginRequest) -> LoginResponse:
        return await self.auth_service.authenticate_user(db, login_data.email, login_data.password)

    async def verify_token(self, db, token: str) -> User:
        return await self.auth_service.verify_token(db, token)

    # Add methods for signup, login, and token verification as needed 