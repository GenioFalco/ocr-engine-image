import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI


# ── Логирование с временем МСК (UTC+3) ───────────────────────────────────────
class _MskFormatter(logging.Formatter):
    """Форматтер с временными метками МСК (UTC+3)."""
    _MSK_OFFSET = 3 * 3600  # секунд

    def converter(self, timestamp):  # type: ignore[override]
        return time.gmtime(timestamp + self._MSK_OFFSET)

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            return time.strftime(datefmt, ct)
        return time.strftime("%Y-%m-%d %H:%M:%S", ct) + " МСК"


def _setup_msk_logging():
    fmt = _MskFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(fmt)

    # Применяем и к uvicorn-логгерам
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        for h in lg.handlers:
            h.setFormatter(fmt)


_setup_msk_logging()
from fastapi.openapi.utils import get_openapi
from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.api.saml_auth import router as saml_router
from app.db.base import engine, Base
from app.config.settings import settings
import app.models.models  # noqa: F401 — ensure all tables are registered with Base before create_all

logger = logging.getLogger(__name__)

# Create DB tables (In prod, use Alembic)
Base.metadata.create_all(bind=engine)

# ── APScheduler: ежедневный отчёт ────────────────────────────────────────────
# При --workers 8 каждый uvicorn-воркер импортирует main.py и запускает свой
# планировщик → 8 писем одновременно. Защита: эксклюзивная файловая блокировка.
# Только один процесс захватит замок и запустит scheduler; остальные пропустят.
_scheduler = None
try:
    import fcntl as _fcntl
    _LOCK_PATH = "/tmp/ocr_scheduler.lock"
    _lock_fd = open(_LOCK_PATH, "w")
    _fcntl.flock(_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)  # неблокирующий захват

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from app.services.report_service import send_daily_report

    _scheduler = BackgroundScheduler(timezone="UTC")
    # Каждый день в 21:00 UTC = 00:00 МСК (UTC+3).
    # В момент срабатывания datetime.now(UTC) = ещё тот же день МСК → не вычитаем день.
    _scheduler.add_job(send_daily_report, CronTrigger(hour=21, minute=0), id="daily_report")
    _scheduler.start()
    logger.info("APScheduler запущен (lock захвачен). Ежедневный отчёт в 21:00 UTC (00:00 МСК).")
except (IOError, OSError):
    logger.info("APScheduler: другой воркер уже владеет блокировкой — планировщик не запускаем.")
except Exception as _sch_err:
    logger.warning(f"APScheduler не удалось запустить: {_sch_err}")

app = FastAPI(
    title="OCR Engine API",
    description="Industrial High-Accuracy OCR Engine",
    version="1.0.0"
)

app.include_router(api_router)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(saml_router, prefix="/auth/saml", tags=["auth-saml"])

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
