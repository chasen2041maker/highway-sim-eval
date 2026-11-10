"""B3 第 3 步（中）：录像存成 MCAP（多轨录音带），再按“轨道 + 时间段”读回来。

outputs/recordings/b1_bank_p0.parquet 里 5 道题，每道题存一个 .mcap 文件（outputs/recordings/b1_q<题号>.mcap），4 条轨道：
  /ego       我在哪、多快（真实世界）
  /cutter    加塞那辆车在哪（真实世界）
  /seen      考生看到的那张小表（几辆车 × 5 个数）
  /decision  考生的决定：认没认出前车、踩多大
每条消息 = 时间戳（纳秒）+ 内容（JSON）；每条轨道先登记“它的消息长什么样”（schema）。
读的时候可以只要某几条轨道、某一段时间——这是 MCAP 比一张表方便的地方。
运行（在项目根目录，先 conda activate py310；先跑过 b3_record）：
    python -m examples.b_eval.b3_mcap
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
from mcap.reader import make_reader
from mcap.writer import Writer

REC_DIR = Path(__file__).resolve().parents[2] / "outputs" / "recordings"
NUMBER = {"type": "number"}
TOPICS = {                                         # 轨道名: (schema 名字, 这条轨道的消息长什么样)
    "/ego":      ("Ego",      {"type": "object", "properties": {"x": NUMBER, "y": NUMBER, "v": NUMBER}}),
    "/cutter":   ("Cutter",   {"type": "object", "properties": {"x": NUMBER, "y": NUMBER}}),
    "/seen":     ("Seen",     {"type": "object", "properties": {"rows": {"type": "array",
                                                                         "items": {"type": "array", "items": NUMBER}}}}),
    "/decision": ("Decision", {"type": "object", "properties": {"lead_seen": {"type": "boolean"}, "accel_cmd": NUMBER}}),
}


def to_ns(t_s: float) -> int:
    """第几秒 → 纳秒（MCAP 的时间戳单位）。"""
    return int(round(t_s * 1e9))


def write_mcap(frames: list[dict], path: Path) -> None:
    """一道题的帧 → 一个 .mcap 文件：先登记 4 条轨道，再每一帧往每条轨道各写一条消息。"""
    with path.open("wb") as f:
        writer = Writer(f)
        writer.start(profile="", library="highway-sim-eval")
        channels = {}
        for topic, (schema_name, schema) in TOPICS.items():
            schema_id = writer.register_schema(name=schema_name, encoding="jsonschema",
                                               data=json.dumps(schema).encode())
            channels[topic] = writer.register_channel(topic=topic, message_encoding="json", schema_id=schema_id)
        for fr in frames:
            t = to_ns(fr["t_s"])
            messages = {
                "/ego": {"x": fr["ego_x"], "y": fr["ego_y"], "v": fr["ego_v"]},
                "/cutter": {"x": fr["cutter_x"], "y": fr["cutter_y"]},
                "/seen": {"rows": fr["seen"]},
                "/decision": {"lead_seen": fr["lead_seen"], "accel_cmd": fr["accel_cmd"]},
            }
            for topic, msg in messages.items():
                writer.add_message(channel_id=channels[topic], log_time=t, publish_time=t,
                                   data=json.dumps(msg).encode())
        writer.finish()


def read_mcap(path: Path, topics: list[str] | None = None, start_s: float | None = None, end_s: float | None = None):
    """按轨道、按时间段读：一条一条交回（轨道名, 第几秒, 内容）。end_s 那一刻不算在内。"""
    start = None if start_s is None else to_ns(start_s)
    end = None if end_s is None else to_ns(end_s)
    with path.open("rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages(topics=topics, starting_at=start, ending_before=end):
            yield channel.topic, message.log_time / 1e9, json.loads(message.data)


def summary(path: Path) -> dict:
    """不用把整个文件读一遍，就知道每条轨道有几条消息（MCAP 文件尾巴上存着目录）。"""
    with path.open("rb") as f:
        s = make_reader(f).get_summary()
    counts = {}
    for channel_id, channel in s.channels.items():
        counts[channel.topic] = s.statistics.channel_message_counts[channel_id]
    return counts


def load_frames(parquet: Path) -> dict[int, list[dict]]:
    """读 b3_record 录的 Parquet：{第几题: [一帧一个字典]}。"""
    rel = duckdb.execute("SELECT * FROM read_parquet($p) ORDER BY question, k", {"p": parquet.as_posix()})
    names = [d[0] for d in rel.description]
    by_question = {}
    for row in rel.fetchall():
        fr = dict(zip(names, row))
        by_question.setdefault(fr["question"], []).append(fr)
    return by_question


def main():
    frames = load_frames(REC_DIR / "b1_bank_p0.parquet")
    print("① 每道题存一个 .mcap 文件")
    for n, fr in frames.items():
        path = REC_DIR / f"b1_q{n}.mcap"
        write_mcap(fr, path)
        print(f"  第 {n} 题：{len(fr)} 帧 → {path.name}（{path.stat().st_size / 1000:.0f} KB）")

    q3 = REC_DIR / "b1_q3.mcap"
    print(f"\n② 看目录（不读消息）：{q3.name} 每条轨道几条消息")
    for topic, n in summary(q3).items():
        print(f"  {topic:10s} {n} 条")

    print("\n③ 只读一条轨道、一段时间：第 3 题 /decision，第 0.5 到 1.0 秒")
    for topic, t, msg in read_mcap(q3, topics=["/decision"], start_s=0.5, end_s=1.0):
        print(f"  第 {t:.1f} 秒  认出前车：{'是' if msg['lead_seen'] else '否'}  踩 {msg['accel_cmd']:6.2f}")

    print("\n④ 同一时刻读好几条轨道：第 3 题第 0.8 秒")
    for topic, t, msg in read_mcap(q3, topics=["/ego", "/cutter", "/decision"], start_s=0.8, end_s=0.81):
        print(f"  {topic:10s} {msg}")


if __name__ == "__main__":
    main()
