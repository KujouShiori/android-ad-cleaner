# vivo X Fold6 机型脚本：V2545A（OriginOS 6 Fold，Android 16，PD2545B_A_16.0.16.0.W10）
# 入口沿用同代 OriginOS 6 路径，逐步在真机核对；全段只用 only=[] 点名关闭，找不到就跳过。
# 用法：python3 tool/run.py -s 序列号 recipe [段名…]
BUILD = "PD2545B_A_16"
MODELS = ["V2545A"]
import time

ONLY = globals().get("ONLY") or []

def step(name):
    def deco(f):
        if (not ONLY or name in ONLY) and p.locked():
            print(f"\n== {name}：手机锁屏了，后面的都不跑"); return f
        if not ONLY or name in ONLY:
            print(f"\n== {name}"); p.miss = 0
            t = time.time()
            try:
                f()
            except Exception as e:
                print(f"  ✗ 出错：{e}")
            print(f"  ({time.time()-t:.0f} 秒)")
        return f
    return deco

def maybe(name, scrolls=6):
    """有就点，没有不算走丢。"""
    p.miss = 0
    ok = p.tap(name, exact=True, scrolls=scrolls)
    p.miss = 0
    return ok

def gear():
    """vivo App 设置多是右上角齿轮，没有文字。"""
    for n in p.tree().iter("node"):
        d = (n.get("content-desc") or "") + (n.get("resource-id") or "")
        if any(k in d.lower() for k in ("设置", "setting")) and n.get("clickable") == "true" and p.on_screen(n):
            from fast import bounds
            l, t, r, b = bounds(n); p.click((l + r) // 2, (t + b) // 2); time.sleep(1)
            return True
    return p.tap("设置", exact=True, scrolls=0)

def settings_home():
    p.d.shell("am start -f 0x10008000 -a android.settings.SETTINGS"); time.sleep(1.2)

def tap_confirm():
    """vivo 的二次确认弹框：按钮文字是子 TextView，Button 节点本身取不到 text。"""
    from fast import bounds
    for n in p.tree().iter("node"):
        if (n.get("text") or "").strip() in ("关闭", "确定", "仍要关闭", "确认关闭", "确认"):
            l, t, r, b = bounds(n)
            p.click((l + r) // 2, (t + b) // 2)
            return True
    return False

def by_desc(kw, wait=1.2):
    """底部 tab、右上齿轮这类入口只有 content-desc，没有文字。"""
    from fast import bounds
    for n in p.tree().iter("node"):
        if kw in (n.get("content-desc") or "") and n.get("clickable") == "true" and p.on_screen(n):
            l, t, r, b = bounds(n)
            p.click((l + r) // 2, (t + b) // 2); time.sleep(wait)
            return True
    return False

def switch_off(title, tries=2):
    """标题在开关行外（vivo 商店），只能按「同一个 Switch 节点」配对，点完回读状态。"""
    from fast import bounds
    for _ in range(tries):
        root = p.tree()
        rows = [bounds(n) for n in root.iter("node") if (n.get("text") or "").strip() == title]
        hit = None
        for n in root.iter("node"):
            if "Switch" in (n.get("class") or ""):
                l, t, r, b = bounds(n)
                if any(t <= (t2 + b2) // 2 <= b and t2 >= t and b2 <= b for l2, t2, r2, b2 in rows):
                    hit = (n.get("checked") == "true", (l + r) // 2, (t + b) // 2)
        if hit is None:
            return None
        if not hit[0]:
            return True
        p.click(hit[1], hit[2]); time.sleep(0.9); tap_confirm(); time.sleep(0.9)
    return False

def turn_off(title, tries=3):
    """带上确认框，按回读状态判断，而不是点完就算成功。"""
    from fast import bounds
    for _ in range(tries):
        row = [(c, xy) for t, c, xy in p.switches() if title in t]
        if not row:
            return None
        if not row[0][0]:
            return True
        p.click(*row[0][1]); time.sleep(0.7); tap_confirm(); time.sleep(0.7)
    return not any(title in t and c for t, c, _ in p.switches())

def setting_search(keyword, result):
    """设置页层级变了就用搜索兜底。"""
    try:
        return bool(p.setting(keyword, result))
    except Exception as e:
        print(f"  设置搜索「{keyword}」没走通：{e}")
        return False

@step("系统广告")
def _():
    settings_home()
    done = False
    if maybe("安全") or maybe("安全与隐私"):
        if maybe("更多安全设置") and maybe("广告与隐私"):
            p.off(only=["个性化广告", "个性化推荐", "智能推荐服务"], page="系统·广告与隐私")
            done = True
    if not done and setting_search("广告", "广告与隐私"):
        p.off(only=["个性化广告", "个性化推荐", "智能推荐服务"], page="系统·广告与隐私（搜索）")

@step("全局搜索")
def _():
    settings_home()
    if maybe("系统管理与升级") and maybe("全局搜索"):
        if maybe("个性化内容"):
            p.off(only=["广告个性化"], page="全局搜索·个性化内容"); p.back()

@step("阅图锁屏")
def _():
    settings_home()
    if maybe("桌面、锁屏与壁纸") and maybe("锁屏设置") and maybe("阅图锁屏"):
        for name in ("阅图锁屏", "轮播壁纸"):
            r = turn_off(name)
            print(f"  {name}：{'已经是关' if r else '关不掉' if r is False else '没找到'}")

@step("应用商店")
def _():
    p.start("com.bbk.appstore")
    time.sleep(2)
    by_desc("我的")
    gear()
    if maybe("关于"):
        if maybe("个性化推荐"):
            for t in ("个性化推荐", "个性化广告推荐"):
                r = switch_off(t)
                print(f"  {t}：{'已经是关' if r else '关不掉' if r is False else '没找到'}")
            p.back()
        if maybe("服务管理"):
            p.off(only=["签到有礼", "顶部轮播图", "顶部栏目", "开屏", "摇一摇", "悬浮窗", "限时推广"],
                  keep=["我的服务", "空间清理"], page="商店·服务管理")
            p.back()
        p.back(2)

@step("浏览器")
def _():
    p.start("com.vivo.browser")
    time.sleep(2)
    by_desc("菜单")
    by_desc("设置", wait=2)
    if maybe("首页设置"):
        maybe("极简首页", scrolls=0)
        for n in ("首页上滑展示资讯",):
            r = turn_off(n)
            print(f"  {n}：{'已经是关' if r else '关不掉' if r is False else '没找到'}")
        p.back(); time.sleep(1)
    if maybe("隐私权限设置"):
        for n in ("个性化内容", "第三方应用来源个性化推荐", "个性化广告推荐"):
            r = turn_off(n)
            print(f"  {n}：{'已经是关' if r else '关不掉' if r is False else '没找到'}")
        p.back(); time.sleep(1)
    if maybe("网页浏览设置"):
        for n in ("网页下载相关推荐",):
            r = turn_off(n)
            print(f"  {n}：{'已经是关' if r else '关不掉' if r is False else '没找到'}")
        p.back(); time.sleep(1)
    if maybe("更多设置"):
        for n in ("WiFi连接跳转新闻资讯", "跳转新闻资讯"):
            r = turn_off(n)
            print(f"  {n}：{'已经是关' if r else '关不掉' if r is False else '没找到'}")
        p.back(); time.sleep(1)
    p.back(2)

@step("i管家")
def _():
    print("  跳过：i管家首次启动强制要求同意用户协议，按规则不代点。")
    print("  手动做：i管家 → 设置 → 关于 → 个性化设置 → 关「应用个性化推荐」")

@step("天气")
def _():
    p.start("com.vivo.weather")
    time.sleep(2)
    by_desc("更多")
    maybe("设置", scrolls=0)
    r = turn_off("天气服务")
    print(f"  天气服务：{'已经是关' if r else '关不掉' if r is False else '没找到'}（气象预警、异常天气保留）")
    p.back(2)
