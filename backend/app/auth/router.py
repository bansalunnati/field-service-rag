"""
auth/router.py
Endpoints: POST /api/auth/register, POST /api/auth/login, GET /api/auth/me
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.auth_service import (
    hash_password, verify_password,
    create_access_token, get_current_user,
    Token, TokenData,
)
from app.chat.database import get_db
from app.chat.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email:    EmailStr
    password: str
    role:     str = "user"   # default role for new signups


class RegisterResponse(BaseModel):
    user_id: str
    email:   str
    role:    str


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return RegisterResponse(user_id=str(user.id), email=user.email, role=user.role)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role}
    )
    return Token(access_token=token, token_type="bearer", role=user.role)


@router.get("/me", response_model=TokenData)
async def me(current_user: TokenData = Depends(get_current_user)):
    return current_user
