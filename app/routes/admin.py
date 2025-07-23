from fastapi import APIRouter, HTTPException, Request, Depends
from app.models.schemas import (
    TargetDBConfig,
    TargetDBResponse,
    StoredDBConfig,
    StoredDBResponse,
    SelectDBRequest,
    ListDBResponse
)
from app.dependencies.auth import get_current_active_user
from app.models.schemas import User
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os

router = APIRouter(prefix="/admin", tags=["Admin"])

TARGET_DB_URI = os.getenv('TARGET_DB_URI')
TARGET_DB = os.getenv('TARGET_DB', 'CRM')
CURRENT_ACTIVE_DB = "default"

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return request.app.state.db

async def get_db_config_collection(request: Request):
    return request.app.state.db["db_configs"]

@router.post("/store-db-config", response_model=StoredDBResponse)
async def store_database_config(
    config: StoredDBConfig, 
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Store a new database configuration.
    Requires authentication.
    """
    try:
        test_client = AsyncIOMotorClient(config.target_db_uri)
        await test_client.admin.command('ping')
        test_client.close()
        db_configs = await get_db_config_collection(request)
        await db_configs.update_one(
            {"name": config.name},
            {"$set": {
                "target_db_uri": config.target_db_uri,
                "target_db": config.target_db,
                "description": config.description or f"Database configuration for {config.name}",
                "created_by": current_user.email,
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
        return StoredDBResponse(
            success=True,
            message=f"Database configuration '{config.name}' stored successfully",
            name=config.name,
            target_db_uri=config.target_db_uri,
            target_db=config.target_db,
            description=config.description
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {str(e)}")
    
@router.post('/hayyan')
async def stupid_function():
    return {"message":'hayyan kutti rrand nigger'}

@router.post("/select-db", response_model=TargetDBResponse)
async def select_database(
    request: Request, 
    select_request: SelectDBRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Select and activate a database configuration.
    Requires authentication.
    """
    global TARGET_DB_URI, TARGET_DB, CURRENT_ACTIVE_DB
    db_configs = await get_db_config_collection(request)
    db_config = await db_configs.find_one({"name": select_request.name})
    if not db_config:
        raise HTTPException(status_code=404, detail=f"Database configuration '{select_request.name}' not found")
    try:
        test_client = AsyncIOMotorClient(db_config["target_db_uri"])
        await test_client.admin.command('ping')
        test_client.close()
        TARGET_DB_URI = db_config["target_db_uri"]
        TARGET_DB = db_config["target_db"]
        CURRENT_ACTIVE_DB = select_request.name
        os.environ['TARGET_DB_URI'] = db_config["target_db_uri"]
        os.environ['TARGET_DB'] = db_config["target_db"]
        scheduler = request.app.state.scheduler
        if scheduler:
            scheduler.update_target_connection(db_config["target_db_uri"], db_config["target_db"])
        return TargetDBResponse(
            success=True,
            message=f"Database '{select_request.name}' activated successfully. All operations will now use {db_config['target_db']}",
            target_db_uri=db_config["target_db_uri"],
            target_db=db_config["target_db"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to database '{select_request.name}': {str(e)}")

@router.get("/list-db-configs", response_model=ListDBResponse)
async def list_database_configs(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    List all database configurations.
    Requires authentication.
    """
    db_configs = await get_db_config_collection(request)
    configs = db_configs.find()
    databases = []
    async for config in configs:
        databases.append(StoredDBResponse(
            success=True,
            message="",
            name=config["name"],
            target_db_uri=config["target_db_uri"],
            target_db=config["target_db"],
            description=config.get("description")
        ))
    return ListDBResponse(
        success=True,
        message=f"Found {len(databases)} database configurations",
        databases=databases,
        current_active=CURRENT_ACTIVE_DB
    )

@router.delete("/delete-db-config/{name}")
async def delete_database_config(
    name: str, 
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Delete a database configuration.
    Requires authentication.
    """
    global CURRENT_ACTIVE_DB
    db_configs = await get_db_config_collection(request)
    db_config = await db_configs.find_one({"name": name})
    if not db_config:
        raise HTTPException(status_code=404, detail=f"Database configuration '{name}' not found")
    if name == "default":
        raise HTTPException(status_code=400, detail="Cannot delete the default database configuration")
    if name == CURRENT_ACTIVE_DB:
        CURRENT_ACTIVE_DB = "default"
        default_config = await db_configs.find_one({"name": "default"})
        if default_config:
            TARGET_DB_URI = default_config["target_db_uri"]
            TARGET_DB = default_config["target_db"]
    await db_configs.delete_one({"name": name})
    return {"success": True, "message": f"Database configuration '{name}' deleted successfully"}

@router.post("/set-target-db", response_model=TargetDBResponse)
async def set_target_database(
    config: TargetDBConfig, 
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Set the target database configuration.
    Requires authentication.
    """
    global TARGET_DB_URI, TARGET_DB
    try:
        test_client = AsyncIOMotorClient(config.target_db_uri)
        await test_client.admin.command('ping')
        test_client.close()
        TARGET_DB_URI = config.target_db_uri
        TARGET_DB = config.target_db
        os.environ['TARGET_DB_URI'] = config.target_db_uri
        os.environ['TARGET_DB'] = config.target_db
        scheduler = request.app.state.scheduler
        if scheduler:
            scheduler.update_target_connection(config.target_db_uri, config.target_db)
        return TargetDBResponse(
            success=True,
            message=f"Target database configuration updated successfully. All operations will now use {config.target_db}",
            target_db_uri=config.target_db_uri,
            target_db=config.target_db
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect to target database: {str(e)}"
        )

@router.get("/get-target-db", response_model=TargetDBResponse)
async def get_target_database(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current target database configuration.
    Requires authentication.
    """
    return TargetDBResponse(
        success=True,
        message="Current target database configuration",
        target_db_uri=TARGET_DB_URI,
        target_db=TARGET_DB
    )

# Import datetime for the created_at field
from datetime import datetime 