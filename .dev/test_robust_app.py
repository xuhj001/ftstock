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
TMP = HERE / "local_robust.json"
for p in (TMP, TMP.with_name(TMP.name + ".bak")):
    p.unlink(missing_ok=True)
shutil.copy(HERE.parent / "local_watchlist.json", TMP)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)
futu_app.log_uncaught_exceptions()

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.resize(1440, 900)
w.show()
w.act_auto.setChecked(False)
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
    if not ok:
        fails.append(name)


ROWS = """JSON.stringify([...document.querySelectorAll('section.watchlist-modal .list > .list-item')].map(r => {
  const b = r.getBoundingClientRect();
  return {code: r.querySelector('.code').textContent.trim(), price: r.querySelector('.col.price').textContent.trim(),
          x: b.left + 100, y: b.top + b.height / 2};
}))"""


def mouse(kind, x, y):
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease}[kind]
    button = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.NoButton if kind == "release" else Qt.MouseButton.LeftButton
    pos = QPointF(x, y)
    tgt = w.watch_view.focusProxy()
    QApplication.sendEvent(tgt, QMouseEvent(t, pos, tgt.mapToGlobal(pos), button, held, Qt.KeyboardModifier.NoModifier))


def rows(cb):
    w.watch_view.page().runJavaScript(ROWS, 0, lambda r: cb(json.loads(r)))


def step1(r):
    # 按下后不松开（模拟在窗口外松手、页面收不到 pointerup），然后推一次新行情
    mouse("press", r[0]["x"], r[0]["y"])
    first = w.local.entries[0]["stockId"]
    w.local_quotes[first] = {"price": "12345.678"}
    w._push_local()
    QTimer.singleShot(1200, lambda: rows(step2))


def step2(r):
    check("pressed-but-not-released does not freeze quotes", r[0]["price"] == "12345.678", r[0]["price"])
    # 页面发来坏消息：槽函数里抛异常，程序不能退出
    w.watch_view.page().runJavaScript("console.info('__FA_LOCAL_MOVE__{bad json')")
    QTimer.singleShot(800, lambda: rows(step3))


def step3(r):
    check("malformed message: app still alive", len(r) == len(w.local.entries))
    before = [x["code"] for x in r]
    a, b = r[0], r[2]
    mouse("press", a["x"], a["y"])
    for k in range(1, 11):
        mouse("move", a["x"], a["y"] + (b["y"] + 5 - a["y"]) * k / 10)
    mouse("release", a["x"], b["y"] + 5)
    QTimer.singleShot(800, lambda: rows(lambda r2: step4(before, r2)))


def step4(before, r):
    after = [x["code"] for x in r]
    want = before[1:3] + before[:1] + before[3:]
    saved = [e["stockCode"] for e in json.loads(TMP.read_text(encoding="utf-8"))]
    check("drag still works afterwards", after == want == saved, after[:4])
    print("ALL PASS" if not fails else f"FAILED: {fails}", flush=True)
    os._exit(0)


QTimer.singleShot(18000, lambda: rows(step1))
QTimer.singleShot(45000, lambda: (print("TIMEOUT", flush=True), os._exit(1)))
app.exec()
