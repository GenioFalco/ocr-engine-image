import secrets as _secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import Any
import secrets
import uuid as _uuid
from pydantic import BaseModel

from app.db.base import get_db
from app.models.models import User, ApiKey
from app.schemas.user import UserCreate, UserResponse, Token
from app.services.auth_service import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_admin_user, get_current_active_user
)
from app.config.settings import settings

router = APIRouter()


# ── Регистрация (только Admin) ─────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    """Создать нового пользователя — только для администратора."""
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")

    role = user_in.role if user_in.role in ("user", "robot", "admin") else "user"

    # Обычные пользователи должны иметь пароль
    if role == "user" and not user_in.password:
        raise HTTPException(status_code=400, detail="Для обычного пользователя необходим пароль")

    # Роботы получают случайный неиспользуемый хэш — логин через /auth/login невозможен
    raw_password = user_in.password if user_in.password else _secrets.token_urlsafe(48)

    user = User(
        username=user_in.username,
        email=user_in.email or None,
        hashed_password=get_password_hash(raw_password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Обычный вход (логин / пароль) ─────────────────────────────────────────────

@router.post("/login", response_model=Token)
def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """Стандартный вход по логину и паролю. Роботы должны использовать /auth/token."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь деактивирован")
    if user.role == "robot":
        raise HTTPException(status_code=403, detail="Роботы не могут войти через пароль. Используйте /auth/token с client_id и client_secret.")

    access_token = create_access_token(
        {"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


@router.get("/me")
def read_user_me(current_user: User = Depends(get_current_user)) -> Any:
    """Текущий авторизованный пользователь."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


# ── API ключи (для роботов / RPA) ─────────────────────────────────────────────

class ApiKeyCreateRequest(BaseModel):
    user_id: int
    label: str = ""


class ApiKeyTokenRequest(BaseModel):
    client_id: str
    client_secret: str


@router.post("/token", summary="Получить 30-минутный токен по API ключу")
def get_token_by_api_key(
    body: ApiKeyTokenRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Роботы/RPA используют этот endpoint для получения JWT.
    Токен действует 30 минут. После истечения — запросить заново.
    """
    key = db.query(ApiKey).filter(
        ApiKey.client_id == body.client_id,
        ApiKey.is_active == True,
    ).first()

    if not key or not verify_password(body.client_secret, key.client_secret_hash):
        raise HTTPException(status_code=401, detail="Неверный client_id или client_secret")

    user = db.query(User).filter(User.id == key.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден или деактивирован")

    key.last_used_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token(
        {"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.API_KEY_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "expires_in": settings.API_KEY_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/admin/api_keys", summary="Создать API ключ (только Admin)")
def create_api_key(
    body: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    """Создаёт пару client_id / client_secret. Secret показывается только один раз."""
    target_user = db.query(User).filter(User.id == body.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    raw_secret = secrets.token_urlsafe(32)
    client_id = f"ocr-{target_user.username}-{_uuid.uuid4().hex[:8]}"

    key = ApiKey(
        user_id=body.user_id,
        client_id=client_id,
        client_secret_hash=get_password_hash(raw_secret),
        label=body.label or f"Ключ для {target_user.username}",
    )
    db.add(key)
    db.commit()
    db.refresh(key)

    return {
        "id": key.id,
        "client_id": client_id,
        "client_secret": raw_secret,  # показывается ОДИН РАЗ
        "label": key.label,
        "warning": "Сохраните client_secret — он больше не будет показан.",
    }


@router.get("/admin/api_keys", summary="Список API ключей (только Admin)")
def list_api_keys(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    uid_set = list({k.user_id for k in keys if k.user_id})
    users_map: dict = {}
    if uid_set:
        users_map = {u.id: u.username for u in db.query(User).filter(User.id.in_(uid_set)).all()}
    return [
        {
            "id": k.id,
            "client_id": k.client_id,
            "label": k.label,
            "user_id": k.user_id,
            "username": users_map.get(k.user_id, "?"),
            "is_active": k.is_active,
            "created_at": k.created_at,
            "last_used_at": k.last_used_at,
        }
        for k in keys
    ]


@router.delete("/admin/api_keys/{key_id}", summary="Отозвать API ключ (только Admin)")
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Ключ не найден")
    key.is_active = False
    db.commit()
    return {"status": "revoked", "client_id": key.client_id}
