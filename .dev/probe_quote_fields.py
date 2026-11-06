import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from futu_api import FutuClient  # noqa: E402

jar = futu_app.read_profile_cookies(futu_app.PROFILE_DIR / "storage" / "Cookies")
cookies = {n: v for (d, n), v in jar.items() if d == "futunn.com"}
cookies.update({n: v for (d, n), v in jar.items() if d == "www.futunn.com"})
from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication(sys.argv)
c = FutuClient(cookies, futu_app.create_profile(app).httpUserAgent())
q = c.stock_quote("205189", 2, 3)
print("quote keys:", json.dumps(q, ensure_ascii=False)[:1500])
print("infos:", json.dumps(c.stock_infos(["205189", "70000944"]), ensure_ascii=False)[:1500])
print("search:", json.dumps(c.search("NQmain")[:2], ensure_ascii=False)[:800])
