import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
_op = futu_app.MainWindow.open_path
futu_app.MainWindow.open_path = lambda self, p, item=None: (
    print("open_path", p, "item:", bool(item), flush=True), _op(self, p, item))[1]

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
wv = w.watch_view


def report(tag):
    print(tag, "| left:", wv.url().path(), w.states["watch"].get("watch"), "| right:", w.detail_view.url().path(),
          "| market checked:", w.act_market.isChecked(), "| status:", w.status.text(), flush=True)
    w.grab().save(str(HERE / f"toolbar_{tag}.png"))


def click_row():
    js = ("(function(){var e=document.querySelectorAll('section.watchlist-modal .list-item .col.name')[2];"
          "if(!e)return null;var r=e.getBoundingClientRect();"
          "return JSON.stringify([r.left+r.width/2,r.top+r.height/2,e.innerText]);})()")

    def do(raw):
        if not raw:
            print("ROW NOT FOUND", flush=True)
            return
        x, y, text = json.loads(raw)
        QTest.mouseClick(wv.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked left row", text.replace("\n", " "), flush=True)

    wv.page().runJavaScript(js, 0, do)


steps = [
    (3000, w.act_market.trigger),
    (16000, lambda: report("both")),
    (16500, click_row),
    (20000, lambda: report("after_click")),
    (20500, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
