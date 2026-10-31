"""改「认渠道页」时的对拍：同一份页面样本喂给两份 `tool/`，比较认页与进页这两步的出口。

样本取本仓库 `tests/` 里所有 `<hierarchy>` 字面量；基线取改动前的干净副本：

    git archive origin/main | tar -x -C /tmp/aac-baseline
    python tests/compare_chan_pages.py /tmp/aac-baseline/tool

比三件事，组数一多就会跑上十几秒：
  `top_title()` —— 不依赖焦点；
  `channel_switch()` —— 样本页 × 两种屏尺寸 × 六种通知页焦点 × `Attempt.vivo_app` 取空 / 「示例应用」
    × 页面上出现的每个文字 + 「营销通知」；
  `via_app_page()` —— 同样本 × 两种屏尺寸 × 两种 vivo 焦点 × 页面上的前六个文字 + 「营销通知」，
    比返回值、卡在哪一环、记下的 App 名、点了几下、滑了几下。

结论不只看「相等」：驱动同时打印守卫数字（旧实现认出开关的组数、认得顶栏标题的组数、
进页真的点了行的组数），任一项为 0 就以非零退出——样本或探针退化时「零差异」是必然相等，不能当证据。
两边各起一个子进程：模块名相同，同进程里 import 不了两份 chan_fast。
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
SIZES = ((1080, 2340), (720, 1600))
FOCI = (
    "com.android.systemui/com.vivo.systemui.statusbar.notification.settings.channels.NotificationSettingsActivity",
    "com.vivo.systemuiplugin/com.vivo.systemui.statusbar.notification.settings.channels.NotificationSettingsActivity",
    "com.android.settings/com.android.settings.Settings$AppNotificationSettingsActivity",
    "com.android.settings/.SubSettings",
    "com.oplus.notificationmanager/com.oplus.notificationmanager.ChannelNotificationSettingsActivity",
    "com.hihonor.systemmanager/com.hihonor.notificationmanager.ui.ChannelNotificationSettingsActivity",
)
VIVO_FOCI = FOCI[:2]


def probe(tool):
    """喂一份 `tool/`，返回 {样本键: 这一组每一步的出口}。"""
    sys.path.insert(0, str(ROOT / "tool"))    # fixtures.load_tool() 见到它就不再插当前副本，免得混用两份 fast
    sys.path.insert(0, str(tool))
    sys.path.insert(1, str(TESTS))
    import chan_fast as chan
    from fixtures import all_pages, phone_stub

    def stub(xml, size, focus):
        p = phone_stub("probe", d=Mock())
        p.W, p.H = size
        p.focus = Mock(return_value=focus)
        root = ET.fromstring(xml)
        p.tree = Mock(return_value=root)
        p.locked = Mock(return_value=False)
        p.sig = Mock(return_value="")
        p.settle = Mock(return_value=True)
        p.scroll, p.scroll_more = Mock(), Mock(return_value=False)
        p.click = Mock()
        return p

    out = {}
    chan.time.sleep = lambda _seconds: None      # 等待只为了真机；对拍里按次数走完就够
    for label, xml in all_pages(str(TESTS)):
        names = []
        for n in ET.fromstring(xml).iter("node"):
            t = (n.get("text") or n.get("content-desc") or "").strip()
            if t and t not in names:
                names.append(t)
        for size in SIZES:
            for focus in FOCI:
                for vivo_app in (None, "示例应用"):
                    for name in names[:12] + ["营销通知"]:
                        p = stub(xml, size, focus)
                        try:
                            sw = chan.channel_switch(p, name, chan.Attempt(vivo_app=vivo_app))
                        except Exception as e:          # noqa: BLE001 - 对拍要看到异常本身
                            sw = f"EXC:{type(e).__name__}"
                        key = f"switch|{label}|{size[0]}x{size[1]}|{focus.split('/')[0]}|{vivo_app}|{name}"
                        out[key] = [str(sw), str(chan.top_title(p, p.tree()))]
            for focus in VIVO_FOCI:
                for name in names[:6] + ["营销通知"]:
                    p, at = stub(xml, size, focus), chan.Attempt()
                    try:
                        got = chan.via_app_page(p, "com.example.app", name, at)
                    except Exception as e:          # noqa: BLE001
                        got = f"EXC:{type(e).__name__}"
                    key = f"via|{label}|{size[0]}x{size[1]}|{focus.split('/')[0]}|{name}"
                    out[key] = [str(got), at.stage, str(at.vivo_app), p.click.call_count, p.scroll.call_count]
    return out


def run(tool):
    return json.loads(subprocess.run([sys.executable, __file__, str(tool), "--dump"],
                                     capture_output=True, text=True, check=True).stdout)


def main(argv):
    if len(argv) == 2 and argv[1] == "--dump":
        json.dump(probe(argv[0]), sys.stdout, ensure_ascii=False)
        return 0
    if len(argv) != 1:
        raise SystemExit("用法：python tests/compare_chan_pages.py <改动前的 tool 目录>")
    old, new = run(Path(argv[0]).resolve()), run(ROOT / "tool")
    assert old.keys() == new.keys(), "两边样本集不同"
    clicks = [v for k, v in old.items() if k.startswith("via|")]
    hits = sum(1 for k, v in old.items() if k.startswith("switch|") and v[0] != "None" and not v[0].startswith("EXC:"))
    titles = sum(1 for k, v in old.items() if k.startswith("switch|") and v[1] != "None")
    entered = sum(1 for v in clicks if v[3])
    if not (hits and titles and entered):
        raise SystemExit(f"对拍什么也没测到：认出开关 {hits} 组、认得顶栏标题 {titles} 组、进页点了行 {entered} 组")
    diff = {k: (old[k], new[k]) for k in old if old[k] != new[k]}
    switch = {k: v for k, v in diff.items() if k.startswith("switch|") and v[0][0] != v[1][0]}
    via = {k: v for k, v in diff.items() if k.startswith("via|")}
    print(f"样本组 {len(old)}（认页 {len(old) - len(clicks)}、进页 {len(clicks)}）；"
          f"旧实现认出开关 {hits} 组、认得顶栏标题 {titles} 组、进页点了行 {entered} 组")
    print(f"top_title 不同 {len(diff) - len(switch) - len(via)} 组，channel_switch 不同 {len(switch)} 组，"
          f"via_app_page 不同 {len(via)} 组")
    for k, (a, b) in list(switch.items())[:10] + list(via.items())[:10]:
        print(f"  {k}\n    旧: {a}\n    新: {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
