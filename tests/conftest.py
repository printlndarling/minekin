"""Make the shared test helpers importable from every test directory.

`tests/session_support.py` and `tests/bridge_peer.py` are used from `unit/` and
`contract/` alike. Without this, each test would reach across directories on
pytest's collection-order sys.path, which works until the day the other
directory is not collected.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
