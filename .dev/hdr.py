import urllib.request

URL = "https://www.futunn.com/quote-api/quote-v2/get-stock-quote?stockId=201335"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
cases = {
    "ua only": {"User-Agent": UA},
    "+accept json": {"User-Agent": UA, "Accept": "application/json, text/plain, */*"},
    "+referer": {"User-Agent": UA, "Referer": "https://www.futunn.com/"},
    "+empty cookie": {"User-Agent": UA, "Cookie": ""},
    "+csrf empty": {"User-Agent": UA, "futu-x-csrf-token": ""},
    "+quote-token": {"User-Agent": UA, "quote-token": "abc"},
    "+fake cookie": {"User-Agent": UA, "Cookie": "csrfToken=abc"},
    "no ua": {},
}
for name, h in cases.items():
    req = urllib.request.Request(URL, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read(80)
            print(f"{name:15} {r.status} {r.headers.get('Content-Type')} {body[:60]!r}")
    except Exception as e:
        print(name, "ERR", e)
