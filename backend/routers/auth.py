"""
MedoraAI — Authentication Router
JWT-based login with bcrypt password hashing.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from db.database import get_db
from db import crud
from models.schemas import LoginRequest, LoginResponse, ProfileUpdate, RegisterRequest, UserSummary

logger = logging.getLogger(__name__)

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def serialize_user(user) -> dict:
    """Return the safe, role-aware identity shape used across the API."""
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name or user.username,
        "email": user.email or "",
        "phone": user.phone or "",
        "avatar_url": user.avatar_url or "",
        "specialization": user.specialization or "",
        "qualification": user.qualification or "",
        "department_id": user.department_id,
        "department_name": user.department.name if user.department else None,
        "is_active": bool(user.is_active),
        "is_available": bool(user.is_available),
        "availability_note": user.availability_note or "",
    }


def create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency: extracts and validates JWT from Authorization header.
    Returns the authenticated User object.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_roles(*allowed_roles: str):
    """Create a FastAPI dependency that authorizes one or more user roles."""
    async def role_guard(current_user=Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_guard


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT token.
    
    Demo credentials: demo / demo123
    """
    user = crud.get_user_by_username(db, request.username)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role}
    )

    logger.info(f"User '{user.username}' logged in successfully.")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRY_HOURS * 3600,
        user=UserSummary(**serialize_user(user)),
    )


@router.post("/register", response_model=LoginResponse, status_code=201)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Self-register a patient and return an authenticated session."""
    username = request.username.strip().lower()
    if crud.get_user_by_username(db, username):
        raise HTTPException(status_code=409, detail="Username is already registered")

    user = crud.create_user(
        db,
        username=username,
        hashed_password=pwd_context.hash(request.password),
        role="patient",
        full_name=request.full_name.strip(),
        email=request.email.strip(),
        phone=request.phone.strip(),
    )
    token = create_access_token(
        {"sub": user.username, "user_id": user.id, "role": user.role}
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_HOURS * 3600,
        user=UserSummary(**serialize_user(user)),
    )


@router.get("/me", response_model=UserSummary)
async def me(current_user=Depends(get_current_user)):
    return UserSummary(**serialize_user(current_user))


@router.patch("/me", response_model=UserSummary)
async def update_me(request: ProfileUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.full_name = request.full_name.strip()
    current_user.email = request.email.strip()
    current_user.phone = request.phone.strip()
    db.commit()
    db.refresh(current_user)
    return UserSummary(**serialize_user(current_user))


@router.post("/me/avatar", response_model=UserSummary)
async def upload_avatar(file: UploadFile = File(...), current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    allowed_types = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    extension = allowed_types.get(file.content_type or "")
    if not extension:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Profile image must be 5 MB or smaller")
    avatar_dir = os.path.join(settings.DATA_DIR, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"user-{current_user.id}-{uuid.uuid4().hex}{extension}"
    path = os.path.join(avatar_dir, filename)
    with open(path, "wb") as destination:
        destination.write(content)
    current_user.avatar_url = f"/static/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    return UserSummary(**serialize_user(current_user))
