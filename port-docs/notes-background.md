# LaterOn 1.66.1 — background / service worker 事实清单（为 Firefox 移植准备）

- 仓库：`F:\ALL_AI\小助理\open-source-collection\lateron-firefox-port\repo`
- git HEAD：`00fde27 Fix YouTube video tab reuse and release 1.66.1`；`git status` 干净（本次分析全程只读，未改动任何仓库文件）
- `manifest.json:4` version `1.66.1`；`manifest.json:2` manifest_version 3；`manifest.json:6` minimum_chrome_version `121`；`manifest.json:5` default_locale `zh_CN`
- 姊妹目录 `lateron-firefox-port/upstream/LaterOn.git` 是一个裸仓库（未纳入本次分析）
- 引用格式：`文件:行号`，行号均为真实行号；`rpb` = `reading-position-background.js` 的简写（该文件被 `background.js:1` 用 importScripts 载入，**运行在同一个 service worker 全局作用域内**，因此它注册的监听器与主文件同级）

## 0. 本次阅读范围（决定结论置信度）

**通读全文**：`background.js`（1706 行 / 81,138 B）、`boot.js`（93 行）、`reading-position-background.js`（89 行）、`tab-navigation.js`（36 行）、`url-utils.js`（38 行）、`manifest.json`（78 行）、`scripts/build-release.py`（166 行）、`README.md`（83 行）。

**仅 grep / 局部读**：`library.js`（2523 行，只读了 2230-2269）、`sidepanel.js`（1563 行，只读了 610-634）、`settings.js`、`content-metadata.js`、`picker-ui.js`、`content-folder-picker.js`、`content-translation.js`、`content-reading-position.js`、`dialog.js`、`i18n.js`、`theme.js`、`onboarding.js`、`CHANGELOG.md`、`_locales/*/messages.json`、`tests/**`（只 grep，未运行）。

---

## 1. Service worker 装配与顶层执行顺序

- `manifest.json:37-39`：`background.service_worker = "background.js"`，**没有** `"type": "module"` → 经典脚本，不是 ESM。
- `background.js:1`：`importScripts("url-utils.js", "reading-position-background.js");`
- `url-utils.js:2-37`：IIFE，导出 `globalThis.LaterOnUrl = { normalize }`（`url-utils.js:37`）；`background.js:2` 立即 `const normalizeUrl = LaterOnUrl.normalize;`
- `reading-position-background.js:3-89`：IIFE，直接用 `globalThis.LaterOnUrl.normalize`（`rpb:7`），并在**后台上下文**注册 `chrome.tabs.onUpdated`（`rpb:66`）、`chrome.tabs.onActivated`（`rpb:71`）、`chrome.storage.onChanged`（`rpb:73`）、`chrome.runtime.onMessage`（`rpb:82`）。
- `tab-navigation.js` / `boot.js` **不在** SW 里：`tab-navigation.js:35` 挂 `globalThis.LaterOnTabs`（页面侧复用标签页逻辑）；`boot.js` 是 library/sidepanel 页面的骨架屏与计时脚本（`boot.js:16` 读 `laterOnSettings`，`boot.js:55` 用 `setInterval`）。
- SW 顶层立即执行的副作用顺序：
  1. `background.js:115` `resetActionAppearance().catch(() => {})`（每次 SW 启动都重置角标/标题）
  2. `background.js:275` `setupContextMenus()`（未 await）
  3. `background.js:279` `setupSidePanelAction()`（未 await）
  4. `background.js:348-353` 注册 `chrome.alarms.onAlarm` 并 `chrome.alarms.create(CLEAN_ALARM, { delayInMinutes: 2, periodInMinutes: 720 })`
  5. `background.js:355` `purgeExpiredItems().catch(() => {})`（每次唤醒都跑一次清理）
  6. `background.js:380` `ensureLegacyCleanup().catch(() => {})`（一次性迁移；注释 `background.js:377-379` 说明「重新加载扩展不会触发 onInstalled」，所以放在顶层）

---

## 2. 消息协议

### 2.1 background 收到的 `onMessage`（主监听器 `background.js:382-472`）

| type | 处理器行号 | 触发方（文件:行） | 参数 | 响应语义 | 异步 return true |
|---|---|---|---|---|---|
| `MUTATE_ITEMS` | `background.js:383-388` | `library.js:2268`、`sidepanel.js:1480` | `{operation:"delete"\|"update", ids:string[], patch?:{}}` | `{ok:true, items, covers, affected}`（`background.js:53`）或 `{ok:false, error}` | 是（`background.js:387`） |
| `SAVE_ITEM` | `background.js:389-394` | **全仓库找不到发送方**（仅此一处出现该字符串）→ 疑似遗留死代码；`popup.js` 已删除且被 `scripts/build-release.py:63-65` 列为 FORBIDDEN_NAMES | `message.item` | `saveItem()` 结果 `{ok, item, updated, duplicated, refreshed}`（`background.js:790`/`808`） | 是（`background.js:393`） |
| `OPEN_LIBRARY` | `background.js:395-400` | `sidepanel.js:611-619` | `context:{source:"sidepanel", projectId, filter, focusItemId}` | `{ok:true}` 或 `{ok:false,error}` | 是（`background.js:399`） |
| `CONFIRM_BATCH_SAVE` | `background.js:402-417` | `content-folder-picker.js:50` | `projectId` | 先用 `reply()` 去重回执 `{ok:true, tabCount}`（`background.js:404-412,1308`），后台继续 `runBatchSave` | 是（`background.js:416`） |
| `CANCEL_BATCH_SAVE` | `background.js:418-423` | `content-folder-picker.js:51` | — | `{ok:true, cancelled:boolean}`（`background.js:1301`） | 是（`background.js:422`） |
| `CREATE_PROJECT` | `background.js:425-430` | `picker-ui.js:20`、`content-folder-picker.js:47`、`library.js:2303` | `name` | `{ok:true, project, existed}`（`background.js:1259`/`1263`）或 `{ok:false,error}`（`background.js:1253`） | 是（`background.js:429`） |
| `EXTRACT_METADATA` | `background.js:433-449` | `sidepanel.js:485` | `tabId` | `{ok:true, metadata:{...url}}`（`background.js:1371`）或 `{ok:false,error}`；成功时先写 `lastCoverFrom/lastTitleFrom/lastCoverTitle/lastCoverAt` 诊断（`background.js:438-443`） | 是（`background.js:448`） |
| `QUICK_SAVE_TAB` | `background.js:453-471` | `sidepanel.js:591`（`source:"panel"`） | `tabId?`, `source?` | `{ok:true, ...quickSave结果}`（可能含 `pending:true`）/ `{ok:false,error}`；非 http(s) 页面拒绝（`background.js:459-462`） | 是（`background.js:470`） |
| `SAVE_READING_POSITION` | `rpb:82-88`（另一个独立监听器） | `content-reading-position.js:75` | `{itemId, y}` | `{ok:boolean}` | 是（`rpb:87`） |

