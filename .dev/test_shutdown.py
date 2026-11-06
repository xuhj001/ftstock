"""正常关闭窗口时的退出顺序：看 Qt 有没有报「profile 先于 page 释放」之类的警告"""
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402

HERE = Path(__file__).parent
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(HERE / "local_shutdown.json")
sys.argv = [sys.argv[0]]
orig_init = futu_app.MainWindow.__init__


def init(self, *a, **kw):
    orig_init(self, *a, **kw)
    self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    QTimer.singleShot(15000, self.close)


futu_app.MainWindow.__init__ = init
futu_app.PROFILE_DIR.mkdir(exist_ok=True)
try:
    futu_app.main()
except SystemExit as e:
    print("exit code", e.code, flush=True)
print("returned from main", flush=True)
