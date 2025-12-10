"""
Pytest configuration for Goldflipper test suite.

This conftest.py ensures proper imports by adding the project root to sys.path
before any tests run.
"""
import os
import sys

# Add project root to path before any goldflipper imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Fixtures can be added here as needed
