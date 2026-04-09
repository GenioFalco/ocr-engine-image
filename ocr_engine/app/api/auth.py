from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Any

from app.db.base import get_db
from app.models.models import User
from app.schemas.user import UserCreate, UserResponse, Token
from app.services.auth_service import (
    verify_password, get_password_hash, create_access_token, get_current_user, get_current_admin_user
)
from app.config.settings import settings

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)) -> Any:
    """
    Create new user (Admins Only).
    """
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    
    role = user_in.role if user_in.role in ('user', 'robot') else 'user'
    
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    return {
        "access_token": create_access_token(
            {"sub": user.username, "role": user.role}, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "role": user.role
    }

@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: User = Depends(get_current_user)) -> Any:
    """
    Get current user.
    """
    return current_user

# ── API Key auth ──────────────────────────────────────────────────────────────
import secrets
import uuid as _uuid
from pydantic import BaseModel as _BaseModel
from app.models.models import ApiKey
from datetime import datetime

class TokenRequest(_BaseModel):
    client_id: str
    client_secret: str

class ApiKeyCreateRequest(_BaseModel):
    user_id: int
    label: str = ""

@router.post("/token")
def get_token_by_api_key(
    body: TokenRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Exchange client_id + client_secret for a JWT access token.
    Secure alternative to login/password for RPA robots.
    """
    key_record = db.query(ApiKey).filter(
        ApiKey.client_id == body.client_id,
        ApiKey.is_active == True
    ).first()

    if not key_record or not verify_password(body.client_secret, key_record.client_secret_hash):
        raise HTTPException(status_code=401, detail="Invalid client_id or client_secret")

    user = db.query(User).filter(User.id == key_record.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Associated user not found or inactive")

    # Update last_used_at
    key_record.last_used_at = datetime.utcnow()
    db.commit()

    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token({"sub": user.username, "role": user.role}, expires_delta=expires),
        "token_type": "bearer",
        "role": user.role,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/admin/api_keys")
def create_api_key(
    body: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
) -> Any:
    """Generate a new client_id/client_secret pair for a user (Admin only)."""
    target_user = db.query(User).filter(User.id == body.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    raw_secret = secrets.token_urlsafe(32)
    client_id = f"ocr-{target_user.username}-{_uuid.uuid4().hex[:8]}"

    key = ApiKey(
        user_id=body.user_id,
        client_id=client_id,
        client_secret_hash=get_password_hash(raw_secret),
        label=body.label or f"Key for {target_user.username}"
    )
    db.add(key)
    db.commit()
    db.refresh(key)

    return {
        "id": key.id,
        "client_id": client_id,
        "client_secret": raw_secret,  # Shown ONCE
        "label": key.label,
        "warning": "Save the client_secret now! It will not be shown again."
    }

@router.get("/admin/api_keys")
def list_api_keys(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
) -> Any:
    """List all API keys (Admin only). Secret hashes are never returned."""
    keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    return [{
        "id": k.id,
        "client_id": k.client_id,
        "label": k.label,
        "user_id": k.user_id,
        "username": k.user.username if k.user else "?",
        "is_active": k.is_active,
        "created_at": k.created_at,
        "last_used_at": k.last_used_at,
    } for k in keys]

@router.delete("/admin/api_keys/{key_id}")
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
) -> Any:
    """Revoke (deactivate) an API key (Admin only)."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    db.commit()
    return {"status": "revoked", "client_id": key.client_id}

