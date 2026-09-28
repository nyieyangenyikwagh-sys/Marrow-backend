from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

class LoginRequest(BaseModel):
    # Login looks up an existing identifier, including seeded .local accounts.
    # Public email validation belongs at signup, not authentication.
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
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
