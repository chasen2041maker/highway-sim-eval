"""C3 第 4b 步：工具调用版 Review 智能体。

和 3c 一个模型比，起点完全一样：同一张照片（规则挑中的东西画橙框）、同样的事实、同样的两把尺子。
多出来的是 3 个查东西的工具，查不查、查哪个、查几次由模型自己定；最后用“交卷”工具交答案：
  look_at(offset)     前后几帧的前视照片（关键帧每 0.5 秒一帧，最多前后 4 帧 = 2 秒），规则挑中的东西照样框出来。
                      3c 只有一张静止的照片，看不出东西往哪走；这个工具让它看“动起来”的样子。
  my_motion()         我前后 2 秒的车速、加速度（测量值）。看我是不是一直在刹、刹了多久。
  road_users(max_m)   这一刻我前方的车和人（人工标注的 3D 框，相当于完美的感知）：在哪、离我的路多远、往哪走、多快。
                      照片上估距离不准（3d 看图员找错人），这里给量出来的数。
  submit_answer(...)  交卷。verdict、cause 的取值写死在说明书里（enum），交上来再用 3c 的规矩校验一遍。
这些都用到了“这一刻之后”的数据（后面几帧的照片、接下来 5 秒的路），只有录好的数据能这么做，和 C3 第 2 步一样是离线复核。

护栏：最多 6 轮；工具出错（offset 超范围等）把错误告诉它，让它自己改；没交卷直接用文字答了，照 3c 的办法从文字里取 JSON。
每一轮都要把整段对话（含之前的照片）重发一遍，所以多查一次，后面每轮都更贵；DeepSeek 对“和上一轮开头一样”的部分有缓存，
命中的部分便宜，token 里单独打印。

先拿 3c 那 3 条调参题看它查了什么（4b），再在 51 条答案卷上和 3c 比（4c：python -m examples.c_review.c3_eval agent）。

结果（11-13，deepseek-flash）：
  4b 3 条调参题 3/3，23,403 token（3c 约 7,600）；每条都把三个工具查一遍，提示词里“每查一次都要花钱”不管用。
     依据变了：3c 靠看照片猜，这里引用量出来的数（“前后 2 秒车速都是 0”“工人离我的路 4.9 米”）。
  4c 51 条：平均 2.4 轮，4 条一个工具没查（路上没东西），难的查 4–6 次；344,122 token（单模型 v2 70,326）。
     4 个错逐条核对：0103_13 是它的错（SUV 这一刻停着、离我的路 6.9 米，2.5 秒后开进我的路 → road_users 只给这一刻，
     缺“前后几秒离我的路多远”；还把 −2.5 ~ −3.2 的刹车说成平缓）；1094_13 是答案卷的错（打伞行人离我左转的路 7.3 米，
     标注时只看了照片），复核后改成“没事”；0916_05、1094_05 是规范 v2 没写“多远、几秒、中间隔着车算不算”。
     改完答案卷：工具版 48/51、召回 1/2、精确 1/3；单模型 v2 49/51、2/2、2/4。剩下的 2 条值得看是同一辆 SUV 的前后两帧，
     mini 分不出谁更好。不在这 51 条上再调；下一版（轨迹工具、规范 v3）到 nuScenes 全量里另抽新题考。

运行（项目根目录，conda activate py310；.env 里填好 key、地址、模型）：
    python -m examples.c_review.c3_agent
"""

from __future__ import annotations

import json
import math

from examples.c_review.c3_agent_hello import run_loop, show, tool
from examples.c_review.c3_pick import (LANE_HALF_M, MOVING_MPS, TTC_MAX_S, accel, draw_box, find, is_road_user,
                                       its_velocity, my_path, path_dist, scene_frames)
from examples.c_review.c3_review import (CASES, CAUSE_RULE, CAUSES, TRUST_PICKED, TRUST_RANDOM, VERDICTS, WHY_PICKED,
                                         WHY_RANDOM, check_answer, facts, parse_answer, picked, review_photo)
from examples.c_review.c3_scene_view import ZH
from examples.c_review.c3_vlm_hello import image_part
from examples.c_review.llm_client import config
from examples.c_review.nuscenes_tables import load

