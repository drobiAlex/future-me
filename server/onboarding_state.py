"""Onboarding state management for goal-setting questionnaire.

This module manages the state for an onboarding flow where users answer 3 Y/N
questions about their goal-setting preferences. State is stored in-memory
and will be replaced with persistent storage later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import uuid4


# Onboarding questions (Y/N format)
ONBOARDING_QUESTIONS = [
    "Do you prefer focusing on daily goals rather than long-term goals?",
    "Do you work better when you have specific deadlines?",
    "Do you prefer tracking multiple goals at the same time?",
]


@dataclass
class OnboardingState:
    """Represents the state of an onboarding session."""

    session_id: str
    current_question: int = 0  # 0, 1, 2, or 3 (completed)
    answers: List[bool] = field(default_factory=list)  # Y=True, N=False
    completed: bool = False


# In-memory store for onboarding sessions
_sessions: Dict[str, OnboardingState] = {}


def create_session() -> OnboardingState:
    """Create a new onboarding session.

    Returns:
        A new OnboardingState with a unique session ID.
    """
    session_id = uuid4().hex
    session = OnboardingState(session_id=session_id)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Optional[OnboardingState]:
    """Get an existing onboarding session by ID.

    Args:
        session_id: The unique session identifier.

    Returns:
        The OnboardingState if found, None otherwise.
    """
    return _sessions.get(session_id)


def get_current_question(session: OnboardingState) -> Optional[str]:
    """Get the current question text for a session.

    Args:
        session: The onboarding session.

    Returns:
        The question text if there are remaining questions, None if completed.
    """
    if session.current_question >= len(ONBOARDING_QUESTIONS):
        return None
    return ONBOARDING_QUESTIONS[session.current_question]


def record_answer(session_id: str, answer: bool) -> Optional[OnboardingState]:
    """Record an answer for the current question and advance to the next.

    Args:
        session_id: The session to update.
        answer: True for Y, False for N.

    Returns:
        The updated OnboardingState, or None if session not found.
    """
    session = _sessions.get(session_id)
    if session is None:
        return None

    if session.completed:
        return session

    # Record the answer
    session.answers.append(answer)
    session.current_question += 1

    # Check if onboarding is complete
    if session.current_question >= len(ONBOARDING_QUESTIONS):
        session.completed = True

    return session


def get_summary(session: OnboardingState) -> Dict[str, str]:
    """Generate a personalized summary based on onboarding answers.

    Args:
        session: A completed onboarding session.

    Returns:
        A dictionary with 'profile', 'description', and 'recommendation'.
    """
    if not session.completed or len(session.answers) != 3:
        return {
            "profile": "Incomplete",
            "description": "Please complete all questions first.",
            "recommendation": "",
        }

    # Unpack answers: Q1=daily, Q2=deadlines, Q3=multi-goals
    daily, deadlines, multi = session.answers

    # Profile mapping based on answer combinations
    profiles = {
        (True, True, True): {
            "profile": "Sprint-focused Achiever",
            "description": "You thrive with daily deadlines and enjoy juggling multiple concurrent goals. You're energized by short-term wins.",
            "recommendation": "Set 2-3 daily goals with specific deadlines. Use a task board to visualize all active goals and celebrate small wins daily.",
        },
        (True, True, False): {
            "profile": "Focused Daily Planner",
            "description": "You work best tackling one goal at a time with clear daily deadlines. You value deep focus over breadth.",
            "recommendation": "Focus on a single important goal each day with a specific deadline. Complete it before moving to the next.",
        },
        (True, False, True): {
            "profile": "Flexible Multi-tasker",
            "description": "You prefer daily goals but without rigid deadlines. You enjoy variety and flexibility in your approach.",
            "recommendation": "Set 2-3 small daily goals and review progress weekly. Don't stress about exact completion times.",
        },
        (True, False, False): {
            "profile": "Day-by-day Achiever",
            "description": "You prefer a single daily focus with a flexible approach. You value simplicity and taking things one step at a time.",
            "recommendation": "Pick one meaningful goal each morning. Focus on progress, not perfection.",
        },
        (False, True, True): {
            "profile": "Strategic Project Manager",
            "description": "You excel at long-term planning with clear milestones while tracking multiple projects simultaneously.",
            "recommendation": "Create a roadmap with quarterly goals broken into monthly milestones. Use a project tracker for visibility.",
        },
        (False, True, False): {
            "profile": "Milestone-driven Achiever",
            "description": "You focus deeply on a single long-term goal with clear deadlines. You're driven by significant milestones.",
            "recommendation": "Set one major goal with a clear deadline. Break it into weekly milestones and track progress consistently.",
        },
        (False, False, True): {
            "profile": "Exploratory Goal-setter",
            "description": "You prefer flexibility with multiple long-term pursuits. You value exploration and gradual progress.",
            "recommendation": "Maintain 2-3 long-term goals and review monthly. Allow yourself to pivot as interests evolve.",
        },
        (False, False, False): {
            "profile": "Deep Focus Achiever",
            "description": "You work best with one long-term goal and a flexible timeline. You value depth over breadth.",
            "recommendation": "Choose one meaningful long-term goal. Focus on consistent progress without pressure from deadlines.",
        },
    }

    return profiles.get(
        (daily, deadlines, multi),
        {
            "profile": "Unique Achiever",
            "description": "Your goal-setting style is unique!",
            "recommendation": "Experiment with different approaches to find what works best for you.",
        },
    )


def get_answer_summary_text(session: OnboardingState) -> str:
    """Generate human-readable text summarizing the answers.

    Args:
        session: A completed onboarding session.

    Returns:
        A formatted string describing the user's answers.
    """
    if len(session.answers) != 3:
        return ""

    daily, deadlines, multi = session.answers

    lines = [
        f"- You {'prefer daily goals' if daily else 'prefer long-term goals'} over {'long-term planning' if daily else 'daily tasks'}",
        f"- You {'work better with' if deadlines else 'work better without'} strict deadlines",
        f"- You {'like tracking multiple goals' if multi else 'prefer focusing on one goal at a time'}",
    ]

    return "\n".join(lines)


def clear_session(session_id: str) -> Optional[OnboardingState]:
    """Remove a session from the store.

    Args:
        session_id: The session to remove.

    Returns:
        The removed session, or None if not found.
    """
    return _sessions.pop(session_id, None)
