import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
TMP = HERE / "local_sync.json"
for p in (TMP, TMP.with_name(TMP.name + ".bak")):
    p.unlink(missing_ok=True)
entries = json.loads((HERE.parent / "local_watchlist.json").read_text(encoding="utf-8"))
real_aapl = next(e for e in entries if e["stockId"] == "205189")
stale = dict(real_aapl, stockCode="AAPLOLD", name="旧苹果")
entries = [stale if e["stockId"] == "205189" else e for e in entries]
TMP.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

shown, calls = [], []
futu_app.QMessageBox.information = staticmethod(lambda *a: shown.append(a[2]))
futu_app.QMessageBox.warning = staticmethod(lambda *a: shown.append("WARN " + a[2]))
real_infos = futu_app.FutuClient.stock_infos
futu_app.FutuClient.stock_infos = lambda self, ids: (calls.append(len(ids)), real_infos(self, ids))[1]

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
w.act_auto.setChecked(False)


def done():
    saved = {e["stockId"]: e for e in json.loads(TMP.read_text(encoding="utf-8"))}
    ok = saved["205189"] == real_aapl and len(saved) == len(entries)
    print("stock_infos calls:", calls, flush=True)
    print("dialog:", shown, flush=True)
    print("status:", w.statusBar().currentMessage(), flush=True)
    print("PASS AAPL restored from live data" if ok else f"FAIL {saved['205189']}", flush=True)
    os._exit(0)


QTimer.singleShot(25000, done)
app.exec()
