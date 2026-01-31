"""Middleware package for FastAPI application."""

from server.middleware.cors import add_cors

__all__ = ["add_cors"]
