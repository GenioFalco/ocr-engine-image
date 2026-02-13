from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.db.base import Base

from app.api.routes import documents, models, contracts, logs, health

# Import all models to ensure they are registered with Base
from app.db.models import document, ocr_result, model_registry, contract, log

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if they don't exist (useful for dev/mvp)
    # In production, use Alembic migrations instead.
    Base.metadata.create_all(bind=engine)
    
    # Auto-register GigaChat if credentials are set
    if settings.GIGACHAT_CREDENTIALS:
        from app.db.session import SessionLocal
        from app.services.model_service import ModelService
        from app.schemas.model import ModelCreate
        
        db = SessionLocal()
        try:
            model_service = ModelService(db)
            existing = model_service.get_by_provider("gigachat")
            if not existing:
                logger.info("Auto-registering GigaChat model...")
                model_service.create(ModelCreate(
                    name="GigaChat",
                    provider="gigachat",
                    api_key=settings.GIGACHAT_CREDENTIALS,
                    is_active=True,
                    parameters={}
                ))
        except Exception as e:
            logger.error(f"Failed to auto-register GigaChat: {e}")
        finally:
            db.close()
            
    yield
    # Shutdown logic if needed

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["contracts"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["logs"])
app.include_router(health.router, prefix="/health", tags=["health"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
