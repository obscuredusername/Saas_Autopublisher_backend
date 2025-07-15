from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services.dedicatednews_service import DedicatedNewsService

router = APIRouter()

@router.get("/dedicated-news")
async def get_dedicated_news(
    source: str = Query("all", enum=["google", "bing", "yahoo", "all"]),
    category: str = Query("technology"),
    max: int = Query(5, ge=1, le=20),
    language: str = Query("en"),
    country: str = Query("us")
):
    service = DedicatedNewsService()
    if source == "google":
        result = await service.fetch_google_news(category, max, language, country)
    elif source == "bing":
        result = await service.fetch_bing_news(category, max, language, country)
    elif source == "all":
        result = await service.fetch_all(category, max, language, country)
    else:
        result = {"error": "Yahoo news not implemented yet."}
    return JSONResponse(content=result) 