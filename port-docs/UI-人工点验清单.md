# LaterOn Firefox 移植版 · 有头人工点验清单

> 对应《Firefox-适配技术方案.md》附录 **F.6 仍未实测**的 7 项。
> 这份清单是给**人**用的操作脚本：每一步要做什么、看哪里、什么算通过、失败时记录什么。
> 无头自动化的结论见附录 **F.5**；本文只覆盖必须由真人点击才能确认的部分。

---

## 1. 为什么这 7 项无头测不了

无头 `web-ext run` 已经能证明的事：脚本零报错、各扩展页 `readyState=complete`、`manifest.json` 被 Firefox 接受、后台事件页能起来、`commands.getAll()` 注册成功、`sidebarAction.getPanel()/isOpen()` 可用。**这些都是"文档树里的东西"。**

无头证明不了的是**浏览器外壳（browser chrome）本身**的三类行为：

| 类别 | 为什么无头测不到 |
|---|---|
| 侧栏尺寸与布局 | 无头窗口没有真实侧栏宽度；`--headless` 下侧栏根本不渲染，量不到 620px / 330px 断点 |
| 用户手势与真实输入 | `sidebarAction.open()` 要求"用户手势内调用"；合成/无人操作时手势链是断的，测出来会假阴性；反向也会假阳性（附录 F 记录过一次探针自误判） |
| 系统级上下文 | 快捷键是否与系统或其它扩展冲突、右键菜单实际弹在哪、Trusted Types 站点上的 innerHTML 行为——都取决于真实 GUI 会话 |

> 一句话：无头能证明"没有崩"，证明不了"看起来对、点得通"。

---

## 2. 前置准备（约 3 分钟）

```powershell
# 1) 出包（干净 36 文件目录，不要直接用 -s work，否则 node_modules 会被打进临时扩展）
cd F:\ALL_AI\小助理\open-source-collection\lateron-firefox-port\work
D:\ALL_Python\python312\python312.exe scripts\build-release.py --target firefox

# 2) 解包到临时目录
$dst = "$env:TEMP\latoron-ff-headed"
Remove-Item $dst -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive "dist\LaterOn-1.66.1-firefox.zip" $dst

# 3) 有头启动（去掉 --args=-headless；web-ext 8.10.0 没有 --headless 选项，必须用 --args=）
& "node_modules\.bin\web-ext.cmd" run `
  --source-dir $dst `
  --firefox "D:\Firefox\firefox.exe" `
  --no-reload --verbose `
  --firefox-profile "$env:TEMP\latoron-ff-profile-headed"
```

**每次记录都要带上的环境信息**：Firefox 版本（`about:support` 第一行）、屏幕缩放、窗口宽度、侧栏宽度（拖动后读数值）、系统版本。

**三条检查通道**（出问题时看这里）：
1. `about:debugging#/runtime/this-firefox` → LaterOn → **检查**：分别能打开后台页与扩展页的控制台。
2. 侧栏内**右键 → 检查**（或 `about:debugging` 里的 `sidepanel.html` 检查）。
3. 浏览器控制台里的 `[LaterOn]` 前缀日志（垫片打的警告都带这个前缀）。

> ⚠️ 本次验证机上用户自己的 Firefox 正在运行。`web-ext` 用的是独立 `--firefox-profile`，**不要**去结束系统里其它 `firefox.exe` 进程；收尾只结束命令行里带 `latoron-ff-profile-headed` 的实例。

---

## 3. 七项逐条操作脚本

### A-01 · 侧栏内调用 `close()` 到底能不能关掉自己

- **为什么无头不行**：无头下没有"面板自己要求关闭"的真实链路，`canClose` 分支只能静态推断。
- **代码位置**：`work/sidepanel.js:648-653`（先 `LaterOnSidePanel.close({ windowId })`，失败走 `window.close()` 退路；`libraryOpened` 时无条件 `window.close()`）；垫片实现在 `work/ff-sidebar.js:58-63`，忽略 `windowId` 时会打 `[LaterOn] Firefox 的 sidebarAction.close() 不支持指定 windowId`（`work/ff-sidebar.js:38-43`）。
- **操作**：
  1. 打开侧栏，侧栏里点一条已有的项目卡片；
  2. 触发跨窗口路径：在库页面选一个不同窗口的目标，或在侧栏点「在库中打开」后返回；
  3. 观察侧栏是否消失、多久消失。
