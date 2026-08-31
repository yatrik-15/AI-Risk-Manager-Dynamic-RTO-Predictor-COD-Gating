"""
Configuration module — loads environment variables via Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Razorpay
    RAZORPAY_KEY_ID: str = Field(default="rzp_test_placeholder", description="Razorpay Test Key ID")
    RAZORPAY_KEY_SECRET: str = Field(default="placeholder_secret", description="Razorpay Test Key Secret")

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # ML
    RISK_THRESHOLD: float = Field(default=0.75, description="RTO risk threshold for blocking COD (0.0 - 1.0)")

    # Server
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=True)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
