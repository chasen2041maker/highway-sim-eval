"""C3 第 4a 步：工具调用（function calling）跑通，先不碰 nuScenes。

和 3c 的区别：3c 是我们把流程写死——照片 + 数一次给全，模型答一次。工具调用是把几个“查东西的函数”的说明书交给模型，
模型自己决定要不要查、查哪个、参数填什么；它只“提出要调用”，函数由我们的代码跑，结果再送回给它，
来回几轮，直到它不再要工具、直接回答（或调用“交卷”工具）。这个“模型提要求 → 代码执行 → 结果送回”的循环就是智能体的骨架。

DeepSeek 官方接口的两条规矩（文档 api-docs.deepseek.com：guides/tool_calls、guides/thinking_mode、guides/vision）：
  1. 思考模式（默认开）+ 带工具时，模型每一轮的 reasoning_content（它的思考过程）要原样放回对话里再发，否则报 400。
     做法：它回什么消息，我们就把这条消息（含 reasoning_content、tool_calls）整条存进 messages。
  2. 图片只能放在 user 消息里，tool 消息只能是文字。工具要“给图”，就在 tool 结果里写“照片在下一条消息”，
     再补一条 user 消息放图。

两个小实验：
  ① 只有文字：get_speed(t) 查第 t 秒的车速（假数据），问“第 2 秒到第 3 秒车速变了多少”。看它调几次、参数对不对。
  ② 要看图：三张卡片 A / B / C，show_card(name) 给一张纯色图，问“哪张是红的”。验证“图片走 user 消息”这条路通不通。

运行（项目根目录，conda activate py310；.env 里填好 key、地址、模型）：
    python -m examples.c_review.c3_agent_hello
"""

from __future__ import annotations

import json

from PIL import Image

from examples.c_review.c3_vlm_hello import image_part
from examples.c_review.llm_client import call, config


def tool(name: str, description: str, properties: dict | None = None, required: list | None = None) -> dict:
    """一个工具的说明书（OpenAI 格式）：名字、干嘛用、参数（JSON Schema）。模型只看得到这份说明，看不到函数代码。"""
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []}}}


def assistant_message(msg: dict) -> dict:
    """模型这一轮的回复，原样存回对话。reasoning_content 必须带上（DeepSeek 思考模式 + 工具，不带报 400）。
    只留这四个字段，别的（比如以后接口多出来的字段）不往回发。"""
    out = {"role": "assistant", "content": msg.get("content") or ""}
    if msg.get("reasoning_content") is not None:
        out["reasoning_content"] = msg["reasoning_content"]
    if msg.get("tool_calls"):
        out["tool_calls"] = msg["tool_calls"]
    return out


def run_loop(model: str, messages: list, tools: list, run_tool, max_steps: int = 6,
             final_tool: str | None = None, send=call, log=print) -> dict:
    """智能体的循环。messages 会被就地追加（整段对话都在里面，方便事后看）。
    run_tool(name, args) 返回 (文字结果, 图片或 None)；工具出错（参数不对等）就把错误当结果告诉模型，让它自己改。
    停下的三种情况：
      answered    模型这一轮没要工具，直接回答了；
      final_tool  模型调用了“交卷”工具（final_tool），参数就是答案；
      max_steps   来回 max_steps 轮还没答完——防止它一直查下去，花光 token。
    返回 {"stopped", "answer"（文字）, "final_args"（交卷的参数）, "steps", "usage", "trace"（每次调用了什么）}。"""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "cache_hit_tokens": 0}
    trace = []
    for step in range(1, max_steps + 1):
        r = send("/chat/completions", {"model": model, "messages": messages, "tools": tools})
        u = r.get("usage", {})
        usage["prompt_tokens"] += u.get("prompt_tokens", 0)
        usage["completion_tokens"] += u.get("completion_tokens", 0)
        usage["reasoning_tokens"] += (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        usage["cache_hit_tokens"] += u.get("prompt_cache_hit_tokens", 0)   # 和上一轮开头一样的部分，DeepSeek 缓存命中、更便宜
        msg = r["choices"][0]["message"]
        messages.append(assistant_message(msg))
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"stopped": "answered", "answer": msg.get("content") or "", "final_args": None,
                    "steps": step, "usage": usage, "trace": trace}
        log(f"  第 {step} 轮：要调用 " + "、".join(f"{c['function']['name']}({c['function']['arguments']})" for c in calls))
        images = []
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args, text, img = None, "出错：参数不是合法的 JSON", None
            else:
                if name == final_tool:
                    trace.append({"step": step, "tool": name, "args": args})
                    return {"stopped": "final_tool", "answer": None, "final_args": args,
                            "steps": step, "usage": usage, "trace": trace}
                try:
                    text, img = run_tool(name, args)
                except Exception as e:                    # 工具名不存在、参数越界……都告诉模型，让它改
                    text, img = f"出错：{e}", None
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": text})
            trace.append({"step": step, "tool": name, "args": args, "result": text[:200]})
            log(f"     → {text[:120]}")
            if img is not None:
                images.append((f"{name}({c['function']['arguments']})", img))
        if images:                                        # 图片只能放 user 消息：按顺序补一条
            content = [{"type": "text", "text": "下面是刚才工具要的照片，按调用顺序："}]
            for label, img in images:
                content += [{"type": "text", "text": label}, image_part(img)]
            messages.append({"role": "user", "content": content})
    return {"stopped": "max_steps", "answer": None, "final_args": None,
            "steps": max_steps, "usage": usage, "trace": trace}


