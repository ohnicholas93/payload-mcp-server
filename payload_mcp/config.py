"""
Configuration management for Payload CMS MCP Server.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class PayloadConfig(BaseModel):
    """Configuration for Payload CMS connection."""
    
    base_url: str = Field(
        default="http://localhost:3000/api",
        description="Base URL for Payload CMS API"
    )
    
    auth_token: Optional[str] = Field(
        default=None,
        description="JWT token for authentication"
    )
    
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )
    
    verify_ssl: bool = Field(
        default=False,
        description="Whether to verify SSL certificates"
    )
    
    bypass_proxy: bool = Field(
        default=True,
        description="Whether to bypass proxy for localhost connections"
    )


class ServerConfig(BaseSettings):
    """Server configuration for MCP server."""
    
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    payload: PayloadConfig = Field(
        default_factory=PayloadConfig,
        description="Payload CMS configuration"
    )
    
    class Config:
        env_prefix = "PAYLOAD_MCP_"
        env_nested_delimiter = "__"
        
    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables."""
        return cls(
            log_level=os.getenv("PAYLOAD_MCP_LOG_LEVEL", "INFO"),
            payload=PayloadConfig(
                base_url=os.getenv("PAYLOAD_MCP_PAYLOAD__BASE_URL", "http://localhost:3000/api"),
                auth_token=os.getenv("PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN"),
                timeout=int(os.getenv("PAYLOAD_MCP_PAYLOAD__TIMEOUT", "30")),
                verify_ssl=os.getenv("PAYLOAD_MCP_PAYLOAD__VERIFY_SSL", "false").lower() == "true",
                bypass_proxy=os.getenv("PAYLOAD_MCP_PAYLOAD__BYPASS_PROXY", "true").lower() == "true"
            )
        )