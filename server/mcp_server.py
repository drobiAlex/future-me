"""Goal tracking MCP server with widget UI support for ChatGPT Apps SDK.

This server exposes tools for setting and clearing goals, returning a calendar
widget UI that renders inline in ChatGPT conversations.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from pydantic import Field

from server.state import clear_goal as do_clear_goal
from server.state import get_goal
from server.state import set_goal as do_set_goal
from server.onboarding_state import (
    ONBOARDING_QUESTIONS,
    create_session,
    get_session,
    get_current_question,
    record_answer,
    get_summary,
    get_answer_summary_text,
)

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


def _split_env_list(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _transport_security_settings() -> TransportSecuritySettings:
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
    """Create and configure the MCP server with goal tracking tools."""
    mcp = FastMCP(
        name="chatgpt-apps-sdk-demo",
        stateless_http=True,
        transport_security=_transport_security_settings(),
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

    # --- Onboarding Tools ---

    def _onboarding_meta(session_id: Optional[str] = None):
        """Meta for onboarding tools with optional session tracking."""
        meta = {
            "openai/toolInvocation/invoking": "Processing onboarding",
            "openai/toolInvocation/invoked": "Onboarding response ready",
        }
        if session_id:
            meta["openai/widgetSessionId"] = session_id
        return meta

    @mcp.tool()
    async def start_onboarding() -> CallToolResult:
        """Starts the onboarding questionnaire to learn about your goal-setting preferences.

        This begins a 3-question Y/N questionnaire that helps understand how you
        prefer to set and track goals. After completing all questions, you'll
        receive a personalized summary and recommendations.
        """
        session = create_session()
        first_question = get_current_question(session)

        message = (
            "Welcome! Let's learn about your goal-setting style.\n\n"
            f"Question 1/{len(ONBOARDING_QUESTIONS)}: {first_question}\n\n"
            "Please answer Y (Yes) or N (No)."
        )

        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            structuredContent={
                "sessionId": session.session_id,
                "currentQuestion": session.current_question + 1,
                "totalQuestions": len(ONBOARDING_QUESTIONS),
                "questionText": first_question,
                "completed": False,
            },
            _meta=_onboarding_meta(session.session_id),
        )

    @mcp.tool()
    async def answer_onboarding(
        answer: bool = Field(
            ...,
            description="The user's answer: true for Yes (Y), false for No (N).",
        ),
        session_id: str = Field(
            ...,
            description="The onboarding session ID from the previous response.",
        ),
    ) -> CallToolResult:
        """Records an answer to the current onboarding question and returns the next question or final summary.

        Call this tool when the user answers Y/N to an onboarding question.
        After all 3 questions are answered, returns a personalized goal-setting profile.
        """
        session = get_session(session_id)
        if session is None:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="Session not found. Please start onboarding again.",
                    )
                ],
                structuredContent={"error": "Session not found"},
                isError=True,
            )

        if session.completed:
            summary = get_summary(session)
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Onboarding already completed. Your profile: {summary['profile']}",
                    )
                ],
                structuredContent={
                    "sessionId": session.session_id,
                    "completed": True,
                    "profile": summary,
                },
                _meta=_onboarding_meta(session.session_id),
            )

        # Record the answer and advance
        updated_session = record_answer(session_id, answer)
        if updated_session is None:
            return CallToolResult(
                content=[TextContent(type="text", text="Failed to record answer.")],
                structuredContent={"error": "Failed to record answer"},
                isError=True,
            )

        # Check if onboarding is now complete
        if updated_session.completed:
            summary = get_summary(updated_session)
            answer_text = get_answer_summary_text(updated_session)

            message = (
                f"Onboarding complete! Your goal-setting profile: **{summary['profile']}**\n\n"
                f"{summary['description']}\n\n"
                f"Based on your answers:\n{answer_text}\n\n"
                f"**Recommendation:** {summary['recommendation']}"
            )

            return CallToolResult(
                content=[TextContent(type="text", text=message)],
                structuredContent={
                    "sessionId": updated_session.session_id,
                    "completed": True,
                    "answers": updated_session.answers,
                    "profile": summary,
                },
                _meta=_onboarding_meta(updated_session.session_id),
            )

        # Return the next question
        next_question = get_current_question(updated_session)
        question_num = updated_session.current_question + 1

        message = (
            f"Question {question_num}/{len(ONBOARDING_QUESTIONS)}: {next_question}\n\n"
            "Please answer Y (Yes) or N (No)."
        )

        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            structuredContent={
                "sessionId": updated_session.session_id,
                "currentQuestion": question_num,
                "totalQuestions": len(ONBOARDING_QUESTIONS),
                "questionText": next_question,
                "completed": False,
                "answersGiven": len(updated_session.answers),
            },
            _meta=_onboarding_meta(updated_session.session_id),
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
