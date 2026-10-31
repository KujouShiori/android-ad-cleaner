"""引擎事件（ADR-0004）：在人类可读的行之外，向客户端报一条它自己看不到的状态。

只有客户端设了 AAC_EVENTS 才发；直接跑脚本的人看不到这一行。客户端认固定前缀，
剥掉之后再解析，所以机器行不会进界面、也不会进上报日志。
"""
import json
import os

PREFIX = "#aac:event "

KINDS = ("paused", "resumed", "locked", "ui_busy", "link_lost")


def emit(kind):
    """发一条事件。kind 拼错是编程错误，直接抛；没设 AAC_EVENTS 时什么都不做。"""
    if kind not in KINDS:
        raise ValueError(f"未定义的事件：{kind}")
    if not os.environ.get("AAC_EVENTS"):
        return
    print(PREFIX + json.dumps({"kind": kind}), flush=True)


def is_event(line):
    return line.startswith(PREFIX)


def parse(line):
    """事件行 → kind；不是事件行、或解析不出来，一律返回 None。"""
    if not is_event(line):
        return None
    try:
        kind = json.loads(line[len(PREFIX):]).get("kind")
    except (ValueError, AttributeError):
        return None
    return kind if kind in KINDS else None
