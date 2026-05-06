from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

# Ovo je ono što tvoj dependencies.py traži
ALGORITHM = settings.JWT_ALGORITHM

# Kontekst za hešovanje lozinki
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(user_id: UUID | Any) -> str:
    """Kreira potpisani JWT token koristeći UUID korisnika."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=ALGORITHM,
    )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Proverava da li se uneta lozinka poklapa sa onom u bazi."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Pretvara običan tekst lozinke u siguran heš."""
    return pwd_context.hash(password)