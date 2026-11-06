import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FutuProbe/1.0"
for url in ("https://www.futunn.com/stock/AAPL-US", "https://www.futunn.com/quote/us"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(400).decode("utf-8", "ignore")
            print(url, "->", r.status, r.geturl(), body[:150].replace("\n", " "))
    except Exception as e:  # noqa: BLE001
        print(url, "ERR", e)
