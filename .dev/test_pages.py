import json
import os
import shutil
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
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
TMP = HERE / "local_default.json"
TMP.unlink(missing_ok=True)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
wv, dv = w.watch_view, w.detail_view
_msg = w.statusBar().showMessage
w.statusBar().showMessage = lambda m, t=0: (print("STATUS", m, flush=True), _msg(m, t))[1]
LEFT = """JSON.stringify([...document.querySelectorAll('section.watchlist-modal .list-item')].slice(0,3).map(r=>r.innerText.replace(/\\n/g,' ')))"""
for t in (12000, 14000):
    QTimer.singleShot(t, lambda t=t: wv.page().runJavaScript(LEFT, 0, lambda r, t=t: print(f"left@{t//1000}s", r, flush=True)))


def report(tag):
    w.grab().save(str(OUT / f"{tag}.png"))
    tabs = [a.text() for a in (w.act_local, w.act_watch, w.act_market) if a.isChecked()]
    print(f"{tag:12s} page={w.page:6s} tab={tabs} watch={wv.isVisible()}:{wv.width()} "
          f"detail={dv.isVisible()}:{dv.width()} blank={w.blank.isVisible()}:{w.blank.width()} "
          f"url={dv.url().path()} | {w.status.text()}", flush=True)


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


def click_market_row():
    js = ("(function(){var a=[...document.querySelectorAll('a[target=_blank]')].find(a=>/\\/stock\\//.test(a.href));"
          "if(!a)return null;a.click();return a.href;})()")
    dv.page().runJavaScript(js, 0, lambda r: print("market click", r, flush=True))


steps = [
    (16000, lambda: report("1_start")),
    (17000, lambda: click_left("MSFT")),
    (24000, lambda: report("2_local_msft")),
    (25000, lambda: w.act_watch.trigger()),
    (31000, lambda: report("3_site")),
    (32000, lambda: click_left("NVDA")),
    (39000, lambda: report("4_site_nvda")),
    (40000, lambda: w.act_market.trigger()),
    (50000, lambda: report("5_market")),
    (51000, click_market_row),
    (59000, lambda: report("6_market_stk")),
    (60000, lambda: w.act_local.trigger()),
    (63000, lambda: report("7_local")),
    (64000, lambda: click_left("AAPL")),
    (70000, lambda: report("8_local_aapl")),
    (71000, lambda: w.act_local.trigger()),
    (73000, lambda: report("9_close")),
    (74000, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