MAX_STEPS = 6          # 最多来回几轮
LOOK_FRAMES = 4        # look_at 最多往前 / 往后看几帧（1 帧 0.5 秒）
NEAR_M = 40.0          # road_users 默认列多少米以内
MAX_USERS = 12         # road_users 最多列几个
NO_CAUSE = "无"        # 交卷时 verdict 不是危险 / 值得看，cause 选它
TRACK_OFFSETS = (-2, 0, 2, 4, 6)   # track 变体：看它在这些帧（约 −1、0、+1、+2、+3 秒）离我的路多远；3 秒和规则的 TTC 门槛一样

def tool_specs(track: bool = False) -> list:
    """工具说明书。track=True 时 road_users 的说明里加一句“还给前后几秒离我的路多远”。"""
    specs = json.loads(json.dumps(TOOLS))
    if track:
        f = specs[2]["function"]
        f["description"] += f"每个还给“从 1 秒前到 {TTC_MAX_S:.0f} 秒后离我的路多远”，看它是不是正在走进我的路。"
    return specs


TOOLS = [
    tool("look_at", "看这一刻前后某一帧的前视照片（关键帧每 0.5 秒一帧）。用来看清东西在怎么动、会不会走进我的路。"
                    "规则挑中的那个东西在那一帧里也会用橙色框框出来。",
         {"offset": {"type": "integer", "description": f"相对这一刻差几帧，−{LOOK_FRAMES} 到 {LOOK_FRAMES}"
                                                       "（负数 = 之前，正数 = 之后；1 帧 = 0.5 秒）"}}, ["offset"]),
    tool("my_motion", "我自己前后 2 秒的车速和加速度（测量值，可信）。用来看我是不是在刹车、刹了多久、刹得多猛。"),
    tool("road_users", "这一刻我前方的车和人（人工标注的 3D 框，可信）：是什么、在我前方几米、偏左偏右几米、"
                       f"离我接下来要走的路多远、往哪个方向走、多快。离我的路近的排前面，最多 {MAX_USERS} 个。",
         {"max_m": {"type": "number", "description": f"只列离我多少米以内的，默认 {NEAR_M:.0f}"}}),
    tool("submit_answer", "交卷：两把尺子的答案。查够了就调用它，不要用文字回答。",
         {"verdict": {"type": "string", "enum": list(VERDICTS)},
          "cause": {"type": "string", "enum": list(CAUSES) + [NO_CAUSE],
                    "description": f"verdict 是“危险”或“值得看”才选原因，否则选“{NO_CAUSE}”"},
          "evidence": {"type": "string", "description": "一句话：照片里看到了什么、工具查到了什么，让你这么判"}},
         ["verdict", "cause", "evidence"]),
]


def agent_prompt(fact_text: str, picked: bool = True, track: bool = False) -> str:
    """起点和 3c 的 build_prompt 一样（同样的事实、同样的尺子），只是多了工具的说明，答案改成调用 submit_answer。"""
    verdicts = "\n".join(f"- {k}：{v}" for k, v in VERDICTS.items())
    causes = "\n".join(f"- {k}：{v}" for k, v in CAUSES.items())
    return f"""你在审一段自动驾驶路采数据（录好的，可以看这一刻前后的数据）。下面是这一刻车的前视摄像头照片，以及程序给的事实。
{TRUST_PICKED if picked else TRUST_RANDOM}
{WHY_PICKED if picked else WHY_RANDOM}

事实：
{fact_text}

你可以先用工具查更多再判断，也可以不查：
- look_at：看前后几帧的照片，看清东西在怎么动；
- my_motion：我前后 2 秒的车速、加速度；
- road_users：这一刻我前方的车和人，在哪、离我的路多远、往哪走、多快{"；还有它从 1 秒前到 3 秒后离我的路多远" if track else ""}。
每查一次都要花钱：这张照片已经能判断清楚，就直接交卷。判断好了调用 submit_answer 交卷，不要用文字回答。

两把尺子，只能从格子里选：
尺子一，值不值（必选一个）：
{verdicts}
尺子二，原因（只有选了“危险”或“值得看”才选，否则选“{NO_CAUSE}”）：
{causes}
{CAUSE_RULE}"""


