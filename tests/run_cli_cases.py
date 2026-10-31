"""run.py 每条命令的对拍用例：同一份用例既生成基线，也比对新实现。

规则是「按顺序取第一条 match 命中 argv 拼接串的规则」，越具体的排越前；
没命中的命令回 rc 0、空输出，等价于「这台手机上什么也没有」。
`ui-check` / `chan-scan` / `chan-off` / `chan-on` 会真的起子进程（fast.py / chan_fast.py），
输出取决于本机 adb 服务，不做逐字节对拍，改在 tests/test_run_commands.py 里替身化。
"""

# 一台小米手机：型号、系统、锁屏状态、广告包、插电常亮都给确定的回答。
PHONE = [
    {"match": "getprop ro.product.brand", "stdout": "Xiaomi\n"},
    {"match": "getprop ro.product.model", "stdout": "M154FF\n"},
    {"match": "getprop ro.vendor.oplus.market.name", "stdout": ""},
    {"match": "getprop ro.product.marketname", "stdout": "Xiaomi 13\n"},
    {"match": "getprop ro.build.display.id", "stdout": "OS1.0.1.0\n"},
    {"match": "getprop ro.mi.os.version.incremental", "stdout": "OS1.0.1.0\n"},
    {"match": "getprop ro.build.version.release", "stdout": "13\n"},
    {"match": "input keyevent 0", "stdout": ""},
    {"match": "dumpsys package", "stdout": "suspended={suspended}\n"},
    {"match": "dumpsys usagestats", "stdout": ""},
    {"match": "pm list packages", "stdout": "package:com.android.systemui\n"},
    {"match": "pm path com.miui.systemAdSolution", "stdout": "package:/product/app/AdServices/base.apk\n"},
    {"match": "pm path", "stdout": ""},
    {"match": "settings get secure switch_quick_app_service", "stdout": ""},
    {"match": "settings get global stay_on_while_plugged_in", "stdout": "0\n"},
    {"match": "settings get global development_settings_enabled", "stdout": "0\n"},
    {"match": "wm size", "stdout": "Physical size: 1080x2400\n"},
    {"match": "pidof", "stdout": ""},
]

# 确认断线：所有命令都回 adb 客户端自己的断开文案（Client.GONE），wait-for-device 也不回来。
GONE = [{"match": "", "rc": 1, "stdout": "", "stderr": "adb: device 'S' not found"}]

QUICKAPP_INSTALLED = [
    {"match": "pm path com.nearme.instant.platform", "stdout": "package:/data/app/platform/base.apk\n"},
    {"match": "pm path com.oppo.instant.local.service", "stdout": "package:/data/app/local/base.apk\n"},
    {"match": "pm path", "stdout": ""},
]

BACKUP_DIR = "M154FF-20260101-0000"

# 这几条会真的起子进程，输出取决于本机 adb 服务，不放进逐字节对拍；
# 它们的转发语义由 tests/test_run_commands.py 的 HandlerInterfaceTests 替身化后断言。
HOST_SIDE = ("ui-check", "chan-scan", "chan-off", "chan-on")


def case(name, argv, rules, seed=None, state=None, expect=(), expect_empty=False):
    """expect 是守卫断言：这些子串必须出现在假 adb 收到的 argv 里，证明这条用例走的是目标分支。
    expect_empty 用于「一条 adb 命令都不该发」的分支（参数错、未知命令、还没确认的破坏性操作）。"""
    return {"name": name, "argv": argv, "rules": rules, "seed": seed or {}, "state": state or {},
            "expect": list(expect), "expect_empty": expect_empty}


