from pydantic import BaseModel, EmailStr, Field

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class TokenResponse(BaseModel):
    """Closes the §6.2/§7.3 gap: the frontend already expects both an
    access and a refresh token back from login — this is the schema
    that finally makes that contract explicit and typed."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str
