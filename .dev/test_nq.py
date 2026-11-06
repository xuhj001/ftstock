import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
TMP = HERE / "local_default.json"
TMP.unlink(missing_ok=True)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
wv, dv = w.watch_view, w.detail_view

LEFT = """JSON.stringify([...document.querySelectorAll('section.watchlist-modal .list-item')].map(r=>r.innerText.replace(/\\n/g,' ')))"""
RIGHT = """JSON.stringify({path:location.pathname,title:document.title,
 h:(document.querySelector('h1, .stock-name, .name')||{}).innerText,
 p:(document.querySelector('[class*=price]')||{}).innerText})"""


def report(tag):
    w.grab().save(str(HERE / f"nq_{tag}.png"))
    print(tag, "| code", w.code, "| reload url", w._detail_url(), "| status", w.status.text(), flush=True)
    wv.page().runJavaScript(LEFT, 0, lambda r: print("   left:", r, flush=True))
    dv.page().runJavaScript(RIGHT, 0, lambda r: print("   right:", r, flush=True))


def click_left(code):
    js = ("(function(){var r=[...document.querySelectorAll('section.watchlist-modal .list-item')]"
          ".find(r=>r.querySelector('.col.name').innerText.split('\\n')[0].trim()==%s);if(!r)return null;"
          "var b=r.querySelector('.col.name').getBoundingClientRect();"
          "return JSON.stringify([b.left+b.width/2,b.top+b.height/2]);})()") % json.dumps(code)

    def do(raw):
        if not raw:
            print("NOT FOUND", code, flush=True)
            return
        x, y = json.loads(raw)
        QTest.mouseClick(wv.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked", code, flush=True)

    wv.page().runJavaScript(js, 0, do)


QTimer.singleShot(16000, lambda: report("a_start"))
QTimer.singleShot(17000, lambda: click_left("NQmain"))
QTimer.singleShot(26000, lambda: report("b_nq"))
QTimer.singleShot(27000, lambda: click_left("MSFT"))
QTimer.singleShot(34000, lambda: report("c_msft"))
QTimer.singleShot(35000, lambda: os._exit(0))
app.exec()
