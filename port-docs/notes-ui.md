# LaterOn 1.66.1 — UI 层代码事实（Chrome/Edge MV3 → Firefox 移植前置分析）

- 分析对象：`F:\ALL_AI\小助理\open-source-collection\lateron-firefox-port\repo`
- 版本：manifest `1.66.1`，`manifest_version: 3`，`minimum_chrome_version: "121"`，`default_locale: "zh_CN"`（manifest.json 全文已读）
- 方式：只读源码，未修改 repo 任何文件。下文所有 `文件:行号` 均来自实际读取。
- 行号基准：`sidepanel.js` 共 **1563** 行、`library.js` 共 **2523** 行（读取工具报告的总行数；PowerShell `Measure-Object -Line` 不数空行，故给出 1469/2361，引用一律用前者）。
- UI 文件行数：sidepanel.css 241、library.css 595、dialog.js 640、picker-ui.js 605、i18n.js 288、theme.js 67、boot.js 93、settings.js、settings.css 119、dialog.css 240、onboarding.css 24、theme-vars.css。

manifest 关键事实（manifest.json）：
- `side_panel.default_path = "sidepanel.html"`；`options_page = "settings.html"`；`action` 只有 `default_title` + `default_icon`，**无 `default_popup`**。
- `permissions`：`activeTab, storage, unlimitedStorage, alarms, scripting, tabs, sidePanel, contextMenus`；`host_permissions`：`http://*/*`、`https://*/*`。
- `commands`：`quick-save`(Alt+1)、`toggle-translation`(Alt+2)、`save-all-tabs`(Alt+Shift+1)。
- `omnibox.keyword = "lo"`；`background.service_worker = "background.js"`。
- `web_accessible_resources` 只暴露 `icon128.png`（给注入到网页的浮层用）。
- **没有 `browser_specific_settings`，没有任何 Firefox 相关键，没有 `sidebar_action`。**

---

## 1. 侧栏生命周期：打开、关闭、常驻假设、与 background 的协议

### 1.1 谁打开侧栏

- 侧栏不是由 UI 页面自己拉的，而是后台/浏览器行为打开：
  - `background.js:261-268`（注释「Chrome 与 Edge 共用 Side Panel API…显式开启 openPanelOnActionClick，工具栏图标便会在两端直接切换 LaterOn 侧栏」）调用 `chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })`，并 `typeof chrome.sidePanel?.setPanelBehavior !== "function"` 时才返回 false —— 已有能力探测。
  - `library.js:2241-2251` `openSidePanel(windowId)`：`if (typeof chrome.sidePanel?.open !== "function") return false;` 然后 `chrome.sidePanel.open({ windowId })`；无 windowId 时回退到 `chrome.tabs.query({active:true,currentWindow:true})` 再开。
  - `sidepanel.js:1452-1454`：打开收藏条目时若命中的标签页在**另一个窗口**，`chrome.sidePanel.open({ windowId: openTab.windowId })` 把侧栏跟过去。

### 1.2 谁关闭侧栏

- `sidepanel.js:607-628` `#openLibrary` 点击 → `chrome.runtime.sendMessage({ type: "OPEN_LIBRARY", context: { source: "sidepanel", projectId, filter, focusItemId } })` → 成功后 **`await chrome.sidePanel.close({ windowId: activeTab.windowId })`（sidepanel.js:622）**；异常分支里才是 `window.close()`（sidepanel.js:625，且仅在 `libraryOpened` 为真时调用）。
- 因此对 `chrome.sidePanel.close()` 的依赖是**硬依赖**，而 Firefox 没有 `sidePanel.close` 的等价物（Firefox `sidebarAction` 无 close API）。这是移植必须处理的点。

### 1.3 与 background 的消息协议（UI 侧实际用到的 type，全部带行号）

| type | 发送方:行号 | 语义 |
|---|---|---|
| `PING_SIDEPANEL` | 监听于 `sidepanel.js:37-41`；请求方 `library.js:2258`（`waitForSidePanelReady`） | 询问「某窗口的侧栏是否已就绪」，应答 `{ ready: sidePanelReady && id === message.windowId }` |
| `EXTRACT_METADATA` | `sidepanel.js:485` | 让后台抓当前页标题/摘要/封面 |
| `QUICK_SAVE_TAB` | `sidepanel.js:591`（`source: "panel"`） | 收藏当前页，走与快捷键同一条链路 |
| `OPEN_LIBRARY` | `sidepanel.js:611-619` | 打开/接管全屏 library.html，携带侧栏现场 |
| `MUTATE_ITEMS` | `sidepanel.js:1480`、`library.js:2268` | 批量改条目（operation/ids/patch） |
| `CREATE_PROJECT` | `picker-ui.js:20`、`library.js:2303` | 新建项目 |
| `SHOW_LIBRARY_NOTICE` | 监听于 `library.js:129` | 在全屏页显示提示 toast |

- `sidepanel.js` **没有** `chrome.runtime.getContexts`，**没有** `navigator.userAgent`，**没有** `chrome.storage.session`，**没有** `chrome.action.*`。

### 1.4 「侧栏常驻 / 只加载一次」的假设 —— 存在但已做防护

