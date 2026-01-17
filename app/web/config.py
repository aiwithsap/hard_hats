"""Web service configuration from environment variables."""

import os
from typing import Optional


class WebConfig:
    """Configuration for web service."""

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8123"))

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # Cookie settings
    COOKIE_NAME: str = "session"
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "strict"

    # CORS (for development)
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_AUTH: int = int(os.getenv("RATE_LIMIT_AUTH", "5"))  # per minute
    RATE_LIMIT_API: int = int(os.getenv("RATE_LIMIT_API", "100"))  # per minute

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Features
    REGISTRATION_ENABLED: bool = os.getenv("REGISTRATION_ENABLED", "true").lower() == "true"
    MAX_CAMERAS_DEFAULT: int = int(os.getenv("MAX_CAMERAS_DEFAULT", "5"))
    MAX_USERS_DEFAULT: int = int(os.getenv("MAX_USERS_DEFAULT", "3"))

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production."""
        return os.getenv("RAILWAY_ENVIRONMENT") is not None or \
               os.getenv("ENVIRONMENT", "").lower() == "production"

    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration and return list of warnings."""
        warnings = []

        if cls.SECRET_KEY == "CHANGE_ME_IN_PRODUCTION":
            if cls.is_production():
                raise ValueError("SECRET_KEY must be set in production!")
            warnings.append("Using default SECRET_KEY - not safe for production")

        return warnings


config = WebConfig()
