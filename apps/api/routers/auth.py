"""Auth router."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from apps.api.schemas.auth import TokenResponse, LoginRequest
from apps.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain, hashed):
    return plain == hashed  # stub


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@router.post("/login")
async def login(req: LoginRequest):
    # In production: verify against DB
    hashed = get_password_hash(req.password)
    if req.username != "admin":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub": req.username})
    return TokenResponse(access_token=access_token, expires_in=settings.JWT_EXPIRATION_HOURS * 3600)


@router.post("/logout")
async def logout():
    return {"status": "logged_out"}


@router.post("/refresh")
async def refresh_token():
    return {"access_token": "new_token", "expires_in": settings.JWT_EXPIRATION_HOURS * 3600}
