"""Goal tracking MCP server with widget UI support for ChatGPT Apps SDK.

This server exposes tools for setting and clearing goals, returning a calendar
widget UI that renders inline in ChatGPT conversations.
"""

from __future__ import annotations

import time
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from pydantic import Field

from server.state import clear_goal as do_clear_goal
from server.state import get_goal
from server.state import set_goal as do_set_goal

# Widget configuration
WIDGET_DIR = Path(__file__).resolve().parent.parent / "public"
TEMPLATE_URI = "ui://widget/calendar-widget.html"
MIME_TYPE = "text/html+skybridge"


@lru_cache(maxsize=1)
def _load_widget_html() -> str:
    """Load and cache the calendar widget HTML."""
    return (WIDGET_DIR / "calendar-widget.html").read_text(encoding="utf-8")


def _widget_meta():
    """Standard meta for widget-backed tools (used in tool listing and results)."""
    return {
        "openai/outputTemplate": TEMPLATE_URI,
        "openai/toolInvocation/invoking": "Preparing widget",
        "openai/toolInvocation/invoked": "Widget rendered",
        "openai/widgetAccessible": True,
    }


def _parse_date(s: str) -> date:
    """Parse ISO date string to date object."""
    return datetime.strptime(s, "%Y-%m-%d").date()


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with goal tracking tools."""
    mcp = FastMCP(
        name="chatgpt-apps-sdk-demo",
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    # Register the widget resource
    @mcp.resource(TEMPLATE_URI, name="Goal countdown widget", mime_type=MIME_TYPE)
    async def calendar_widget() -> str:
        return _load_widget_html()

    # Register tools
    @mcp.tool(meta=_widget_meta())
    async def set_goal(
        title: str = Field(..., description="The title/name of the goal to track."),
        targetDate: str = Field(
            ..., description="The target date for the goal in YYYY-MM-DD format."
        ),
        startDate: Optional[str] = Field(
            default=None,
            description="Optional start date in YYYY-MM-DD format. Defaults to today.",
        ),
    ) -> CallToolResult:
        """Sets a goal with a title, optional start date, and target date for countdown tracking."""
        title_clean = title.strip()
        if not title_clean:
            return _error_result("Missing goal title.")
        if not targetDate:
            return _error_result("Missing target date.")

        try:
            today = date.today()
            start = _parse_date(startDate) if startDate else today
            target = _parse_date(targetDate)
        except ValueError as e:
            return _error_result(f"Invalid date format: {e}")

        if target <= start:
            return _error_result("Target date must be after start date.")

        # Create and store the goal
        goal = {
            "id": f"goal-{int(time.time() * 1000)}",
            "title": title_clean,
            "startDate": start.isoformat(),
            "targetDate": targetDate,
        }
        do_set_goal(goal)

        days_until = (target - today).days
        total_days = (target - start).days
        message = f'Goal "{title_clean}" set! {total_days} day journey, {days_until} days remaining.'

        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            structuredContent={"goal": get_goal()},
            _meta=_widget_meta(),
        )

    @mcp.tool(meta=_widget_meta())
    async def clear_goal() -> CallToolResult:
        """Clears the current goal."""
        current = do_clear_goal()

        if not current:
            message = "No goal to clear."
        else:
            message = f'Goal "{current["title"]}" cleared.'

        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            structuredContent={"goal": get_goal()},
            _meta=_widget_meta(),
        )

    return mcp


def _error_result(message: str) -> CallToolResult:
    """Return an error result with the current goal state."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structuredContent={"goal": get_goal()},
        _meta=_widget_meta(),
        isError=True,
    )
