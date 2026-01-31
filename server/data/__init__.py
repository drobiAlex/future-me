"""Data and state management package."""

from server.data.state import get_goal, set_goal, clear_goal
from server.data.onboarding_state import (
    ONBOARDING_QUESTIONS,
    OnboardingState,
    create_session,
    get_session,
    get_current_question,
    record_answer,
    get_summary,
    get_answer_summary_text,
    clear_session,
)

__all__ = [
    # Goal state
    "get_goal",
    "set_goal",
    "clear_goal",
    # Onboarding state
    "ONBOARDING_QUESTIONS",
    "OnboardingState",
    "create_session",
    "get_session",
    "get_current_question",
    "record_answer",
    "get_summary",
    "get_answer_summary_text",
    "clear_session",
]
