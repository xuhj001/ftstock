import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import QEvent, QPointF, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QMouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
TMP = HERE / "local_drag2.json"
for p in (TMP, TMP.with_name(TMP.name + ".bak")):
    p.unlink(missing_ok=True)
shutil.copy(HERE.parent / "local_watchlist.json", TMP)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.resize(1440, 900)
w.show()

pushes = []
orig_push = w._push_local
w._push_local = lambda: (pushes.append(1), orig_push())

ROWS = """JSON.stringify([...document.querySelectorAll('section.watchlist-modal .list > .list-item')].map(r => {
  const b = r.getBoundingClientRect();
  return {code: r.querySelector('.code').textContent.trim(), x: b.left + 100, y: b.top + b.height / 2};
}))"""


def mouse(kind, x, y):
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease}[kind]
    button = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.NoButton if kind == "release" else Qt.MouseButton.LeftButton
    pos = QPointF(x, y)
    tgt = w.watch_view.focusProxy()
    QApplication.sendEvent(tgt, QMouseEvent(t, pos, tgt.mapToGlobal(pos), button, held, Qt.KeyboardModifier.NoModifier))


def start(raw):
    r = json.loads(raw)
    before = [x["code"] for x in r]
    a, b = r[4], r[1]
    mouse("press", a["x"], a["y"])
    for k in range(1, 11):
        mouse("move", a["x"], a["y"] + (b["y"] - 20 - a["y"]) * k / 10)
    n0 = len(pushes)
    QTimer.singleShot(1000, lambda: w.grab().save(str(HERE / "drag_mid.png")))

    def release():
        mouse("release", a["x"], b["y"] - 20)
        QTimer.singleShot(800, lambda: w.watch_view.page().runJavaScript(ROWS, 0, lambda raw2: finish(before, raw2, n0)))
    QTimer.singleShot(7000, release)


def finish(before, raw, n0):
    after = [x["code"] for x in json.loads(raw)]
    want = before[:1] + before[4:5] + before[1:4] + before[5:]
    file_codes = [e["stockCode"] for e in json.loads(TMP.read_text(encoding="utf-8"))]
    print("pushes during hold:", len(pushes) - n0, flush=True)
    print("PASS" if after == want == file_codes else "FAIL", after[:6], file_codes[:6], flush=True)
    os._exit(0)


QTimer.singleShot(18000, lambda: w.watch_view.page().runJavaScript(ROWS, 0, start))
QTimer.singleShot(45000, lambda: (print("TIMEOUT", flush=True), os._exit(1)))
app.exec()
