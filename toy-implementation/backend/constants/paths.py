"""
Where things live on disk, all anchored to the backend folder.
"""

from pathlib import Path

# This file sits in backend/constants/, so two levels up is the backend folder.
BACKEND_DIR = Path(__file__).resolve().parent.parent
