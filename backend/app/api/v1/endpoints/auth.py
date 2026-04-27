"""
Endpoints de autenticacion del admin.
Login/logout con cookie de sesion firmada con HMAC-SHA256.
"""
import hashlib
import hmac
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.config import settings

router = APIRouter()


# ─── UTILIDADES DE SESION ─────────────────────────────────────────────────────

def verify_password(plain: str, stored: str) -> bool:
    """Comparacion segura — evita timing attacks."""
    return hmac.compare_digest(plain.strip(), stored.strip())


def create_session_token(username: str) -> str:
    """Genera un token de sesion firmado con el secret key."""
    payload = f"{username}:{int(time.time())}"
    sig = hmac.new(
        settings.ADMIN_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{sig}"


def verify_session_token(token: str) -> bool:
    """Verifica que el token es valido y no expiro (8 horas)."""
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return False
        payload, sig = parts
        expected_sig = hmac.new(
            settings.ADMIN_SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        # Verificar expiracion
        _username, timestamp = payload.rsplit(":", 1)
        if time.time() - int(timestamp) > 28800:  # 8 horas
            return False
        return True
    except Exception:
        return False


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
):
    if username == settings.ADMIN_USERNAME and verify_password(password, settings.ADMIN_PASSWORD):
        token = create_session_token(username)
        redirect = RedirectResponse(url="/admin/", status_code=302)
        redirect.set_cookie(
            key="pca_admin_session",
            value=token,
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="lax",
            max_age=28800,
        )
        return redirect
    return RedirectResponse(url="/admin/login.html?error=1", status_code=302)


@router.post("/logout")
async def logout():
    redirect = RedirectResponse(url="/admin/login.html", status_code=302)
    redirect.delete_cookie("pca_admin_session")
    return redirect


@router.get("/check")
async def check_auth(request: Request):
    """Verifica desde el frontend si la sesion sigue activa."""
    token = request.cookies.get("pca_admin_session", "")
    if verify_session_token(token):
        return {"authenticated": True}
    return {"authenticated": False}