CASES = [
    case("devices-有设备", ["devices"],
         [{"match": "devices", "stdout": "List of devices attached\nS\tdevice\n\n"}] + PHONE,
         expect=["devices"]),
    case("devices-没有设备", ["devices"],
         [{"match": "devices", "stdout": "List of devices attached\n\n"}] + PHONE,
         expect=["devices"]),
    case("check-成功", ["-s", "S", "check"], PHONE,
         expect=["getprop ro.product.brand", "dumpsys window", "pm path com.miui.systemAdSolution"]),
    case("check-断线", ["-s", "S", "check"], GONE, expect=["wait-for-device"]),
    case("backup-成功", ["-s", "S", "backup"], PHONE,
         expect=["pm list packages", "dumpsys notification"]),
    case("backup-包列表读不到", ["-s", "S", "backup"],
         [{"match": "pm list packages", "stdout": ""}, {"match": "cmd package list packages", "stdout": ""}] + PHONE,
         expect=["cmd package list packages"]),
    case("backup-断线", ["-s", "S", "backup"], GONE, expect=["wait-for-device"]),
    case("recipe-没有机型脚本", ["-s", "S", "recipe"],
         [{"match": "getprop ro.product.model", "stdout": "NOPE-1\n"}] + PHONE,
         expect=["getprop ro.product.model"]),
    case("suspend-成功", ["-s", "S", "suspend", "com.example.ad"],
         [{"match": "pm suspend", "stdout": "success\n", "set": {"suspended": "true"}}] + PHONE,
         expect=["pm suspend --user 0 com.example.ad", "dumpsys package com.example.ad"]),
    case("suspend-挂起失败", ["-s", "S", "suspend", "com.example.ad"],
         [{"match": "pm suspend", "rc": 1, "stderr": "Error: not allowed\n"}] + PHONE,
         expect=["pm suspend --user 0 com.example.ad"]),
    case("suspend-禁止包", ["-s", "S", "suspend", "com.android.systemui"], PHONE, expect_empty=True),
    case("suspend-断线", ["-s", "S", "suspend", "com.example.ad"], GONE, expect=["wait-for-device"]),
    case("unsuspend-按记录还原", ["-s", "S", "unsuspend"],
         [{"match": "pm unsuspend", "stdout": "", "set": {"suspended": "false"}}] + PHONE,
         seed={BACKUP_DIR + "/suspended.txt": "com.example.ad\n"},
         expect=["pm unsuspend --user 0 com.example.ad"]),
    case("unsuspend-还原失败", ["-s", "S", "unsuspend"],
         [{"match": "pm unsuspend", "stdout": ""}] + PHONE,
         seed={BACKUP_DIR + "/suspended.txt": "com.example.ad\n"}, state={"suspended": "true"},
         expect=["pm unsuspend --user 0 com.example.ad", "dumpsys package com.example.ad"]),
    case("unsuspend-断线", ["-s", "S", "unsuspend"],
         [{"match": "pm unsuspend", "stdout": ""}] + GONE,
         seed={BACKUP_DIR + "/suspended.txt": "com.example.ad\n"}, expect=["wait-for-device"]),
    case("quickapp-没有组件", ["-s", "S", "quickapp"], PHONE,
         expect=["dumpsys usagestats", "pm path"]),
    case("quickapp-off-成功", ["-s", "S", "quickapp", "off"],
         [{"match": "pm suspend", "stdout": "", "set": {"suspended": "true"}}] + QUICKAPP_INSTALLED + PHONE,
         expect=["pm suspend --user 0 com.oppo.instant.local.service", "am force-stop --user 0 com.oppo.instant.local.service"]),
    case("quickapp-off-有失败", ["-s", "S", "quickapp", "off"],
         [{"match": "pm suspend", "rc": 1, "stderr": "Error: not allowed\n"}] + QUICKAPP_INSTALLED + PHONE,
         expect=["pm suspend --user 0 com.oppo.instant.local.service"]),
    case("quickapp-on-还原", ["-s", "S", "quickapp", "on"],
         [{"match": "pm unsuspend", "stdout": "", "set": {"suspended": "false"}}] + QUICKAPP_INSTALLED + PHONE,
         state={"suspended": "true"}, expect=["pm unsuspend --user 0 com.oppo.instant.local.service"]),
    case("quickapp-未知子命令", ["-s", "S", "quickapp", "bogus"], QUICKAPP_INSTALLED + PHONE,
         expect=["dumpsys usagestats"]),
    case("quickapp-断线", ["-s", "S", "quickapp"], GONE, expect=["wait-for-device"]),
    case("finish-成功", ["-s", "S", "finish"],
         [{"match": "settings get global development_settings_enabled", "stdout": "1\n"}] + PHONE,
         seed={BACKUP_DIR + "/stay_on.txt": "7\n"},
         expect=["settings put global stay_on_while_plugged_in 7", "input keyevent HOME"]),
    case("finish-断线", ["-s", "S", "finish"], GONE, expect=["wait-for-device"]),
    case("status-json-成功", ["-s", "S", "status-json"], PHONE,
         expect=["wm size", "settings get global stay_on_while_plugged_in"]),
    case("status-json-断线", ["-s", "S", "status-json"], GONE, expect=["wait-for-device"]),
    case("dev-off-缺确认", ["-s", "S", "dev-off"], PHONE, expect_empty=True),
    case("dev-off-成功", ["-s", "S", "dev-off", "--yes"], PHONE,
         expect=["settings put global adb_wifi_enabled 0"]),
    case("dev-off-断线", ["-s", "S", "dev-off", "--yes"], GONE, expect=["wait-for-device"]),
    case("格式错", ["-s", "S"], PHONE, expect_empty=True),
    case("未知命令", ["-s", "S", "no-such-command"], PHONE, expect_empty=True),
]
