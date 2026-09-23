"""
Where things live on disk, all anchored to the backend folder.
"""

from pathlib import Path

# This file sits directly in backend/, so its folder is the backend folder.
BACKEND_DIR = Path(__file__).resolve().parent
