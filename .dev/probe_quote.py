import json
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from futu_api import FutuClient  # noqa: E402

HERE = Path(__file__).parent
jar = futu_app.read_profile_cookies(HERE / "qt_profile_minute" / "storage" / "Cookies")
cookies = {n: v for (d, n), v in jar.items() if d == "futunn.com"}
cookies.update({n: v for (d, n), v in jar.items() if d == "www.futunn.com"})
c = FutuClient(cookies, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QtWebEngine/6.11 FutuWatchlist/1.0")

T = {"stockId": "201335", "marketType": 2}
for params in (
    {**T, "instrumentType": 3},
    {**T, "instrumentType": 3, "subInstrumentType": 3002},
    {**T, "marketCode": 11, "instrumentType": 3},
    {**T, "marketCode": 11, "instrumentType": 3, "subInstrumentType": 3002},
    {**T, "marketCode": 11, "lotSize": 1, "spreadCode": 45, "underlyingStockId": 0, "instrumentType": 3,
     "subInstrumentType": 3002},
    {"stockId": "54047868453564", "marketType": 1, "instrumentType": 3, "subInstrumentType": 3002},
):
    res = c.get("/get-stock-quote", params)
    d = res.get("data") or {}
    print(params, "->", res.get("code"), res.get("message"),
          {k: d.get(k) for k in ("price", "priceNominal", "change", "changeRatio", "volume", "delayTime", "priceDirect")},
          "keys:", len(d))
