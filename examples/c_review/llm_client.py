"""C3 第 3 步：连 GPT（OpenAI 兼容的接口，中转也行）。只用 Python 自带的库，不用装 openai 包。

key、地址、模型名放在项目根目录的 .env（.gitignore 里有它，不会提交）。格式见 .env.example：
    OPENAI_API_KEY=你的key
    OPENAI_BASE_URL=https://xxx.com/v1
    OPENAI_MODEL=模型名
名字叫 OPENAI_*，是因为这套接口格式是 OpenAI 定的；别家兼容它的也能用，比如 DeepSeek 官方：
    OPENAI_BASE_URL=https://api.deepseek.com      OPENAI_MODEL=deepseek-flash（能看图；deepseek-v4-pro 不能）
代码里只写“去 .env / 环境变量里找 OPENAI_API_KEY”，不写 key 本身。

运行（项目根目录，conda activate py310）：
    python -m examples.c_review.llm_client       检查配置 + 列出这个地址能用的模型（不显示 key）
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env(path: Path = ROOT / ".env") -> None:
    """把 .env 里“名字=值”的行读进环境变量。环境里已经有的不覆盖（比如用 setx 设过的）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(name.strip(), value)


def config() -> tuple[str, str, str]:
    """返回 (key, 地址, 模型名)。地址没写就用 OpenAI 官方的。"""
    load_env()
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "")
    return key, base, model


def call(path: str, body: dict | None = None, timeout: float = 120, tries: int = 3, wait_s: float = 3) -> dict:
    """发一个请求：body 是 None 就 GET，否则 POST JSON。返回解析好的 JSON；出错时把服务器的原话带出来。
    连接半路断开会自动重试（最多 tries 次）；服务器明确拒绝（HTTP 4xx / 5xx）不重试。"""
    key, base, _ = config()
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, method="GET" if body is None else "POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # 有的中转在 Cloudflare 后面，会拦 Python 默认的 “Python-urllib/3.x”，所以换个名字
            "User-Agent": "highway-sim-eval/1.0",
        })
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:            # 服务器明确拒绝（key 错、模型不让用……）：重试没用
            raise RuntimeError(f"HTTP {e.code}：{e.read().decode('utf-8', 'replace')[:500]}") from None
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            # 连接半路断了（中转偶尔会，比如 SSL EOF）：等一下再试，最多 tries 次
            reason = getattr(e, "reason", e)
            if attempt == tries:
                raise RuntimeError(f"连不上 {base}（试了 {tries} 次）：{reason}") from None
            print(f"   （连接断了：{reason}，{wait_s} 秒后重试第 {attempt + 1} 次）")
            time.sleep(wait_s)


def main():
    key, base, model = config()
    print(f"地址：{base}")
    print(f"key：{'没设' if not key else f'已设（{len(key)} 位，不显示）'}")
    print(f"模型：{model or '没设'}")
    if not key:
        print("先在项目根目录的 .env 里填 OPENAI_API_KEY")
        return
    names = sorted(m.get("id", "") for m in call("/models").get("data", []))
    print(f"这个地址能用的模型 {len(names)} 个：")
    for n in names:
        print("  ", n)


if __name__ == "__main__":
    main()
