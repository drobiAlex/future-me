"""MCP resources package (widget HTML, templates).

This package contains resource registration and template utilities.
"""

from server.resources.templates import (
    CALENDAR_TEMPLATE_URI,
    MIME_TYPE,
    WIDGET_DIR,
    load_calendar_widget_html,
    register_resources,
    widget_meta,
)

__all__ = [
    "CALENDAR_TEMPLATE_URI",
    "MIME_TYPE",
    "WIDGET_DIR",
    "load_calendar_widget_html",
    "register_resources",
    "widget_meta",
]
