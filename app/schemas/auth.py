"""
Authentication Pydantic schemas for request/response validation.

These schemas define the structure of auth-related API requests and responses.
"""

from pydantic import BaseModel, EmailStr, Field


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    """Schema for user registration request."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters)"
    )


class UserLoginRequest(BaseModel):
    """Schema for user login request."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str = Field(..., description="Valid refresh token")


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """Schema for token response after login/register."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class UserResponse(BaseModel):
    """Schema for user data in responses."""
    id: int
    email: str
    is_active: bool
    is_verified: bool
    default_provider_id: int | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Schema for auth response with user data and tokens."""
    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    """Schema for simple message responses."""
    message: str
    detail: str | None = None
