"""本地自选：股票列表只保存在本机 local_watchlist.json，不需要登录。

列表条目拼成与 get-watch-list 返回值相同的格式（个股静态信息 + get-stock-quote 行情），
交给站点自己的 WatchListModal 渲染，所以显示效果和「热门自选 / 我的自选」一致。
"""

import contextlib
import json
import os
import re
import time
from pathlib import Path

from futu_api import DEFAULT_MARKET_CODE, FutuClient, app_dir

LOCAL_FILE = app_dir() / "local_watchlist.json"
MARKET_LABELS = {"us": "US", "hk": "HK", "sh": "SH", "sz": "SZ"}


FUTURES_TYPE = 9
_US_TYPES = {"stock": (3, 3002), "etf": (4, 4002), "futures": (FUTURES_TYPE, 9002)}


def _us(stock_id: str, code: str, name: str, kind: str = "stock") -> dict:
    instrument, sub = _US_TYPES[kind]
    return {"stockId": stock_id, "stockCode": code, "marketType": 2, "marketLabel": "US", "name": name,
            "instrumentType": instrument, "subInstrumentType": sub}


# 还没有 local_watchlist.json 时的默认本地自选（静态信息写死，启动时不用再查接口）
DEFAULT_ENTRIES = [
    _us("70000944", "NQmain", "纳斯达克100指数期货主连", "futures"),
    _us("203290", "QQQ", "纳指100ETF-Invesco QQQ Trust", "etf"),
    _us("206647", "GOOGL", "谷歌-A"),
    _us("205189", "AAPL", "苹果"),
    _us("201345", "MSFT", "微软"),
    _us("207605", "SOXX", "半导体ETF-iShares", "etf"),
]


class StockNotFound(Exception):
    pass


def parse_code(text: str) -> tuple[str, str | None]:
    """TSLA -> (TSLA, None)，NVDA.US / NVDA-US -> (NVDA, US)，700 -> (00700, HK)，600519 -> (600519, None)"""
    s = text.strip().upper().replace(".", "-")
    m = re.fullmatch(r"(.+?)-(US|HK|SH|SZ)", s)
    symbol, market = (m.group(1), m.group(2)) if m else (s, None)
    if symbol.isdigit() and len(symbol) <= 5:
        return symbol.zfill(5), market or "HK"
    return symbol, market


def resolve(client: FutuClient, text: str) -> dict:
    """用站点搜索接口把代码解析成本地自选条目（静态信息）"""
    symbol, market = parse_code(text)
    if not symbol:
        raise StockNotFound("请输入股票代码")
    candidates = [
        q for q in client.search(symbol)
        if q.get("stockSymbol", "").upper() == symbol
        and (market is None or MARKET_LABELS.get(q.get("market", "")) == market)
    ]
    if not candidates:
        raise StockNotFound(f"没有找到 {text.strip()}，请确认代码，如 TSLA、00700、600519-SH")
    q = candidates[0]
    entry = {
        "stockId": str(q["stockId"]),
        "stockCode": q["stockSymbol"],
        "marketType": q["marketType"],
        "marketLabel": MARKET_LABELS.get(q.get("market", ""), q.get("market", "").upper()),
        "name": q.get("stockName") or q["stockSymbol"],
        "instrumentType": 3,
        "subInstrumentType": 0,
    }
    try:
        info = next(iter(client.stock_infos([entry["stockId"]])), {})
        entry["instrumentType"] = info.get("instrument_type_v2") or 3
        entry["subInstrumentType"] = info.get("sub_instrument_type_v2") or 0
    except Exception:  # noqa: BLE001  证券类型只影响跳转路径（stock / etfs），取不到就按正股处理
        pass
    return entry


def build_item(entry: dict, quote: dict | None) -> dict:
    item = {
        **entry,
        "displaySymbol": f"{entry['stockCode']}.{entry['marketLabel']}",
        "marketCode": DEFAULT_MARKET_CODE.get(entry["marketType"], 11),
        "isOption": False,
        "isPlate": False,
        "isFutures": entry.get("instrumentType") == FUTURES_TYPE,
        "underlyingStock": {},
        "delayTime": 0,
        "price": "--",
        "change": "--",
        "changeRatio": "--",
        "volume": "--",
    }
    item.update(quote or {})
    return item


FUTURES_MONTH_RE = re.compile(r"\s*\(\d{4}\)$")


