"""
Server module for remote mobile access.
"""

from .app import app
from .auth import auth_manager

__all__ = ["app", "auth_manager"]
