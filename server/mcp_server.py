"""Goal tracking MCP server with widget UI support for ChatGPT Apps SDK.

This server exposes tools for setting and clearing goals, returning a calendar
widget UI that renders inline in ChatGPT conversations.
"""

from __future__ import annotations

import os
from typing import List

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from server.resources.templates import register_resources
from server.tools.goals import register_goal_tools
from server.tools.onboarding import register_onboarding_tools


def _split_env_list(value: str | None) -> List[str]:
    """Split comma-separated environment variable into list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _transport_security_settings() -> TransportSecuritySettings:
    """Configure transport security based on environment variables."""
    allowed_hosts = _split_env_list(os.getenv("MCP_ALLOWED_HOSTS"))
    allowed_origins = _split_env_list(os.getenv("MCP_ALLOWED_ORIGINS"))
    if not allowed_hosts and not allowed_origins:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with all tools and resources."""
    mcp = FastMCP(
        name="chatgpt-apps-sdk-demo",
        stateless_http=True,
        transport_security=_transport_security_settings(),
    )

    # Register all tools and resources
    register_resources(mcp)
    register_goal_tools(mcp)
    register_onboarding_tools(mcp)

    return mcp
