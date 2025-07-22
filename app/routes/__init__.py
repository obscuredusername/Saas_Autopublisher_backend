from fastapi import APIRouter
from .keywords import router as keywords_router
from .auth import router as auth_router
from .content import router as content_router
from .admin import router as admin_router
from .dedicatednews import router as dedicatednews_router
# from .news import router as news_router  # Uncomment when news router is implemented
from app.routes import *
from app.routes import keywords
from app.routes import *
# You can now use the routes from routes.py here

router = APIRouter()
router.include_router(keywords_router)
router.include_router(auth_router)
router.include_router(content_router)
router.include_router(admin_router)
router.include_router(dedicatednews_router)
# router.include_router(news_router)  # Uncomment when news router is implemented 