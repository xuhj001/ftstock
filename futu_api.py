"""复刻 futunn.com 前端调用行情/自选接口的方式。

网页端没有单独的 access token，身份完全靠 futunn.com 域下的 cookie：
  - 登录态 cookie：passport 登录成功后写入，浏览器自动携带；
  - csrfToken cookie：前端把它的值放进请求头 futu-x-csrf-token；
  - quote-token 请求头：前端对请求参数做的签名，服务端会校验，算法见 quote_token()。

登录 cookie 由 futu_app.py 从 QWebEngine profile 里取出后传进来。

网关会拦截「UA 声称是 Chrome、TLS 指纹却不是正式版 Chrome」的请求，Python 的 TLS 显然不是 Chrome，
所以 User-Agent 不能冒充浏览器，被拦时返回的是 200 + 「访问频繁，请稍后重试」的 HTML。
"""

import hashlib
import hmac
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def app_dir() -> Path:
    """配置和 .qt_profile 的存放目录：打包成 exe 后用 exe 所在目录，脚本运行时用源码目录。复制到哪就用哪。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    """只读资源（图标等）的目录：打包后是解压出的内部目录（onedir 下为 _internal），脚本运行时用源码目录。"""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else Path(__file__).resolve().parent


BASE_URL = "https://www.futunn.com"
QUOTE_API = BASE_URL + "/quote-api/quote-v2"
NNQ_URL = "https://q.futunn.com"
# get-stock-quote 必须带 marketCode，但只用来区分市场，同一市场内取任一有效值返回的行情都一样
DEFAULT_MARKET_CODE = {1: 1, 2: 11}
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FutuWatchlist/1.0 (Python)"

OPTIONAL_ADD = 1
OPTIONAL_DEL = 2


class RateLimited(Exception):
    """被网关拦截时仍返回 200，但内容是「访问频繁，请稍后重试」的 HTML 页面。"""


def quote_token(payload: str) -> str:
    """SHA256(HmacSHA512(payload, "quote_web").hex[:10]).hex[:10]"""
    if not payload:
        payload = "quote"
    first = hmac.new(b"quote_web", payload.encode(), hashlib.sha512).hexdigest()[:10]
    return hashlib.sha256(first.encode()).hexdigest()[:10]


def _js_json(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def params_payload(params: dict | None) -> str:
    # 对应前端 ng()：GET 参数的值全部转成字符串后 JSON.stringify，没有参数时是 "{}"
    return _js_json({k: str(v) for k, v in (params or {}).items() if v is not None})


class FutuClient:
    def __init__(self, cookies: dict[str, str], user_agent: str = DEFAULT_UA):
        self.cookies = dict(cookies)
        self.user_agent = user_agent

    def _headers(self, payload: str) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Referer": BASE_URL + "/",
            "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items()),
            "futu-x-csrf-token": urllib.parse.unquote(self.cookies.get("csrfToken", "")),
            "quote-token": quote_token(payload),
        }

    def _get_json(self, url: str, params: dict, extra_headers: dict | None = None) -> dict:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json", "Referer": BASE_URL + "/"}
        headers.update(extra_headers or {})
        req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers=headers)
        return self._send(req)

    def _send(self, req: urllib.request.Request) -> dict:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", "ignore")
            if "json" not in (resp.headers.get("Content-Type") or ""):
                raise RateLimited("被富途网关拦截（访问频繁，或 User-Agent 冒充了浏览器）")
            return json.loads(body)

    def get(self, path: str, params: dict | None = None) -> dict:
        query = urllib.parse.urlencode(params or {})
        url = f"{QUOTE_API}{path}" + (f"?{query}" if query else "")
        req = urllib.request.Request(url, headers=self._headers(params_payload(params)))
        return self._send(req)

    def post(self, path: str, body: dict) -> dict:
        payload = _js_json(body)
        headers = self._headers(payload)
        headers["Content-Type"] = "application/json;charset=UTF-8"
        req = urllib.request.Request(
            f"{QUOTE_API}{path}", data=payload.encode(), headers=headers, method="POST"
        )
        return self._send(req)

    def watch_list(self, page: int = 0, page_size: int = 20) -> dict:
        """已登录返回自己的自选，未登录返回热门自选。data = {list, allCount}"""
        return self.get(
            "/get-watch-list",
            {"page": page, "page_size": page_size, "t": int(time.time() * 1000)},
        )

    def watch_ids(self) -> list[str]:
        data = self.get("/get-watch-ids").get("data") or {}
        return [i for i in (data.get("ids") or "").split(",") if i]

    def set_optional(self, stock_id: str, add: bool = True) -> dict:
        """resultCode == 3 表示自选数量已达上限"""
        return self.post(
            "/set-optional",
            {"stockId": stock_id, "optional": OPTIONAL_ADD if add else OPTIONAL_DEL},
        )

    def search(self, keyword: str) -> list[dict]:
        """站点顶部搜索框的联想接口。每项含 market(us/hk/sh/sz)、marketType、stockSymbol、stockId、stockName"""
        res = self._get_json(f"{BASE_URL}/search-stock/predict",
                             {"keyword": keyword, "lang": "zh-cn", "site": "cn"})
        return (res.get("data") or {}).get("quote") or []

    def stock_infos(self, stock_ids: list[str]) -> list[dict]:
        """牛牛圈的批量个股静态信息，含 instrument_type_v2 / sub_instrument_type_v2"""
        res = self._get_json(f"{NNQ_URL}/api/stock/list", {"stock_ids": ",".join(stock_ids)},
                             {"x-futu-nnq-new-website": "nnq"})
        return res.get("data") or []

    def stock_quote(self, stock_id: str, market_type: int, instrument_type: int = 3) -> dict:
        """个股实时报价，字段与 get-watch-list 的条目一致（price / change / changeRatio / volume ...）"""
        res = self.get("/get-stock-quote", {
            "stockId": stock_id,
            "marketType": market_type,
            "marketCode": DEFAULT_MARKET_CODE.get(market_type, 11),
            "instrumentType": instrument_type,
        })
        return res.get("data") or {}

