from decimal import Decimal
from typing import Literal
from cryptography.fernet import Fernet
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)
    APP_NAME: str = "KOHO Banking Core"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str
    SQLALCHEMY_ECHO: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_BACKEND: Literal["redis", "sqlite"] | None = None
    LOCAL_SESSION_DB: str = ".tools/local-sessions.db"
    SECRET_KEY: str = Field(min_length=32)
    ENCRYPTION_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    TRANSFER_FEE_PERCENTAGE: Decimal = Field(default=Decimal("0.01"), ge=0, le=1)
    MIN_TRANSFER_AMOUNT: Decimal = Decimal("0.01")
    MAX_TRANSFER_AMOUNT: Decimal = Decimal("1000000.00")
    AML_HIGH_RISK_THRESHOLD: int = 70
    AML_MEDIUM_RISK_THRESHOLD: int = 40
    TRANSACTION_REVIEW_AMOUNT: Decimal = Decimal("10000.00")
    KYC_DOCUMENT_STORAGE_PATH: str = "./uploads/kyc"

    @model_validator(mode="after")
    def validate_security(self):
        Fernet(self.ENCRYPTION_KEY.encode())
        if self.ALGORITHM != "HS256":
            raise ValueError("Only HS256 is configured")
        if self.ENVIRONMENT == "production" and not self.DATABASE_URL.startswith("postgresql"):
            raise ValueError("Production requires PostgreSQL")
        if self.SESSION_BACKEND == "sqlite" and self.ENVIRONMENT != "development":
            raise ValueError("SQLite sessions are only supported in development")
        return self

    @property
    def cors_origins_list(self):
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]


settings = Settings()