要点：
- `background.js:382` 与 `rpb:82` 是**两个独立的 onMessage 监听器**（同一 SW）。`rpb:83` 对非 `SAVE_READING_POSITION` 直接 `return`（不返回值），不干扰主监听器。
- 全部 9 个处理器都是 `return true` 异步响应，没有同步处理器。
- `background.js:404-412` 的 `replied` 标志是「窗口已关闭时端口断开」的容错（注释 `background.js:409`）。

### 2.2 background 主动发出的消息

| 发送行号 | API | 消息 | 接收方 |
|---|---|---|---|
| `rpb:19` | `chrome.tabs.sendMessage` | `{type:"LATERON_READING_POSITION_INIT", itemId:null}`（未收藏时只通知「不用恢复」） | `content-reading-position.js:153` |
| `rpb:24-29` | `chrome.tabs.sendMessage` | `{type:"LATERON_READING_POSITION_INIT", itemId, y, language:"en"\|"zh-CN"}` | 同上 |
| `background.js:588-592` | `chrome.runtime.sendMessage` | `{type:"SHOW_LIBRARY_NOTICE", tabId, message}`，期望 `{shown:true}`（`background.js:593`） | `library.js:130` |

**不经 background 的消息**：`PING_SIDEPANEL` 由 `library.js:2258` 发给 `sidepanel.js:38-39`（background 无该处理器）；`SHOW_LIBRARY_NOTICE` 的处理器在 `library.js:130`。

---

## 3. `chrome.storage` schema

### 3.1 local（`chrome.storage.local`）

| key | 声明行 | 数据结构 | 写入位置 | 读取位置 |
|---|---|---|---|---|
| `laterOnItems` | `background.js:4` | `Array<Item>`，最新在前（`unshift` `background.js:805`）；`Item = {id: crypto.randomUUID(), title, description, image, favicon, source, projectId, url, savedAt:number, status:"unread"\|"done", doneAt:number\|null}` + 可选用户锁定标记 `titleEdited/descriptionEdited/imageEdited:true`；legacy 兼容字段 `read:boolean` | `789`、`806`、`1032`、`1049`、`1654`、`339` | `23`、`131`、`165`、`192`、`519`、`779`、`857`、`1023`、`1144`、`1645` |
| `laterOnProjects` | `background.js:5` | `Array<{id, name, createdAt, archived?:boolean, cover?:dataURL}>`（`archived` 过滤见 `1177`，`cover` 见 `1160`） | `1262` | `772`、`1143`、`1256` |
| `laterOnSettings` | `background.js:6` | 对象，background 只读：`language`（`"en"` 判定 `58`）、`theme`（`1185`）、`autoCleanDays`（`319`）、`askFolderOnBatch`（`864`）、`askFolderOnSingle` + `askFolderOnSingleOptIn`（`892`） | background **从不写** | `58`、`234`、`319`、`848`、`891`、`1145`（页面侧还见 `boot.js:16`） |
| `laterOnCurrentItem` | `background.js:7` | `string \| null` | `195`（设为当前条目）、`49`（删除该条目时置 null） | `22`、`49` |
| `laterOnOrder` | `background.js:62` | `{ [scope:string]: string[] }` | `46-48`（删除时过滤）、`339` | `46`、`328` |
| `laterOnCovers` | `background.js:65` | `{ [itemId]: dataURL }`；条目 `image` 字段存 `"local://<id>"` 指针（`1163-1168`） | `45`、`339` | `41`、`334`、`1146`、`1164`、`1167` |
| `laterOnPendingBatch` | `background.js:67` | `{createdAt, source, notifyTabId, projectId, savedCount, tabs:[{id,url,title,favIconUrl,discarded,status,windowId}]}`（`903-920`） | `903` | `1271`、`1275`、`1278`、`1297`、`1299` |
| `laterOnLastProjectId` | `background.js:69` | project id 字符串 | `1284`（set）、`1285`（remove） | `849`、`900` |
| `laterOnDiag` | `background.js:211` | 累积对象（字段见 3.3） | `215` | `214` |
| `laterOnCleanupV165` | `background.js:1633` | `true`，一次性迁移标记（键名写 V165，注释指向 1.14.0：`1637`、`1642`） | `1639` | `1634` |
| `laterOnRecentItems` | `background.js:1638` | 仅被 `remove`（「最近在看」已撤下） | `1638` | — |
| `laterOnReadingPositions` | `rpb:5` | `{ [itemId]: scrollY:number }` | `rpb:50`、`rpb:62` | `rpb:16`、`rpb:45`、`rpb:58` |

### 3.2 session（`chrome.storage.session`）

- 仅 1 个键，即 `laterOnPendingBatch`（`background.js:67`，注释 `background.js:66` 说明「关掉浏览器就没了，不占磁盘」）。
- 写入 `background.js:903`；读取/删除 `1271`/`1275`/`1278`（`claimPendingBatch`）与 `1297`/`1299`（`cancelPendingBatch`）。
- **10 分钟过期**：`background.js:1274` `Date.now() - (pending.createdAt || 0) > 10 * 60 * 1000` → 删除并返回 null。
- svnc/sync storage：全仓库未使用。

### 3.3 `laterOnDiag` 字段清单（`recordDiag` 合并写入，`background.js:212-219`）