- **通过判据**：侧栏关闭，控制台无未捕获异常；出现 `windowId 忽略` 警告属预期。
- **失败特征**：侧栏纹丝不动且无任何提示 → 说明三级降级里第二、三级没兜住，需要改 `work/sidepanel.js:650` 的退路策略（例如改用 `chrome.tabs.remove` 或提示用户手动收起）。
- **记录**：是否关闭 / 延迟 ms / 控制台原文 / 是否出现 windowId 警告 / 走的哪一级退路。

### A-02 · `sidebarAction.open()` 的用户手势约束

- **为什么无头不行**：手势只能由真人点击产生，程序化触发一律被拒绝。
- **代码位置**：`work/library.js:2223-2230`（Firefox 分支在 `openItem` 里把手势**提前**用掉，得到 `earlyPanelOpen`）、`work/library.js:2278-2282`（`earlyPanelOpen` 已就绪就直接 await 它，不再二次调用）、垫片 `work/ff-sidebar.js:53-57`、`:84-90`。
- **操作**：在库页面（`library.html`）**单击**一张卡片 → 观察右侧侧栏是否自动打开；再单独点工具栏的 `#openLibrary` 类入口。
- **通过判据**：侧栏打开；控制台无手势相关的拒绝错误。
- **失败特征**：控制台出现 `sidebarAction.open requires a user gesture` 之类报错，或静默不打开 → 手势被中间的 `await` 吃掉，需要把开面板动作再往点击处理函数的最前面提。
- **记录**：是否打开 / 报错原文 / 点击的是哪个入口 / 是否需要第二次点击。

### A-03 · 侧栏真实布局（三档宽度）

- **为什么无头不行**：量不到真实侧栏宽度，也看不到重叠/裁切。
- **代码位置**：`work/sidepanel.css:6`（`body { min-width: 280px }`）、`:220`（`@media (max-width:330px)` → 隐藏保存按钮文案）、`:223`（`@media (min-width:620px)` → 展开布局，搜索框上限 420px）；顶栏兜底高度 `work/sidepanel.js:98`（`TOPBAR_FALLBACK_H = 58`），被 `work/sidepanel.js:1147` 用于滚动定位。
- **操作**：把侧栏拖到最窄 → 中间 → 最宽三档，每档**截图**，并记录侧栏像素宽度（拖动时读一下或量截图）。
- **通过判据**：三档都没有横向滚动条、顶栏不重叠/不被裁、卡片网格正常；≤330px 时保存按钮只剩图标；≥620px 时搜索框不超过 420px。
- **失败特征**：顶栏被裁、元素错位、出现横向滚动条 → 记录"窗口宽度 + 侧栏宽度 + 断点档位 + 截图"，据此调 `sidepanel.css` 的断点或 `TOPBAR_FALLBACK_H`。
- **记录**：Firefox 版本 / 侧栏宽度 / 缩放 / 三张截图 / 是否有滚动条。

### A-04 · `Alt+1`、`Alt+Shift+1` 的真实冲突

- **为什么无头不行**：`commands.getAll()` 只证明"注册了"，证明不了"按下去真的触发、没被别人抢走"。
- **代码位置**：`work/manifest.firefox.json` 的 `commands` 段（`quick-save = Alt+1`、`save-all-tabs = Alt+Shift+1`；`toggle-translation` 已在移植时移除）。
- **操作**：
  1. 在任意普通网页按 `Alt+1`、`Alt+Shift+1`，看是否分别触发"保存此页 / 保存全部标签页"；
  2. 打开 `about:addons` → 齿轮 → **管理扩展快捷键**，看这两条是否被标为冲突/未分配。
- **通过判据**：两个快捷键都能触发；快捷键页无冲突标记。
- **失败特征**：与系统其它软件（如某些 Alt+数字 的窗口切换）或其它扩展冲突 → 换键并同步改 manifest 与文档。
- **记录**：是否触发 / 冲突标记 / 冲突方是谁。

### A-05 · `contextMenus` 的 `"action"` 上下文在 Firefox 里长什么样

- **为什么无头不行**：菜单是外壳 UI，弹在哪、有没有弹，只有真人右键才看得到。
- **代码位置**：`work/background.js:255-256`（`contexts: ["page", "action"]`，两条菜单：保存此页 / 保存全部标签页）。
- **操作**：① 工具栏 LaterOn 图标上**右键**；② 网页正文空白处右键。
- **通过判据**：图标右键菜单里能看到那两项（Firefox 对 `"action"` 上下文支持有差异，这是本项存在的意义）；正文右键同样能看到。
- **失败特征**：图标右键没有这两项 → 需要补 `"browser_action"` 上下文或退化为只保留 `"page"`，并同步改文档。
- **记录**：两种右键各自看到什么（截图或文字）。