def live_fields(info: dict) -> dict:
    """批量个股资料（FutuClient.stock_infos 的一项）里会随时间变的字段：代码、名称、证券类型。
    取不到或格式不对的字段不返回，校对时就保持原值。"""
    out = {}
    symbol = info.get("symbol")
    if isinstance(symbol, str) and "." in symbol:
        code = symbol.rsplit(".", 1)[0].strip()
        if code:
            out["stockCode"] = code
    name = info.get("sc_name")
    if isinstance(name, str) and name.strip():
        name = name.strip()
        if info.get("instrument_type_v2") == FUTURES_TYPE:
            name = FUTURES_MONTH_RE.sub("", name)  # 期货主连名称带当前合约月份「(2612)」，每季度都变，不跟
        out["name"] = name
    for key, src in (("instrumentType", "instrument_type_v2"), ("subInstrumentType", "sub_instrument_type_v2")):
        value = info.get(src)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            out[key] = value
    return out


def describe_change(entry: dict, diff: dict) -> str:
    parts = []
    if "stockCode" in diff:
        parts.append(f"代码 {entry['stockCode']} → {diff['stockCode']}")
    if "name" in diff:
        parts.append(f"名称 {entry['name']} → {diff['name']}")
    if "instrumentType" in diff or "subInstrumentType" in diff:
        old = f"{entry['instrumentType']}/{entry['subInstrumentType']}"
        new = f"{diff.get('instrumentType', entry['instrumentType'])}/{diff.get('subInstrumentType', entry['subInstrumentType'])}"
        parts.append(f"证券类型 {old} → {new}")
    return f"{diff.get('stockCode', entry['stockCode'])}：" + "，".join(parts)


ENTRY_FIELDS = {"stockId": str, "stockCode": str, "marketType": int, "marketLabel": str, "name": str,
                "instrumentType": int, "subInstrumentType": int}


class SaveError(Exception):
    pass


def validate(entries) -> list[dict]:
    """检查本地自选数据结构完整：列表，每项字段齐全、类型正确、stockId 不重复"""
    if not isinstance(entries, list):
        raise ValueError("顶层不是列表")
    seen = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise ValueError(f"第 {i + 1} 项不是对象")
        for key, typ in ENTRY_FIELDS.items():
            if not isinstance(e.get(key), typ) or isinstance(e.get(key), bool):
                raise ValueError(f"第 {i + 1} 项字段 {key} 缺失或类型不对")
        if e["stockId"] in seen:
            raise ValueError(f"stockId {e['stockId']} 重复")
        seen.add(e["stockId"])
    return entries


def read_entries(path: Path) -> list[dict]:
    return validate(json.loads(path.read_text(encoding="utf-8")))


def _move_write_through(src: Path, dst: Path):
    """原子替换。Windows 上带 MOVEFILE_WRITE_THROUGH：替换动作落盘后才返回，断电重启也不会退回旧文件"""
    if os.name != "nt":
        os.replace(src, dst)
        return
    import ctypes

    move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    move.restype = ctypes.c_int
    MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH = 0x1, 0x8
    if not move(str(src), str(dst), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH):
        err = ctypes.get_last_error()
        raise OSError(None, ctypes.FormatError(err).strip(), str(dst), err)


def _replace(src: Path, dst: Path):
    # 编辑器、杀毒软件短暂占用文件时 Windows 会拒绝访问 / 共享冲突，稍等重试
    for attempt in range(5):
        try:
            _move_write_through(src, dst)
            return
        except OSError as exc:
            if attempt == 4 or getattr(exc, "winerror", None) not in (5, 32):
                raise
            time.sleep(0.2)


def _tmp_of(path: Path) -> Path:
    return path.with_name(path.name + ".tmp")


def _unlink_quietly(path: Path):
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)


def _read_retry(path: Path) -> bytes:
    """编辑器、杀毒软件可能短暂独占文件，稍等重试；文件不存在直接抛出"""
    for attempt in range(5):
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.2)
    raise AssertionError("unreachable")


def _corrupt_path(path: Path) -> Path:
    """损坏 / 手改坏的文件另存的名字，同一秒里多次也不互相覆盖"""
    stem = f"{path.stem}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
    candidate, n = path.with_name(stem + ".json"), 1
    while candidate.exists():
        candidate, n = path.with_name(f"{stem}-{n}.json"), n + 1
    return candidate


