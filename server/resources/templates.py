"""MCP resources for widget templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Widget configuration
WIDGET_DIR = Path(__file__).resolve().parent.parent.parent / "public"
CALENDAR_TEMPLATE_URI = "ui://widget/calendar-widget.html"
MIME_TYPE = "text/html+skybridge"


@lru_cache(maxsize=1)
def load_calendar_widget_html() -> str:
    """Load and cache the calendar widget HTML."""
    return (WIDGET_DIR / "calendar-widget.html").read_text(encoding="utf-8")


def widget_meta() -> dict:
    """Standard meta for widget-backed tools (used in tool listing and results)."""
    return {
        "openai/outputTemplate": CALENDAR_TEMPLATE_URI,
        "openai/toolInvocation/invoking": "Preparing widget",
        "openai/toolInvocation/invoked": "Widget rendered",
        "openai/widgetAccessible": True,
    }


def register_resources(mcp: FastMCP) -> None:
    """Register widget resources with the MCP server."""

    @mcp.resource(
        CALENDAR_TEMPLATE_URI,
        name="Goal countdown widget",
        mime_type=MIME_TYPE,
    )
    async def calendar_widget() -> str:
        """Returns the calendar widget HTML for goal tracking."""
        return load_calendar_widget_html()
