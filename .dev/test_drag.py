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
TMP = HERE / "local_drag.json"
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
w.act_auto.setChecked(False)  # 少发请求

opened = []
w.open_path = lambda path, item=None: opened.append(path)
removed = []
w.remove_local = lambda sid: removed.append(sid)
warned = []
futu_app.QMessageBox.warning = staticmethod(lambda *a: warned.append(a[2]))

ROWS = """JSON.stringify([...document.querySelectorAll('section.watchlist-modal .list > .list-item')].map(r => {
  const b = r.getBoundingClientRect(), h = r.querySelector('.col.watchlist').getBoundingClientRect();
  return {code: r.querySelector('.code').textContent.trim(), x: b.left + 100, y: b.top + b.height / 2,
          hx: h.left + h.width / 2, t: r.style.transform};
}).concat([{list: document.querySelector('section.watchlist-modal .list').getBoundingClientRect().bottom,
            scroll: document.querySelector('section.watchlist-modal .list').scrollTop}]))"""

failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
    if not ok:
        failures.append(name)


def target():
    return w.watch_view.focusProxy()


def mouse(kind, x, y, buttons=Qt.MouseButton.LeftButton):
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease}[kind]
    button = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.NoButton if kind == "release" else buttons
    pos = QPointF(x, y)
    QApplication.sendEvent(target(), QMouseEvent(t, pos, target().mapToGlobal(pos), button, held,
                                                 Qt.KeyboardModifier.NoModifier))


def rows(cb):
    w.watch_view.page().runJavaScript(ROWS, 0, lambda r: cb(json.loads(r)))


def file_codes():
    return [e["stockCode"] for e in json.loads(TMP.read_text(encoding="utf-8"))]


def gesture(points, hold_ms, done):
    """points: [(x, y)]，第一个按下，最后一个松开；每步间隔 30ms，松开前停 hold_ms"""
    steps = [lambda p=points[0]: mouse("press", *p)]
    steps += [lambda p=p: mouse("move", *p) for p in points[1:]]
    seq = list(steps)

    def run(i=0):
        if i < len(seq):
            seq[i]()
            QTimer.singleShot(30, lambda: run(i + 1))
        else:
            QTimer.singleShot(hold_ms, lambda: (mouse("release", *points[-1]), QTimer.singleShot(800, done)))
    run()


def lerp(a, b, n):
    return [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]


state = {}


def step1(r):
    state["before"] = [x["code"] for x in r[:-1]]
    print("before", state["before"], flush=True)
    a, b = r[0], r[3]
    gesture(lerp((a["x"], a["y"]), (a["x"], b["y"] + 5), 12), 300, lambda: rows(step1_check))


def step1_check(r):
    after = [x["code"] for x in r[:-1]]
    want = state["before"][1:4] + state["before"][:1] + state["before"][4:]
    check("drag row 1 -> 4: page order", after == want, after[:6])
    check("drag row 1 -> 4: json order", file_codes() == want)
    check("drag row 1 -> 4: no detail opened", not opened, opened)
    check("no leftover transforms", all(not x["t"] for x in r[:-1]))
    state["order"] = after
    a = r[2]
    gesture([(a["x"], a["y"]), (a["x"] + 2, a["y"] + 2)], 50, lambda: rows(step2_check))


def step2_check(r):
    check("plain click opens detail", len(opened) == 1, opened)
    check("plain click keeps order", file_codes() == state["order"])
    a = r[1]
    gesture([(a["hx"], a["y"])] + [(a["hx"], a["y"] + 20 * k) for k in range(1, 6)], 50, lambda: rows(step3_check))


def step3_check(r):
    check("drag on heart does not reorder", file_codes() == state["order"])
    a, bottom = r[1], r[-1]["list"]
    pts = lerp((a["x"], a["y"]), (a["x"], bottom - 10), 15)
    gesture(pts, 3000, lambda: rows(step4_check))


def step4_check(r):
    after = [x["code"] for x in r[:-1]]
    o = state["order"]
    want = o[:1] + o[2:] + o[1:2]
    check("auto-scroll drag to end: page order", after == want, f"scroll={r[-1]['scroll']} last={after[-1]}")
    check("auto-scroll drag to end: json order", file_codes() == want)
    check("bak matches", json.loads(TMP.with_name(TMP.name + ".bak").read_text(encoding="utf-8"))
          == json.loads(TMP.read_text(encoding="utf-8")))
    state["bytes"] = TMP.read_bytes()
    w.reorder_local(["bogus"])
    w.reorder_local("bogus")
    QTimer.singleShot(500, lambda: rows(step5_check))


def step5_check(r):
    check("bogus ids ignored, file unchanged", TMP.read_bytes() == state["bytes"]
          and file_codes() == [x["code"] for x in r[:-1]])
    check("malformed order warned once", len(warned) == 1, warned)
    edited = json.loads(TMP.read_text(encoding="utf-8"))[::-1]
    edited[0]["name"] = "手改名称"
    TMP.write_text(json.dumps(edited, ensure_ascii=False, indent=2), encoding="utf-8")
    state["edited"] = [e["stockCode"] for e in edited]
    QTimer.singleShot(2500, lambda: rows(step6_check))


def step6_check(r):
    check("external edit shown live", [x["code"] for x in r[:-1]] == state["edited"],
          w.statusBar().currentMessage())
    print("ALL PASS" if not failures else f"FAILED: {failures}", flush=True)
    os._exit(0)


QTimer.singleShot(18000, lambda: rows(step1))
QTimer.singleShot(60000, lambda: (print("TIMEOUT", flush=True), os._exit(1)))
app.exec()
