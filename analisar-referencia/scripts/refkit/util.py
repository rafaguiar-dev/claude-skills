import json
import subprocess
import sys
import time
from pathlib import Path


def log(msg: str) -> None:
    print(f"[ref] {msg}", file=sys.stderr, flush=True)


def run(cmd, input_bytes=None) -> bytes:
    proc = subprocess.run([str(c) for c in cmd], input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")[-1200:]
        raise RuntimeError(f"{Path(str(cmd[0])).name} falhou (código {proc.returncode}): {err}")
    return proc.stdout


def write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def r(x, nd=3):
    return None if x is None else round(float(x), nd)


def fmt_t(t: float) -> str:
    """12.3 -> '0:12.30'"""
    m, s = divmod(max(0.0, float(t)), 60)
    return f"{int(m)}:{s:05.2f}"


def hexcolor(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*[int(max(0, min(255, round(c)))) for c in rgb[:3]])


class Timer:
    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self.t0 = time.time()
        log(f"{self.label}...")
        return self

    def __exit__(self, *exc):
        if exc[0] is None:
            log(f"{self.label}: ok ({time.time() - self.t0:.1f}s)")
        return False
