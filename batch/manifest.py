"""运行清单（manifest）：每跑完一批，在结果表旁边存一个同名的 .json。

记下这张表是怎么来的：什么时候、哪条命令、哪版代码、什么设置、什么环境、跑得怎样。
一个月后表对不上时，先把两份清单放在一起对一对。

用法（b2_grid 里）：
    snap = snapshot()                                   开跑前拍快照（代码版本要记开跑那一刻的）
    rows = run_jobs_safe(...)
    save_csv(rows, path)
    write_manifest(path, snap, settings, rows, seconds)
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    """在项目根目录跑一条 git 命令，返回它打印的文字（只去掉末尾的换行：行首的空格在 git status 里有意思，不能删）。"""
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.rstrip()


def _code_fingerprint() -> str:
    """代码指纹（见 batch/resume.py）：考生、考场、出题代码的哈希，改一个字就变。11-10 起记进运行清单。"""
    from batch.resume import code_fingerprint      # 放在函数里：resume 不依赖 manifest，避免互相导入
    return code_fingerprint()


def snapshot() -> dict:
    """开跑前拍一张快照：什么时候、哪条命令、哪版代码（有没有没提交的改动）、什么环境、哪台电脑。"""
    changed = _git("status", "--porcelain").splitlines()   # 改了没提交的、新建了还没进 git 的都算；outputs 在 .gitignore 里，不算
    try:
        highway_env_version = version("highway-env")
    except PackageNotFoundError:
        highway_env_version = None
    return {
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": " ".join(sys.orig_argv),
        "commit": _git("rev-parse", "--short", "HEAD"),
        "code_fingerprint": _code_fingerprint(),
        "uncommitted_changes": [line[3:] for line in changed],
        "python": platform.python_version(),
        "highway_env": highway_env_version,
        "machine": platform.node(),
    }


def status_counts(rows: list[dict]) -> dict:
    """数每种 status 各几个。

    参数 rows：run_jobs_safe 交回的结果，一个任务一行（字典），每行都有 "status"："ok" / "timeout" / "error"。
    返回：{status: 个数}，只放出现过的，例如 {"ok": 63998, "timeout": 1, "error": 1}。
    """
    counts = {}
    for r in rows:
        s = r["status"]
        if s not in counts:
            counts[s] = 0
        counts[s] += 1
    return counts


def write_manifest(table_path: Path, snap: dict, settings: dict, rows: list[dict], seconds: float) -> Path:
    """在结果表旁边存一份同名的 .json 运行清单，返回 .json 的路径。

    参数：
      table_path  结果表的路径，例如 outputs/b2_grid_1000_seed2.csv → 清单存成 outputs/b2_grid_1000_seed2.json
      snap        开跑前 snapshot() 拍的快照
      settings    这批的设置（出几道题、种子、旋钮表、超时、重试……），原样放进去
      rows        结果，一个任务一行
      seconds     整批用了几秒
    清单里要有：快照里的每一项，再加 "settings"、"table"（表的文件名）、"rows"（几行）、
              "status"（status_counts 的结果）、"seconds"（保留 1 位小数）。
    """
    info = dict(snap)                                   # 先复印一份快照，再往上加，不改原来那份
    info["settings"] = settings
    info["table"] = table_path.name
    info["rows"] = len(rows)
    info["status"] = status_counts(rows)
    info["seconds"] = round(seconds, 1)
    path = table_path.with_suffix(".json")              # b2_grid_1000_seed2.csv → b2_grid_1000_seed2.json
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