def show(result: dict) -> str:
    u = result["usage"]
    return (f"停下原因：{result['stopped']}，共 {result['steps']} 轮；token：发过去 {u['prompt_tokens']:,}"
            f"（其中缓存命中 {u['cache_hit_tokens']:,}）+ 回答 {u['completion_tokens']:,}（其中思考 {u['reasoning_tokens']:,}）")


# ---------- 实验 ①：只有文字 ----------
SPEEDS = {0: 10.0, 1: 10.5, 2: 11.2, 3: 9.4, 4: 8.1}          # 假数据：第 t 秒的车速 m/s


def speed_tool(name, args):
    t = args["t"]
    if t not in SPEEDS:
        raise ValueError(f"只有第 0–4 秒的数据，没有第 {t} 秒")
    return f"第 {t} 秒车速 {SPEEDS[t]} m/s", None


# ---------- 实验 ②：要看图 ----------
CARDS = {"A": (0, 170, 0), "B": (200, 0, 0), "C": (0, 0, 200)}  # 绿、红、蓝


def card_tool(name, args):
    color = CARDS[args["name"]]
    return f"卡片 {args['name']} 的照片在下一条消息里", Image.new("RGB", (64, 64), color)


def main():
    _, base, model = config()
    if not model:
        print("先在 .env 里填 OPENAI_MODEL")
        return
    print(f"地址 {base}，模型 {model}\n")

    print("① 只有文字：get_speed")
    tools = [tool("get_speed", "查第 t 秒我的车速（m/s）。一次查一个时刻。",
                  {"t": {"type": "integer", "description": "第几秒，0–4"}}, ["t"])]
    messages = [{"role": "user", "content": "第 2 秒到第 3 秒，我的车速变了多少 m/s？是加速还是减速？用工具查，不要猜。"}]
    r = run_loop(model, messages, tools, speed_tool)
    print(f"  回答：{(r['answer'] or '').strip()}")
    print(f"  {show(r)}")
    print("  （正确：11.2 → 9.4，减速 1.8 m/s）\n")

    print("② 要看图：show_card")
    tools = [tool("show_card", "看一张卡片的照片。", {"name": {"type": "string", "enum": ["A", "B", "C"]}}, ["name"])]
    messages = [{"role": "user", "content": "有三张卡片 A、B、C，每张是一种纯色。用 show_card 工具看，找出红色的是哪张，只回答字母。"}]
    r = run_loop(model, messages, tools, card_tool)
    print(f"  回答：{(r['answer'] or '').strip()}")
    print(f"  {show(r)}")
    print("  （正确：B。答对 = 图片走 user 消息这条路通了）")


if __name__ == "__main__":
    main()