- 明确假设侧栏会被反复关闭再打开，因此做了「秒开缓存」：
  - `sidepanel.js:17-23`：`CACHE_KEY = "laterOnPanelCache"` 存在**本页 localStorage**（「打开侧栏时先画缓存，再去 chrome.storage 拿最新数据核对」），并有 `localStorageSlow` 降级开关。
  - `sidepanel.js:25-26`：模块级 `sidePanelWindowId`、`sidePanelReady` 跨调用保留（同一页面实例内）。
  - `sidepanel.js:28-34`：`const windowIdReady = chrome.windows.getCurrent().then(...)` —— **每次页面加载只查一次**窗口 id。
  - `sidepanel.js:301-312`：`cacheHit` → 先画 `CACHE_PREVIEW_LIMIT`（=12，sidepanel.js:65）条缓存 → `sidepanel.js:316` 才 `await storedPromise` 拿真数据 → `sidepanel.js:362` `sidePanelReady = true`。
  - `sidepanel.js:63-65` 注释：「秒开缓存只为第一屏服务，不是第二份完整数据库」。
- 结论：**没有「侧栏进程常驻」的硬假设**，页面每次重开都会完整重跑 `init()`（sidepanel.js:264-368）并从 `chrome.storage.local` 校准。跨会话状态一律走 `chrome.storage.local` + 本页 localStorage 缓存，不依赖内存全局变量存活。这一点对 Firefox 是**好消息**。
- 但 `sidepanel.js:39` 的 `sidePanelReady` 语义是「**本窗口**这页侧栏已就绪」，握手依赖 `chrome.windows.getCurrent().id` 与 `message.windowId` 相等 —— Firefox 的 `sidebarAction` 没有 windowId 概念（每个窗口一个侧栏，但无 API 去查询/打开指定窗口的侧栏），这块语义要整体重设计。

---

## 2. 页面类型差异：library.html（全屏）vs sidepanel.html（侧栏）

### 2.1 资源清单是**两套独立实现**

- `sidepanel.html:98-105`：`boot.js, theme.js, i18n.js, onboarding.js, url-utils.js, tab-navigation.js, sidepanel.js`（全部 `defer`）；样式 `theme-vars.css + sidepanel.css + onboarding.css`（`sidepanel.html:89-95`，以 `media="print"` + `data-boot-style` 延迟生效）。
- `library.html:15-19, 195-197`：`theme.js, i18n.js, dialog.js, picker-ui.js, onboarding.js(defer)` + `url-utils.js, tab-navigation.js, library.js`；样式 `theme-vars.css + dialog.css + onboarding.css + library.css`。
- **两侧不共用任何渲染 JS**：`sidepanel.js`（1563 行）与 `library.js`（2523 行）是两份各自独立的列表渲染/存储读写的实现，只共享：
  - `theme-vars.css`（配色变量）、`theme.js`、`i18n.js`、`onboarding.js/.css`、`url-utils.js`、`tab-navigation.js`
  - `dialog.js/.css`（**sidepanel 只在首次用到弹窗时才动态加载**，见 2.3）
  - `picker-ui.js`（**仅 library.html 静态加载**，sidepanel 完全不用）
  - 存储键与 `chrome.storage.onChanged` 广播（`sidepanel.js:370-384`、`library.js:290`）
- `sidepanel.html` **不加载** `dialog.css`/`dialog.js`/`library.css`/`library.js`。

### 2.2 两者互相打开的方式

- 侧栏 → 全屏：`sidepanel.js:607-628`，走 `chrome.runtime.sendMessage({type:"OPEN_LIBRARY", context:{source:"sidepanel",...}})` 交给后台开（后台侧 `background.js:1670-1694`：`baseUrl = chrome.runtime.getURL("library.html")`，`background.js:1672` 注释「只有从侧栏明确点『展开全屏』时才携带现场」，已存在则 `chrome.tabs.update(existing.id, patch)`）。
- 全屏 → 侧栏：`library.js:2196-2213`，`if (!(await openSidePanel(destinationWindowId))) { …; showToast(tr("sidePanelFallback")) }`，否则 `chrome.tabs.create({url: target, openerTabId: libraryTabId})`。i18n 键 `sidePanelFallback`（`i18n.js:113` / `i18n.js:239`）=「侧栏打开失败，已在新标签页中打开」/「Couldn't open the side panel; opened the page in a new tab instead」——**已经为「没有侧栏 API」准备了降级文案**。
- 现场传递用 URL query：`library.js:256-283` 读 `launchParams.get("from") === "sidepanel"`，据此决定 `activeProject`、`pageTitleMode`（`"section"` vs `"home"`）、`filter`、`initialLocateItemId`。这是**唯一**的页面类型分支机制，移植时可原样保留。
- 全屏 → 设置：`library.js:353-362` `chrome.runtime.getURL("settings.html")` + `chrome.tabs.getCurrent()` → `chrome.tabs.update(tab.id,{url})`，否则 `chrome.tabs.create`。
- 侧栏 → 设置：`settings.js` 里 `chrome.tabs.getCurrent()`（settings.js:95, 136）配合 `chrome.tabs.update`。
- 全屏拖动排序/打开多标签用 `chrome.tabs.create({url, active:false, openerTabId: libraryTabId || undefined})`（`library.js:2106`）。

### 2.3 sidepanel 的按需加载（移植相关）

- `sidepanel.js:430-446`（注释：「编辑弹窗不是首屏能力：侧栏打开时不加载 27KB 的 dialog.js 和对应 CSS」）：首次需要弹窗时创建 `<style data-lateron-dialog-style>` 与 `<script src="dialog.js">` 动态插入，`script.onload` 里断言 `window.LaterOnDialog` 存在，失败 reject `new Error("弹窗脚本未就绪")`。
- 这是**扩展页内**从自身包加载脚本，MV3 默认 CSP（`script-src 'self'`）下 Firefox 同样允许，但属于需要在 Firefox 实测的点（见「未证实」）。

---

## 3. 浏览器专有假设（UI 层）

