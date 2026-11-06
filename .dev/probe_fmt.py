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
wl = c.watch_list(page_size=3)
items = (wl.get("data") or {}).get("list") or []
print("watch-list keys:", json.dumps({k: v for k, v in (wl.get("data") or {}).items() if k != "list"}, ensure_ascii=False))
for it in items[:2]:
    print(json.dumps(it, ensure_ascii=False))
