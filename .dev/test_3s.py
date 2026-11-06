import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
TMP = HERE / "local_3s.json"
shutil.copy(HERE.parent / "local_watchlist.json", TMP)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()

T0 = time.monotonic()
orig = w._on_local_quotes


def hooked(quotes, error):
    prices = {k: (v or {}).get("price") for k, v in list(quotes.items())[:3]}
    print(f"{time.monotonic() - T0:5.1f}s quotes={len(quotes)} err={error!r} sample={prices}", flush=True)
    orig(quotes, error)


w.local_quotes_done.disconnect()
w.local_quotes_done.connect(hooked)
print("interval", w.refresh_timer.interval(), "| action", w.act_auto.text(), "|", w.act_auto.toolTip(), flush=True)


def done():
    print("paused", w.refresh_paused_until > time.monotonic(), "| status", w.status.text(), flush=True)
    os._exit(0)


QTimer.singleShot(40000, done)
app.exec()
