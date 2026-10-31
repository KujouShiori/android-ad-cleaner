# 小米 / HyperOS 手动清单

实测机型：Xiaomi 18 Pro Max（M154FF，HyperOS 4，Android 17），2026-10-22。Redmi 结构相近。
符号：🔴 关掉　🟢 保留　⚠️ 注意

---

## 1. 系统广告

**路径**：设置 → 隐私与安全 → 更多安全设置 → 广告服务

- 🔴 个性化广告推荐

## 2. 应用商店

**路径**：应用商店 → 我的 → 右上齿轮

- 🔴 隐私 → 个性化服务
- 🔴 模式切换 → 极简模式（只留搜索、安装、更新）
- 🔴 通知设置 → 新手帮助
- 🟢 通知设置 → 应用更新
- ⚠️ 小米 17（HyperOS 4）此版本设置页没有「隐私」入口，个性化服务无从关起；极简模式和通知设置正常。

## 3. 手机管家

**路径**：手机管家 → 右上齿轮

- 🔴 隐私设置 → 个性化推荐
- 🔴 垃圾清理 → 推荐内容

## 4. 下载管理

**路径**：下载管理 → 右上齿轮 → 信息流设置

- 🔴 资源推荐、热榜推荐

## 5. 主题

**路径**：主题 → 我的 → 右上齿轮

- 🔴 每次联网时通知
- 🔴 隐私设置 → 个性化推荐
- ⚠️ 包名差异：多数机型入口包为 `com.android.thememanager`；小米 17 实机该包无 LAUNCHER 入口，实际启动的是 `com.miui.themestore`（主题商店），设置项一致。

## 6. 浏览器

**路径**：浏览器 → 我的 → 齿轮

- 🔴 主页设置 → 宫格位推送
- 🔴 搜索设置 → 显示猜你想搜模块
- 🔴 功能设置 → 小说；🟢 我的网盘
- 🔴 隐私和安全 → 个性化内容推荐、个性化广告推荐
- ⚠️ 首页「默认 / 极简」二选一，极简版没有资讯流，按你的喜好选。
- ⚠️ 浏览器会弹小米账号登录框，点「取消」。

## 7. 全局搜索

**路径**：桌面下滑 → 搜索页右上齿轮

- 🔴 首页展示模块 → 搜索提示词
- 🔴 应用推荐 → 推荐未安装应用；🟢 展示常用应用
- 🔴 热搜榜单 → 推荐、微博、资讯、全网、影视、音乐、小说、知乎，全关
- ⚠️ 小米 17 的热榜管理是**双列布局**，`fast.py only/off` 点不动开关；需 dump 层级找到 Switch 控件本体坐标逐个点击（点标题行无效）。实际榜单 7 项：微博热搜榜、千问热议、微博智搜榜、全网热搜榜、小米好物、音乐热搜榜、知乎热搜榜。
- ⚠️ 桌面下滑手势在部分机型会拉通知栏，可直达设置页：`am start -n com.android.quicksearchbox/.preferences.SearchSettingsPreferenceActivity`。

## 8. 负一屏

**路径**：桌面从左边缘向右滑 → 设置

- 🔴 推荐卡片、热门活动
- 🔴 隐私设置 → 个性化推荐
- 🟢 搜索框、出行助手
- ⚠️ 小米 17 负一屏无文字入口、长按也唤不出设置，可直达：`am start -n com.miui.personalassistant/.settings.PASettingActivity`（实机推荐卡片、热门活动、个性化推荐默认全关）。

## 9. 营销通知

**路径**：设置 → 通知与控制中心 → 通知管理 → 选 App → 点渠道名

- 🔴 应用商店「平台活动通知」、浏览器「新闻资讯」、Play「特惠」、Edge「热门资讯」「突发新闻」等
- ⚠️ 小米的渠道 id 形如 `mipush|包名|数字`，带竖线。

## 10. 系统广告组件 msa（要 adb，要你同意）

`com.miui.systemAdSolution` 负责各系统 App 的开屏广告。

```bash
adb -s S shell pm suspend --user 0 com.miui.systemAdSolution
adb -s S shell cmd connectivity set-package-networking-enabled false com.miui.systemAdSolution
adb -s S shell cmd connectivity set-chain3-enabled true
```

- ⚠️ 只挂起拦不住：系统 App 启动时会把它拉起来，所以加了断网。
- ⚠️ 断网规则重启后可能失效，重启后重跑后两行。
- 实测：商店、浏览器、主题、天气正常打开，内容正常加载。

还原：

```bash
adb -s S shell pm unsuspend --user 0 com.miui.systemAdSolution
adb -s S shell cmd connectivity set-package-networking-enabled true com.miui.systemAdSolution
```

---

## 不同机型的差异

| 项 | Xiaomi 18 Pro Max（M154FF，HyperOS 4） | 小米 17（25113PN0EC，HyperOS 4，Android 17） |
|---|---|---|
| 应用商店「隐私→个性化服务」 | 有 | 无此入口，跳过 |
| 主题入口包名 | `com.android.thememanager` | 该包无 LAUNCHER 入口，实为 `com.miui.themestore` |
| 手机管家启动 | 桌面图标 | monkey 启动失败，需 `am start` 直达 `com.miui.securitycenter` 主 Activity |
| 全局搜索热榜 | 单列，引擎可开关 | 双列布局，需解析 Switch 控件坐标逐个点击 |
| 负一屏设置入口 | 左边缘右滑后可见 | 无文字入口、长按无效，需 `am start` 直达 `PASettingActivity` |
| 营销通知渠道 | 正常扫描 | 很干净，仅 1 条服务类候选 |
| 浏览器 | — | 结构与主清单完全一致，账号登录框同样会弹，点「取消」 |

欢迎补充：提 PR 改这张表。

---

## 小米的坑

| 现象 | 对策 |
|---|---|
| 脚本能读屏、点不动 | 开发者选项里打开「USB 调试（安全设置）」 |
| 关开关弹「确认关闭」 | 点确定 |
| 浏览器吞掉点击 | 用 80 毫秒短按，引擎已处理 |
| 带背屏的机型截图报多屏 | `screencap` 加 `-d <主屏 display id>` |
