"""WSGI entrypoint for Elastic Beanstalk and gunicorn."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

# Gunicorn and Elastic Beanstalk expect this name.
application = app
