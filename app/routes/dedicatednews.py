from fastapi import APIRouter, Query, Body, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, Literal
from app.services.dedicatednews_service import DedicatedNewsService
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/news", tags=["DedicatedNews"])

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return request.app.state.db

class NewsScheduleRequest(BaseModel):
    categories: Dict[Literal["finance", "business", "fashion", "news", "lifestyle", "world"], int] = Field(..., example={"finance": 4, "business": 2, "fashion": 3, "lifestyle": 2, "world": 1})
    language: str = Field("en", example="en")
    country: str = Field("us", example="us")
    source: Literal["yahoo", "google"] = Field("yahoo", example="yahoo")

    @validator("categories")
    def check_categories(cls, v):
        allowed = {"finance", "business", "fashion", "news", "lifestyle", "world"}
        for cat in v:
            if cat not in allowed:
                raise ValueError(f"Invalid category: {cat}. Allowed: {allowed}")
        return v

@router.get("/")
async def get_dedicated_news(
    source: str = Query("all", enum=["google", "bing", "yahoo"]),
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
    elif source == "yahoo":
        result = await service.fetch_yahoo_news(category, max, language, country)
    else:
        result = {"error": "Source not supported."}
    return JSONResponse(content=result)

@router.post("/schedule")
async def schedule_rotating_news(
    payload: NewsScheduleRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Schedule news posts for multiple categories in a rotating, interleaved fashion.
    Expects JSON: {"categories": {"finance": 4, "business": 2, "fashion": 3}, "language": "en", "country": "us", "source": "google"}
    """
    categories = payload.categories
    language = payload.language
    country = payload.country
    source = payload.source
    service = DedicatedNewsService()
    if source == "google":
        result = await service.schedule_rotating_google_news(categories, language, country, db=db)
    else:
        result = await service.schedule_rotating_yahoo_news(categories, language, country, db=db)
    return JSONResponse(content=result) 