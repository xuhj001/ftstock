import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from futu_api import FutuClient  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

jar = futu_app.read_profile_cookies(futu_app.PROFILE_DIR / "storage" / "Cookies")
cookies = {n: v for (d, n), v in jar.items() if d == "futunn.com"}
cookies.update({n: v for (d, n), v in jar.items() if d == "www.futunn.com"})
app = QApplication(sys.argv)
c = FutuClient(cookies, futu_app.create_profile(app).httpUserAgent())
entries = json.loads((Path(__file__).resolve().parents[1] / "local_watchlist.json").read_text(encoding="utf-8"))
infos = {i["stock_id"]: i for i in c.stock_infos([e["stockId"] for e in entries])}
for e in entries:
    i = infos.get(e["stockId"])
    if not i:
        print("MISSING", e["stockCode"])
        continue
    print(f'{e["stockCode"]:7s}|{i["symbol"]:10s}|{i["stock_code"]:10s}|{i["market_type_label"]}| '
          f'{e["instrumentType"]}/{e["subInstrumentType"]} vs {i["instrument_type_v2"]}/{i["sub_instrument_type_v2"]} | '
          f'{e["name"]} || {i["sc_name"]}')
