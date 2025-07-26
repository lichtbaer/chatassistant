"""
Configuration management for the AI Assistant Platform.

This module provides centralized configuration management using Pydantic settings
for type-safe environment variable handling and validation.
"""

from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = Field(
        default="AI Assistant Platform",
        description="Application name",
    )
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="production", description="Environment")

    # Server
    host: str = Field(
        default="0.0.0.0", description="Host"
    )  # nosec B104 - 0.0.0.0 is correct for server binding
    port: int = Field(default=8000, description="Port")
    frontend_port: int = Field(default=3000, description="Frontend port")

    # Frontend-Backend Communication
    backend_url: str = Field(
        default="http://localhost:8000",
        description="Backend URL for frontend communication",
    )
    ws_url: str = Field(
        default="ws://localhost:8000",
        description="WebSocket URL for frontend communication",
    )
    frontend_url: str = Field(
        default="http://localhost:5173",
        description="Frontend URL for CORS configuration",
    )
    cors_origins: list[str] = Field(
        default=[
            "https://yourdomain.com",
            "https://www.yourdomain.com",
        ],
        description="List of allowed CORS origins - restrict in production",
    )

    # Database
    database_url: str = Field(default="sqlite:///./test.db", description="Database URL")
    database_pool_size: int = Field(default=20, description="Database pool size")
    database_max_overflow: int = Field(default=30, description="Database max overflow")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    redis_db: int = Field(default=0, description="Redis database")

    # Security
    secret_key: str = Field(
        default=None,  # Kein Default für Production
        description="Secret key - must be set in production",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="JWT access token expire minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="JWT refresh token expire days",
    )

    # AI Providers
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    google_api_key: str | None = Field(default=None, description="Google API key")

    # LiteLLM Configuration
    litellm_model: str = Field(default="gpt-4", description="LiteLLM model")
    litellm_max_tokens: int = Field(default=4096, description="LiteLLM max tokens")
    litellm_temperature: float = Field(default=0.7, description="LiteLLM temperature")
    litellm_proxy_host: str | None = Field(
        default=None,
        description="LiteLLM proxy host",
    )

    # Weaviate Configuration
    weaviate_url: str = Field(
        default="http://localhost:8080",
        description="Weaviate URL",
    )
    weaviate_api_key: str | None = Field(default=None, description="Weaviate API key")

    # Knowledge Base Configuration
    default_embedding_model: str = Field(
        default="text-embedding-ada-002",
        description="Default embedding model",
    )
    default_chunk_size: int = Field(default=500, description="Default chunk size")
    default_chunk_overlap: int = Field(default=50, description="Default chunk overlap")
    max_chunk_size: int = Field(default=2000, description="Max chunk size")
    min_chunk_size: int = Field(default=100, description="Min chunk size")

    # Document Processing
    chunk_size: int = Field(default=500, description="Chunk size")
    chunk_overlap: int = Field(default=50, description="Chunk overlap")
    max_file_size: int = Field(default=10485760, description="Max file size")  # 10MB
    supported_file_types: list[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/html",
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/bmp",
            "image/tiff",
        ],
        description="Supported file types",
    )

    # File Storage
    upload_dir: str = Field(default="./uploads", description="Upload directory")

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_file: str = Field(default="./logs/app.log", description="Log file")

    # Internationalization
    default_language: str = Field(default="de", description="Default language")
    languages: list[str] = Field(
        default=["de", "en", "fr", "es"],
        description="Supported languages",
    )

    # Email Configuration
    smtp_host: str | None = Field(default=None, description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_user: str | None = Field(default=None, description="SMTP user")
    smtp_password: str | None = Field(default=None, description="SMTP password")

    # External Services
    serper_api_key: str | None = Field(default=None, description="Serper API key")
    wolfram_alpha_api_key: str | None = Field(
        default=None,
        description="Wolfram Alpha API key",
    )

    # SSO Configuration
    # Google OAuth2
    sso_google_enabled: bool = Field(default=False, description="Enable Google SSO")
    sso_google_client_id: str | None = Field(
        default=None,
        description="Google OAuth2 client ID",
    )
    sso_google_client_secret: str | None = Field(
        default=None,
        description="Google OAuth2 client secret",
    )
    sso_google_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/sso/callback/google",
        description="Google OAuth2 redirect URI",
    )

    # Microsoft OAuth2
    sso_microsoft_enabled: bool = Field(
        default=False,
        description="Enable Microsoft SSO",
    )
    sso_microsoft_client_id: str | None = Field(
        default=None,
        description="Microsoft OAuth2 client ID",
    )
    sso_microsoft_client_secret: str | None = Field(
        default=None,
        description="Microsoft OAuth2 client secret",
    )
    sso_microsoft_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/sso/callback/microsoft",
        description="Microsoft OAuth2 redirect URI",
    )
    sso_microsoft_tenant_id: str | None = Field(
        default=None,
        description="Microsoft tenant ID",
    )

    # GitHub OAuth2
    sso_github_enabled: bool = Field(default=False, description="Enable GitHub SSO")
    sso_github_client_id: str | None = Field(
        default=None,
        description="GitHub OAuth2 client ID",
    )
    sso_github_client_secret: str | None = Field(
        default=None,
        description="GitHub OAuth2 client secret",
    )
    sso_github_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/sso/callback/github",
        description="GitHub OAuth2 redirect URI",
    )

    # SAML Configuration
    sso_saml_enabled: bool = Field(default=False, description="Enable SAML SSO")
    sso_saml_metadata_url: str | None = Field(
        default=None,
        description="SAML metadata URL",
    )
    sso_saml_entity_id: str = Field(
        default="http://localhost:8000",
        description="SAML entity ID",
    )
    sso_saml_acs_url: str = Field(
        default="http://localhost:8000/api/v1/auth/sso/callback/saml",
        description="SAML assertion consumer service URL",
    )
    sso_saml_cert_file: str | None = Field(
        default=None,
        description="SAML certificate file path",
    )
    sso_saml_key_file: str | None = Field(
        default=None,
        description="SAML private key file path",
    )

    # OIDC Configuration
    sso_oidc_enabled: bool = Field(default=False, description="Enable OIDC SSO")
    sso_oidc_issuer_url: str | None = Field(default=None, description="OIDC issuer URL")
    sso_oidc_client_id: str | None = Field(default=None, description="OIDC client ID")
    sso_oidc_client_secret: str | None = Field(
        default=None,
        description="OIDC client secret",
    )
    sso_oidc_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/sso/callback/oidc",
        description="OIDC redirect URI",
    )

    # Registration
    registration_enabled: bool = Field(
        default=True,
        json_schema_extra={"env": "REGISTRATION_ENABLED"},
    )

    performance_monitoring_enabled: bool = Field(
        default=True,
        json_schema_extra={"env": "PERFORMANCE_MONITORING_ENABLED"},
    )
    performance_monitoring_interval: int = Field(
        default=60,
        json_schema_extra={"env": "PERFORMANCE_MONITORING_INTERVAL"},
    )
    performance_alert_thresholds: dict = Field(default_factory=dict)

    default_ai_model: str = Field(
        default="gpt-4",
        json_schema_extra={"env": "DEFAULT_AI_MODEL"},
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v):
        """Validate secret key."""
        if not v:
            raise ValueError("Secret key must be set in production")
        if v == "dev-secret-key-for-development-only-change-in-production":
            raise ValueError("Secret key must be properly configured in production")
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v

    @field_validator("litellm_temperature")
    @classmethod
    def validate_temperature(cls, v):
        """Validate temperature range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8081",
        ]

    model_config = ConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
    )


_settings_instance = None


def get_settings() -> Settings:
    """Get application settings instance (singleton)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


# Global settings instance
settings = get_settings()
