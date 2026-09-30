"""Application Configuration and Environmental Settings.

Loads, parses, and validates runtime parameters using Pydantic Settings.
"""

from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Comprehensive environment configuration for ZERMP Enterprise platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Core Application
    APP_NAME: str = Field(default="ZERMP-Enterprise")
    APP_ENV: str = Field(default="development")
    APP_PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    API_V1_PREFIX: str = Field(default="/api/v1")
    SECRET_KEY: str = Field(default="insecure-dev-key-must-be-rotated-for-production-min32chars")
    ALLOWED_HOSTS: str = Field(default="*")
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # PostgreSQL OLTP
    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="zermp_core")
    POSTGRES_USER: str = Field(default="zermp_admin")
    POSTGRES_PASSWORD: str = Field(default="zermp_secure_dev_password_2026")
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://zermp_admin:zermp_secure_dev_password_2026@postgres:5432/zermp_core"
    )
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)

    # ClickHouse OLAP
    CLICKHOUSE_HOST: str = Field(default="clickhouse")
    CLICKHOUSE_PORT: int = Field(default=8123)
    CLICKHOUSE_NATIVE_PORT: int = Field(default=9000)
    CLICKHOUSE_DB: str = Field(default="zermp_analytics")
    CLICKHOUSE_USER: str = Field(default="default")
    CLICKHOUSE_PASSWORD: str = Field(default="clickhouse_dev_pass_2026")

    # Redis Cache & Rate Limiting
    REDIS_HOST: str = Field(default="redis")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(default="redis_secure_dev_password_2026")
    REDIS_DB: int = Field(default=0)
    REDIS_URL: str = Field(default="redis://:redis_secure_dev_password_2026@redis:6379/0")

    # AWS S3 / LocalStack Object Storage
    AWS_ACCESS_KEY_ID: str = Field(default="test")
    AWS_SECRET_ACCESS_KEY: str = Field(default="test")
    AWS_DEFAULT_REGION: str = Field(default="ap-south-1")
    S3_ENDPOINT_URL: str = Field(default="http://s3:4566")
    S3_BUCKET_REPORTS: str = Field(default="zermp-regulatory-reports")
    S3_BUCKET_INGEST: str = Field(default="zermp-raw-ingestion")
    S3_USE_SSL: bool = Field(default=False)

    # SFTP Server (FinnOne Batch Drops - DS-01)
    SFTP_HOST: str = Field(default="sftp")
    SFTP_PORT: int = Field(default=22)
    SFTP_USER: str = Field(default="finnone_etl")
    SFTP_PASSWORD: str = Field(default="finnone_drop_password_2026")
    SFTP_REMOTE_DIR: str = Field(default="/upload")

    # Authentication & JWT Security (CFG-UM-01)
    AUTH_METHOD: str = Field(default="SAML_MOCK")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    MFA_ENFORCED_ROLES: List[str] = Field(
        default_factory=lambda: ["Admin", "CRO", "Head of Credit Risk", "Internal Auditor"]
    )

    # Regulatory Classification & Provisioning Norms (RBI IRAC)
    NPA_DPD_THRESHOLD: int = Field(default=90)
    SUBSTANDARD_PROVISION_SECURED: float = Field(default=0.10)
    SUBSTANDARD_PROVISION_UNSECURED: float = Field(default=0.10)
    D1_PROVISION_SECURED: float = Field(default=0.25)
    D2_PROVISION_SECURED: float = Field(default=0.40)
    D3_PROVISION_TOTAL: float = Field(default=1.00)
    LOSS_PROVISION_TOTAL: float = Field(default=1.00)


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of validated settings."""
    return Settings()