### 3.1 `chrome.*` 在 UI 页面里的完整用法

`sidepanel.js`（全部命中，grep 逐行）：
`chrome.windows.getCurrent()` 31；`chrome.runtime.onMessage` 37；`chrome.storage.local.get/set` 115/261/295/418/562/571/841/843/1134/1168/1241/1244/1279/1446；`chrome.storage.onChanged` 370；`chrome.tabs.query({active:true,currentWindow:true})` 472/610；`chrome.runtime.sendMessage` 485/591/611/1480；`chrome.tabs.onActivated` 509、`chrome.tabs.onUpdated` 510；**`chrome.sidePanel.close({windowId})` 622**；`chrome.tabs.create` 920/1460；**`chrome.sidePanel.open({windowId})` 1452-1453**。

`library.js`：
`chrome.runtime.onMessage` 129；`chrome.storage.local.*` 178/181/189/235/242/251/378/727/778/813/816/1281/1543/1589/1859/1996/2005/2033/2036/2191；`chrome.tabs.query({active:true,currentWindow:true})` 243；`chrome.storage.onChanged` 290；`chrome.runtime.getURL("settings.html")` 353；`chrome.tabs.create` 357/2106/2200/2213；`chrome.tabs.getCurrent()` 360/2229；`chrome.tabs.update` 361/2212；`chrome.windows.getCurrent()` 2235；**`chrome.sidePanel?.open` 2242-2244, 2249**；`chrome.runtime.sendMessage` 2258/2268/2303；`chrome.windows.create({url: targets, focused: true, type: "normal"})` 2468。

其他 UI 文件：
- `theme.js:29/38/49`（storage.local.get/set/onChanged）、`theme.js:18/60`（matchMedia）。
- `i18n.js:264/270/271`（storage.local）、`i18n.js:30/40/156/166`（**Chrome 专有文案 + `chrome://extensions/shortcuts` 硬编码 URL**）。
- `settings.js:71` `chrome.commands.getAll()`；**`settings.js:85` `chrome.tabs.create({ url: "chrome://extensions/shortcuts" }).catch(()=>{})`**；`settings.js:94-96`（`getURL("library.html")?guide=1` + `tabs.getCurrent/update`）；`settings.js:109/126/128`（getURL + tabs.create）；`settings.js:136-137`；`settings.js:143-217`（storage 导入导出/清空，键：`laterOnItems/laterOnProjects/laterOnCovers/laterOnOrder/laterOnCurrentItem/laterOnReadingPositions`）；`settings.js:273`（`laterOnDiag/laterOnPanelDiag/laterOnLocateDiag`）。
- `onboarding.js:14/100`（storage.local）。
- `boot.js:16`（storage.local，为了首屏语言）。
- `picker-ui.js:20`（runtime.sendMessage CREATE_PROJECT）、`picker-ui.js:26`（runtime.getURL，包裹在 try/catch 的 `safeRuntimeUrl` 里）。
- `tab-navigation.js:20/28/29/30`：`chrome.tabs.query({})`、`chrome.tabs.update`、`chrome.windows?.update`（**已做 `typeof chrome.windows?.update === "function"` 特性检测**）。
- `dialog.js`：**零 `chrome.*` 调用**（grep 无命中）——纯 DOM + `window.LaterOnI18n`。
- `url-utils.js`：零 `chrome.*`。

### 3.2 没有的东西（对移植是好消息）

- **全部 UI 文件中没有** `navigator.userAgent` / `window.chrome` 特性检测 / `chrome.runtime.getContexts` / `chrome.storage.session` / `chrome.action.*` / `chrome.windows.create({type:'popup'})`（用的是 `type: "normal"`，library.js:2468）/ `ResizeObserver`。
- 浏览器分支判断只在**两个地方**以能力探测形式出现：`chrome.sidePanel?.open/setPanelBehavior`（library.js:2242、background.js:266）与 `chrome.windows?.update`（tab-navigation.js:29）。没有 UA 嗅探，没有「是 Chrome 还是 Firefox」的显式分支。
- `picker-ui.js:199` 的安全来源白名单**已经包含 `"moz-extension:"`**：`["https:","data:","blob:","chrome-extension:","moz-extension:"]` —— 可见作者已考虑过 Firefox。

### 3.3 需要改的 Chrome 专有项（UI 层硬编码）

1. `sidepanel.js:622` `chrome.sidePanel.close({ windowId })` —— Firefox 无等价 API。
2. `sidepanel.js:1452`、`library.js:2242-2249` `chrome.sidePanel.open({ windowId })` —— Firefox 无 `sidePanel`，需换成 `browser.sidebarAction.open()`（且**只能在用户手势里调用**，Firefox 限制严格）。
3. `settings.js:85` `chrome://extensions/shortcuts` + `i18n.js:40/166` 同一 URL 的文案 —— Firefox 应为 `about:addons` 的「管理扩展快捷键」。
4. `i18n.js:30/156`、`i18n.js:32/158`（「Chrome 不允许扩展在内部修改快捷键」/「在 Chrome 中管理快捷键」/「Manage shortcuts in Chrome」）—— 文案需按浏览器改写。
5. `sidepanel.js:39` 与 `library.js:2254-2260` 的 `windowId` 握手 —— Firefox `sidebarAction` 无 windowId 语义。
6. `manifest.json` 的 `side_panel` + `minimum_chrome_version: 121` —— Firefox 需 `sidebar_action`（default_panel / default_icon / default_title），且 `sidePanel` 权限在 Firefox 无意义。

---

## 4. 布局对侧栏宽度的假设

