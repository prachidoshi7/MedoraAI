"""
MedoraAI — Authentication Router
JWT-based login with bcrypt password hashing.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from db.database import get_db
from db import crud
from models.schemas import LoginRequest, LoginResponse, RegisterRequest, UserSummary

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
