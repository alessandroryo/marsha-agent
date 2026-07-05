"""Put news_scout/ itself on sys.path so tests use the same flat imports
(`from models import ...`) that main.py uses when run directly via
`uv run --script main.py` -- mirrors production exactly instead of testing
a different import mode.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