### 4.1 CSS 断点（sidebar 页专用）

- `sidepanel.css:6` `body { min-width: 280px; … }` —— **对侧栏最小宽度的硬编码假设**。
- `sidepanel.css:9` `header { … height: 58px; }`（窄栏默认）。
- `sidepanel.css:220` `@media (max-width:330px) { .save-label{display:none} .open-item{grid-template-columns:78px minmax(0,1fr)} .thumb{width:78px;min-height:88px} }` —— **极窄栏降级**。
- `sidepanel.css:222-247` `/* 拖宽侧边栏后，自动切换为完整界面的纵向卡片。 */ @media (min-width:620px) { … }`
  - `sidepanel.css:224` `header { height:64px; padding:0 22px; }`
  - `sidepanel.css:232` `.items { display:grid; grid-template-columns:repeat(auto-fill,202px); … }`（单列列表 → 多列网格）
  - `sidepanel.css:235` `.thumb { width:100%; height:auto; aspect-ratio:1.62; }`
  - `sidepanel.css:223-247` 整段是**「侧栏可被用户拖宽」这一 Chrome 特性的直接依赖**。
- 另有 `sidepanel.css:200` `@media (hover: none)`、`sidepanel.css:220` 窄栏断点，以及 `dialog.css:243` `@media (max-width:460px)`、`dialog.css:250` 与 `library.css:232`、`onboarding.css:24` 的 `prefers-reduced-motion`。

### 4.2 CSS 里的全屏页宽度假设（对比）

- `library.css:41` `.workspace { display:grid; grid-template-columns:248px minmax(0,1fr); max-width:1680px; min-height:calc(100vh - 78px); }`
- `library.css:510` `@media (max-width:900px)`、`library.css:517` `@media (max-width:620px)`、`library.css:263` `main { min-width:0; padding:36px clamp(24px,4vw,60px) 120px; }`、`library.css:494/536/582` 的 `max-width: min(…, calc(100vw - 36px))`。
- `settings.css:10/47/68` 的 `max-width:760px` 与 560/620 断点。

### 4.3 JS 里的宽度/高度判断

- **没有 `ResizeObserver`**（全仓 UI 文件 grep 无命中）。宽度变化只靠 **CSS 媒体查询**，JS 不监听尺寸变化。
- `sidepanel.js:72-74` 注释即缺陷记录：「顶部吸顶标题栏的窄栏兜底高度。实际定位会实时量 header：**侧栏拖宽后它会变成 64px**，再写死 58px 就会让卡片上沿藏在吸顶栏下面。」→ `const TOPBAR_FALLBACK_H = 58;`
  - `sidepanel.js:1117-1119`：`document.querySelector("header")?.getBoundingClientRect?.()` 实时测量，`Number.isFinite(measured) && measured > 0 ? measured : TOPBAR_FALLBACK_H`，再加 `LOCATE_EDGE_GAP`（sidepanel.js:75 = 10）。
  - 即**唯一**的宽度敏感 JS 逻辑已经写成「实时量 + 兜底常量」，Firefox 侧栏宽度不同不会算错，只是兜底值可能不准。
- 其他 `window.innerWidth/innerHeight` 都只用于**浮层/菜单夹到视口内**：`sidepanel.js:884-885`（右键菜单）、`sidepanel.js:1095/1125/1134/1135`（定位诊断记录 viewport）、`library.js:2114-2115`（菜单）、`picker-ui.js:292-294`（浮层上下翻转与水平夹取）。
- `sidepanel.js:1180-1181` 用 `container.getBoundingClientRect()` / `button.getBoundingClientRect()` 做分段控件的滑块定位。
- 全屏与侧栏的切换逻辑：见 2.2。**没有**「同一个页面根据宽度自适应变成侧栏/全屏」的 JS 逻辑 —— 二者是**两个独立 HTML**，靠 URL query 传现场。

### 4.4 Firefox 侧栏宽度/高度行为差异下的风险点

- Firefox 侧栏宽度由用户拖动、且**没有 620px 以上的「拖宽到极致」预期**（Firefox 侧栏通常较窄且上限小）；`sidepanel.css:223` 的整段多列网格可能永远不生效或在小宽度下抖动。
- Firefox 侧栏是**整个浏览窗口高度**、可任意宽；`sidepanel.css:6` 的 `min-width:280px` 与 `sidepanel.css:220` 的 330px 降级阈值在 Firefox 里可能落在不同位置（Firefox 侧栏默认 ~330px，正好在断点边界上）。
- `sidepanel.css:9` 的 `position: sticky; top: 0` + `backdrop-filter: blur(15px)`（sidepanel.css:9）在 Firefox 需要确认渲染表现（Firefox 支持 backdrop-filter，但侧栏合成层可能不同）。

---

## 5. i18n 与主题

### 5.1 i18n.js = **自研双语字典，不用 `chrome.i18n`**