def motion_text(frames, k, o) -> str:
    """它往哪走、多快：按它的行驶方向和我的车头差几度分四类。"""
    v = its_velocity(frames, k, o["inst"])
    if v is None:
        return "怎么动不知道（前后帧里没有它）"
    speed = math.hypot(v[0], v[1])
    if speed < MOVING_MPS:
        return "基本停着"
    diff = math.degrees(math.atan2(v[1], v[0]) - frames[k]["ego_yaw"])
    diff = (diff + 180) % 360 - 180                       # 换到 −180° 到 180°；正 = 往我的左边偏
    if abs(diff) < 45:
        d = "和我同向走"
    elif abs(diff) > 135:
        d = "和我反向走（迎面）"
    elif diff > 0:
        d = "从右往左横着走"
    else:
        d = "从左往右横着走"
    return f"{d}，{speed:.1f} m/s"


def track_text(frames, k, o, path) -> str:
    """它在 −1、0、+1、+2、+3 秒（大约）离我的路多远；这一刻不在路上、3 秒内会走进来的，明说。
    4c 发现：road_users 只给这一刻，scene-0103 第 13 帧那辆 SUV 停着、离我的路 6.9 米，模型判“没事”，
    可 3 秒后它开进了我的路（6.9 → 1.2 米）。"""
    near = LANE_HALF_M + o["w"] / 2
    dists = []
    for off in TRACK_OFFSETS:
        m = k + off
        other = find(frames[m], o["inst"]) if 0 <= m < len(frames) else None
        dists.append(None if other is None else path_dist(path, other["xy"]))
    shown = " → ".join("—" if d is None else f"{d:.1f}" for d in dists)
    now = dists[TRACK_OFFSETS.index(0)]
    later = [d for off, d in zip(TRACK_OFFSETS, dists) if off > 0 and d is not None]
    note = ""
    if now is not None and now >= near and any(d < near for d in later):
        note = f"，{TTC_MAX_S:.0f} 秒内会走进我的路"
    return f"离我的路（1 秒前 → 这一刻 → 1、2、3 秒后，米；— = 那一帧没有它）：{shown}{note}"


def make_tools(T, frames, k, target, track: bool = False):
    """返回 run_tool(name, args)：三个查东西的工具，都只读录好的数据。target = 规则挑中的那个东西（没有就 None）。
    track：road_users 每个东西多给一行“从 1 秒前到 3 秒后离我的路多远”（4c 之后的变体，轮次名 route）。"""
    path = my_path(frames, k)

    def rel(m):
        return f"第 {frames[m]['t']:.2f} 秒（相对这一刻 {frames[m]['t'] - frames[k]['t']:+.1f} 秒）"

    def look_at(args):
        off = int(args["offset"])
        if not -LOOK_FRAMES <= off <= LOOK_FRAMES:
            raise ValueError(f"offset 只能是 −{LOOK_FRAMES} 到 {LOOK_FRAMES}")
        m = k + off
        if not 0 <= m < len(frames):
            raise ValueError(f"这段只有第 1–{len(frames)} 帧，这一刻是第 {k + 1} 帧，没有第 {m + 1} 帧")
        who = find(frames[m], target["inst"]) if target else None
        note = ""
        if target:
            note = "，橙色框是规则挑中的那个东西" if who else "，规则挑中的那个东西这一帧里没有（出了视野或没标）"
        return f"{rel(m)}的前视照片在下一条消息里{note}。", draw_box(T, frames[m], who).resize((800, 450))

    def my_motion(args):
        lines = []
        for m in range(max(0, k - LOOK_FRAMES), min(len(frames), k + LOOK_FRAMES + 1)):
            v, a = frames[m]["v"], accel(frames, m)
            v = "不知道" if v is None else f"{v:.1f} m/s"
            a = "不知道" if a is None else f"{round(a, 2) + 0.0:.2f} m/s²"
            lines.append(f"{rel(m)}：车速 {v}，加速度 {a}{'  ← 这一刻' if m == k else ''}")
        return "我的车速和加速度（测量值；加速度负数 = 在减速）：\n" + "\n".join(lines), None

    def road_users(args):
        max_m = float(args.get("max_m") or NEAR_M)
        # 按离“我的路”多近排（不是离我多近）：路边远处停着的车再近也不相干，路上的、快走上来的排前面
        near = [(path_dist(path, o["xy"]), o) for o in frames[k]["objs"]
                if is_road_user(o) and o["ex"] > 0 and math.hypot(o["ex"], o["ey"]) <= max_m]
        near.sort(key=lambda x: x[0])
        if not near:
            return f"我前方 {max_m:.0f} 米以内没有车和人。", None
        lines = []
        for d, o in near[:MAX_USERS]:
            side = f"左 {o['ey']:.1f} 米" if o["ey"] >= 0 else f"右 {-o['ey']:.1f} 米"
            where = f"前方 {o['ex']:.1f} 米、{side}"
            on = "在我的路上" if d < LANE_HALF_M + o["w"] / 2 else f"离我的路 {d:.1f} 米"
            boxed = "（橙色框）" if target and o["inst"] == target["inst"] else ""
            lines.append(f"- {ZH.get(o['cat'], o['cat'])}{boxed}：{where}，{on}，{motion_text(frames, k, o)}"
                         + (f"\n    {track_text(frames, k, o, path)}" if track else ""))
        more = f"\n（还有 {len(near) - MAX_USERS} 个离我的路更远的没列）" if len(near) > MAX_USERS else ""
        return (f"这一刻我前方 {max_m:.0f} 米以内的车和人（“我的路”= 录像里我接下来 5 秒实际开过的路，"
                f"离它 < 半个车道 + 半个身宽算在路上）：\n" + "\n".join(lines) + more), None

    tools = {"look_at": look_at, "my_motion": my_motion, "road_users": road_users}

    def run_tool(name, args):
        if name not in tools:
            raise ValueError(f"没有叫 {name} 的工具")
        return tools[name](args)

    return run_tool


