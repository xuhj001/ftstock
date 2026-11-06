"""local_watchlist 保存 / 加载的安全性测试，全部在临时子目录里进行，不碰正式文件"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_watchlist as lw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
D = Path(__file__).resolve().parent / "save_test"
shutil.rmtree(D, ignore_errors=True)
D.mkdir()
P = D / "local_watchlist.json"


def files():
    return sorted(f.name for f in D.iterdir())


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name, flush=True)


# 0. 当前正式文件能通过校验
real = lw.read_entries(ROOT / "local_watchlist.json")
check(f"正式文件校验通过（{len(real)} 只）", True)

# 1. 首次：写入默认列表，只剩正式文件
w = lw.LocalWatchlist(P)
check("首次生成默认列表", [e["stockCode"] for e in w.entries][:2] == ["NQmain", "QQQ"] and files() == ["local_watchlist.json", "local_watchlist.json.bak"])

# 2. 添加：正式文件更新、.bak 是旧版本、无 .tmp
w.add(dict(real[-1], stockId="999999", stockCode="TEST"))
check("添加后正式文件含新条目", lw.read_entries(P)[-1]["stockCode"] == "TEST")
check("添加后 .bak 与正式文件一致", lw.read_entries(D / "local_watchlist.json.bak") == w.entries)
check("添加后没有 .tmp", "local_watchlist.json.tmp" not in files())

# 3. 非法数据：拒绝保存，正式文件不变，内存回滚
before = P.read_bytes()
try:
    w.add({"stockId": "1", "stockCode": "BAD"})
    check("非法条目被拒绝", False)
except lw.SaveError as e:
    check(f"非法条目被拒绝（{e}）", P.read_bytes() == before and w.find("1") is None)

# 4. 删除
w.remove("999999")
check("删除后正式文件不含该条目", all(e["stockId"] != "999999" for e in lw.read_entries(P)))

# 5. 正式文件损坏：改名保留、从备份恢复、不覆盖
P.write_text('[{"stockId": "1", "stockCo', encoding="utf-8")
w2 = lw.LocalWatchlist(P)
corrupt = [f for f in files() if ".corrupt-" in f]
check(f"损坏文件被改名保留 {corrupt}", len(corrupt) == 1 and (D / corrupt[0]).read_text(encoding="utf-8").startswith('[{"stockId": "1"'))
check(f"从备份恢复到最新版 {len(w2.entries)} 只，提示：{w2.warning}",
      w2.entries == w.entries and lw.read_entries(P) == w2.entries)

# 6. 残留 .tmp 被清理
(D / "local_watchlist.json.tmp").write_text("garbage", encoding="utf-8")
lw.LocalWatchlist(P)
check("启动时清理残留 .tmp", "local_watchlist.json.tmp" not in files())

print("files:", files())
shutil.rmtree(D)