- `i18n.js:287` `window.LaterOnI18n = { t, getLanguage, setLanguage, applyStatic, dictionaries, ready }`。
- 结构：IIFE 内 `dictionaries = { "zh-CN": {…}, en: {…} }`，**每个语言约 250+ 个键**（这是 36 KB 的全部来源；`_locales` 只有 528 B/564 B 的小 messages.json，仅提供 `__MSG_extensionName__` 等 manifest 文案）。
- **不使用 `chrome.i18n.getMessage`**（grep 全仓 UI 文件无命中），也不读 `_locales`。
- 语言来源：`i18n.js:264` `await chrome.storage.local.get(KEY)`，`result[KEY]?.language === "en" ? "en" : "zh-CN"`；写回 `i18n.js:270-271`。`KEY = "laterOnSettings"`。
- 静态文案用 `data-i18n*` 属性 + `applyStatic()` 批量替换（`settings.js:19-20`、`library.js:239-240`、`sidepanel.js:281`、`onboarding.js:98` 都调它）。
- 页面内**还有第二套文案来源**必须同步改：`document.documentElement.lang === "en"` 的运行时分支 —— `sidepanel.js:166/187/1518`、`library.js:1144/1154/2504`、`picker-ui.js:33`、`boot.js:11-19/63/67-69`（boot.js 甚至自带一句硬编码英文 "Opening your saves…"）。
- `picker-ui.js:34-54` **自带一份中英文 copy 对象**（因为要注入网页、不能依赖 `window.LaterOnI18n`），与 `i18n.js` 的字典是**重复维护**的两份文案。
- `dialog.js:37` 用 `window.LaterOnI18n?.t(key, vars) || key` 的软依赖写法（拿不到就显示 key 本身）。
- **对移植的影响：i18n 与浏览器 API 完全解耦，Firefox 侧零改动即可工作**（唯一要改的是 `chrome://extensions/shortcuts` 那几条文案，见 3.3）。

### 5.2 theme.js = 明确三态 + prefers-color-scheme

- `theme.js:4-14` `DEFAULTS`：`theme: "light"`（可选 `light | dark | system`）、`defaultSort`、`autoMarkRead`、`askFolderOnBatch/Single`、`autoCleanDays: 30`、`language: "zh-CN"`。
  - **默认是 `light` 而非 `system`** —— 不跟随浏览器主题，除非用户显式选「跟随系统」。
- `theme.js:16-22` `resolveTheme`：`theme === "system"` 时才 `window.matchMedia("(prefers-color-scheme: dark)").matches`。
- `theme.js:24-26` `applyTheme` → `document.documentElement.dataset.theme = "dark" | "light"`（唯一主题挂载点，CSS 变量在 `theme-vars.css` 里按 `[data-theme]` 覆盖）。
- `theme.js:28-34` `get()`（storage 读取 + 默认值合并）、`theme.js:36-46` `set()`、`theme.js:48-54` `watch()`（`chrome.storage.onChanged`，`area === "local"`）。
- `theme.js:57-64`：进入页面立即 `get().then(applyTheme)`；`matchMedia(...).addEventListener("change", …)` 监听系统主题变化，**并带 `else if (media.addListener)` 的老式 API 回退**（Firefox 老版本兼容写法）。
- `theme.js:66` 暴露 `window.LaterOnSettings`。
- **三方独立实现同名逻辑**：`sidepanel.js` 不静态加载 `dialog.js`，但 `sidepanel.html:100` **确实加载了 theme.js**；`picker-ui.js:61-63` 则自己重算了一遍 `matchMedia`（`themeSetting !== "light" && prefersDark`）——即注入网页的浮层无法读 `window.LaterOnSettings`，只能靠调用方把 `theme` 塞进 options。
- `library.html`/`settings.html` 的 `<head>` 早期加载 theme.js（`library.html:15`、`settings.html:14`），但 `sidepanel.html:100` 是 `defer`（theme.js:2 的注释「被 library / settings 两个页面在 <head> 早期引入」已过时）。
- **移植影响：theme 完全基于 `matchMedia` + `chrome.storage.local`，Firefox 全兼容，零改动。**

---

## 6. 对话框 / 选择器 UI：页面内 DOM 还是注入网页？

两个文件**定位完全不同**，不能混为一谈：

### 6.1 `dialog.js`（+`dialog.css`）= **纯扩展页 DOM，不注入网页**

- 使用方式：`dialog.js:2-3` 注释「页面需引入 dialog.css + dialog.js」；静态加载于 `library.html:12/17`、`settings.html:12/16`；`sidepanel.js:430-446` 在首次需要时**动态**插入 style + `<script src="dialog.js">`。
- 挂载点：`dialog.js:111` `const mount = document.body || document.documentElement;` → `dialog.js:137` `mount.append(host)`。**普通 DOM，不是 Shadow DOM**，样式靠 `dialog.css` 的 `.lod-*` 类名。
- 因为是扩展页特权上下文，**不存在宿主页面 CSS 冲突问题**，所以不需要隔离。
- API（`dialog.js:629-639`）：`LaterOnDialog.confirm/alert/prompt/close/isOpen`；`prompt` 返回 `{ok, values}`，支持 `fields`（input/textarea，`dialog.js:192-215`）、`cover`（本地上传 + canvas 压缩，`dialog.js:46-78`，`COVER_MAX_EDGE = 720`、`COVER_QUALITY = 0.72`、20 MB 上限）、`picks`（封面组合拖拽排序，`dialog.js:344-517`）。
- 键盘：`dialog.js:158-189` 捕获阶段处理 Esc / Tab 循环焦点 / Enter（textarea 里 Ctrl/⌘+Enter 才提交）；同一时刻只显示一个（`dialog.js:611-627` 的 Promise 链排队）。
- **无任何 `chrome.*` 调用**，i18n 走软依赖 —— Firefox 可直接用。

### 6.2 `picker-ui.js` = **同一份代码既作扩展页浮层、也注入网页**

