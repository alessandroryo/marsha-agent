"""Put fundamentals/ parent dir on sys.path so tests use the same flat
imports (`from fundamentals.core import ...`) that fundamentals-fetcher.py
and fundamentals_mcp.py use when run directly -- mirrors production.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
