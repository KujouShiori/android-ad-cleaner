"""假 adb：替 run.py 的对拍回答每一条 shell，手机不需要存在。

规则文件是 JSON 数组，按顺序取第一条「match 是 argv 拼接串的子串」的规则；
规则可以带 `set`，把值写进状态文件，`stdout` / `stderr` 里的 `{键}` 用状态替换
（`pm suspend` 之后 `dumpsys package` 要能回 suspended=true，真 adb 就是这个行为）。
环境变量由 tests/run_cli_driver.py 给，直接跑没有意义。
"""
import json
import os
import sys


def listed(text, state):
    for key, value in state.items():
        text = text.replace("{" + key + "}", value)
    return text


def main(argv):
    with open(os.environ["FAKE_ADB_RULES"], encoding="utf-8") as f:
        rules = json.load(f)
    state_path = os.environ["FAKE_ADB_STATE"]
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    with open(os.environ["FAKE_ADB_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps(argv, ensure_ascii=False) + "\n")
    text = " ".join(argv)
    rule = next((r for r in rules if r["match"] in text), {})
    sys.stdout.write(listed(rule.get("stdout", ""), state))
    sys.stderr.write(listed(rule.get("stderr", ""), state))
    if rule.get("set"):
        state.update(rule["set"])
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    return rule.get("rc", 0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