- `picker-ui.js:1-12` 顶部注释即设计说明：「收藏库（全屏页）和网页浮层（content script）共用的『选项目』面板」；「约定：本文件**不依赖任何外部变量/函数**（包括 chrome.* 也不在顶层调用），这样它**既能作为 content script 注入网页，也能被扩展页用 `<script>` 直接加载**。」
- 两种用法：不传 `anchor` = 整屏弹窗（带灰色遮罩、居中）；传 `anchor` = 贴着按钮的浮层（无遮罩、`positionPanel()` 定位，`picker-ui.js:285-297`）。
- 唯一的 chrome 调用都在函数体内并被 try/catch 包裹：`picker-ui.js:20` `chrome.runtime.sendMessage({type:"CREATE_PROJECT"})`、`picker-ui.js:26` `chrome.runtime.getURL`（`safeRuntimeUrl`，失败返回 `""`）。
- **注入方式（不在 manifest，而是后台运行时注入）**：`background.js:1219-1222`
  - `background.js:1221` 注释：「picker-ui.js 先注入（提供 window.openFolderPicker），content-folder-picker.js 再调用它。」
  - `background.js:1222` `files: ["picker-ui.js", "content-folder-picker.js"]`（`chrome.scripting.executeScript`）。
  - `content-folder-picker.js:2-6/31-36`：「⚠️ 必须自包含地被注入：不依赖任何外部变量，只靠 `window.openFolderPicker`」；若 `typeof window.openFolderPicker !== "function"` 就安静退出。
  - 另有 `background.js:1198`、`1236` 两处 `chrome.scripting.executeScript`。
- **宿主页面 CSS 冲突防护（三层，全部在 picker-ui.js 内）**：
  1. `picker-ui.js:72-75`：宿主 `div#lateron-folder-picker` 上加**内联 `all: initial !important`**（注释：「双保险：内联 !important 能压过页面自己的样式表，保证浮层不被页面搞变形」）。
  2. `picker-ui.js:77` `host.attachShadow({ mode: "open" })`；`picker-ui.js:450` 样式表第一条 `:host { all: initial; }`；`picker-ui.js:451` 对内部所有元素 `box-sizing: border-box`；`picker-ui.js:452-460` 显式重置 font-family/size/weight/line-height/letter-spacing/text-align/text-transform/text-indent/white-space/direction。
  3. `picker-ui.js:453` `z-index: 2147483600`（近 int32 上限）。
  - 品牌图用 `safeRuntimeUrl("icon128.png")`（`picker-ui.js:86`），对应 manifest `web_accessible_resources` 里的 `icon128.png`（manifest.json 尾部）。
  - 封面来源白名单含 `moz-extension:`（`picker-ui.js:199`），并明确拒绝 HTTPS 页面里的 HTTP 图（`picker-ui.js:202`）。
- **键盘/媒体冲突防护**（对 Firefox 同样重要，因为要注入网页）：
  - `picker-ui.js:369-396` 在捕获阶段统一处理键盘，用 `event.composedPath().includes(newInput)` 判断焦点（因为 Shadow DOM 会把 target 重定向）。
  - `picker-ui.js:257-283` 「播放守卫」：记录正在播放的 `<video>/<audio>`（`WeakSet`），浮层开着时被意外暂停就立刻 `media.play()` 恢复；注释指出「视频网站的空格键监听可能挂在 window 捕获阶段、比浮层更早注册，`stopPropagation` 拦不住」。
  - `picker-ui.js:299-313` `close()` 逐一移除所有 window 级监听（keydown/keyup/scroll/resize/pause/ended）后 260 ms 再删宿主。
- **结论：picker-ui.js 已按「会被注入到任意网页」的严格标准写，隔离手段对 Firefox 同样有效；移植风险低于预期。**

---

## 7. 中文注释里的线索（Chrome / Edge / 侧栏 / 快捷键 / 浏览器差异）

UI 层（本次负责范围）：
- `sidepanel.js:17-23`：「侧栏『秒开』缓存…打开侧栏时先画缓存…**就算存储读取慢，界面也不会白屏干等**」；`sidepanel.js:21-23`：「本机 localStorage 是不是本身就慢（第一次读就超过 0.4 秒即判定）。**慢的话就彻底不再碰它**」。
- `sidepanel.js:57-65`：「收藏一多（几百上千条），一次性把卡片全画出来会把主线程占住好几秒…**侧栏一屏通常只看得到 4–6 张**」→ `FIRST_BATCH = 8`、`CACHE_PREVIEW_LIMIT = 12`。**「侧栏一屏 4–6 张」是对侧栏可见区域高度的经验假设**。
- `sidepanel.js:72-74`：「**侧栏拖宽后它会变成 64px**」→ 见 4.3（已知缺陷记录）。
- `sidepanel.js:289-291`：「存储冷的时候这一次读取要好几秒…**排成一队的话，谁慢整条链就卡在谁后面（这正是之前白等十几秒的原因）**」。
- `sidepanel.js:430`：「编辑弹窗不是首屏能力：**侧栏打开时不加载 27KB 的 dialog.js** 和对应 CSS」。
- `sidepanel.js:1451`：「如果命中的页面在另一个窗口，也让 LaterOn 侧栏跟到那个窗口。」
- `sidepanel.js:1457-1458`：「**侧栏依附在用户正在浏览的网页旁边**，普通点击不能把那个网页覆盖掉。」
- `sidepanel.css:1-2`：「颜色全部来自 theme-vars.css（和全屏共用）：这里不再自己定义 :root 变量，否则这份写死的浅色值会和 `[data-theme="dark"]` 的覆盖冲突、把深色盖回浅色。」（**已知踩坑记录**）
- `sidepanel.css:4-5`：「padding 必须显式清零：head 里的首屏兜底样式给 body 留了 12px/16px 的空，不清掉的话吸顶导航栏够不到面板两缘（毛玻璃块两头缺一截，滚动时露馅）。」
- `sidepanel.css:222`：「**拖宽侧边栏后，自动切换为完整界面的纵向卡片。**」
- `sidepanel.js:265-267`、`boot.js:1-3`：侧栏打开耗时埋点体系（`laterOnPanelDiag` / `laterOnLocateDiag` / `laterOnDiag`），i18n 键 `panelSpeedLabel`「侧栏打开耗时」、`panelLocateLabel`「侧栏『滚到正在读』」（i18n.js:35）、`panelNever`「还没有打开过侧栏」（i18n.js:42）。**移植时应保留这套诊断，便于对比 Firefox 打开速度。**
- `library.js:256-283`：`from === "sidepanel"` 的启动现场分支（见 2.2）。
- `library.js:2286`：「复用 picker-ui.js 的 openFolderPicker（和网页收藏时选『收藏到哪个项目』是同一个窗口）」。
- `boot.js:67-69`：「This is taking longer than usual. **Close and reopen the side panel**; if it keeps happening, reload LaterOn on the Extensions page.」/「…可以先试试**关掉侧栏再打开**；一直这样就在**扩展页**点一下「重新加载」。」→ 已假定「扩展页」= `chrome://extensions`。
- `i18n.js:118` 同一句的字典版；`i18n.js:124`「暂时无法读取网页，请**关闭侧栏后重试**」。
- `i18n.js:96` 引导文案：「全屏管理，侧栏继续浏览 —— 在侧栏点击右上角全屏图标，切换全屏视图；**点击任意网页，自动缩放为侧栏模式**。」（描述的是 Chrome 的行为）
- `i18n.js:30/32/40`、`i18n.js:156/158/166`：**Chrome 专有 + `chrome://extensions/shortcuts` 硬编码**（见 3.3）。
- `i18n.js:35/42/113/124`：侧栏/面板相关文案（`sidePanelFallback`「侧栏打开失败，已在新标签页中打开」）。
- `settings.html:33` 标题「外观、快捷键、数据与启动方式」；`settings.html:92/106` 的 Chrome 文案。

