import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

futu_app.PROFILE_DIR = Path(__file__).with_name(sys.argv[1])
app = QApplication(sys.argv)
prof = futu_app.create_profile(app)
seen = []
prof.cookieStore().cookieAdded.connect(lambda c: seen.append((c.domain(), bytes(c.name()).decode())))
from PyQt6.QtWebEngineCore import QWebEnginePage
pg = QWebEnginePage(prof)
prof.cookieStore().loadAllCookies()
QTimer.singleShot(3000, lambda: (print(len(seen), sorted(set(seen))), app.quit()))
app.exec()

