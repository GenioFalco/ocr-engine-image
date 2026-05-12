"""
SAML 2.0 интеграция с AD FS (fs.askona.ru)

Flow:
  1. GET  /auth/saml/login    → редирект на AD FS
  2. POST /auth/saml/acs      → AD FS постит сюда SAML Response после входа
  3. GET  /auth/saml/metadata → наш SP Metadata XML (отдаём IT для регистрации)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional
import re

from app.db.base import get_db
from app.models.models import User
from app.services.auth_service import create_access_token
from app.config.settings import settings

router = APIRouter()


def _get_saml_auth(request_data: dict):
    """Создаёт объект OneLogin_Saml2_Auth для обработки запроса."""
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
    except ImportError:
        raise HTTPException(status_code=503, detail="python3-saml не установлен")

    saml_settings = {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": f"{settings.APP_URL}/auth/saml/metadata",
            "assertionConsumerService": {
                "url": f"{settings.APP_URL}/auth/saml/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": f"{settings.APP_URL}/auth/saml/sls",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": settings.SAML_SP_CERT,
            "privateKey": settings.SAML_SP_KEY,
        },
        "idp": {
            # AD FS entity ID
            "entityId": f"{settings.SAML_IDP_URL}/services/trust",
            "singleSignOnService": {
                "url": f"{settings.SAML_IDP_URL}/ls/",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": {
                "url": f"{settings.SAML_IDP_URL}/ls/?wa=wsignout1.0",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": settings.SAML_IDP_CERT,
        },
    }
    return OneLogin_Saml2_Auth(request_data, saml_settings)


def _prepare_saml_request(request: Request, body: bytes = b"") -> dict:
    """Преобразует FastAPI Request в формат понятный python3-saml."""
    from urllib.parse import parse_qs

    # Корректное определение HTTPS за nginx reverse-proxy
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    is_https = forwarded_proto == "https" or request.url.scheme == "https"

    # Правильный URL-decode POST-тела (SAMLResponse — base64 с =, %XX, + и т.д.)
    post_data = {}
    if body:
        for key, values in parse_qs(body.decode("utf-8"), keep_blank_values=True).items():
            post_data[key] = values[0] if values else ""

    return {
        "https": "on" if is_https else "off",
        "http_host": request.headers.get("host", ""),
        "server_port": 443 if is_https else 80,
        "script_name": request.url.path,
        "get_data": dict(request.query_params),
        "post_data": post_data,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/login", summary="Редирект на AD FS (SAML 2.0)")
async def saml_login(request: Request):
    if not settings.SAML_ENABLED:
        raise HTTPException(status_code=503, detail="SAML аутентификация не включена")

    req = _prepare_saml_request(request)
    auth = _get_saml_auth(req)
    return RedirectResponse(url=auth.login())


@router.post("/acs", summary="Assertion Consumer Service — принимает ответ AD FS")
async def saml_acs(
    request: Request,
    db: Session = Depends(get_db),
):
    """AD FS делает POST сюда после успешной аутентификации пользователя."""
    body = await request.body()
    req = _prepare_saml_request(request, body)
    auth = _get_saml_auth(req)
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        raise HTTPException(status_code=400, detail=f"SAML ошибка: {', '.join(errors)}")

    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="SAML аутентификация не прошла")

    # Извлекаем атрибуты пользователя из SAML Assertion
    attrs = auth.get_attributes()
    name_id = auth.get_nameid()  # обычно email или UPN

    # AD FS возвращает атрибуты по полным URI
    def get_attr(uri_endings: list) -> Optional[str]:
        for key, val in attrs.items():
            for ending in uri_endings:
                if key.endswith(ending) and val:
                    return val[0]
        return None

    email = get_attr(["emailaddress", "mail", "Email"]) or name_id
    first_name = get_attr(["givenname", "GivenName", "firstname"])
    last_name = get_attr(["surname", "Surname", "lastname"])
    display_name = get_attr(["displayname", "DisplayName", "name"])
    upn = get_attr(["upn", "UPN"]) or email
    department = get_attr(["department", "Department"])

    if not email and not name_id:
        raise HTTPException(status_code=400, detail="AD FS не вернул email пользователя")

    # Ищем пользователя — сначала по saml_nameid, потом по email
    user = db.query(User).filter(User.saml_nameid == name_id).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()

    if not user:
        # Автосоздание при первом входе
        username = re.sub(r"[^a-z0-9_]", "_", (upn.split("@")[0]).lower())
        base = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base}{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            saml_nameid=name_id,
            display_name=display_name or f"{first_name or ''} {last_name or ''}".strip() or username,
            department=department,
            hashed_password=None,
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Обновляем данные при каждом входе (имя, отдел могли измениться)
        changed = False
        if not user.saml_nameid:
            user.saml_nameid = name_id
            changed = True
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if department and user.department != department:
            user.department = department
            changed = True
        if changed:
            db.commit()

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Пользователь деактивирован")

    # Выдаём наш JWT
    access_token = create_access_token(
        {"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}?token={access_token}",
        status_code=303,
    )


@router.get("/metadata", summary="SP Metadata XML — отдаём IT для регистрации в AD FS")
async def saml_metadata(request: Request):
    """
    Этот URL передаётся IT-администраторам AD FS.
    Они импортируют его в AD FS как Relying Party Trust.
    """
    req = _prepare_saml_request(request)
    auth = _get_saml_auth(req)
    settings_obj = auth.get_settings()
    metadata = settings_obj.get_sp_metadata()

    errors = settings_obj.validate_metadata(metadata)
    if errors:
        raise HTTPException(status_code=500, detail=f"Ошибка SP metadata: {errors}")

    return Response(
        content=metadata,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="sp-metadata.xml"'},
    )
