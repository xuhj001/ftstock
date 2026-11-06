import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "shots_pages"
OUT.mkdir(exist_ok=True)
TMP = HERE / "local_default.json"
TMP.unlink(missing_ok=True)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
wv, dv = w.watch_view, w.detail_view


def report(tag):
    w.grab().save(str(OUT / f"peek_{tag}.png"))
    print(f"{tag:8s} box={w.watch_box.isVisible()}:{w.watch_box.width()} view={wv.width()} "
          f"detail={dv.isVisible()}:{dv.width()} blank={w.blank.isVisible()}:{w.blank.width()} "
          f"nameRight={w.states['watch'].get('nameRight')}", flush=True)
    wv.page().runJavaScript("innerWidth", 0, lambda r: print("   page innerWidth:", r, flush=True))


def click_left(code):
    js = ("(function(){var r=[...document.querySelectorAll('section.watchlist-modal .list-item')]"
          ".find(r=>r.querySelector('.col.name').innerText.split('\\n')[0].trim()==%s);if(!r)return null;"
          "var b=r.querySelector('.col.name').getBoundingClientRect();"
          "return JSON.stringify([b.left+30,b.top+b.height/2]);})()") % json.dumps(code)

    def do(raw):
        if raw:
            x, y = json.loads(raw)
            QTest.mouseClick(wv.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                             QPoint(int(x), int(y)))
        print("clicked", code, bool(raw), flush=True)

    wv.page().runJavaScript(js, 0, do)


steps = [
    (15000, lambda: report("list")),
    (16000, lambda: click_left("MSFT")),
    (22000, lambda: report("detail")),
    (23000, lambda: w.act_local.trigger()),
    (25000, lambda: report("closed")),
    (29000, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
