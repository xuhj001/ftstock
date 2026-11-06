import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "shots_local"
OUT.mkdir(exist_ok=True)
for f in OUT.glob("*.png"):
    f.unlink()
TMP = HERE / "local_test.json"
TMP.unlink(missing_ok=True)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)
futu_app.QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
wv = w.watch_view
_msg = w.statusBar().showMessage
w.statusBar().showMessage = lambda m, t=0: (print("STATUS", m, flush=True), _msg(m, t))[1]

INFO = """JSON.stringify({head:(document.querySelector('section.watchlist-modal .header h3')||{}).dataset,
rows:[...document.querySelectorAll('section.watchlist-modal .list-item')].map(r=>r.innerText.replace(/\\n/g,' ')),
empty:document.documentElement.classList.contains('fa-local-empty')})"""


def report(tag):
    w.grab().save(str(OUT / f"{tag}.png"))
    print(tag, "| mode", w.left_mode, "| entries", [e["stockCode"] for e in w.local.entries],
          "| right", w.detail_view.url().path(), "| status", w.status.text(), flush=True)
    wv.page().runJavaScript(INFO, 0, lambda r: print("   left:", r, flush=True))


def add(code):
    w.local_input.setText(code)
    w._add_local_input()


def click_left(code, col="name"):
    js = ("(function(){var r=[...document.querySelectorAll('section.watchlist-modal .list-item')]"
          ".find(r=>r.querySelector('.col.name').innerText.split('\\n')[0].trim()==%s);if(!r)return null;"
          "var e=r.querySelector('.col.%s');var b=e.getBoundingClientRect();"
          "return JSON.stringify([b.left+b.width/2,b.top+b.height/2]);})()") % (json.dumps(code), col)

    def do(raw):
        if not raw:
            print("NOT FOUND", code, col, flush=True)
            return
        x, y = json.loads(raw)
        QTest.mouseClick(wv.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked", code, col, flush=True)

    wv.page().runJavaScript(js, 0, do)


steps = [
    (11000, lambda: w.toggle_left("local")),
    (13000, lambda: report("0_empty")),
    (14000, lambda: add("TSLA")),
    (16000, lambda: add("00700")),
    (18000, lambda: add("KO")),
    (20000, lambda: add("600519")),
    (22000, lambda: add("NOSUCHXX")),
    (30000, lambda: report("1_local")),
    (31000, lambda: click_left("KO")),
    (38000, lambda: report("2_click_ko")),
    (39000, lambda: click_left("600519", "watchlist")),
    (42000, lambda: report("3_removed")),
    (43000, lambda: w.toggle_left("site")),
    (50000, lambda: report("4_site")),
    (51000, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
