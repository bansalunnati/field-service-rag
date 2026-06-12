"""
auth/auth_service.py
JWT creation/validation, bcrypt password hashing, role-based permissions.
Matches your existing Azure OpenAI + dotenv style.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# What each role is allowed to do
ROLE_PERMISSIONS = {
    "admin":  {"upload", "query", "view_history", "manage_users"},
    "user":   {"upload", "query", "view_history"},
    "viewer": {"query"},
}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TokenData(BaseModel):
    user_id: str
    email:   str
    role:    str


class Token(BaseModel):
    access_token: str
    token_type:   str
    role:         str


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload.get("role", "viewer"),
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return decode_token(token)


def require_permission(permission: str):
    """
    Dependency factory.
    Usage: user: TokenData = Depends(require_permission("upload"))
    Raises 403 if the user's role lacks the permission.
    """
    async def checker(user: TokenData = Depends(get_current_user)) -> TokenData:
        if permission not in ROLE_PERMISSIONS.get(user.role, set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' does not have '{permission}' permission",
            )
        return user
    return checker
