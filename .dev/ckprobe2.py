import random, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app

jar = futu_app.read_profile_cookies(Path(__file__).with_name("qt_profile_test3") / "storage" / "Cookies")
cookies = {n: v for (d, n), v in jar.items()}
URL = "https://www.futunn.com/quote-api/quote-v2/get-stock-quote?stockId=201335"
tag = random.randint(1000, 9999)


def probe(label, extra):
    h = {"User-Agent": f"Mozilla/5.0 (FutuProbe-{tag}-{label})", **extra}
    with urllib.request.urlopen(urllib.request.Request(URL, headers=h), timeout=10) as r:
        print(f"{label:12} {r.headers.get('Content-Type')}")


probe("nocookie", {})
probe("qtcookies", {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())})
probe("waf-only", {"Cookie": "wafToken=" + cookies.get("wafToken", "")})
probe("nowaf", {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items() if k != "wafToken")})
