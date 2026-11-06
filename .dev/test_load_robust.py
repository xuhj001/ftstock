"""启动加载的异常情况：正式文件被独占、损坏且改名失败、残留临时文件删不掉"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_watchlist as lw  # noqa: E402

HERE = Path(__file__).resolve().parent
D = HERE / "load_test"
F = D / "local_watchlist.json"
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail)
    if not ok:
        fails.append(name)


def fresh():
    shutil.rmtree(D, ignore_errors=True)
    D.mkdir()
    w = lw.LocalWatchlist(F)
    w.reorder([e["stockId"] for e in w.entries][::-1])  # 正式文件和 .bak 都是这一版
    return w


# 1. 正式文件一直被独占：用备份顶上，不改名、不覆盖；能读了以后轮询载入正式文件
w0 = fresh()
edited = lw.read_entries(F)
edited[0]["name"] = "手改过"
F.write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
main_bytes = F.read_bytes()
real_read = lw._read_retry
lw._read_retry = lambda p: (_ for _ in ()).throw(PermissionError(32, "另一个程序正在使用此文件"))
w = lw.LocalWatchlist(F)
lw._read_retry = real_read
check("locked main: loaded from backup", len(w.entries) == 6 and "暂时读不了" in w.warning, w.warning)
check("locked main: main untouched", F.read_bytes() == main_bytes)
check("locked main: no corrupt copy", not list(D.glob("*.corrupt-*")))
check("locked main: picked up when readable", w.external_change() and w.entries[0]["name"] == "手改过")

# 2. 损坏且改名失败：用备份，保存时先另存坏文件再覆盖
fresh()
F.write_text("{坏的", encoding="utf-8")
real_replace = lw._replace
state = {"first": True}


def replace_fail_once(src, dst):
    if state["first"] and ".corrupt-" in dst.name:
        state["first"] = False
        raise OSError(5, "拒绝访问")
    real_replace(src, dst)


lw._replace = replace_fail_once
w = lw.LocalWatchlist(F)
lw._replace = real_replace
copies = list(D.glob("local_watchlist.corrupt-*.json"))
check("corrupt + rename failed: backup used", len(w.entries) == 6 and "保存时会先另存一份" in w.warning, w.warning)
check("corrupt + rename failed: bad content preserved", len(copies) == 1 and copies[0].read_text(encoding="utf-8") == "{坏的")
check("corrupt + rename failed: main valid again", lw.read_entries(F) == w.entries)

# 3. 残留临时文件删不掉：不影响启动
fresh()
(D / "local_watchlist.json.tmp").write_text("x")
real_unlink = Path.unlink
Path.unlink = lambda self, missing_ok=False: (_ for _ in ()).throw(PermissionError(5, "拒绝访问")) \
    if self.suffix == ".tmp" else real_unlink(self, missing_ok)
try:
    w = lw.LocalWatchlist(F)
    ok = len(w.entries) == 6
except Exception as exc:  # noqa: BLE001
    ok, w = False, exc
Path.unlink = real_unlink
check("undeletable leftover tmp: startup ok", ok, w if not ok else "")

# 4. 同一秒内两次另存坏文件不互相覆盖
fresh()
a, b = lw._corrupt_path(F), None
a.write_text("1")
b = lw._corrupt_path(F)
check("corrupt copies never overwrite each other", a != b and not b.exists(), (a.name, b.name))

shutil.rmtree(D)
print("ALL PASS" if not fails else f"FAILED: {fails}")
