"""
Security utilities for authentication and authorization.

This module provides:
- Password hashing and verification using bcrypt
- JWT token creation and validation
- Security-related helper functions

Usage:
    from app.core.security import (
        hash_password,
        verify_password,
        create_access_token,
        verify_token,
    )
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# -----------------------------------------------------------------------------
# Password Hashing Configuration
# -----------------------------------------------------------------------------

# CryptContext handles password hashing with bcrypt
# - bcrypt is automatically salted and resistant to timing attacks
# - deprecated="auto" allows smooth migration if we change schemes
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.PASSWORD_HASH_ROUNDS,
)


def hash_password(plain_password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Args:
        plain_password: The user's plain text password
        
    Returns:
        str: The hashed password (includes salt)
        
    Example:
        >>> hashed = hash_password("mysecretpassword")
        >>> hashed.startswith("$2b$")
        True
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    Uses constant-time comparison to prevent timing attacks.
    
    Args:
        plain_password: The plain text password to check
        hashed_password: The bcrypt hash to verify against
        
    Returns:
        bool: True if the password matches, False otherwise
        
    Example:
        >>> hashed = hash_password("mysecretpassword")
        >>> verify_password("mysecretpassword", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


# -----------------------------------------------------------------------------
# JWT Token Configuration
# -----------------------------------------------------------------------------

class TokenPayload(BaseModel):
    """
    JWT token payload schema.
    
    Attributes:
        sub: Subject (typically user ID or email)
        exp: Expiration time as Unix timestamp
        type: Token type (access or refresh)
        iat: Issued at time as Unix timestamp
    """
    sub: str
    exp: int
    type: str = "access"
    iat: Optional[int] = None


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: The token subject (usually user ID or email)
        expires_delta: Optional custom expiration time
        additional_claims: Optional extra claims to include in the token
        
    Returns:
        str: The encoded JWT token
        
    Example:
        >>> token = create_access_token(subject="user@example.com")
        >>> token.count('.') == 2  # JWT format: header.payload.signature
        True
    """
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    
    if additional_claims:
        payload.update(additional_claims)
    
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(subject: str | int) -> str:
    """
    Create a JWT refresh token.
    
    Refresh tokens have a longer lifespan and are used to obtain
    new access tokens without requiring re-authentication.
    
    Args:
        subject: The token subject (usually user ID or email)
        
    Returns:
        str: The encoded JWT refresh token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_token(token: str, token_type: str = "access") -> Optional[TokenPayload]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token to verify
        token_type: Expected token type ("access" or "refresh")
        
    Returns:
        TokenPayload: The decoded token payload if valid
        None: If the token is invalid, expired, or wrong type
        
    Example:
        >>> token = create_access_token(subject="user@example.com")
        >>> payload = verify_token(token)
        >>> payload.sub
        'user@example.com'
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        
        # Verify token type matches expected
        if payload.get("type") != token_type:
            return None
        
        return TokenPayload(**payload)
        
    except JWTError:
        return None


def token_predates_password_change(
    iat: Optional[int],
    password_changed_at: Optional[datetime],
) -> bool:
    """Return True if a token was issued before the user's last password change.

    Used to invalidate existing access/refresh tokens after a password reset.
    A token with no ``iat`` is treated as predating any password change (it
    cannot prove it was issued afterwards). Users who have never changed their
    password (``password_changed_at`` is None) are unaffected.
    """
    if password_changed_at is None:
        return False
    if iat is None:
        return True
    return iat < int(password_changed_at.timestamp())


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode a JWT token without verification.
    
    WARNING: This does not verify the token signature!
    Only use for debugging or when verification is handled elsewhere.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        dict: The decoded payload
        None: If decoding fails
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_signature": False},
        )
    except JWTError:
        return None