def review_agent(model, T, frames, k, use_path=True, same_dir=True, log=print,
                 route: bool = False, track: bool = False) -> dict:
    """复核一帧，返回和 c3_eval 一样格式的一行，多存：几轮、调了哪些工具、为什么停。
    route：事实里加我接下来 5 秒的路；track：road_users 加前后几秒离我的路多远。"""
    p = picked(frames, k, use_path, same_dir)
    fact_text = facts(frames, k, use_path, same_dir, with_route=route)
    messages = [{"role": "user", "content": [
        {"type": "text", "text": agent_prompt(fact_text, p is not None, track)},
        image_part(review_photo(T, frames, k, use_path, same_dir))]}]
    r = run_loop(model, messages, tool_specs(track), make_tools(T, frames, k, p["who"] if p else None, track),
                 max_steps=MAX_STEPS, final_tool="submit_answer", log=log)
    if r["stopped"] == "final_tool":
        a = check_answer(r["final_args"])
        raw = json.dumps(r["final_args"], ensure_ascii=False)
    elif r["stopped"] == "answered":                       # 没按要求交卷：照 3c 的办法从文字里取 JSON
        a, raw = parse_answer(r["answer"]), r["answer"]
    else:
        a, raw = {"valid": False, "why": f"{MAX_STEPS} 轮还没交卷"}, ""
    u = r["usage"]
    return {"tokens": u["prompt_tokens"] + u["completion_tokens"], "cache_hit_tokens": u["cache_hit_tokens"],
            "steps": r["steps"], "stopped": r["stopped"], "show": show(r),
            "tools": [t["tool"] for t in r["trace"] if t["tool"] != "submit_answer"],
            "raw": raw.strip(), "valid": a["valid"], "verdict": a.get("verdict"), "cause": a.get("cause"),
            "evidence": a.get("evidence", ""), "why": a.get("why", "")}


def main():
    _, _, model = config()
    if not model:
        print("先在 .env 里填 OPENAI_MODEL")
        return
    T = load()
    scenes = {s["name"]: s for s in T["scene"].values()}
    right = total = 0
    for name, frame_no, (use_path, same_dir), (h_verdict, h_cause) in CASES:
        frames = scene_frames(T, scenes[name])
        print(f"\n{name} 第 {frame_no} 帧    人的答案：{h_verdict}{' / ' + h_cause if h_cause else ''}")
        row = review_agent(model, T, frames, frame_no - 1, use_path, same_dir)
        total += row["tokens"]
        if not row["valid"]:
            print(f"  模型：无效（{row['why']}）  原话：{row['raw'][:200]}")
        else:
            ok = row["verdict"] == h_verdict and row["cause"] == h_cause
            right += ok
            print(f"  模型：{row['verdict']}{' / ' + row['cause'] if row['cause'] else ''}    {'✓' if ok else '✗'}")
            print(f"  依据：{row['evidence']}")
        print(f"  查了：{'、'.join(row['tools']) or '什么都没查'}；{row['show']}")
    print(f"\n两把尺子都对：{right} / {len(CASES)}；一共 {total:,} token（3c 一个模型：3 / 3，约 7,600 token）")


if __name__ == "__main__":
    main()
