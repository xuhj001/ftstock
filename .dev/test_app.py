import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

OUT = Path(__file__).with_name("shots")
OUT.mkdir(exist_ok=True)
futu_app.PROFILE_DIR = Path(__file__).with_name("qt_profile_test")

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "TSLA-US")
w.show()
w.api_done.connect(lambda r, _: print("API:", {k: (str(v)[:300]) for k, v in r.items()}, flush=True))


def shot(name):
    w.grab().save(str(OUT / f"{name}.png"))
    print(name, w.view.url().toString()[:120], w.state, flush=True)


def step(t, fn):
    QTimer.singleShot(t, fn)


step(12000, lambda: shot("1_login"))
step(13000, w.show_watchlist)
step(26000, lambda: shot("2_watchlist"))
step(27000, lambda: w.page.runJavaScript(
    "document.querySelector('section.watchlist-modal .list-item:nth-child(4)').click()"))
step(33000, lambda: shot("3_detail"))
step(34000, lambda: w.verify_with_token(False))
step(40000, lambda: (shot("4_after_api"), app.quit()))
app.exec()

