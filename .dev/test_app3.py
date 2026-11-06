import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

OUT = Path(__file__).with_name("shots")
OUT.mkdir(exist_ok=True)
futu_app.PROFILE_DIR = Path(__file__).with_name("qt_profile_test3")

app = QApplication(sys.argv)
prof = futu_app.create_profile(app)
prof.setHttpUserAgent(prof.httpUserAgent().replace('Chrome/140.0.0.0', 'Chrome/148.0.0.0'))
w = futu_app.MainWindow(prof, 'TSLA-US')
w.login_prompted = True
w.show()
print("UA:", w.profile.httpUserAgent(), flush=True)
w.api_done.connect(lambda r, _: print("API:", str(r)[:600], flush=True))


def shot(name):
    w.grab().save(str(OUT / f"{name}.png"))
    print(name, w.view.url().toString()[:100], w.state, flush=True)


QTimer.singleShot(14000, lambda: shot("v148_2_watchlist"))
QTimer.singleShot(15000, lambda: w.page.runJavaScript(
    "var r=document.querySelectorAll('section.watchlist-modal .list-item');r.length>2&&r[2].click()"))
QTimer.singleShot(22000, lambda: shot("v148_3_detail"))
QTimer.singleShot(23000, lambda: w.verify_with_token(False))
QTimer.singleShot(29000, lambda: (shot("v148_4_after_api"), app.quit()))
app.exec()