### A-06 · 4 处 `innerHTML` 在开启 Trusted Types 的站点上

- **为什么无头不行**：需要真实站点 + 真实 CSP 响应头。
- **位置**（addons-linter 报的 4 条 `UNSAFE_VAR_ASSIGNMENT`）：`work/content-reading-position.js:124`、`work/dialog.js:117`、`work/dialog.js:534`、`work/picker-ui.js:94`。
- **操作**：在启用 `require-trusted-types-for 'script'` 的站点（或本地自建一个带该响应头的演示页）触发：阅读进度条、保存对话框、选择器面板。
- **通过判据**：控制台没有 `This document requires 'TrustedHTML' assignment` 之类报错，UI 正常。
- **失败特征**：报 Trusted Types 错误、对应 UI 不出现 → 记录站点 + 报错原文 + 受影响的 UI。
- **备注**：这是**上游遗留**问题，与 Firefox 移植无关；但 AMO 审核会看这 4 条告警，若要走正式上架需要改。

### A-07 · 附录 F.6 第 7 项的其余零散待实测

逐项过一遍即可，不需要复杂操作：

| 待测点 | 代码位置 | 怎么看 | 通过判据 |
|---|---|---|---|
| `storage.session` 可用性与配额 | `work/background.js:903`、`:1271-1299` | 触发依赖"待处理会话"的流程，看控制台 | 无 `storage.session is undefined` / 配额报错 |
| `executeScript({ files })` 返回语义 | `work/background.js:565`、`:632`、`:1198`、`:1219`、`:1236`、`:1439`、`:1619` | 注入类功能是否取到结果 | 返回值结构与 Chrome 一致，无 `undefined` 崩 |
| 事件页回收后 `injectedCssTabs` 内存态丢失 → 可能重复 `insertCSS` | `work/background.js:72-88` | 等后台被回收（`about:debugging` 里可手动终止后台）后再触发注入 | 观察 CSS 是否重复注入 / 样式是否异常 |
| Firefox bug 1525400 内容脚本重复注入 | 内容脚本 `*-content*/` 系列 | 导航往返后看 `content-*` 是否被注入多次 | 无重复监听/重复副作用 |

---

## 4. 结论与记录模板

**能"半自动"覆盖的部分**（不必写进人工记录）：页面能否加载、脚本是否报错、manifest 是否被接受、API 是否存在、快捷键是否注册、面板路径是否正确——这些在无头轮次（附录 F.5）已给出结论，人工轮次只需**抽查复核**。

**必须人工记录的部分**：A-01 ~ A-06 全部，以及 A-07 表格里 "事件页回收后重复注入" 一行。

复制下面模板逐项填写：

```text
[环境] Firefox ______ | 系统缩放 ______ | 窗口宽 ______ | 侧栏宽 ______ |
[A-01] 结果 ______ | 走的退路 ______ | 延迟 ______ ms | 控制台 ______
[A-02] 结果 ______ | 注意入口 ______ | 报错 ______
[A-03] <330px ______ | 中档 ______ | >620px ______ | 横向滚动条 ______ | 截图 ______
[A-04] 触发 ______ | 快捷键页冲突 ______ | 冲突方 ______
[A-05] 图标右键 ______ | 正文右键 ______
[A-06] 站点 ______ | 报错 ______ | 受影响 UI ______
[A-07] session ______ | executeScript ______ | 重复注入 ______ | 1525400 ______
[结论] 通过 ______ 项 / 失败 ______ 项 / 需要改代码的点 ______
```

---

## 5. 与其他文档的关系

| 文档 | 覆盖 |
|---|---|
| `Firefox-适配技术方案.md` 附录 F.5 | 无头真机已实测通过的部分（脚本零报错、API 存在性、manifest 被接受） |
| `Firefox-适配技术方案.md` 附录 F.6 | 这 7 项的原始清单（本文是它的可执行版本） |
| 本文 | 有头人工点验的操作脚本与判据 |
| `port-docs/RELEASE-v1.66.1-ff-port.md` | 安装方法与逐项验证状态 |