`lastCommand`、`lastTrigger`、`lastCommandAt`（`478`、`522-527`、`823`、`965`）；`lastStage`、`lastStageAt`（`526`、`823`、`830`、`875`、`936`、`1002`、`1104`、`1300`）；`lastRunAt`（`526`、`826`）；`lastTabCount`（`527`、`830`、`875`）；`lastProgress`（`1004`）；`lastAdded`、`lastDuplicated`、`lastMoved`、`lastEnriched`、`lastDegraded`（`836-841`、`1005-1006`、`1104-1110`）；`lastResultAt`（`841`、`1112`、`1300`）；`lastError`、`lastErrorAt`（`604`、`839-840`、`878-881`、`939-940`、`980-981`、`1117-1120`）；`lastCoverFrom`、`lastTitleFrom`、`lastCoverTitle`、`lastCoverAt`（`438-443`、`547-551`、`1014-1019`）。

### 3.4 迁移 / 版本逻辑

- **没有 schema 版本号字段**。版本化只靠 3 处兼容代码：
  1. `ensureLegacyCleanup()`（`background.js:1632-1640`）+ `cleanupLegacyContent()`（`1642-1655`）：把旧收藏上的 `contentHtml`/`wordCount`/`byline` 字段剥除（`1648-1653`），并删 `laterOnRecentItems`，用 `laterOnCleanupV165` 标记只跑一次。
  2. `isDoneItem()`（`background.js:305-309`）：1.40 之前只有 `read` 布尔、没有 `status`。
  3. picker 封面兼容三种历史形态：`covers` 直查、`local://<id>` 指针、旧 `data:`/远程 URL（`background.js:1163-1171`）。
- 未使用 `chrome.storage.local.setAccessLevel` 之类调用。

### 3.5 页面侧（非 background，但同一存储）相关键

`laterOnActiveProject`（`library.js:3`、`sidepanel.js:3`）、`laterOnFilter`/`laterOnFilterChosen`（`library.js:10-11`、`sidepanel.js:9-10`）、`laterOnPanelCache`（**localStorage**，`sidepanel.js:20`，探针 `sidepanel.js:251-252`，清除 `settings.js:218`）、`laterOnOnboardingSeen`（`onboarding.js:4`）、`laterOnPanelDiag`/`laterOnLocateDiag`（`settings.js:273` 读取）。清空数据时 `settings.js:216` 会 remove `laterOnCovers`、`laterOnOrder`、`laterOnCurrentItem`、`laterOnReadingPositions`。

---

## 4. Service worker 假设（可被回收的后果）

### 4.1 模块顶层可变状态（全部在 SW 全局）

| 状态 | 行号 | 用途 |
|---|---|---|
| `let itemWriteQueue = Promise.resolve()` | `background.js:10` | 串行化「读-改-写」；`queueItemWrite`（`11-15`）。`mutateItems`（`17-55`）、`saveItem`（`778`）、`runBatchSave` 内层（`1022`）、`purgeExpiredItems`（`312`）都走它 |
| `const injectedCssTabs = new Set()` | `background.js:72` | 记录哪些 tab 已注入 `translation.css`，避免重复堆叠（注释 `71`）；`ensureTranslationCss`（`73-81`）；清理 `onUpdated`（`85-87`）/`onRemoved`（`88`） |
| `actionFeedbackTimer` / `actionFeedbackUntil` | `background.js:93-94` | 工具栏角标临时反馈的定时器与截止时间；`showActionFeedback`（`104-113`，`setTimeout` 在 `109`）；`resetActionAppearance`（`96-102`） |
| `let omniboxGeneration = 0` | `background.js:160` | 地址栏联想防竞态（`162-176` 用 `163`/`169` 校验） |
| `let contextMenuRefresh = Promise.resolve()` | `background.js:226` | 串行化 `removeAll → create`（`232-257`），注释 `229-231` 解释防 duplicate id |
| `const pickerRunByTab = new Map()` | `background.js:1135` | 每个 tab 的浮层 runId；用于 `1139-1140` 递增、`1201-1203` 页面侧 `previous > id` 去重、`1230` 复核 |
| `let writeQueue = Promise.resolve()` | `rpb:8` | 阅读位置的串行写（`rpb:44-53`） |

### 4.2 定时器 / 延时

- SW 作用域的 `setTimeout`：`background.js:109`（角标复位）、`928`（浮层重试前等 180ms）、`1344`（`withTimeout` 通用超时）、`1454` 与 `1597`（抖音轮询 `DOUYIN_POLL_MS=100`，`1384`）。
- SW 作用域**没有** `setInterval`（`boot.js:55` 的 `setInterval` 在页面里，不在 SW）。
- `withTimeout(promise, ms, fallback)`（`background.js:1335-1350`）：到点返回兜底值，**永不 reject**；这是整套注入流程不卡死的核心保险。
- 相关超时常量：`EXTRACT_TIMEOUT_MS = 3000`（`1355`）、`PICKER_INJECT_TIMEOUT_MS = 1600`（`1133`）、`PICKER_VERIFY_TIMEOUT_MS = 700`（`1134`）、`DOUYIN_SETTLE_MS = 1500`（`1383`）、`DOUYIN_POLL_MS = 100`（`1384`）、`SERVER_META_TIMEOUT_MS = 8000`（`1477`）。

### 4.3 无 DOM 依赖（好消息）

- `background.js` 中出现的 `document.` / `window.` **全部在被注入的函数体内**（`636-660` 药丸 UI、`1205-1211` picker payload、`1238` 浮层复核、`1414-1415` 抖音探测）——这些函数是被序列化后送到页面执行的，不在 SW 里跑。
- SW 内**没有** `DOMParser`、`OffscreenCanvas`、`createImageBitmap`、`new Image`、`localStorage`、`indexedDB`。
- SW 内唯一的网络请求：`fetch(url, { credentials: "omit" })`（`background.js:1482`）+ `response.text()`（`1486`），由 `refetchMetaFromServer`（`1479-1533`）用正则解析 og 标签（无 DOMParser，注释 `1485` 说明只取前 200KB）。

### 4.4 依赖「后台常驻」的逻辑，与回收后会丢什么

**已按「会被回收」设计的部分**：
- 定时清理用 `chrome.alarms` 而不是 `setInterval`（注释 `background.js:346`：「服务worker 会被浏览器回收，用 alarms 才能在后台稳定触发」）。
- 批量收藏的待处理批次存 `chrome.storage.session`（`895-920`，注释 `902`），并带 10 分钟过期（`1274`），让 SW 重启后仍能 `claimPendingBatch`。
- `background.js:355` 每次唤醒都补跑一次过期清理；`115` 每次唤醒都重置角标外观。

