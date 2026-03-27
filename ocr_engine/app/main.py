from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from app.api.routes import router as api_router
from app.api.auth import router as auth_router
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
app.include_router(auth_router, prefix="/auth", tags=["auth"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Override OpenAPI schema to add HTTPBearer security (direct token paste field in Swagger)
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Вставьте JWT токен полученный из POST /auth/login"
    }
    # Apply BearerAuth globally so all endpoints can use it
    for path in schema.get("paths", {}).values():
        for method in path.values():
            if isinstance(method, dict):
                method.setdefault("security", []).append({"BearerAuth": []})
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi
