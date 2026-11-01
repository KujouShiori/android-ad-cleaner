"""Windows 启动失败的归因：缺 WebView2、程序文件被 Windows 标记为「来自网络」、其他（#228）。

`gui/app.py` 原来把所有启动异常都说成「缺少 WebView2」。实测 portable 包解压后，
`Python.Runtime.dll` 带 `Zone.Identifier`（MOTW），.NET 加载器拒载，`import clr` 失败，
症状与缺运行时一模一样。这里只做判定，不碰界面、不碰 `tool/`。

注册表读取与 ADS 探测从外面注入，非 Windows 上也能跑这套判定。
"""
import os

WEBVIEW2_CLIENT_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

# 64 位安装、32 位安装、按用户安装各一处；读到一个有值的 pv 就算装了。
WEBVIEW2_KEYS = (
    ("HKLM", r"SOFTWARE\Microsoft\EdgeUpdate\Clients" + "\\" + WEBVIEW2_CLIENT_ID),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients" + "\\" + WEBVIEW2_CLIENT_ID),
    ("HKCU", r"Software\Microsoft\EdgeUpdate\Clients" + "\\" + WEBVIEW2_CLIENT_ID),
)

# 这两个 dll 被拒载就足以让 `import clr` 失败；不全扫解压目录，避免把无关文件算进来。
BLOCKED_RELATIVE = (
    ("pythonnet", "runtime", "Python.Runtime.dll"),
    ("clr_loader", "ffi", "dlls", "amd64", "ClrLoader.dll"),
)


def read_pv(hive, path):
    """读某个 EdgeUpdate 客户端键的 pv；键不存在抛 FileNotFoundError。"""
    import winreg
    root = winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER
    with winreg.OpenKey(root, path) as key:
        return winreg.QueryValueEx(key, "pv")[0]


def has_zone_identifier(path):
    """文件带「来自网络」标记（`Zone.Identifier` 备用数据流）时为真。"""
    try:
        with open(path + ":Zone.Identifier", "rb"):
            return True
    except OSError:
        return False


def webview2_state(read=None):
    """`installed` / `missing` / `unknown`。三处键都读不到真值但至少一处报错时是 unknown。"""
    read = read or read_pv
    errored = False
    for hive, path in WEBVIEW2_KEYS:
        try:
            version = read(hive, path)
        except FileNotFoundError:           # 这台机器上没有这一处键
            continue
        except (OSError, ImportError):      # 拒绝访问、非 Windows（没有 winreg）
            errored = True
            continue
        if version:
            return "installed"
    return "unknown" if errored else "missing"


def blocked_files(root, detect=None):
    """`root` 下那两个关键 dll 里带 MOTW 的绝对路径。

    PyInstaller 6 把依赖放进 `_internal`，而 `sys._MEIPASS` 指的就是它；打包器版本没钉，
    两种布局都查。文件不在就不探测——`detect` 只在真存在时才被调用。
    """
    detect = detect or has_zone_identifier
    found = []
    for rel in BLOCKED_RELATIVE:
        for base in (root, os.path.join(root, "_internal")):
            path = os.path.join(base, *rel)
            if os.path.isfile(path) and detect(path):
                found.append(path)
                break
    return tuple(found)


def describe(root, read=None, detect=None):
    """给 `--smoke-gui` 打的一行结论，CI 日志里能分清环境问题与代码回归。"""
    blocked = blocked_files(root, detect)
    return f"webview2={webview2_state(read)} motw={'yes' if blocked else 'no'}"