**SW 被回收后会丢的具体清单**：
1. `injectedCssTabs`（`72`）丢失 → 同一 tab 会再次 `insertCSS` `translation.css`（`76`），可能堆叠重复样式表（该 Set 的存在意义就是避免这个，见注释 `71`）。
2. `pickerRunByTab`（`1135`）重置为 0 → 页面里的 `globalThis.__laterOnPickerRunId` 可能大于新 SW 的 runId，使 `background.js:1201-1203` 的 `if (previous > id) return;` **提前返回、不写 payload 节点**，随后 `1235-1243` 的存在性复核失败 → `showPickerOverlay` 返回 false。（**这是从代码逻辑推断，未实测**。）
3. `itemWriteQueue`（`10`）/ `writeQueue`（`rpb:8`）中断 → 已排队但未执行的「读-改-写」丢失；因为每次都重新 `get` 最新列表（注释 `9`），不会写坏数据，但那次修改会静默消失。
4. `actionFeedbackUntil`/`actionFeedbackTimer`（`93-94`）丢失 → 角标复位定时器消失；由顶层 `resetActionAppearance()`（`115`）在下一次 SW 启动时兜底。
5. `contextMenuRefresh`（`226`）中断 → `removeAll` 与 `create` 之间被打断时菜单可能短暂为空，直到下次 `setupContextMenus`（`275`、`281`、`285`）。
6. `omniboxGeneration`（`160`）丢失 → 正在进行的联想 `suggest()` 随端口一起消失，用户重新输入即可。
7. **长时间运行的 `runBatchSave`**（`962-1125`）：逐标签页顺序抓取（每篇最多 3s，`1355`），整批可能持续数十秒到数分钟。若 SW 在循环中途被回收，该批次**静默停止**（只留下 `laterOnDiag.lastStage = "逐个添加中"`），没有断点续作机制。
8. `settleDouyinDom` 的轮询循环（`1435-1455`，最长 1500ms）与所有 `withTimeout` 计时器（`1335-1350`）随 SW 消失。
9. `chrome.alarms.create` 在**顶层**每次唤醒都执行（`352`）——同名 alarm 会被重新创建；若浏览器把 alarms 持久化，则每次 SW 启动都会重置 12 小时周期。这是**推断**（Chrome 语义），未实测。

---

## 5. sidePanel 相关（全部调用点）

| 调用 | 行号 | 语义 |
|---|---|---|
| `typeof chrome.sidePanel?.setPanelBehavior !== "function"` | `background.js:266` | 能力探测，不支持就 `return false` |
| `await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` | `background.js:268` | 唯一的行为设置；注释 `261-264`：「Chrome 与 Edge 共用 Side Panel API…manifest 里不再绑定 default_popup，再显式开启 openPanelOnActionClick…避免 Edge 更新、扩展重新加载或浏览器同步后退回默认的『图标无动作』」 |
| `setupSidePanelAction()` 调用点 | `background.js:279`（SW 顶层）、`280-283`（`onInstalled`）、`284-287`（`onStartup`） | 冷启动 / 安装 / 浏览器启动都重申一次 |
| `manifest.json:15` `"sidePanel"` 权限；`manifest.json:34-36` `side_panel.default_path = "sidepanel.html"`；`manifest.json:22-30` `action` **无 `default_popup`** | — | 图标点击交给浏览器原生处理 |
| `chrome.sidePanel.open({ windowId })` | `library.js:2244`、`library.js:2249`、`sidepanel.js:1453` | 从全屏收藏库/侧栏打开侧栏；`library.js:2242` 先做 `typeof !== "function"` 探测，注释 `library.js:2240` 强调必须在用户点击手势内调用 |
| `chrome.sidePanel.close({ windowId: activeTab.windowId })` | `sidepanel.js:622` | 切到全屏收藏库后关闭侧栏 |
| 侧栏就绪握手 | `library.js:2254-2264`（80ms 轮询、1500ms 上限，发 `PING_SIDEPANEL`）↔ `sidepanel.js:31-39`（用 `chrome.windows.getCurrent()` 取 windowId，回 `{ready}`） | — |
| i18n 文案 | `i18n.js:113`（zh：`sidePanelFallback`「侧栏打开失败，已在新标签页中打开」）/ `i18n.js:239`（en）；使用点 `library.js:2198` | — |

- **全仓库没有 `chrome.action.onClicked` 监听器**（grep 无命中）→ 工具栏图标的点击行为**完全依赖** `openPanelOnActionClick`；`background.js:374-375` 的注释明确写了这一点。
- 全仓库**没有** `chrome.sidePanel.setOptions` / `getOptions` / `setPanelBehavior` 以外的 sidePanel 方法（grep 命中仅 `setPanelBehavior`、`open`、`close`）。

---

## 6. 内容脚本注入（`chrome.scripting`）

### 6.1 `executeScript` 逐条

| 行号 | 注入内容 | world | target | 用途 / 备注 |
|---|---|---|---|---|
| `rpb:23` | `files: ["content-reading-position.js"]` | 未指定 → ISOLATED | `{tabId: tab.id}` | 阅读位置恢复；仅当该网址已在 `laterOnItems` 中（`rpb:17-21`） |
| `background.js:565-569` | `files: ["content-translation.js"]` | **`world: "MAIN"`** | `{tabId: tab.id}` | `toggleTranslation`；失败（`injection[0]?.result?.ok === false`）时 `showActionError()`（`570`） |
| `background.js:632-664` | `func:` 内联药丸栈 + `args: [shown, overflow, 文案]` | 未指定 → ISOLATED | `{tabId}` | 页面右上角 pill 通知；`MAX_PILLS = 10`（`626`）、页面内 `MAX_STACK = 6`（`642`） |
| `background.js:1198-1214` | `func:` 写 `<script id="lateron-picker-payload-data" type="application/json">`（`1206-1209`）并 `document.dispatchEvent(new CustomEvent("lateron-picker-payload-ready"))`（`1211`）+ `args: [pickerPayload, runId]` | 未指定 → ISOLATED | `{tabId: tab.id}` | 传递浮层配置（注释 `1192-1195`：files 注入不能带 args，用 DOM 节点传递比两次注入共享全局更稳） |
| `background.js:1219-1223` | `files: ["picker-ui.js", "content-folder-picker.js"]`（顺序敏感，注释 `1221`） | 未指定 → ISOLATED | `{tabId: tab.id}` | 项目选择浮层；与上一条 `Promise.all` 并行（`1196-1227`） |
| `background.js:1236-1239` | `func: () => !!document.getElementById("lateron-folder-picker")?.shadowRoot` | 未指定 → ISOLATED | `{tabId: tab.id}` | 注入后存在性复核（注释 `1232-1234`） |
| `background.js:1439` | `func: probeDouyinFreshness`（`1412-1425`） | 未指定 → ISOLATED | `{tabId: tab.id}` | 抖音标题面板新鲜度探测，单次 900ms 超时（`1440`） |
| `background.js:1619-1622` | `files: ["content-metadata.js"]` | 未指定 → ISOLATED | `{tabId: tab.id}` | 元数据抓取；`readTabMetadata`（`1616-1630`） |

### 6.2 `insertCSS`

- `background.js:76` `chrome.scripting.insertCSS({ target: { tabId }, files: ["translation.css"] })`，由 `ensureTranslationCss`（`73-81`）保护一次。

### 6.3 target 与 URL 白/黑名单判断

- **所有注入的 target 只有 `{tabId}`**；没有 `allFrames`、没有 `frameIds`、没有 `frameId`（对已通读文件中每一处 `executeScript` 逐条核对得出；**未对整仓 grep** `allFrames/frameIds`）。
- 可注入性判断**只有一个函数**：`isWebUrl(url)`（`background.js:1665-1667`）= `/^https?:\/\//i.test(url || "")`。
  - 调用点：`131`（omnibox 过滤）、`191`/`194`（omnibox 打开）、`459`（QUICK_SAVE_TAB）、`498`（handleCommand）、`608`（reportFailure）、`829`（整窗收藏过滤）、`927`/`933`/`943`（浮层重试与降级提示）、`1138`（showPickerOverlay 入口）、`1326`（notifyOnActiveTab）、`1371`（extractTabMetadataById）、`1480`（服务端兜底）。
  - `rpb:10` 自己有一份同义实现（`const isWebUrl = (url) => /^https?:\/\//i.test(...)`），用于 `rpb:15`。
- **代码里没有针对 `chrome://`、`edge://`、`about:`、`file:`、`data:` 的显式黑名单**。受保护页面完全靠「非 http(s) 一律拒绝」隐式挡掉；相关说明只在注释与文档里：`rpb:32`（「标签可能已关闭、正在跳转，或属于浏览器保护页面」）、`background.js:79`（「页面受保护或已关闭，忽略即可」）、`background.js:501`（「Chrome 设置页等其它受保护页面收不到扩展页消息」）、`background.js:1322`（「若当前停在 Chrome 内部页面（新标签页 / 设置页等）无法注入」）、`background.js:1245`、`README.md:69-71`。
- 注入失败一律 `try/catch` + `withTimeout` 兜底，绝不抛出到顶层（`rpb:31-34`、`background.js:1244-1247`、`1627-1629`）。

---

## 7. 其他 API 用法细节

### 7.1 `chrome.tabs.*`

- **方法**：`query`（`458`、`496`、`607`、`828`、`1325`、`1681`；条件为 `{active:true,currentWindow:true}`、`{currentWindow:true}` 或 `{}`）、`get`（`457`、`1316`、`1364`、`rpb:14`）、`create`（`181`、`185`、`1694`）、`update`（`184` **未传 tabId**、`1691`）、`sendMessage`（`rpb:19`、`rpb:24`）。
- **事件**：`onUpdated`（`background.js:85` 清 `injectedCssTabs`；`rpb:66` 触发阅读位置 setup）、`onRemoved`（`background.js:88`）、`onActivated`（`rpb:71`）。
- **读取的 Tab 属性**：`id`、`url`、`title`、`favIconUrl`、`windowId`、`active`、`discarded`（`915`、`1431`、`1582`）、`status`（`916`、`1431`、`1582`，判定值 `"unloaded"`）、`pendingUrl`（`1683`、`1690`；`tab-navigation.js:22`）。
- `chrome.tabs.captureVisibleTab`、`chrome.tabs.discard`、`chrome.tabs.move/remove/reload/reloadAll` 等**均未使用**。

### 7.2 `chrome.windows.*`

- `background.js:1692` `chrome.windows.update(existing.windowId, { focused: true })`；`tab-navigation.js:29-31` 同样（先 `typeof chrome.windows?.update === "function"` 探测）。
- 页面侧：`library.js:2235` `chrome.windows.getCurrent()`、`sidepanel.js:31` `chrome.windows.getCurrent()`、`library.js:2468` `chrome.windows.create({ url: targets, focused: true, type: "normal" })`。

### 7.3 `chrome.contextMenus.*`

- 常量：`MENU_SAVE_ALL = "lateron-save-all-tabs"`（`background.js:224`）、`MENU_SAVE_PAGE = "lateron-save-page"`（`225`）。
- `removeAll`（`240`，回调里消费 `runtime.lastError` `241`）→ 两次 `create`（`255` contexts `["page","action"]`、`256` 同样）；标题按语言（`235-237`）。
- `onClicked`（`366-372`）：`MENU_SAVE_ALL` → `saveAllTabsInWindow("menu")`（`368`）；`MENU_SAVE_PAGE` → `quickSave(tab, "menu")`（`370`）。
- 刷新时机：`275-278`（`storage.onChanged` 且 `laterOnSettings` 变化）、`281`（`onInstalled`）、`285`（`onStartup`）；竞态串行化注释 `229-231`；`create/removeAll` 全部包 `try/catch`（`238-254`）。
- 注释 `221-223` 说明右键菜单的定位是「快捷键可能被系统占用」的兜底入口（README `README.md:67` 也这么写）。

### 7.4 `chrome.omnibox.*`

