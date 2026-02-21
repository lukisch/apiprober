"""python -m ApiProber"""
import sys
from pathlib import Path

# Package-Dir sicherstellen
PACKAGE_DIR = Path(__file__).resolve().parent
_parent = str(PACKAGE_DIR.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from ApiProber.api_prober import main

sys.exit(main())
