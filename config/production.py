"""Explicit settings entry point for Passenger/WSGI and release commands."""
import os

os.environ['DJANGO_ENV'] = 'production'
from .settings import *  # noqa: E402,F403