def _write_durable(path: Path, data: bytes):
    """写完并 fsync 落盘才返回，之后断电内容也不会丢"""
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def _atomic_write(path: Path, data: bytes):
    """先写 path.tmp 并落盘，再原子替换 path：任何时刻中断，path 要么是旧内容要么是新内容"""
    tmp = _tmp_of(path)
    _write_durable(tmp, data)
    _replace(tmp, path)


class LocalWatchlist:
    """保存流程：写临时文件 → 回读校验 → 备份旧文件为 .bak → 原子替换正式文件 → 回读校验正式文件
    → .bak 更新为新版本。每次写文件都是「写 .tmp 落盘 → 原子替换」，程序在任何一步被中断，
    正式文件和备份都只会是完整的旧版或完整的新版。

    所有修改（添加、删除、拖动排序、启动校对）都在界面线程里依次执行，每次都先载入文件的外部修改
    （比如在编辑器里手改了 json），再在最新的数据上改动并保存，不会把别处的修改覆盖掉。"""

    def __init__(self, path: Path = LOCAL_FILE):
        self.path = path
        self.tmp = _tmp_of(path)
        self.backup = path.with_name(path.name + ".bak")
        self.entries: list[dict] = []
        self.warning = ""  # 加载时出过问题（文件损坏、用了备份等），交给界面提示
        self.notices: list[str] = []  # 运行中发现的外部修改等，交给界面提示后清空
        self._disk: bytes | None = None  # 最近一次从文件读到 / 写进文件的内容，用来发现外部修改
        self._bad: bytes | None = None  # 已提示过的格式有误的外部修改，不重复提示
        self._pending_bad: bytes | None = None
        self._load()

    def _load(self):
        # 上次保存中途退出留下的临时文件：替换没发生，正式文件 / 备份都还是完整的
        _unlink_quietly(self.tmp)
        _unlink_quietly(_tmp_of(self.backup))
        try:
            raw = _read_retry(self.path)
        except FileNotFoundError:
            if self.backup.exists():
                self._load_backup("local_watchlist.json 不见了")
            else:
                self.entries = [dict(e) for e in DEFAULT_ENTRIES]
                self._try_save()
            return
        except OSError as exc:
            # 一直被别的程序独占：先用备份顶上，不改名也不覆盖它；能读了以后轮询会把它载入
            self._load_backup(f"local_watchlist.json 暂时读不了（{exc}）", save=False)
            return
        try:
            self.entries = validate(json.loads(raw))
            self._disk = raw
        except ValueError as exc:
            # 损坏的文件改名保留，绝不拿空列表覆盖它；改名失败的话，下次保存前也会先另存一份
            corrupt = _corrupt_path(self.path)
            try:
                _replace(self.path, corrupt)
                note = f"已改名为 {corrupt.name}"
            except OSError:
                note = "保存时会先另存一份"
            self._load_backup(f"local_watchlist.json 损坏（{exc}），{note}")

    def _load_backup(self, reason: str, save: bool = True):
        try:
            self.entries = read_entries(self.backup)
        except (OSError, ValueError):
            self.entries = []
            self.warning = f"{reason}；备份也不可用，本地自选从空列表开始"
            return
        self.warning = f"{reason}；已从备份 {self.backup.name} 恢复 {len(self.entries)} 只"
        if save:
            self._try_save()

    def _try_save(self):
        try:
            self.save()
        except SaveError as exc:
            self.warning = f"{self.warning}；{exc}" if self.warning else str(exc)

    def save(self):
        try:
            entries = validate(self.entries)
            data = json.dumps(entries, ensure_ascii=False, indent=2).encode("utf-8")
            _write_durable(self.tmp, data)
            if read_entries(self.tmp) != entries:
                raise SaveError("临时文件回读内容与要保存的数据不一致")
            if self.path.exists():
                old = self.path.read_bytes()
                try:
                    validate(json.loads(old))
                    _atomic_write(self.backup, old)  # 旧版本先备份；正式文件已损坏就不拿它覆盖好的备份
                except ValueError:
                    # 正式文件格式有误（多半是手改到一半）：另存一份再覆盖，手改的内容不会丢
                    _atomic_write(_corrupt_path(self.path), old)
            _replace(self.tmp, self.path)
            if read_entries(self.path) != entries:
                if self.backup.exists():
                    _atomic_write(self.path, self.backup.read_bytes())
                raise SaveError("写入后正式文件校验不一致，已用备份还原")
            self._disk = data
            # 正式文件确认无误后，备份也更新为这一版：以后正式文件被损坏时能恢复到最新内容。
            # 这一步失败不算保存失败：正式文件已是新版，备份仍是完整的上一版
            try:
                _atomic_write(self.backup, data)
            except OSError:
                pass
        except (OSError, ValueError) as exc:
            raise SaveError(f"保存本地自选失败：{exc}") from exc
        finally:
            _unlink_quietly(self.tmp)
            _unlink_quietly(_tmp_of(self.backup))

    def external_change(self) -> bool:
        """文件被外部改过（和最近一次读到 / 写入的内容不同）就重新载入，返回是否载入了。
        改得格式有误时不载入、也不提示第二次；之后保存会先把它另存为 .corrupt-*.json 再覆盖。"""
        try:
            raw = self.path.read_bytes()
        except OSError:  # 不存在（下次保存会重建）或正被编辑器占用（下次再看）
            return False
        if raw == self._disk or raw == self._bad:
            return False
        try:
            entries = validate(json.loads(raw))
        except ValueError as exc:
            # 编辑器保存到一半时读到的也是坏内容：连续两次读到同样的坏内容才提示
            if raw == self._pending_bad:
                self._bad = raw
                self.notices.append(f"local_watchlist.json 被外部修改但格式有误（{exc}），暂不载入，改好保存后自动载入")
            self._pending_bad = raw
            return False
        self.entries, self._disk, self._bad, self._pending_bad = entries, raw, None, None
        self.notices.append(f"local_watchlist.json 被外部修改，已重新载入（{len(entries)} 只）")
        return True

    def _commit(self, entries: list[dict]):
        """保存新列表；保存失败时内存恢复原样再抛出"""
        old = self.entries
        self.entries = entries
        try:
            self.save()
        except SaveError:
            self.entries = old
            raise

    def find(self, stock_id: str) -> dict | None:
        return next((e for e in self.entries if e["stockId"] == stock_id), None)

    def add(self, entry: dict) -> bool:
        self.external_change()
        if self.find(entry["stockId"]):
            return False
        self._commit(self.entries + [entry])
        return True

    def remove(self, stock_id: str):
        self.external_change()
        if self.find(stock_id):
            self._commit([e for e in self.entries if e["stockId"] != stock_id])

    def sync(self, infos: list, checked_ids: list[str]) -> tuple[list[str], list[str]]:
        """用实时个股资料校对 checked_ids 这些股票的代码、名称、证券类型，有变化就安全保存。
        返回 (变化说明, 没查到资料的代码)。没查到的股票原样保留、绝不删除；stockId 和顺序不动。"""
        self.external_change()
        by_id = {str(i.get("stock_id")): i for i in infos if isinstance(i, dict)}
        checked = set(checked_ids)
        entries, changes, missing = [], [], []
        for e in self.entries:
            info = by_id.get(e["stockId"]) if e["stockId"] in checked else None
            if info is None:
                if e["stockId"] in checked:
                    missing.append(e["stockCode"])
                entries.append(e)
                continue
            diff = {k: v for k, v in live_fields(info).items() if e.get(k) != v}
            if diff:
                changes.append(describe_change(e, diff))
            entries.append({**e, **diff})
        if changes:
            self._commit(entries)
        return changes, missing

    def reorder(self, stock_ids) -> bool:
        """按拖动后的顺序重排，只排现有的股票：页面上有、文件里已经没有的忽略；文件里有、页面上没有的
        （拖动期间刚添加的、或外部修改加进来的）按原先后接在最后。一只不丢，也不会凭空多出来；
        每只股票的资料用当前最新的（启动校对改过的代码、名称都保留）。"""
        if not isinstance(stock_ids, list) or not all(isinstance(i, str) for i in stock_ids):
            raise SaveError("拖动后的顺序数据格式不对")
        self.external_change()
        by_id = {e["stockId"]: e for e in self.entries}
        order = list(dict.fromkeys(i for i in stock_ids if i in by_id))
        placed = set(order)
        order += [e["stockId"] for e in self.entries if e["stockId"] not in placed]
        if order == [e["stockId"] for e in self.entries]:
            return False
        self._commit([by_id[i] for i in order])
        return True
