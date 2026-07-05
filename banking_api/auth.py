"""Utilitaires JWT + dépendances FastAPI — Banking API."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Header
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET", "banking-dev-secret-key-minimum-32-characters!")
ALGORITHM  = "HS256"
TTL_MINUTES = int(os.getenv("JWT_TTL_SECONDS", "3600")) // 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Mot de passe ─────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token ────────────────────────────────────────────────────────────

class TokenClaims(BaseModel):
    user_id: str
    username: str
    email: Optional[str] = None
    role: str  # "CLIENT" | "ADMIN"

def create_access_token(claims: dict) -> str:
    payload = claims.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=TTL_MINUTES)
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> TokenClaims:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenClaims(
            user_id=payload["sub"],
            username=payload["username"],
            email=payload.get("email"),
            role=payload["role"],
        )
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")


# ── Dépendances FastAPI ───────────────────────────────────────────────

async def get_current_user(authorization: str = Header(None)) -> TokenClaims:
    """Vérifie le Bearer token et retourne les claims. Lève 401 si absent/invalide."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token d'authentification manquant (Authorization: Bearer <token>)")
    return decode_token(authorization[7:])

async def require_admin(authorization: str = Header(None)) -> TokenClaims:
    """Comme get_current_user mais exige le rôle ADMIN. Lève 403 sinon."""
    claims = await get_current_user(authorization)
    if claims.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Accès réservé à l'administrateur")
    return claims
