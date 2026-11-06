import sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app

db = Path(__file__).with_name("qt_profile_test") / "storage" / "Cookies"
jar = futu_app.read_profile_cookies(db)
cookies = {n: v for (d, n), v in jar.items()}
print("names:", list(cookies))
URL = "https://www.futunn.com/quote-api/quote-v2/get-stock-quote?stockId=201335"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def probe(label, ck):
    h = {"User-Agent": UA}
    if ck is not None:
        h["Cookie"] = "; ".join(f"{k}={v}" for k, v in ck.items())
    with urllib.request.urlopen(urllib.request.Request(URL, headers=h), timeout=10) as r:
        print(f"{label:30} {r.headers.get('Content-Type')}")


probe("no cookie header", None)
probe("all cookies", cookies)
for name in cookies:
    probe("without " + name, {k: v for k, v in cookies.items() if k != name})
for name in cookies:
    probe("only " + name, {name: cookies[name]})
