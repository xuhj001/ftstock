import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from futu_api import FutuClient  # noqa: E402

HERE = Path(__file__).parent
jar = futu_app.read_profile_cookies(HERE / "qt_profile_minute" / "storage" / "Cookies")
cookies = {n: v for (d, n), v in jar.items() if d == "futunn.com"}
cookies.update({n: v for (d, n), v in jar.items() if d == "www.futunn.com"})
c = FutuClient(cookies, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QtWebEngine/6.11 FutuWatchlist/1.0")


def predict(kw):
    url = "https://www.futunn.com/search-stock/predict?" + urllib.parse.urlencode(
        {"keyword": kw, "lang": "zh-cn", "site": "cn"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FutuProbe/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["data"]["quote"][0]


for kw, codes in (("KO", (11, 10, 12)), ("00700", (1, 2, 11))):
    q = predict(kw)
    print(kw, q)
    for mc in codes:
        res = c.get("/get-stock-quote", {"stockId": q["stockId"], "marketType": q["marketType"],
                                         "marketCode": mc, "instrumentType": 3})
        d = res.get("data") or {}
        print("  marketCode", mc, "->", res.get("code"), res.get("message", "")[:40],
              {k: d.get(k) for k in ("price", "change", "changeRatio", "volume", "delayTime", "marketCode",
                                     "stockStatus", "statusText")})
print("quote keys:", sorted(d.keys()))