- `manifest.json:31-33` keyword `"lo"`。
- `setDefaultSuggestion`（`157`）+ 能力探测（`151`）；`escapeOmniboxText`（`118-125`）做 XML 转义（`&amp;`/`&lt;`/`&gt;`/`&quot;`/`&apos;`）。
- `onInputStarted`（`161`）重置默认提示；`onInputChanged`（`162-177`）→ `omniboxMatches`（`127-148`：按空格分词 AND 过滤、标题前缀/包含打分 4/3/2/1、按 `savedAt` 兜底排序、`.slice(0, 5)`），用 `<match>`/`<dim>` 富文本描述（`173`），`generation` 防竞态（`163`、`169`），异常时 `suggest([])`（`176`）。
- `onInputEntered`（`188-205`）：输入本身是网址且在库中 → 写 `laterOnCurrentItem`（`195`）后打开；否则打开 `library.html?q=<值>&from=omnibox`（`200-203`）。
- `openFromOmnibox`（`179-186`）：`newForegroundTab`/`newBackgroundTab` → `chrome.tabs.create({url, active})`；其余先 `chrome.tabs.update({url})`（无 tabId），失败再 `create`。

### 7.5 `chrome.commands.*`

- `chrome.commands.onCommand`（`476-485`）：先 `recordDiag({lastCommand, lastTrigger:"shortcut", lastCommandAt})`（`478`）再 `handleCommand`（`487-512`）。
- `handleCommand`（`487-512`）：`save-all-tabs` 不依赖当前页（`489-492`）；否则取 `commandTab` 或 `query({active:true,currentWindow:true})`（`494-496`），非 http(s) 时先在 library 页面发提示（`502`，`showLibraryCommandNotice` `579-597`），否则角标报错（`503`）。
- `settings.js:71` `chrome.commands.getAll()` 用于展示快捷键；`manifest.json:40-59` 三个命令：`quick-save`(Alt+1)、`toggle-translation`(Alt+2)、`save-all-tabs`(Alt+Shift+1)。

### 7.6 `chrome.alarms.*`

- `CLEAN_ALARM = "laterOnAutoClean"`（`background.js:292`）；`DAY_MS = 24*60*60*1000`（`293`）；`CLEAN_MIN_DAYS = 30`、`CLEAN_MAX_DAYS = 180`、`CLEAN_DEFAULT_DAYS = 30`（`294-296`）；`normalizeCleanDays`（`298-302`）夹取并取整。
- `onAlarm`（`349-351`）→ `purgeExpiredItems()`（`311-313` 走写队列 → `purgeExpiredItemsNow` `315-344`）。
- `create`（`352`）：`{ delayInMinutes: 2, periodInMinutes: 720 }` = 首次 2 分钟后、之后每 12 小时；注册被 `if (chrome.alarms)` 包住（`348`）。
- 清理判据：`isDoneItem(item) && Number(item.doneAt) > 0 && Number(item.doneAt) < cutoff`（`322-325`，注释 `321`：没有 `doneAt` 的老收藏一律不动），并同步清理 `laterOnOrder`（`328-332`）与 `laterOnCovers`（`333-338`）。
- 设置改动立即重扫（`357-360`）。

### 7.7 `chrome.action.*`

- `setBadgeText`（`100`、`107`）、`setTitle`（`101`）、`setBadgeBackgroundColor`（`108`）。
- 颜色：错误 `#d94841`（`574`）、成功 `#2f9e44`（`1076`、`1081`）、中性 `#111111`（`811`、`1081`）。
- **未使用**：`setIcon`、`setBadgeTextColor`、`onClicked`、`default_popup`（`manifest.json:22-30` 无 popup）。
- 注释 `90-92`：品牌图标不再常驻显示「已收藏 ✓」，只有主动收藏的进度/错误短暂出现。

### 7.8 `chrome.runtime.*`

- `getURL`（`200`、`581`、`1670`）、`onInstalled`（`280`）、`onStartup`（`284`）、`onMessage`（`382`、`rpb:82`）、`lastError`（`241`、`250`）、`sendMessage`（`588`）。

### 7.9 `chrome.storage.*`

- `local.get/set/remove` 遍布；`session.get/set/remove` 见 3.2；`storage.onChanged` **三个监听器**（`background.js:276`、`background.js:357`、`rpb:73`）。

### 7.10 其他库/平台 API

- `crypto.randomUUID()`（`794`、`1036`、`1261`）生成条目与项目 id。
- `new URL(...)`（`200`、`1388`、`1464`、`1517`、`1659`、`1671`；`url-utils.js:5`、`tab-navigation.js:7`）、`URLSearchParams`（`201-202`、`1675-1678`）。
- `fetch`（`1482`），`credentials: "omit"`。
- `matchMedia("(prefers-color-scheme: dark)")`：`picker-ui.js:62`、`theme.js:18`、`theme.js:59-60`（**不是** `display-mode`）。
- `localStorage`：`sidepanel.js:20`（`laterOnPanelCache` 键）、`sidepanel.js:251-252`（探针）、`settings.js:218`（清除）。

---

## 8. Chrome 专有假设（按移植影响排序）

**A. 结构性缺失（必须改架构）**

1. **`chrome.sidePanel.*` + manifest `side_panel`**：`background.js:266-268`、`manifest.json:15`、`manifest.json:34-36`；另有 `library.js:2242/2244/2249`、`sidepanel.js:622/1452-1453`。Firefox 没有 `sidePanel`，对应物是 `sidebar_action` manifest 键 + `browser.sidebarAction`（`open()` 只能在用户手势内调用，且没有 `openPanelOnActionClick` 这种「图标点击即开侧栏」的等价设置）。
2. **`importScripts` + `background.service_worker`**：`background.js:1`、`manifest.json:37-39`，且 manifest **没有** `"type": "module"`。Firefox 的 MV3 后台是**非持久事件页（window 上下文）**，`importScripts` 在该上下文不可用；移植通常要改成 `background.scripts: [...]` 数组（Firefox 专用键，Chrome 不接受）或改成 ESM 打包。这两个键互斥，所以同一份 manifest 无法同时喂两个浏览器。
3. **`manifest.json` 本身是 Chrome 专有**：`minimum_chrome_version`（`6`）、`service_worker`（`38`）、`side_panel`（`34-36`）、`permissions:["sidePanel"]`（`15`）。Firefox 还需要 `browser_specific_settings.gecko.id`；`omnibox.keyword`/`commands`/`options_page`/`web_accessible_resources`/`action.default_icon` 基本同名兼容。

**B. 语义差异（会静默出错）**

