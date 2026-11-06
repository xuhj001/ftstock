import sys
from pathlib import Path

from PyQt6.QtCore import QLockFile

lock = QLockFile(str(Path(__file__).resolve().parents[1] / ".qt_profile" / "app.lock"))
print("second instance can lock:", lock.tryLock(100))
sys.exit(0)
