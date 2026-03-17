from fastapi import FastAPI
from app.api.routes import router as api_router
from app.db.base import engine, Base
from app.config.settings import settings

# Create DB tables (In prod, use Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="OCR Engine API",
    description="Industrial High-Accuracy OCR Engine",
    version="1.0.0"
)

app.include_router(api_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
