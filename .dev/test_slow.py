"""关掉快速刷新后本地自选按 SLOW_REFRESH_S 刷新；为缩短测试把它改成 12 秒"""
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
TMP = HERE / "local_slow.json"
shutil.copy(HERE.parent / "local_watchlist.json", TMP)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.SLOW_REFRESH_S = 12
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()

T0 = time.monotonic()
starts: list[float] = []
orig_refresh = w._refresh_local_quotes


def counted():
    before = w.local_refreshed_at
    orig_refresh()
    if w.local_refreshed_at != before:
        starts.append(time.monotonic() - T0)
        print(f"{starts[-1]:5.1f}s refresh started (auto={w.act_auto.isChecked()})", flush=True)


w._refresh_local_quotes = counted
w.statusBar().messageChanged.connect(
    lambda m: m and print(f"{time.monotonic() - T0:5.1f}s status: {m}", flush=True))
print("tooltip:", w.act_auto.toolTip(), flush=True)


def switch_off():
    w.act_auto.setChecked(False)
    starts.clear()
    print(f"{time.monotonic() - T0:5.1f}s turned off", flush=True)


def done():
    print("debug: since last", round(time.monotonic() - w.local_refreshed_at, 1), "visible", w.watch_view.isVisible(), "busy", w.local_busy, "paused",
          w.refresh_paused_until > time.monotonic(), "timer", w.refresh_timer.isActive(), flush=True)
    gaps = [round(b - a, 1) for a, b in zip(starts, starts[1:])]
    print("starts while off:", [round(s, 1) for s in starts], "gaps:", gaps, flush=True)
    ok = len(starts) >= 2 and all(11 <= g <= 16 for g in gaps)
    print("PASS" if ok else "FAIL", flush=True)
    os._exit(0)


QTimer.singleShot(25000, switch_off)
QTimer.singleShot(60000, done)
app.exec()
