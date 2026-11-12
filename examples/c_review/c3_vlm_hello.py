"""C3 第 3a 步：第一次让模型看图。

两件事：
  ① 先验货：发一张纯色小图，问它“什么颜色”。答对了 = 这个地址真的把图片转给了模型（有的中转只转文字）。
  ② 再看真的：把 2c 挑出来的 scene-0103 急刹那一刻的前视照片发过去，让它说说看到了什么。
每次都打印用了多少 token（图片也算 token，这就是为什么要先用规则挑片段，不能每一帧都发）。

运行（项目根目录，conda activate py310；先跑过 c3_pick，照片在 outputs/c3/picked/）：
    python -m examples.c_review.c3_vlm_hello 模型名        比如 gpt-4o；.env 里填了 OPENAI_MODEL 就可以不写
"""

from __future__ import annotations

import base64
import io
import sys

from PIL import Image

from examples.c_review.llm_client import ROOT, call, config

PHOTO = ROOT / "outputs" / "c3" / "picked" / "scene-0103_14_brake.jpg"


def image_part(img: Image.Image, detail: str | None = None) -> dict:
    """一张图 → 消息里的一块：JPEG 转成 base64，放进 data: 网址。
    detail 是 OpenAI 自己的参数（low 最省 token）；默认不发，DeepSeek 等别家不一定认它。"""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    part = {"type": "image_url", "image_url": {"url": url}}
    if detail:
        part["image_url"]["detail"] = detail
    return part


def ask(model: str, question: str, img: Image.Image, detail: str | None = None) -> tuple[str, dict]:
    """问一个带图的问题，返回 (回答, token 用量)。"""
    body = {"model": model, "messages": [{"role": "user", "content": [
        {"type": "text", "text": question}, image_part(img, detail)]}]}
    out = call("/chat/completions", body)
    return out["choices"][0]["message"]["content"], out.get("usage", {})


def show_usage(u: dict) -> str:
    return f"token：问题 + 图 {u.get('prompt_tokens', '?')}，回答 {u.get('completion_tokens', '?')}"


def main():
    _, base, model = config()
    if len(sys.argv) > 1:
        model = sys.argv[1]
    if not model:
        print("没给模型名：python -m examples.c_review.c3_vlm_hello gpt-4o（或在 .env 里填 OPENAI_MODEL）")
        return
    print(f"地址 {base}，模型 {model}\n")

    print("① 验货：一张纯绿色的 64×64 小图")
    answer, u = ask(model, "这张图是什么颜色？只回答一个颜色词。", Image.new("RGB", (64, 64), (0, 170, 0)))
    print(f"   回答：{answer.strip()}    （{show_usage(u)}）")
    print("   答“绿”= 图片转过去了；答别的或说看不到图 = 这个地址 / 模型不支持看图\n")

    if not PHOTO.exists():
        print(f"② 跳过：没有 {PHOTO}，先跑 python -m examples.c_review.c3_pick")
        return
    print("② 真的：scene-0103 第 6.4 秒，我急刹 −3.2 m/s² 的那一刻（前视照片 800×450）")
    q = ("这是一辆车前视摄像头拍的照片，这一刻司机踩了一脚比较重的刹车。"
         "用中文简短回答：1. 路上有哪些车和人，各在什么位置；2. 司机为什么可能要刹车。")
    answer, u = ask(model, q, Image.open(PHOTO))
    print(f"   {show_usage(u)}")
    print("   回答：\n" + "\n".join("   " + line for line in answer.strip().splitlines()))


if __name__ == "__main__":
    main()
