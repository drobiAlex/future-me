import time
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent

from server.state import clear_goal, get_goal, set_goal

WIDGET_DIR = Path(__file__).resolve().parent.parent / "public"
TEMPLATE_URI = "ui://widget/calendar-widget.html"


@lru_cache(maxsize=1)
def _calendar_html() -> str:
    return (WIDGET_DIR / "calendar-widget.html").read_text(encoding="utf-8")


def _widget_meta():
    return {
        "openai/outputTemplate": TEMPLATE_URI,
        "openai/toolInvocation/invoking": "Setting goal",
        "openai/toolInvocation/invoked": "Goal set",
    }


def _reply_with_goal(message: str | None = None) -> CallToolResult:
    content = [TextContent(type="text", text=message)] if message else []
    return CallToolResult(
        content=content,
        structuredContent={"goal": get_goal()},
        _meta=_widget_meta(),
    )


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def create_mcp_server() -> FastMCP:
    # mcp = FastMCP("todo-app", stateless_http=True)
    mcp = FastMCP(
        name="chatgpt-apps-sdk-demo",
        stateless_http=True,
        # Disable DNS rebinding protection for development with ngrok
        # The MCP SDK doesn't support subdomain wildcards (*.ngrok-free.app),
        # only port wildcards (host:*), so we disable protection entirely
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    @mcp.resource(
        TEMPLATE_URI,
        name="calendar-widget",
        mime_type="text/html+skybridge",
    )
    def calendar_widget() -> str:
        return _calendar_html()

    @mcp.tool(
        name="set_goal",
        description="Sets a goal with a title, optional start date, and target date for countdown tracking. Start date defaults to today if not provided.",
        meta=_widget_meta(),
    )
    def tool_set_goal(
        title: str, targetDate: str, startDate: str | None = None
    ) -> CallToolResult:
        title = title.strip()
        if not title:
            return _reply_with_goal("Missing goal title.")
        if not targetDate:
            return _reply_with_goal("Missing target date.")

        today = date.today()
        start = _parse_date(startDate) if startDate else today
        target = _parse_date(targetDate)

        if target <= start:
            return _reply_with_goal("Target date must be after start date.")

        goal = {
            "id": f"goal-{int(time.time() * 1000)}",
            "title": title,
            "startDate": start.isoformat(),
            "targetDate": targetDate,
        }
        set_goal(goal)

        days_until = (target - today).days
        total_days = (target - start).days
        return _reply_with_goal(
            f'Goal "{title}" set! {total_days} day journey, {days_until} days remaining.'
        )

    @mcp.tool(
        name="clear_goal",
        description="Clears the current goal.",
        meta={
            "openai/outputTemplate": TEMPLATE_URI,
            "openai/toolInvocation/invoking": "Clearing goal",
            "openai/toolInvocation/invoked": "Goal cleared",
        },
    )
    def tool_clear_goal() -> CallToolResult:
        current = clear_goal()
        if not current:
            return _reply_with_goal("No goal to clear.")
        return _reply_with_goal(f'Goal "{current["title"]}" cleared.')

    return mcp
