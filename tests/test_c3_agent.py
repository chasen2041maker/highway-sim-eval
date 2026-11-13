"""C3 4a：智能体循环（不连模型：用一个假服务器，按 DeepSeek 的规矩检查我们发过去的对话）。"""

import json
import math

from PIL import Image

from examples.c_review.c3_agent_hello import run_loop, tool


def call_msg(i, name, args, raw=None):
    return {"id": f"c{i}", "type": "function",
            "function": {"name": name, "arguments": raw if raw is not None else json.dumps(args)}}


class FakeServer:
    """按顺序吐出预先写好的回复；每次收到请求先检查：
    带工具时，之前每条 assistant 消息都得带 reasoning_content（DeepSeek 规矩 1）；图片只能在 user 消息里（规矩 2）。"""

    def __init__(self, replies):
        self.replies, self.bodies = list(replies), []

    def __call__(self, path, body):
        self.bodies.append(json.loads(json.dumps(body)))   # 存一份当时的样子
        for m in body["messages"]:
            if m["role"] == "assistant":
                assert "reasoning_content" in m, "HTTP 400：没带回 reasoning_content"
            if m["role"] != "user" and isinstance(m.get("content"), list):
                assert False, "HTTP 400：图片只能在 user 消息里"
        msg = {"role": "assistant", "reasoning_content": "想一想", **self.replies.pop(0)}
        return {"choices": [{"message": msg}], "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                                                          "completion_tokens_details": {"reasoning_tokens": 5}}}


TOOLS = [tool("get_speed", "查车速", {"t": {"type": "integer"}}, ["t"])]


def speed(name, args):
    if args["t"] > 4:
        raise ValueError("没有这一秒")
    return f"第 {args['t']} 秒 10 m/s", None


def test_two_calls_then_answer():
    srv = FakeServer([{"content": None, "tool_calls": [call_msg(1, "get_speed", {"t": 2}), call_msg(2, "get_speed", {"t": 3})]},
                      {"content": "减速 1.8"}])
    msgs = [{"role": "user", "content": "问"}]
    r = run_loop("m", msgs, TOOLS, speed, send=srv, log=lambda *a: None)
    assert r["stopped"] == "answered" and r["answer"] == "减速 1.8" and r["steps"] == 2
    assert [t["args"] for t in r["trace"]] == [{"t": 2}, {"t": 3}]
    # 第二次请求：user、assistant（带 tool_calls）、两条 tool，tool_call_id 对得上
    roles = [m["role"] for m in srv.bodies[1]["messages"]]
    assert roles == ["user", "assistant", "tool", "tool"]
    assert [m["tool_call_id"] for m in srv.bodies[1]["messages"][2:]] == ["c1", "c2"]
    assert r["usage"] == {"prompt_tokens": 200, "completion_tokens": 40, "reasoning_tokens": 10, "cache_hit_tokens": 0}


def test_tool_error_goes_back_to_model():
    srv = FakeServer([{"tool_calls": [call_msg(1, "get_speed", {"t": 9})]},
                      {"tool_calls": [call_msg(2, "get_speed", None, raw="{t: 2")]},
                      {"content": "好"}])
    r = run_loop("m", [{"role": "user", "content": "问"}], TOOLS, speed, send=srv, log=lambda *a: None)
    assert r["trace"][0]["result"].startswith("出错：没有这一秒")
    assert r["trace"][1]["result"] == "出错：参数不是合法的 JSON"
    assert r["stopped"] == "answered"


def test_image_goes_in_a_user_message():
    srv = FakeServer([{"tool_calls": [call_msg(1, "show", {"n": "A"})]}, {"content": "B"}])
    show = lambda name, args: ("照片在下一条消息里", Image.new("RGB", (8, 8)))
    run_loop("m", [{"role": "user", "content": "问"}], [tool("show", "看")], show, send=srv, log=lambda *a: None)
    last = srv.bodies[1]["messages"][-1]
    assert last["role"] == "user" and any(p["type"] == "image_url" for p in last["content"])


def test_final_tool_and_max_steps():
    srv = FakeServer([{"tool_calls": [call_msg(1, "submit", {"verdict": "没事"})]}])
    r = run_loop("m", [{"role": "user", "content": "问"}], TOOLS, speed, final_tool="submit", send=srv, log=lambda *a: None)
    assert r["stopped"] == "final_tool" and r["final_args"] == {"verdict": "没事"}

    srv = FakeServer([{"tool_calls": [call_msg(i, "get_speed", {"t": 1})]} for i in range(3)])
    r = run_loop("m", [{"role": "user", "content": "问"}], TOOLS, speed, max_steps=3, send=srv, log=lambda *a: None)
    assert r["stopped"] == "max_steps" and r["steps"] == 3 and len(r["trace"]) == 3


# ---------- 4b：Review 智能体的工具（假的几帧，不读 nuScenes） ----------

from examples.c_review.c3_agent import make_tools, motion_text
from examples.c_review.c3_eval import tool_stats
from examples.c_review.c3_review import check_answer


def fake_frames():
    """我沿 x 轴 10 m/s 开，每 0.5 秒一帧；一个行人在我前方 15 米、右边 4 米，往我左边走（+y）2 m/s。"""
    frames = []
    for i in range(3):
        ego_x = 5.0 * i
        ped_y = -5.0 + 1.0 * i
        frames.append({"t": 0.5 * i, "v": None if i == 0 else 10.0, "ego_xy": (ego_x, 0.0), "ego_yaw": 0.0,
                       "objs": [{"inst": "p", "cat": "human.pedestrian.adult", "xy": (20.0, ped_y),
                                 "ex": 20.0 - ego_x, "ey": ped_y, "w": 0.6}]})
    return frames


def test_motion_text_directions():
    frames = fake_frames()
    assert motion_text(frames, 1, frames[1]["objs"][0]) == "从右往左横着走，2.0 m/s"
    for i, f in enumerate(frames):                       # 反过来走 = 从左往右
        f["objs"][0]["xy"] = (20.0, 5.0 - 1.0 * i)
    assert motion_text(frames, 1, frames[1]["objs"][0]).startswith("从左往右")


def test_road_users_and_my_motion_text():
    frames = fake_frames()
    run = make_tools(None, frames, 1, None)
    text, img = run("road_users", {})
    assert img is None and "成年行人：前方 15.0 米、右 4.0 米，离我的路 4.0 米，从右往左横着走，2.0 m/s" in text
    text, _ = run("road_users", {"max_m": 10})
    assert text.startswith("我前方 10 米以内没有车和人")
    text, _ = run("my_motion", {})
    assert "车速 不知道" in text and "第 0.50 秒（相对这一刻 +0.0 秒）：车速 10.0 m/s，加速度 不知道  ← 这一刻" in text


def test_tool_errors():
    run = make_tools(None, fake_frames(), 1, None)
    for name, args in [("look_at", {"offset": 9}), ("look_at", {"offset": 3}), ("fly", {})]:
        try:
            run(name, args)
        except ValueError:
            continue
        assert False, (name, args)


def test_submit_answer_checked_like_3c():
    assert check_answer({"verdict": "没事", "cause": "无", "evidence": "x"})["cause"] is None
    assert check_answer({"verdict": "值得看", "cause": "横穿", "evidence": "x"})["valid"]
    assert not check_answer({"verdict": "值得看", "cause": "无", "evidence": "x"})["valid"]
    assert not check_answer({"verdict": "有点险", "cause": "无"})["valid"]


def test_tool_stats():
    rows = [{"tools": ["look_at", "look_at", "road_users"], "steps": 3, "stopped": "final_tool", "cache_hit_tokens": 10},
            {"tools": [], "steps": 1, "stopped": "final_tool", "cache_hit_tokens": 0}]
    s = tool_stats(rows)
    assert s["counts"] == {"look_at": 2, "road_users": 1} and s["no_tool"] == 1 and s["steps"] == 2.0
    assert s["stopped"] == {"final_tool": 2} and s["cache"] == 10


# ---------- 4c 之后：路线写进事实、road_users 加前后几秒离我的路多远 ----------

from examples.c_review.c3_agent import track_text
from examples.c_review.c3_pick import my_path
from examples.c_review.c3_review import route_text


def long_frames(turn_deg_per_frame=0.0):
    """每 0.5 秒一帧，13 帧；我 10 m/s；可以每帧转一点车头。行人在第 6 帧（中间那帧）前方 15 米、右 4 米，往左 1 m/s。"""
    frames, x, y, yaw = [], 0.0, 0.0, 0.0
    for i in range(13):
        if i:
            x += 5.0 * math.cos(yaw)
            y += 5.0 * math.sin(yaw)
            yaw += math.radians(turn_deg_per_frame)
        frames.append({"t": 0.5 * i, "v": None if i == 0 else 10.0, "ego_xy": (x, y), "ego_yaw": yaw, "objs": []})
    for i, f in enumerate(frames):                       # 行人：地图上 (45, −4 + 0.5 (i−6))，第 6 帧在我前方 15 米、右 4 米
        f["objs"] = [{"inst": "p", "cat": "human.pedestrian.adult", "xy": (45.0, -4.0 + 0.5 * (i - 6)),
                      "ex": 45.0 - f["ego_xy"][0], "ey": -4.0 + 0.5 * (i - 6), "w": 0.6}]
    return frames


def test_route_text_straight_and_turning():
    text = route_text(long_frames(), 6)
    assert text.startswith("1 秒后：前 10.0 米、左 0.0 米，车头方向不变")
    assert "4 秒后：录像到头了" in text and text.endswith("合起来：基本直行，一共开了 30.0 米")
    text = route_text(long_frames(turn_deg_per_frame=10.0), 0)
    assert "1 秒后：" in text and "车头左转 20°" in text and "合起来：左转约 100°" in text


def test_track_text_says_when_it_walks_into_my_path():
    frames = long_frames()
    path = my_path(frames, 6)
    text = track_text(frames, 6, frames[6]["objs"][0], path)
    # 离我的路：5 → 4 → 3 → 2 → 1 米（每秒往左 1 米），门槛 1.75 + 0.3 = 2.05 → 3 秒内会走进
    assert text.endswith("：5.0 → 4.0 → 3.0 → 2.0 → 1.0，3 秒内会走进我的路")


def test_all_variant_puts_route_and_road_users_in_the_facts():
    from examples.c_review.c3_eval import VARIANTS, variant_facts
    text = variant_facts(long_frames(), 6, VARIANTS["all"])
    assert "合起来：基本直行" in text and "下面这段也是测量值" in text and "3 秒内会走进我的路" in text
    plain = variant_facts(long_frames(), 6, {})
    assert "合起来" not in plain and "离我的路" not in plain
