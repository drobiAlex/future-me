"""MCP tools package.

This package contains modular tool registration functions for the MCP server.
Each module focuses on a specific domain of functionality.
"""

from server.tools.goals import register_goal_tools
from server.tools.onboarding import register_onboarding_tools

__all__ = [
    "register_goal_tools",
    "register_onboarding_tools",
]