**UI 层没有 TODO / FIXME 标记**（grep 无命中）。UI 层文件里也**没有**提到 Firefox / 火狐。

范围外（background.js，仅作上下文，非本次交付）：`background.js:261-264`「**Chrome 与 Edge 共用 Side Panel API**。manifest 里不再绑定 default_popup，再显式开启 openPanelOnActionClick，工具栏图标便会在两端直接切换 LaterOn 侧栏。」「避免 Edge 更新、扩展重新加载或浏览器同步后退回默认的『图标无动作』。」`background.js:99`「打开 LaterOn 侧栏」；`background.js:222`「快捷键只在**扩展首次安装**时由 Chrome 绑定，且可能被系统占用」；`background.js:501`「**Chrome 设置页等其它受保护页面**收不到扩展页消息，仍保留角标兜底」；`background.js:903/1271-1299` 使用 **`chrome.storage.session`**（Firefox 需 `storage.session`，MV3 112+ 支持，但与 service worker 生命周期耦合）；`background.js:1375`「抖音是单页应用。实测站内切换视频时各信号的更新时间线（**无头 Chrome**，逐 100ms 采样）」；`background.js:1672`「只有从侧栏明确点『展开全屏』时才携带现场」。

---

## 8. UI 层对 Firefox 侧栏适配影响最大的 5 个点

1. **`chrome.sidePanel.close/open` 三处调用（`sidepanel.js:622`、`sidepanel.js:1452-1453`、`library.js:2242-2249`）没有 Firefox 等价物。**
   - `sidePanel.close` 在 Firefox 完全无对应；`sidePanel.open({windowId})` 需换成 `browser.sidebarAction.open()`，且 Firefox 要求**必须在用户手势的同步调用栈内**（当前 `library.js:2241-2251` 是 async 且前面还 await 过别的，很可能被 Firefox 拒绝）。
   - 好消息：`library.js:2196-2198` 已有 `sidePanelFallback` 降级路径与文案，可复用。

2. **`windowId` 握手协议（`sidepanel.js:31-41` 的 `chrome.windows.getCurrent()` + `PING_SIDEPANEL`；`library.js:2254-2260` 的 `waitForSidePanelReady`）在 Firefox 语义不成立。**
   - Firefox 的 `sidebar_action` 面板没有「哪个窗口的侧栏」这种可查询/可打开的对象，`chrome.sidePanel.open({windowId})` 的窗口定向能力在 Firefox 无法复刻，`chrome.sidePanel.close` 之后就轮到 `window.close()`（`sidepanel.js:625`）——而 **Firefox 侧栏面板里的 `window.close()` 不会关闭侧栏**，`#openLibrary` 的「切到全屏并收起侧栏」体验会退化为「全屏打开了、侧栏还开着」。

3. **侧栏宽度的 620px 断点是整套 Firefox 布局风险的核心（`sidepanel.css:222-247`，尤其 `sidepanel.css:224` header 58→64px、`sidepanel.css:232` 单列→多列网格、`sidepanel.css:235` `aspect-ratio:1.62`）。**
   - Firefox 侧栏宽度由用户拖动且常见值更窄，`sidepanel.css:6` 的 `min-width:280px` 与 `sidepanel.css:220` 的 `max-width:330px` 降级阈值会落在与 Chrome 不同的实际宽度上；`sidepanel.js:74/1117-1119` 的量 header 逻辑虽然已写成实时测量 + 兜底常量，但兜底值 58px 是按 Chrome 窄栏定的，切换点错位会让「滚到正在读」定位偏。
   - `sidepanel.css:9` 的 `position:sticky` + `backdrop-filter: blur(15px)` 也需在 Firefox 侧栏合成层复测。

