"""Goal tracking tools for MCP server."""

from __future__ import annotations

import time
from datetime import date, datetime
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent
from pydantic import Field

from server.data.state import clear_goal as do_clear_goal
from server.data.state import get_goal
from server.data.state import set_goal as do_set_goal
from server.resources.templates import widget_meta


def _parse_date(s: str) -> date:
    """Parse ISO date string to date object."""
    return datetime.strptime(s, "%Y-%m-%d").date()


def _error_result(message: str) -> CallToolResult:
    """Return an error result with the current goal state."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structuredContent={"goal": get_goal()},
        _meta=widget_meta(),
        isError=True,
    )


def register_goal_tools(mcp: FastMCP) -> None:
    """Register goal tracking tools with the MCP server."""

    @mcp.tool(meta=widget_meta())
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
            _meta=widget_meta(),
        )

    @mcp.tool(meta=widget_meta())
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
            _meta=widget_meta(),
        )