4. **`chrome.tabs.update({ url })` 不带 tabId**：`background.js:184`（omnibox 打开）与 `openFromOmnibox`（`179-186`）。Chrome 允许「更新当前活动标签」，Firefox 的 `tabs.update` 要求 tabId。
5. **`tab.pendingUrl`**：`background.js:1683`、`1690`、`tab-navigation.js:22`（`openLibrary`/`findOpen` 去重）。Chrome 专有属性，Firefox 没有 → 去重退化为只看 `url`。
6. **`tab.discarded` + `tab.status === "unloaded"`**：`background.js:915`（存入 pending batch）、`1431`（抖音等待提前放弃）、`1582`（直接用兜底元数据）。Firefox 有 `tabs.discard`/`discarded`，但 `status` 取值不是 `"unloaded"`（Firefox 只有 `"loading"`/`"complete"`）→ 判定需改写。
7. **`chrome.storage.session`**：`background.js:903`、`1271`、`1275`、`1278`、`1297`、`1299`。Firefox 115+ 才有该区域（本机未验证），且配额/退化行为不同。
8. **`chrome.scripting.executeScript({ world: "MAIN" })`**：`background.js:565-569`。Firefox 对 `world` 的支持较晚（需较新版本），是翻译功能的关键路径。
9. **`chrome.*` 命名空间的 Promise 用法**：全文件都是 `await chrome.storage.local.get(...)` / `.then()` 风格（如 `background.js:16`、`58`、`214-215`、`903`）。Firefox 的 `browser.*` 才保证 Promise；`chrome.*` 在 Firefox 上的 Promise 行为需要逐一验证——这决定移植是「加兼容层」还是「全量替换命名空间」。
10. **`contextMenus` 的 `contexts: ["page","action"]`**：`background.js:255-256`。Firefox 对 `"action"` 这个 context 的支持需验证。
11. **`chrome.action.setBadgeBackgroundColor`**（`108`）：Firefox 支持；但 Firefox 的自定义徽章颜色语义历史上有差异。

**C. 明确不存在于本代码库（降低移植难度的好消息）**

- 全仓库 grep **无命中**：`chrome.offscreen`、`chrome.declarativeNetRequest`、`chrome.runtime.getContexts`、`chrome.action.setBadgeTextColor`、`chrome.tabs.captureVisibleTab`、`Tab.frozen`。
- **完全没有浏览器分支判断**：全仓库 grep `navigator.userAgent`/`isFirefox`/`isEdge`/`isChrome`/`typeof browser`/`globalThis.browser` **零命中**。也就是说移植必须**新增**兼容层，现有代码没有任何「已经准备好」的开关。
- `matchMedia` 只用于 `prefers-color-scheme`（`picker-ui.js:62`、`theme.js:18/59-60`），不是 `display-mode`，Firefox 兼容。
- `chrome://` URL 处理：代码里**没有**任何 `chrome://` 字符串匹配逻辑（只出现在注释与 README 里），保护页靠 `isWebUrl` 隐式拒绝。

---

## 9. 中文注释 / 文档里的线索（含 TODO 与已知限制）

- `background.js:261-264`：「Chrome 与 Edge 共用 Side Panel API…manifest 里不再绑定 default_popup，再显式开启 openPanelOnActionClick…避免 Edge 更新、扩展重新加载或浏览器同步后退回默认的『图标无动作』」→ 说明作者已经处理过 **Edge** 的侧栏偏差，但没有处理 Firefox。
- `background.js:346`：「定时跑：服务worker 会被浏览器回收，用 alarms 才能在后台稳定触发」→ 作者对 SW 回收有明确认知。
- `background.js:362-364`：「新标签页劫持（已移除）…曾经支持 newTabPage + onCreated 监听，现已下线」→ 去掉了一处 Firefox 也需处理的 manifest 差异（`chrome_url_overrides`）。
- `background.js:377-379`：「不依赖 onInstalled —— 因为『重新加载扩展』不会触发 onInstalled」（Chrome 行为，Firefox 也不同）。
- `background.js:501`：「Chrome 设置页等其它受保护页面收不到扩展页消息」；`background.js:1322`：「若当前停在 Chrome 内部页面（新标签页 / 设置页等）无法注入」。
- `background.js:1375`：「无头 Chrome，逐 100ms 采样」→ 抖音新鲜度阈值是**在 Chrome 上实测**得出的（`1376-1381` 给出毫秒级时间线：+102ms 网址已换/面板未换，+318ms 全部对齐），Firefox 渲染时序不同，`DOUYIN_SETTLE_MS = 1500` 需重新验证。
- `background.js:1698-1704`：「⚠️ 性能红线：读 naturalWidth/Height 会触发布局重排…图片最多看前 80 张，段落最多看前 200 个」；同处注释说明大块提取代码已移到 `content-metadata.js`（`1704`）与 `content-translation.js`（`1706`）、`content-folder-picker.js`（`1266`）。
- `background.js:71`、`83-84`：`injectedCssTabs` 的设计理由（「保证下次提示时样式能重新注入，否则药丸会变成没有样式的裸文本」）。
- `README.md:26`：「LaterOn 目前通过开发者模式安装，支持 **Chrome / Edge 121 及以上版本**」→ 官方支持范围里**没有 Firefox**。
- `README.md:29`：`chrome://extensions/` / `edge://extensions/`；`README.md:44`/`67`：`chrome://extensions/shortcuts`；`README.md:79`：更新需回 `chrome://extensions/` 点「重新加载」。
- `README.md:81-83`：「侧栏出现在左边，能改到右边吗？…侧栏方向由浏览器控制，在 Chrome 的『设置 → 外观 → 侧栏』中修改」→ 侧栏方向是 Chrome 浏览器层设置，Firefox 的 sidebar 是不同机制（Firefox 的侧栏位置在 `about:config` / 视图菜单）。
- `CHANGELOG.md:204`：记录了 `chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` 的引入；`CHANGELOG.md:1602`：记录了 pending batch 存 `chrome.storage.session`（「关闭浏览器即消失，不占磁盘」）与 10 分钟失效。
- `scripts/build-release.py:2`、`15-17`：发布包用显式白名单构建（`RUNTIME_FILES` `18-52`，`RUNTIME_DIRS = ("_locales",)` `53`），并在 `111-123` 校验 zip 内容；`FORBIDDEN_NAMES` 含 `popup.css/popup.html/popup.js`（`62-65`）→ 印证 `SAVE_ITEM` 处理器是已删除 popup 的遗留。
- `scripts/build-release.py:88-108` 只校验 `background.service_worker`、`side_panel.default_path`、`options_page`、icons、WAR —— **没有**校验 `web_accessible_resources` 之外的内容脚本；改成 Firefox 的 `background.scripts` 会绕过该校验，构建脚本需同步改。
- `_locales/zh_CN/messages.json` 只有 6 条（extensionName/extensionDescription/actionTitle/commandSavePage/commandTranslatePage/commandSaveAllTabs），`_locales` 另有 en（`messages.json` 528 B vs zh 564 B）。

