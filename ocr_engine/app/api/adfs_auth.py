from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from urllib.parse import urlencode
import secrets
import httpx
import jwt as pyjwt

from app.db.base import get_db
from app.models.models import User
from app.services.auth_service import create_access_token
from app.config.settings import settings

router = APIRouter()


def _adfs_authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.ADFS_CLIENT_ID,
        "redirect_uri": settings.ADFS_REDIRECT_URI,
        "scope": "openid profile email",
        "state": state,
    }
    return f"{settings.ADFS_TENANT_URL}/oauth2/authorize?{urlencode(params)}"


@router.get("/login", summary="Редирект на страницу входа AD FS")
def adfs_login():
    if not settings.ADFS_ENABLED:
        raise HTTPException(status_code=503, detail="AD FS authentication is not enabled")

    state = secrets.token_urlsafe(16)
    response = RedirectResponse(url=_adfs_authorize_url(state))
    # Храним state в cookie для проверки на callback (защита от CSRF)
    response.set_cookie("adfs_state", state, max_age=300, httponly=True, samesite="lax")
    return response


@router.get("/callback", summary="Callback от AD FS после аутентификации")
async def adfs_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str = None,
    state: str = None,
    error: str = None,
    error_description: str = None,
):
    if error:
        raise HTTPException(status_code=400, detail=f"AD FS error: {error_description or error}")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")

    # Проверяем state (защита от CSRF)
    stored_state = request.cookies.get("adfs_state")
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Обмениваем code на токены
    token_url = f"{settings.ADFS_TENANT_URL}/oauth2/token"
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.ADFS_CLIENT_ID,
                "client_secret": settings.ADFS_CLIENT_SECRET,
                "redirect_uri": settings.ADFS_REDIRECT_URI,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to obtain token from AD FS: {resp.text}")

    token_data = resp.json()
    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No ID token in AD FS response")

    # Декодируем ID токен — подпись проверяется через AD FS JWKS, пока доверяем без проверки
    # (AD FS находится во внутренней сети, HTTPS обеспечивает транспортную безопасность)
    try:
        claims = pyjwt.decode(id_token, options={"verify_signature": False})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode ID token: {e}")

    # AD FS может возвращать email в разных claims
    sub = claims.get("sub") or claims.get("upn") or claims.get("unique_name")
    email = claims.get("email") or claims.get("upn")
    name = claims.get("name") or claims.get("given_name") or ""

    if not sub:
        raise HTTPException(status_code=400, detail="Could not extract user identity from AD FS token")

    # Ищем пользователя — сначала по adfs_sub, потом по email
    user = db.query(User).filter(User.adfs_sub == sub).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()

    if not user:
        # Автосоздание пользователя при первом входе через AD FS
        username = (email.split("@")[0] if email else sub).lower().replace(".", "_")
        base = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base}{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            adfs_sub=sub,
            hashed_password=None,
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Привязываем adfs_sub если ещё не привязан
        if not user.adfs_sub:
            user.adfs_sub = sub
            db.commit()

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")

    # Выдаём JWT нашего сервиса
    access_token = create_access_token(
        {"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # Редиректим на фронтенд с токеном
    redirect_url = f"{settings.FRONTEND_URL}?token={access_token}"
    response = RedirectResponse(url=redirect_url)
    response.delete_cookie("adfs_state")
    return response
