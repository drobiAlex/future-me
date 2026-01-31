"""Onboarding tools for MCP server."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent
from pydantic import Field

from server.data.onboarding_state import (
    ONBOARDING_QUESTIONS,
    create_session,
    get_current_question,
    get_session,
    get_summary,
    get_answer_summary_text,
    record_answer,
)


def _onboarding_meta(session_id: Optional[str] = None) -> dict:
    """Meta for onboarding tools with optional session tracking."""
    meta = {
        "openai/toolInvocation/invoking": "Processing onboarding",
        "openai/toolInvocation/invoked": "Onboarding response ready",
    }
    if session_id:
        meta["openai/widgetSessionId"] = session_id
    return meta


def register_onboarding_tools(mcp: FastMCP) -> None:
    """Register onboarding tools with the MCP server."""

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
