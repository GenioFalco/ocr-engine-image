"""
SystemSettings service — читает/пишет настройки из таблицы system_settings.
При отсутствии ключа возвращает дефолтное значение из settings.py.
"""
from sqlalchemy.orm import Session
from app.models.models import SystemSetting
from app.config.settings import settings as env_settings

# Дефолтные значения и описания
DEFAULTS = {
    "daily_token_limit": {
        "value": str(env_settings.DAILY_TOKEN_LIMIT),
        "description": "Максимум токенов LLM в сутки (UTC). 0 = без лимита.",
    },
    "max_pages_per_job": {
        "value": str(env_settings.MAX_PAGES_PER_JOB),
        "description": "Максимум страниц в одном документе. 0 = без лимита.",
    },
    "max_jobs_per_user_per_day": {
        "value": str(env_settings.MAX_JOBS_PER_USER_PER_DAY),
        "description": "Максимум заданий на пользователя в сутки. 0 = без лимита.",
    },
}


def get_setting(db: Session, key: str) -> str:
    """Вернуть значение настройки из БД, или дефолт из env/кода."""
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is not None and row.value is not None:
        return row.value
    return DEFAULTS.get(key, {}).get("value", "0")


def get_int_setting(db: Session, key: str) -> int:
    try:
        return int(get_setting(db, key))
    except (ValueError, TypeError):
        return 0


def set_setting(db: Session, key: str, value: str) -> SystemSetting:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        desc = DEFAULTS.get(key, {}).get("description", "")
        row = SystemSetting(key=key, value=value, description=desc)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_all_settings(db: Session) -> dict:
    """Вернуть все известные настройки (из БД + дефолты для отсутствующих)."""
    rows = {r.key: r for r in db.query(SystemSetting).all()}
    result = {}
    for key, meta in DEFAULTS.items():
        row = rows.get(key)
        result[key] = {
            "key": key,
            "value": row.value if row and row.value is not None else meta["value"],
            "description": row.description if row else meta["description"],
            "is_default": row is None or row.value is None,
        }
    return result
