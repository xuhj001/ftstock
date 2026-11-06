import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from futu_api import FutuClient  # noqa: E402
from futu_app import APP_UA_TOKEN  # noqa: E402

ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) QtWebEngine/6.11 Safari/537.36 " + APP_UA_TOKEN
client = FutuClient({}, ua)
kw = sys.argv[1] if len(sys.argv) > 1 else "NQMAIN"
res = client.search(kw)
for q in res[:8]:
    print(json.dumps(q, ensure_ascii=False))
ids = [str(q["stockId"]) for q in res[:3] if q.get("stockId")]
if ids:
    for info in client.stock_infos(ids):
        print("INFO", json.dumps(info, ensure_ascii=False)[:600])