---

## 10. 对 Firefox 移植影响最大的 5 个点（我的判断）

1. **侧栏是产品的核心交互（图标点击 = 开侧栏），而 Firefox 没有 `sidePanel`**：`background.js:265-273` 的 `openPanelOnActionClick` 没有等价物；Firefox 要用 `sidebar_action` + `browser.sidebarAction.open()`，且必须发生在用户手势里；侧栏 ↔ 全屏收藏库的切换依赖 `sidepanel.js:622` 的 `sidePanel.close()`（Firefox 无对应 API）。这是**产品行为级**改造，不是改名。
2. **后台装载方式必须重写**：`background.js:1` 的 `importScripts` 在 Firefox 的事件页（window 上下文）不存在，`manifest.json:37-39` 的 `service_worker` 键 Firefox 不认。要么把三个共享文件改成 ESM/打包，要么切到 Firefox 的 `background.scripts` 数组——而后者会让 manifest 无法同时兼容 Chrome，需要考虑双 manifest 构建。
3. **全代码零浏览器分支 + 全量 `chrome.*` Promise 风格**：grep 证明没有任何 `isFirefox`/`typeof browser` 判断，所有 API 调用都假设 Chrome 的 Promise 行为。移植第一步必须建立 `browser`/`chrome` 兼容层并逐个 API 核对，而不是局部打补丁。
4. **标签页属性与 `tabs.update` 语义差异会造成静默功能降级**：`background.js:184` 的无 tabId `tabs.update`（omnibox 打开）、`tab.pendingUrl`（`1683`/`1690`、`tab-navigation.js:22` 的标签复用去重）、`tab.discarded`/`status === "unloaded"`（`1431`/`1582` 决定是否注入）。这三个点都不会报错，只会「行为变了」，需要专门回归测试。
5. **SW 回收假设与 `storage.session`/`alarms` 的组合**：`background.js:903`（session 暂存待收藏批次）、`352`（12 小时 alarm）、`355`（每次唤醒补扫）组成了一套「随时可能被回收」的容错设计。Firefox 事件页的回收时机、`storage.session` 的可用版本与配额、alarms 的最小周期都不同，需要重新标定 `background.js:1274` 的 10 分钟过期等阈值；另外 `injectedCssTabs`（`72`）与 `pickerRunByTab`（`1135`）这两个内存态在任何回收模型下都会失效。

---

## 11. 未证实 / 不确定

**（a）我没读完的文件**（结论可能不完整）：`library.js`（2523 行，只读 2230-2269）、`sidepanel.js`（1563 行，只读 610-634）、`settings.js`、`content-metadata.js`（31.6 KB）、`picker-ui.js`（30.5 KB）、`content-folder-picker.js`、`content-translation.js`、`content-reading-position.js`、`dialog.js`、`i18n.js`、`theme.js`、`onboarding.js`、`CHANGELOG.md`（132 KB）、`_locales` 全文、`tests/**`。任务指定的 6 个文件（`background.js`、`boot.js`、`reading-position-background.js`、`tab-navigation.js`、`url-utils.js`、`manifest.json`）已**逐行通读**，第 1–8 节中凡引用这些文件的结论都是一手证据；引用其它文件的结论来自 grep 或局部阅读。

**（b）我没有验证的事**：
- 没有运行任何测试（`repo/tests/**` 只 grep 过关键字，未执行；任务要求不运行）。
- 没有联网，没有在真实 Firefox（或 Chrome）里加载扩展。
- 关于 Firefox API 支持的所有陈述（`storage.session` ≥ FF115、`scripting` 的 `world:"MAIN"`、`contextMenus` 的 `"action"` context、`tabs` 的 `discarded`/`status` 取值、`chrome.*` 是否返回 Promise、`sidebarAction.open()` 的手势要求）**来自我已有的知识，未经本机验证**。
- `git log`/`git status` 只看了 HEAD 与工作区干净，没有追溯历史提交去确认某个 API 的引入动机。

**（c）明确标记为「推断」的结论**：
- §4.4 第 2 条：SW 回收后 `pickerRunByTab` 复位会导致 `background.js:1201-1203` 提前 return、浮层配置写不进页面——纯逻辑推断，未实测。
- §4.4 第 9 条：顶层 `chrome.alarms.create`（`352`）每次 SW 唤醒都会重置 12 小时周期——基于 Chrome alarms 持久化语义的推断。
- §4.4 第 1 条：SW 回收后重复 `insertCSS` 的具体视觉后果（重复样式表是否真的造成可见差异）——推断。
- §4.4 第 7 条：「批次中途被回收会静默停止」——从 `runBatchSave`（`962-1125`）无断点续作代码推断。
- §2.1 中「`SAVE_ITEM` 是死代码」——依据是「全仓库找不到发送方」+ popup 文件被列入构建黑名单，属强推断而非官方确认。

**（d）我没做的检查**：
- 没有对整仓 grep `allFrames`/`frameIds`/`frameId`。§6.3「所有注入只针对主框架」是**对已通读文件里每一处 `executeScript` 逐条核对**的结果；`content-*` 注入文件自身若再发起注入，我未检查。
- 没有穷举 `background.js:915` 存入 pending batch 的 `discarded`/`status`/`windowId` 三个字段在重放时（`1271-1293`）被谁消费（`runBatchSave` 只用 `tabs[i].url/title` 等），未读完的 `content-folder-picker.js`/`picker-ui.js` 可能也读它们。
- 没有检查 `_locales/en` 与 `i18n.js` 是否覆盖所有 `chrome.*` 权限文案，也与移植无关。
- 没有确认本主题目录是否已有 `README.md`：本次只写了本笔记文件（任务限定「只允许写自己的笔记文件」），**主题目录 `lateron-firefox-port/` 目前只有 `repo/`、`upstream/` 与本文件**，按工作区 `AGENTS.md` 的要求后续应由主理人补一个 README。
