"""_replace 的错误路径：源文件不存在时应抛出带 winerror 的 OSError"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_watchlist as lw  # noqa: E402

d = Path(__file__).resolve().parent
try:
    lw._replace(d / "no_such_file.tmp", d / "no_such_target.json")
    print("FAIL 没有抛错")
except OSError as exc:
    print("PASS", type(exc).__name__, "winerror=", exc.winerror, "|", exc)
