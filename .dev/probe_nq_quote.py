import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from futu_api import FutuClient  # noqa: E402
from futu_app import APP_UA_TOKEN  # noqa: E402

ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) QtWebEngine/6.11 Safari/537.36 " + APP_UA_TOKEN
client = FutuClient({}, ua)
try:
    q = client.stock_quote("70000944", 2, 9)
    print("QUOTE", json.dumps(q, ensure_ascii=False)[:800])
except Exception as exc:  # noqa: BLE001
    print("ERR", type(exc).__name__, exc)
