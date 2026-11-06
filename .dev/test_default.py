import os
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
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

INFO = """JSON.stringify({title:(document.querySelector('section.watchlist-modal .header h3')||{}).dataset,
rows:[...document.querySelectorAll('section.watchlist-modal .list-item')].map(r=>r.innerText.replace(/\\n/g,' '))})"""


def report(tag):
    w.grab().save(str(HERE / f"default_{tag}.png"))
    acts = [(a.text(), a.isChecked()) for a in w.findChildren(futu_app.QToolBar)[0].actions() if a.text()]
    print(tag, "| mode", w.left_mode, "| file", TMP.exists(), "| actions", acts, "| status", w.status.text(), flush=True)
    w.watch_view.page().runJavaScript(INFO, 0, lambda r: print("   left:", r, flush=True))


QTimer.singleShot(16000, lambda: report("a"))
QTimer.singleShot(24000, lambda: report("b"))
QTimer.singleShot(25000, lambda: os._exit(0))
app.exec()
