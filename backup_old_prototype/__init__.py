"""
IngeTrazo Twinmotion LiveSync Extension Package
"""

import os
import sys

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from igz_tm_sync import TMSyncTool, setup, teardown

__all__ = ["TMSyncTool", "setup", "teardown"]
