"""Context service configuration."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class ContextServiceConfig(BaseSettings):
    """Configuration for the Context Service."""
    
    model_config = ConfigDict(
        env_prefix="CONTEXT_SERVICE_",
        env_file=".env",
        extra="ignore",  # Ignore extra fields from .env
    )
    
    # Service settings
    host: str = "127.0.0.1"
    port: int = 8001
    
    # Default user for demo
    default_user_id: str = "user_test"


config = ContextServiceConfig()