4. **Chrome 专有 URL 与文案（`settings.js:85` 的 `chrome://extensions/shortcuts`；`i18n.js:40/166` 硬编码同一 URL；`i18n.js:30/156`、`i18n.js:32/158`、`settings.html:92/106` 的 Chrome 措辞；`boot.js:67-69` 与 `i18n.js:118` 的「扩展页重新加载」）。**
   - Firefox 需改为 `about:addons` →「管理扩展快捷键」，且 `chrome.commands.getAll()`（settings.js:71）在 Firefox 只返回 `suggested_key`，用户实际改过的键位需按 `about:addons` 语义重做。

5. **`sidepanel.js` 与 `library.js` 是两份独立的列表渲染实现（1563 行 vs 2523 行），只共享 `theme-vars.css/dialog/i18n/theme/onboarding/url-utils/tab-navigation`，且 sidepanel 的 dialog.js 是动态注入（`sidepanel.js:430-446`）。**
   - 任何 Firefox 适配（如侧栏宽度自适应、侧栏打开/收起语义）都必须在**两处分别改**，且 `library.js:256-283` 的 `?from=sidepanel` 现场传递是二者唯一定位通道 —— 移植时应保留这一机制，避免顺手合并。
   - 相反，**i18n（i18n.js 自研字典）与 theme（theme.js 的 matchMedia + storage）对 Firefox 零改动**，`picker-ui.js` 的 Shadow DOM + `all:initial !important` 隔离也已含 `moz-extension:` 支持，均属低风险。

---

## 9. 未证实 / 不确定

以下内容本次**未取得确定性证据**，移植时必须实测或读对应源码确认：

1. **Firefox 是否支持 MV3 的 `side_panel` 键**：manifest.json 用的是 `side_panel.default_path`；Firefox 128+ 有 `sidebar_action`，但**是否接受 `side_panel` 键、是否会自动映射，本次未核实**（未联网、未查 Firefox 文档）。`minimum_chrome_version: 121` 在 Firefox 中被忽略还是报错，也未证实。
2. **Firefox `sidebarAction.open()` 的用户手势约束**：我认为它必须在手势调用栈内同步调用，但**没有在本次会话中验证**；`library.js:2241-2251` 的 async 链路能否满足需实测。
3. **Firefox 侧栏面板内 `window.close()` 的实际行为**：`sidepanel.js:625` 的兜底分支在 Firefox 里的效果未证实（是否抛错、是否静默无效、是否关掉整个面板）。
4. **`sidepanel.js:430-446` 动态 `<script src="dialog.js">` 注入在 Firefox MV3 下的 CSP 结果**：MV3 默认 `script-src 'self'` 应允许自身包内脚本，但 Firefox 的扩展页面 CSP 实现细节（是否需要 `web_accessible_resources`，同扩展内页面加载是否受限）**未实测**。注意 `dialog.js` **不在** manifest 的 `web_accessible_resources` 里（那里只有 `icon128.png`），若 Firefox 要求则需补。
5. **`sidepanel.css` 各断点在 Firefox 侧栏实际宽度下的触发情况**：Firefox 侧栏默认宽度、最小/最大宽度的具体数值未查阅，因此「620px 断点是否会触发」只是推断。
6. **`backdrop-filter` / `position:sticky` 在 Firefox 侧栏合成层下的渲染表现**未验证。
7. **`sidepanel.html:89-95` 的 `media="print"` → `link.sheet` → 切回 `"all"` 的首屏技巧（boot.js:30-42）在 Firefox 的行为**未证实：依赖 `link.sheet` 在样式表就绪时非空这一语义，Firefox 的实现差异未验证；`[300, 1200, 4000]` 三级定时器兜底（boot.js:42）应当能救回，但未实测。
8. **`chrome.storage.session`（background.js:903/1271-1299）与 Firefox `storage.session` 的差异**、以及 Firefox 是否已支持，未核实（且属 background 层，超出本次 UI 范围）。
9. **`chrome.commands.getAll()` 在 Firefox 的返回内容**（是否含用户自定义键、字段名是否一致）未证实。
10. **`_locales/zh_CN` 与 `_locales/en` 的 messages.json 内容**本次只看了文件大小（528 B / 564 B），未逐键读取；仅确认「只有两种语言、只覆盖 manifest 文案（`__MSG_extensionName__`/`__MSG_extensionDescription__`/`__MSG_actionTitle__`/`__MSG_commandSavePage__`/`__MSG_commandTranslatePage__`/`__MSG_commandSaveAllTabs__`）」这一结论是基于 manifest 里的 `__MSG_` 引用与文件体积推断的，**未逐条核对**。
11. **`library.js` 后半部分（961-2523）内部仍有未逐一列举的细节**：本次完整读取过，但笔记只保留了与移植相关的部分（chrome.* 调用、openItem/openSidePanel、菜单定位、封面组合、批量操作）。若移植时需要更细的库函数级事实，应重新定位到具体行号。
12. **`i18n.js` 字典键的完整清单**：本次确认其为自研双语字典、约 250+ 键/语言，但**未逐键导出**；如需对照翻译覆盖度，需另行提取。
13. **本次未分析**（不在交付范围但会影响移植）：`background.js`（81 KB，service worker → Firefox 背景脚本差异、`chrome.storage.session`、`chrome.scripting.insertCSS`）、`content-metadata.js`、`content-translation.js`、`translation.css`、`content-reading-position.js`、`reading-position-background.js`、`tests/`、`scripts/`。
