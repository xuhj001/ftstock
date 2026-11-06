import urllib.request

URL = "https://www.futunn.com/quote-api/quote-v2/get-stock-quote?stockId=201335"
BASE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
for name, ua in {
    "chrome140": BASE + "Chrome/140.0.0.0 Safari/537.36",
    "chrome148": BASE + "Chrome/148.0.0.0 Safari/537.36",
    "chrome148 edge": BASE + "Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
    "qt default": BASE + "QtWebEngine/6.11.2 Chrome/140.0.0.0 Safari/537.36",
}.items():
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": ua}), timeout=10) as r:
        print(f"{name:15} {r.headers.get('Content-Type')}")
