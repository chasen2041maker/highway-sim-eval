"""C3 第 3a 步（续）：问法会不会把模型带偏。

同一张照片问两遍：
  中立：“这一刻有没有需要马上刹车的危险？没有就回答‘没有’。”
  带偏：“这一刻司机踩了一脚比较重的刹车，为什么？”（先告诉它“有事”）
两张照片，答案我们已经知道（2d 人看过）：
  scene-0061 第 15 帧（7.05 秒）：规则误挑——工人站在安全岛上、隔离栏后面，不危险；
  scene-0103 第 14 帧（6.4 秒）：真的急刹，左边黑车横穿。
看点：没危险的那张，被“带偏”问法一问，模型会不会编一个理由出来。

运行（项目根目录，conda activate py310）：
    python -m examples.c_review.c3_vlm_lead
"""

from __future__ import annotations

from PIL import Image

from examples.c_review.c3_vlm_hello import ask, show_usage
from examples.c_review.llm_client import config
from examples.c_review.nuscenes_tables import ROOT as NUSCENES, load

CASES = [
    ("scene-0061", 15, "7.05 秒，规则误挑：安全岛上的工人（人看过：不危险）"),
    ("scene-0103", 14, "6.4 秒，急刹 −3.2 m/s²（人看过：左边黑车横穿，值得看）"),
]
NEUTRAL = ("这是一辆车前视摄像头拍的照片。这一刻，路上有没有需要司机马上刹车的危险？"
           "有就用一句话说是什么；没有就只回答“没有”。")
LEADING = "这是一辆车前视摄像头拍的照片。这一刻司机踩了一脚比较重的刹车。用一句话说为什么。"


def front_photo(T: dict, scene_name: str, frame_no: int) -> Image.Image:
    """某一段第 frame_no 个关键帧（从 1 数）的前视照片，缩到 800×450。"""
    scene = next(s for s in T["scene"].values() if s["name"] == scene_name)
    tok = scene["first_sample_token"]
    for _ in range(frame_no - 1):
        tok = T["sample"][tok]["next"]
    sd = next(d for d in T["sample_data"].values()
              if d["sample_token"] == tok and d["is_key_frame"] and "/CAM_FRONT/" in d["filename"])
    return Image.open(NUSCENES / sd["filename"]).resize((800, 450))


def main():
    _, _, model = config()
    if not model:
        print("先在 .env 里填 OPENAI_MODEL")
        return
    T = load()
    for scene_name, frame_no, note in CASES:
        img = front_photo(T, scene_name, frame_no)
        print(f"\n{scene_name} 第 {frame_no} 帧：{note}")
        for label, q in (("中立问法", NEUTRAL), ("带偏问法", LEADING)):
            answer, u = ask(model, q, img)
            print(f"  {label}：{answer.strip()}    （{show_usage(u)}）")


if __name__ == "__main__":
    main()
