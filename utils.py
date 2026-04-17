"""
utils.py — Party Riot Bot V2
Thin shim: re-exports shared helpers and model from main.py so games.py can import them.
Import this in games.py instead of importing from main directly.
"""

# This file is imported by games.py to avoid circular imports.
# All real definitions live in main.py; we lazily import them here.

import importlib

def __getattr__(name):
    main = importlib.import_module("main")
    return getattr(main, name)
