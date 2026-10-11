# LaterOn 1.66.1 — 内容脚本层代码事实（Firefox 移植前置分析）

- 仓库：`F:\ALL_AI\小助理\open-source-collection\lateron-firefox-port\repo`
- 版本：`manifest.json:4` = `1.66.1`，`manifest.json:2` = `manifest_version: 3`，`manifest.json:6` = `minimum_chrome_version: "121"`
- 本文只读代码，未修改 repo 任何文件。所有引用形如 `文件:行号`。

---

## 0. 结论速览（先看这 5 条）

1. **只有一处使用主世界注入**：`background.js:565-569`（`world: "MAIN"` + `files: ["content-translation.js"]`），其余全部是默认隔离世界。
2. **没有任何 `content_scripts` 静态声明**，5 个内容脚本全部由 `chrome.scripting.executeScript` 在运行时按需注入（见 §1 总表）。
3. **受保护页面没有专门的过滤表**：唯一的门槛是 `isWebUrl()` = `/^https?:\/\//i`（`background.js:1665-1667`）。`chrome://` / `about:` 靠 scheme 天然被挡，但 `https://chromewebstore.google.com`、`https://addons.mozilla.org` 会通过 `isWebUrl`，靠注入失败 + `try/catch` 静默兜底。
4. **内容脚本完全不用 `window.postMessage`；不用 `MutationObserver`；不监听 `pushState`/`popstate`**。SPA 的适配全靠「后台重新注入 + 从 URL 推 id + 抖音轮询等待」。
5. **`web_accessible_resources` 只暴露 `icon128.png`**（`manifest.json:67-77`），而内容脚本实际只用到这一个资源（`content-reading-position.js:122`、`picker-ui.js:86`），**没有越界引用**。

---

## 1. 注入机制总表

| # | 内容脚本 | 注入点 | files/func | world | 其它参数 |
|---|---|---|---|---|---|
| 1 | `content-metadata.js` | `background.js:1619-1622` | `files` | 未指定 → ISOLATED | 无 `allFrames`/`frameIds`/`injectImmediately` |
| 2 | `content-reading-position.js` | `reading-position-background.js:23` | `files` | 未指定 → ISOLATED | 同上 |
| 3 | `content-translation.js` | `background.js:565-569` | `files` | **`"MAIN"`** | 同上 |
| 4 | `picker-ui.js` + `content-folder-picker.js` | `background.js:1219-1223` | `files`（两个文件一次调用） | 未指定 → ISOLATED | 同上 |
| 5 | 药丸通知（内联 func） | `background.js:632-664` | `func` + `args` | 未指定 → ISOLATED | `args: [shown, overflow, overflowText]`（`background.js:663`） |
| 6 | 抖音新鲜度探测（内联 func） | `background.js:1439` | `func: probeDouyinFreshness` | 未指定 → ISOLATED | 外层 `withTimeout(..., 900, null)`（`background.js:1438-1442`） |
| 7 | 浮层存活校验（内联 func） | `background.js:1236-1239` | `func` | 未指定 → ISOLATED | `withTimeout(..., PICKER_VERIFY_TIMEOUT_MS=700, null)`（`background.js:1235-1242`） |
| 8 | 浮层 payload 落 DOM（内联 func） | `background.js:1198-1214` | `func` + `args` | 未指定 → ISOLATED | `args: [pickerPayload, runId]`（`background.js:1213`） |
| 9 | `translation.css`（样式，非脚本） | `background.js:76` | `chrome.scripting.insertCSS` `files: ["translation.css"]` | — | 每标签页只注入一次，`injectedCssTabs` Set 去重（`background.js:72-77`） |

**全部注入的共性事实（重要）**

- 所有 `executeScript` 的 `target` 都只写 `{ tabId }`，**从未出现 `allFrames`、`frameIds`、`injectImmediately`**（对 `background.js` 全文 grep 无命中）。即：只注入顶层框架、默认隔离世界、默认时机。
- `chrome.scripting.executeScript` 被 `withTimeout` 包了 3 处（`background.js:1332-1350` 定义；用于 `1438`、`1618-1625`、`1196-1227`），超时分别 900ms、`EXTRACT_TIMEOUT_MS=3000`（`background.js:1355`）、`PICKER_INJECT_TIMEOUT_MS=1600`（`background.js:1133`）。
- 注释明确写了超时的动机：`background.js:1131-1132`「页面正在跳转、冻结或渲染进程短暂无响应时，executeScript 可能一直不返回」；`background.js:1333-1334`「executeScript 遇到卡死的页面（未加载完、被冻结、渲染进程无响应）可能长时间不返回」。
- **SPA 重注入**：抖音滑动切换视频时 `extractTabMetadata` 会在同一标签页**反复注入 `content-metadata.js`**（`background.js:1590-1612` 的 `for(;;)` 循环 + `1596-1599` 复核重试）。因此所有内容脚本都被要求「可重复注入」，见 §5.3。
- **标签页生命周期驱动的注入**：`reading-position-background.js:66-70` 监听 `chrome.tabs.onUpdated`（`status === "complete"` 或 `changeInfo.url` 是字符串）、`:71` 监听 `chrome.tabs.onActivated`、`:73-80` 监听 `chrome.storage.onChanged`（收藏列表或设置变化时对活动标签页重新 setup）。

### 1.1 受保护页面 / 注入前后 URL 过滤（逐行）

- **没有** `chrome://` / `edge://` / `about:` / `devtools://` / 扩展商店 / PDF viewer 的显式字符串判断（对 `background.js` grep 这些模式无命中）。
- 唯一门槛 `isWebUrl`：`background.js:1665-1667`
  ```js
  function isWebUrl(url) {
    return /^https?:\/\//i.test(url || "");
  }
  ```
- `isWebUrl` 被用作注入前的 gate 的位置（全部）：
  - `background.js:459`（`QUICK_SAVE_TAB`）
  - `background.js:498`（`handleCommand`，快捷键入口）
  - `background.js:608`（`reportFailure` 里决定是否弹药丸）
  - `background.js:1138`（`showPickerOverlay` 第一行 `if (!tab?.id || !isWebUrl(tab.url)) return false;`）
  - `background.js:1317`（`notifyTab`）
  - `background.js:1326`（`notifyOnActiveTab`）
  - `background.js:1369`（`extractTabMetadataById`，非 http(s) 时直接返回错误文案）
  - `background.js:829`（批量收藏过滤 `tabs.filter((tab) => isWebUrl(tab.url))`）
  - `background.js:131`、`:191`、`:194`（收藏条目层面的 URL 过滤）
  - `reading-position-background.js:15`（`setupTab` 里 `if (!tab?.id || !isWebUrl(tab.url)) return false;`）
- 另有**标签状态**级过滤（不是 URL 过滤）：
  - `background.js:1582` `if (tab.discarded || tab.status === "unloaded") return applyServerMetaRescue(fallback);`（休眠/未加载标签直接放弃注入）
  - `background.js:1431` `if (!tab?.id || tab.discarded || tab.status === "unloaded") return;`（抖音探测同样跳过）
- 失败路径的兜底注释：
  - `reading-position-background.js:32`「标签可能已关闭、正在跳转，或属于浏览器保护页面；都不影响正常浏览。」
  - `background.js:1245`「页面受保护 / 权限不足 / 标签已关闭：返回失败，不创建其它形态的选择窗口。」
  - `background.js:1328`「内部页面不允许注入，忽略即可。」
  - `background.js:501`「Chrome 设置页等其它受保护页面收不到扩展页消息，仍保留角标兜底。」
  - `background.js:79`「页面受保护或已关闭，忽略即可。」（insertCSS 失败）

**移植提示**：Firefox 里受保护页面的判定逻辑不同（`about:addons`、`about:preferences`、AMO 域名 `addons.mozilla.org` 被 Firefox 硬性禁止注入，且报错文案不同）。当前代码对「注入失败」一律静默吞掉，行为在 Firefox 上不会崩，但**用户不会得到任何解释**（只留角标）。

---

## 2. 每个内容脚本的逐项事实

### 2.1 `content-metadata.js`（695 行，只读 DOM，无注入副作用）

- 顶层是一个函数声明 + 结尾自调用：`content-metadata.js:8` `function extractPageMetadataForShortcut()`，`:695` `extractPageMetadataForShortcut();`
- **返回值就是 executeScript 的 `result`**：`content-metadata.js:677-692` 返回 `{ title, titleFrom, description, image, imageFrom, favicon, source, url, videoId }`；调用方读 `injection?.[0]?.result`（`background.js:1626`）。**这是 Chrome 的「文件最后一个表达式的完成值」机制**，Firefox 需要单独核实（见 §11）。
- **无 `world` 依赖、无 `chrome.*` 调用、无网络请求**：纯 DOM 读取。这一点对 Firefox 最友好。
- 站点特化逻辑（都在隔离世界靠 DOM/URL 完成）：
  - YouTube：`content-metadata.js:20-21` 域名判断；`:24-35` 只从 URL 推 video id（`/watch?v=`、`/shorts/`、`/embed/`、`/live/`、`/v/`、`youtu.be`）；`:63-91` 从页面 `<script>` 里「括号配平」挖 `ytInitialPlayerResponse.videoDetails`；`:96-122` 优先实时 DOM（`ytd-watch-metadata h1`、`ytd-reel-video-renderer[is-active] h2`、`#description-inline-expander`）；`:657-675` 用 `/vi/<id>/` 校验 og 图是否属于当前视频，否则自己拼 `https://i.ytimg.com/vi/${youtubeId}/maxresdefault.jpg`（`:665`）。
  - 抖音：`content-metadata.js:131` 域名判断（`douyin.com` / `iesdouyin.com`）；`:132` `lark:` 元数据族（`video_title` / `video_brand_name` / `video_cover_image_url` / `video_icon_url`）；`:139` 标题取自 `[data-e2e="detail-video-info"] h1`；`:142` `readId` 取自同容器的 `data-e2e-aweme-id`；`:308-326` 从 `[data-e2e="player-container"]` 取封面，只认 `/PackSourceEnum_AWEME_DETAIL/` 或 `sc=origin_cover`（`:322`）。
  - 小红书类：`content-metadata.js:434-441` 简介容器兜底（`#detail-desc`、`.note-desc`、`.desc`、`[class*='excerpt']`…）。
  - 通用封面降级链（`content-metadata.js:333-406`）：`og:image`/`twitter:image` → `link[rel~=image_src]` → `meta[itemprop=image]` → 抖音播放器 → JSON-LD（`:176-204`）→ `video[poster]`（`:207-215`）→ 行内 CSS 背景图（`:219-241`）→ 懒加载属性（`:244-275`）→ 最大图（`:278-303`）。
  - 平台 logo 过滤 `looksGenericImage`：`content-metadata.js:154-164`（`fe-platform`、`logo/sprite/placeholder/avatar`、`.svg` 一律跳过）。
  - 标题后处理：`content-metadata.js:461-477` 通用标题黑名单（含 `"youtube"`、`"抖音"`）；`:483-487` `inJunkArea` 排除导航/页脚，但允许 `<article><header>`；`:577-610` 剥「- 站点名」后缀（含品牌区文本兜底 `:556-569`、`:603-608`）。

### 2.2 `content-reading-position.js`（181 行，隔离世界，唯一「长期驻留」型内容脚本）

- 头部注释即设计意图：`content-reading-position.js:1-2`「注入到"已收藏网页"的轻量脚本：记住 scrollY…重复注入是安全的；SPA 切换到另一篇收藏时由 INIT 消息更新目标。」
- **反重复注入机制**：`:6` `try { globalThis.__laterOnReadingPosition?.dispose?.(); } catch {}`，`:19` 把状态挂到 `globalThis.__laterOnReadingPosition`，`:31-46` `dispose()` 撤掉全部监听（`:38-43` window 监听 + `pagehide`，`:44` `chrome.runtime.onMessage.removeListener`）。`:4-5` 注释解释了原因：扩展更新后旧实例的 `chrome.runtime` 已失效，不能只凭全局标记 return。
- **同步 throw 与异步 reject 都要吃**：`:48-49` 注释「`chrome.runtime.sendMessage(...).catch(...)` 只处理 Promise 拒绝；扩展上下文失效时 sendMessage 本身会在返回 Promise 之前同步 throw。必须把调用也放进 try/catch。」实现在 `:50-64` `safeSendMessage`（`:53` 取 Promise、`:54` `.catch`、`:58-63` 同步 `catch` → `dispose()`）。
- 上报消息：`:75` `safeSendMessage({ type: "SAVE_READING_POSITION", itemId: state.itemId, y })`（`:74` y = `Math.round(window.scrollY || window.pageYOffset)`）。
- 接收消息：`:151-168` `handleInit`，`:153` 只认 `message?.type !== "LATERON_READING_POSITION_INIT"`；`:157-158` 取 `itemId` / `y`；`:163` 仅当 `savedY >= 160 && |currentY - savedY| >= 120` 才弹提示，否则直接 `armed = true`。
- UI：`:115-149` `showPrompt`，宿主 div id `lateron-reading-position`（`:119`），**Shadow DOM open**（`:120`），图标走 `chrome.runtime.getURL("icon128.png")`（`:122`），`:126` `:host{all:initial;position:fixed;right:28px;top:50%;transform:translateY(-50%);z-index:2147483647;...}`，`:146` 挂到 `document.documentElement || document.body`，12 秒自动消失（`:148`）。
- 滚动恢复：`:96-113`，`:102` `scrollTo({behavior:"smooth"})`，`:104-106` 450ms 后补一次 `auto`，`:107-112` 1100ms 后再补一次并 `sendPosition()`。`:103` 注释「图片和异步正文可能继续撑高页面；短暂复查两次」。
- 事件：`:172-177` `scroll` / `wheel` / `touchstart` / `pointerdown` / `keydown` / `pagehide`，全部 `{ passive: true }`；`:88-94` `userStartedReading` 用 `event?.composedPath?.().includes(state.prompt)` 过滤掉点自己浮层的交互（`:90`）。
- 写入节流：`:78-86` `setTimeout(..., 500)` + `generation`/`itemId` 双校验。
- 后台侧：`reading-position-background.js:42-54` `savePosition` 串行写队列，`:48` 位移小于 8px 不写。

### 2.3 `content-translation.js`（162 行，**唯一 MAIN 世界脚本**）

- 整体只有一个 async 顶层函数 + 结尾调用：`content-translation.js:1` `async function togglePageTranslation()`，`:162` `togglePageTranslation();` → 完成值是被 `background.js:570` 读取的 `injection[0]?.result?.ok`。
- **依赖 Chrome 内建 AI API**（Firefox 完全没有）：
  - `content-translation.js:39` `if (!("Translator" in self)) throw new Error("当前 Chrome 不支持本机网页翻译，请升级浏览器");`
  - `:65-77` `LanguageDetector.availability()` / `LanguageDetector.create({monitor})` / `detector.detect(sample)` / `detector.destroy?.()`
  - `:82` `Translator.availability({sourceLanguage, targetLanguage:"zh"})`；`:86-93` `Translator.create({...options, monitor})`；`:148` `translator.destroy?.()`
  - 这就是 `world: "MAIN"` 的存在理由（这些 API 挂在页面全局 `self` 上，隔离世界拿不到）。
- 状态挂在 `window` 上：`:4` `const stateKey = "__laterOnTranslationRun"`，`:5` `window[stateKey]`，`:35-36` 写入 `{active:true,cancelled:false}`，`:27` 再次调用时置 `cancelled = true` 并移除已有译文（`:26-33`）。
- 正文识别：`:41-42` roots = `article` / `main` / `body` 中第一个含 ≥3 个 `<p>` 的；`:45` 选择器 `p, h1..h4, blockquote, figcaption`；`:46` 排除 `nav, header, footer, aside, form, pre, code, script, style, noscript, [contenteditable='true']`；`:51` 文本长度 8~1800；`:55` 最多 160 段。
- 语言判定：`:58-61` 抽样 24 段、6000 字，汉字占比 > 0.35 直接判定「已经是中文」并报错。
- 译文插入：`:114-126` `buildTranslationElement`，**:`:120-123` 把原文 16 个排版属性逐个用 `element.style.setProperty(property, value, "important")` 抄过去**；`:139` `block.insertAdjacentElement("afterend", el)`。
- 并发：`:130-131` `CONCURRENCY = 6`，`:146` `Promise.all([...Array(min(6, n))].map(worker))`；`:141-143` 单段失败不中断整页。
- Status toast 是**裸 DOM 直插**（不走 Shadow DOM）：`:8-24` 创建 `div#lateron-translation-status`（`:13` 挂到 `document.documentElement`），样式来自 `translation.css:13-38`（`z-index: 2147483647 !important`，`:15`）。

### 2.4 `content-folder-picker.js`（79 行，隔离世界，薄适配层）

- 文件头 3 条硬约束值得原文记录：
  - `content-folder-picker.js:5-6`「⚠️ 必须自包含地被注入：不依赖任何外部变量，只靠 `window.openFolderPicker`（由先于本文件注入的 `picker-ui.js` 提供）。」
  - `content-folder-picker.js:7-8`「整个入口包在函数作用域里：`chrome.scripting.executeScript` 可能在同一网页反复注入本文件，**顶层 `const` / `let` 会留在同一个脚本世界里，第二次声明就会直接抛 `SyntaxError`**。」→ 实现在 `:9` `(() => {`。
  - `:10-12`「同一网页再次注入前，撤掉上一个实例还在等 payload 的一次性监听」→ `window.__laterOnPickerPayloadCleanup?.()`。
- 消息方向（内容脚本 → 后台，全部 fire-and-forget）：
  - `:47` `{ type: "CREATE_PROJECT", name }`，返回体取 `response?.project`（`:48`）
  - `:50` `{ type: "CONFIRM_BATCH_SAVE", projectId }`
  - `:51` `{ type: "CANCEL_BATCH_SAVE" }`
  - 包装器 `:17-20` `safeRuntimeMessage`：`try { return Promise.resolve(chrome.runtime.sendMessage(m)).catch(() => null); } catch { return Promise.resolve(null); }`（注释 `:15-16` 说明扩展更新后旧浮层的失效场景）。
- **payload 通过 DOM 节点传递**：`:57-66` `consumePickerPayload()` 读 `document.getElementById("lateron-picker-payload-data")`（`:58`）→ `JSON.parse(node?.textContent || "null")`（`:60`）→ `node?.remove()`（`:61`）→ `showFolderPickerOverlay(payload)`（`:64`）。同时 `:77` 监听自定义事件 `document.addEventListener("lateron-picker-payload-ready", onPayloadReady, { once: true })`，`:78` 再立刻主动试一次（覆盖「配置先到 / UI 后到」两种顺序，见 `background.js:1192-1195` 注释）。
- `:31-34` 若 `window.openFolderPicker` 不是函数则**安静退出**（注释：picker-ui.js 没先注入完，后台会重试网页内浮层）。
- `:75` `window.showFolderPickerOverlay = showFolderPickerOverlay`（供预览页直接调用，见 `tests/picker-preview.template.html`）。

### 2.5 `picker-ui.js`（605 行，既作内容脚本又作扩展页脚本）

- `picker-ui.js:11-12`「本文件不依赖任何外部变量/函数（包括 `chrome.*` 也不在顶层调用），这样它既能作为 content script 注入网页，也能被扩展页用 `<script>` 直接加载。」
- `:20` 顶层 `defaultCreateProject` 里调用 `chrome.runtime.sendMessage({type:"CREATE_PROJECT", name})`，但**只在函数体内**，符合上面的约束。
- `:25-28` `safeRuntimeUrl(path)` = `try { chrome.runtime.getURL(path) } catch { "" }`；`:86` `const brandIcon = safeRuntimeUrl("icon128.png")`；`:89` 用于品牌行 `<img class="lon-logo" src="${brandIcon}">`（**:仅整屏弹窗模式显示**，`:87-89`）。
- DOM：`:56` `HOST_ID = "lateron-folder-picker"`；`:72-75` 宿主 div + `host.style.setProperty("all", "initial", "important")`（注释 `:74`「双保险：内联 `!important` 能压过页面自己的样式表」）；`:77` `attachShadow({mode:"open"})`；`:119` `document.documentElement.appendChild(host)`。
- 样式：`:448-601` `buildStyle()`；`:450` `:host { all: initial; }`；`:453` `position: fixed; inset: 0; z-index: 2147483600;`；`:580-591` 贴按钮浮层模式（`.lon-popover`，`position:absolute`、`pointer-events` 分层）；`:507-513` 品牌 logo 尺寸。
- `:62-63` 明暗：`matchMedia("(prefers-color-scheme: dark)")`，`:61` 主题来自 `data.theme`。
- `:604` `window.openFolderPicker = openFolderPicker;` ← 这就是 `content-folder-picker.js:31/36` 依赖的全局入口。
- `:443` `requestAnimationFrame(() => root.classList.add("is-in"))` 入场动画。

### 2.6 `reading-position-background.js`（89 行，后台模块，经 `importScripts` 加载）

- `background.js:1` `importScripts("url-utils.js", "reading-position-background.js");`
- 注入 + 初始化的顺序（`:12-30`）：
  1. `:14` 取 tab；
  2. `:15` `isWebUrl` 过滤；
  3. `:17` 从存储里按 `normalizeUrl(entry.url) === normalizeUrl(tab.url)` 找收藏条目；
  4. `:18-21` 找不到 → `chrome.tabs.sendMessage(tab.id, {type:"LATERON_READING_POSITION_INIT", itemId:null})`（此时脚本可能还没注入，`.catch(() => {})` 吞掉）并 return false；
  5. `:23` `executeScript({target:{tabId}, files:["content-reading-position.js"]})`；
  6. `:24-29` `chrome.tabs.sendMessage(tab.id, {type:"LATERON_READING_POSITION_INIT", itemId, y, language: "en"|"zh-CN"})`。
- `:82-88` 后台 onMessage 收 `SAVE_READING_POSITION`（`:83` 校验 `!message.itemId` 则 return），`:87` **`return true;`** 走异步 `sendResponse`。

---

## 3. 内容脚本 ↔ background 通信汇总

### 3.1 消息 type 全表

| type | 方向 | payload 形状 | 定义处 |
|---|---|---|---|
| `MUTATE_ITEMS` | 扩展页 → 后台 | `{operation, ids, patch}` | `background.js:383`（`return true` `:387`） |
| `SAVE_ITEM` | 扩展页 → 后台 | `{item}` | `background.js:389`（`:393`） |
| `OPEN_LIBRARY` | 扩展页 → 后台 | `{context}` | `background.js:395`（`:399`） |
| `CONFIRM_BATCH_SAVE` | **内容脚本**/扩展页 → 后台 | `{projectId}` | `background.js:402`（`:416`，带 `replied` 防重复 `:403-412`） |
| `CANCEL_BATCH_SAVE` | **内容脚本** → 后台 | `{}` | `background.js:418`（`:422`） |
| `CREATE_PROJECT` | **内容脚本**/扩展页 → 后台 | `{name}` | `background.js:425`（`:429`） |
| `EXTRACT_METADATA` | 扩展页 → 后台 | `{tabId}` | `background.js:433`（`:448`） |
| `QUICK_SAVE_TAB` | 扩展页 → 后台 | `{tabId, source}` | `background.js:453`（`:470`） |
| `SAVE_READING_POSITION` | **内容脚本** → 后台 | `{itemId, y}`（**只有这两个字段 + type**，`tests/reading-position-content.test.js:68` 断言 `Object.keys(...).sort() === "itemId,type,y"`） | `reading-position-background.js:83`（`:87`） |
| `LATERON_READING_POSITION_INIT` | 后台 → **内容脚本** | `{itemId, y, language}` 或 `{itemId:null}` | 发送：`reading-position-background.js:19`、`:24-29`；接收：`content-reading-position.js:153` |
| `SHOW_LIBRARY_NOTICE` | 后台 → 扩展页（library.html） | `{tabId, message}` | 发送 `background.js:588-592`；接收 `library.js:129` |

### 3.2 桥接机制

- **`window.postMessage` 全文 0 处使用。**
- **CustomEvent / dispatchEvent 只用于扩展自身两个世界之间的握手，且都是隔离世界内部**：
  - `background.js:1211` `document.dispatchEvent(new CustomEvent("lateron-picker-payload-ready"))` ↔ `content-folder-picker.js:77` `document.addEventListener("lateron-picker-payload-ready", onPayloadReady, { once: true })`。两者都在**同一次 `executeScript` 的隔离世界**里，事件不需要跨越世界边界。事件名无口令，页面脚本也能伪造（可忽略的健壮性小瑕疵，非安全边界）。
  - `window.dispatchEvent(new CustomEvent("lateron-language-change"))` 在 `i18n.js:275`，属扩展页，与内容脚本无关。
- **同步返回依赖（`return true`）**：`background.js:387, 393, 399, 416, 422, 429, 448, 470` 与 `reading-position-background.js:87`，共 9 处。全部是「异步 `sendResponse`」模式。
- 内容脚本侧的**发送**几乎都是「不等回执」的 fire-and-forget（`content-reading-position.js:53`、`content-folder-picker.js:18/47/50/51`），唯一被读取返回值的是 `CREATE_PROJECT`（`content-folder-picker.js:48`）与 `content-translation.js` 的注入返回值（`background.js:570`）。

---

## 4. 隔离世界（ISOLATED）vs 主世界（MAIN）

### 4.1 必须走主世界的逻辑：只有翻译

- `background.js:563-571`：
  ```js
  async function toggleTranslation(tab) {
    await ensureTranslationCss(tab.id);
    const injection = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      files: ["content-translation.js"]
    });
    if (injection[0]?.result?.ok === false) await showActionError();
  }
  ```
- 原因：`Translator` / `LanguageDetector` 是页面全局对象（`content-translation.js:39/65/82/86` 用 `self` 与裸标识符访问）。**注意代码里没有任何 `<script>` 标签注入、没有 `world:"MAIN"` 之外的隔离突破手段**（全文 grep 无 `<script src=` 形式的扩展资源注入；`background.js:1206` 那次 `createElement("script")` 是 `type="application/json"` 的**惰性数据节点**，不执行 JS）。

### 4.2 必须在隔离世界 / 未声明世界的逻辑

- `content-metadata.js`：读 DOM + 读 `<script>` 的 `textContent`（`:64-88`）——**只读文本、不读页面 JS 变量**，所以隔离世界足够。抖音 `data-e2e-aweme-id`（`:142`）、YouTube DOM `ytd-*` 元素（`:99-102`）都是普通 DOM 属性/元素，跨世界可见。
- SPA 路由：**没有任何内容脚本监听 `pushState`/`popstate`/`hashchange`**（全文 grep 的 `pushState` 命中只在注释 `background.js:1472`、`tests/topbook-modal.test.js:4` 和 `tests/settings-navigation.test.js:143`）。SPA 适配全部靠：
  - URL 派生（`content-metadata.js:24-35` YouTube id、`background.js:1398-1407` 抖音 id）；
  - 后台 `tabs.onUpdated` 重注入（`reading-position-background.js:66-70`）；
  - 抖音轮询等待（`background.js:1429-1456`）。
- 隔离世界的全局污染是**可接受的**：`content-reading-position.js:19` 的 `globalThis.__laterOnReadingPosition`、`content-folder-picker.js:75-76` 的 `window.showFolderPickerOverlay` / `window.__laterOnPickerPayloadCleanup`、`background.js:1201-1203` 的 `globalThis.__laterOnPickerRunId` 都在隔离世界，页面看不到。**唯一例外是 `content-translation.js:5/36` 的 `window[stateKey]`（`__laterOnTranslationRun`）——它在 MAIN 世界，页面可见且可篡改。**

---

## 5. CSP / 资源加载假设

### 5.1 扩展资源引用（全部命中 `web_accessible_resources`）

- `content-reading-position.js:122` `safeRuntimeUrl("icon128.png")` → `:140` `<img class="mark" src="${iconUrl}">`。
- `picker-ui.js:86` `safeRuntimeUrl("icon128.png")` → `:89` `<img class="lon-logo" src="${brandIcon}" width="34" height="34">`。
- `manifest.json:67-77` 的 WAR 只含 `"icon128.png"`，`matches` 为 `http://*/*` + `https://*/*`。**两者一致，未发现引用未暴露资源。**
- 其它 `chrome.runtime.getURL(...)` 调用（`background.js:200/581/1670`、`library.js:353`、`settings.js:94/109/126`）指向扩展页 `library.html` / `settings.html`，都在扩展自身上下文，不受内容脚本 WAR 约束。

### 5.2 不依赖网络的资源加载

- **无 `<link rel=stylesheet>` 注入、无 `fetch` 到扩展资源、无外部域名请求**（内容脚本层）。`translation.css` 走 `chrome.scripting.insertCSS`（`background.js:76`），由浏览器直接注入，不需要 WAR。
- 唯一的网络请求在后台（不在内容脚本）：`background.js:1482` `fetch(url, { credentials: "omit" })`（服务端 og 兜底 `refetchMetaFromServer`，超时 `SERVER_META_TIMEOUT_MS = 8000`，`background.js:1477`）。

### 5.3 潜在的 CSP 交互点

1. **`background.js:1206-1210` 往页面 `document.documentElement` 插入 `<script type="application/json" id="lateron-picker-payload-data">`**。它是惰性的（`type="application/json"` 不执行），通常不触发 `script-src`；但严格 CSP 站点上的行为**未在本仓验证**（见 §11）。这同时意味着**页面 JS 能读到、也能改掉这份 payload**（含项目名与待收藏页面列表），属于信息暴露面而非 XSS。
2. `background.js:1211` 的 `new CustomEvent(...)` + `content-folder-picker.js:77` 的监听都发生在隔离世界，**不受页面 CSP 影响**，也不需要 `unsafe-eval`。
3. `content-translation.js` 在 MAIN 世界执行，**直接受页面 CSP 约束**（MAIN 世界注入本身在 Chrome 里可以绕过部分限制，但 `Translator` API 的可用性、`monitor` 回调等都可能被站点策略影响——未验证）。
4. **Trusted Types**：仓库内**没有任何 `Trusted Types` 相关处理**；所有 DOM 插入都用 `innerHTML`（`content-reading-position.js:124`、`picker-ui.js:94`、`:120/`）。若站点开启了 `require-trusted-types-for 'script'`，这些 `innerHTML` 写入会在该站点的 DOM 上抛 `TypeError`。注意：**内容脚本操作的是页面的 DOM 对象，因此 Trusted Types 策略会生效**——这是移植/兼容的潜在故障点（未在仓内验证是否已在真实站点上出现）。
5. `chrome.scripting.insertCSS` 注入的样式**不受页面 `style-src` CSP 限制**（浏览器直接注入），所以药丸/翻译提示的样式在严格 CSP 站点上应当仍然生效。

---

## 6. 页面侵入性与兼容性

### 6.1 注入的 DOM 与样式

| 宿主 | 位置 | 隔离方式 | z-index | `!important` |
|---|---|---|---|---|
| `#lateron-reading-position` | `content-reading-position.js:119`，挂 `document.documentElement \|\| document.body`（`:146`） | **Shadow DOM open**（`:120`） | `2147483647`（`:126`，`:host` 内） | 通过 `all:initial`（`:126`）隔离，非 `!important` |
| `#lateron-folder-picker` | `picker-ui.js:73`，挂 `document.documentElement`（`:119`） | **Shadow DOM open**（`:77`） | `2147483600`（`:453`） | 宿主 `all:initial !important`（`:75`）+ `:host{all:initial}`（`:450`） |
| `#lateron-pill-stack` + `.lateron-pill` | `background.js:635/639-640`，挂 `document.documentElement` | **无 Shadow DOM**（裸 DOM） | `2147483647`（`translation.css:43`） | 几乎每条属性都 `!important`（`translation.css:42-52`、`:55-73`） |
| `#lateron-translation-status` | `content-translation.js:11-13`，挂 `document.documentElement` | **无 Shadow DOM** | `2147483647`（`translation.css:15`） | 全属性 `!important`（`translation.css:14-32`） |
| `.lateron-inline-translation`（译文块） | `content-translation.js:115/139`，插在原文块之后 | 无隔离 | 继承文档流 | `translation.css:2-10` 全 `!important`；另有 JS 内联 `setProperty(..., "important")`（`content-translation.js:122`，16 个排版属性，列表在 `:95-112`） |

- 药丸的通知管理逻辑：`background.js:626` `MAX_PILLS = 10`（后台侧截断）、`:642` `MAX_STACK = 6`（页面同屏最多 6 条，超出移除最早的 `:650`）；每条 2800ms 后隐藏（`:660`），`:643` 溢出文案。
- 翻译状态提示的语义：同一时刻只有一个 `#lateron-translation-status`（`content-translation.js:9` 复用已有节点）。
- `picker-ui.js` 还 **移除** 同 id 的旧宿主：`:57-58` `const stale = document.getElementById(HOST_ID); if (stale) stale.remove();` —— 与重复注入配合，避免浮层叠两层。

### 6.2 SPA / 动态页面处理方式（无 MutationObserver）

- **全仓 0 个 `MutationObserver`**（grep 无命中）。适配策略是「注入时机 + id 校验 + 轮询」，不是「观察 DOM 变化」：
  - YouTube 站内跳转：`content-metadata.js:1-7` 文件头注释解释了 og 不更新的问题，方案是「网址推 id → 优先实时 DOM → og/内嵌数据必须用 id 校验」。`:657-675` 收尾时再用 `/vi/<id>/` 复核封面。
  - 抖音滑动切换：`background.js:1374-1382` 记了实测时间线（+102ms 网址已换、面板还是旧的；+318ms 全部对齐），`:1429-1456` 的 `settleDouyinDom` 每 `DOUYIN_POLL_MS=100`ms 探测一次，最多 `DOUYIN_SETTLE_MS=1500`ms；`:1596-1599` 抓完还用 `data.videoId !== expectedId` 复核一次并重试。
  - 阅读位置跨 SPA：靠后台重发 `LATERON_READING_POSITION_INIT` 切换目标（`content-reading-position.js:2` 注释明说），`:156` `state.generation += 1` 作废旧任务的回调。
  - 选择项目浮层：`:1235-1242` 注入后**主动校验宿主是否还活着**（`document.getElementById("lateron-folder-picker")?.shadowRoot`），页面恰好导航、DOM 被重建时返回 false 让调用方重试（`background.js:1232-1234` 注释）。

### 6.3 重复注入的健壮性要求（移植时必须保留）

- `content-folder-picker.js:7-8`：顶层 `const`/`let` 在同一隔离世界重复声明会 `SyntaxError` → 全文件包 IIFE（`:9`）。
- `content-reading-position.js:4-6`：靠 `globalThis.__laterOnReadingPosition.dispose()` 撤旧实例，而不是靠标记 return。
- `tests/picker-reinjection.test.js:39-47` 就是这个行为的回归测试（连续 `vm.runInContext` 两次，断言不抛错且浮层被打开两次）。
- `tests/reading-position-content.test.js:83-92` 是另一半（重新注入建立新实例，旧 listener 被 `removeListener` 清掉）。

---

## 7. 测试暗示的站点特殊处理与预期行为

### 7.1 `tests/douyin-spa.test.js`（430 行）

- 文件头 `:1-12` 复述了抖音实测时间线，`check("等到了面板对齐才抓（探测 ≥4 次）")` 在 `:288`。
- 站点特化断言：
  - URL 形态（`:240-243`）：`/video/<id>`、`/note/<id>`、`?modal_id=`、用户页 + `modal_id`。
  - 仿冒域名防护（`:253-258`）：`notdouyin.com`、`douyin.com.evil.com`、其它站 `/video/<数字>` 都必须是 false/空串 —— **移植时任何 URL 正则改动都不能破坏这条**。
  - 封面来源标记（`:79`、`:282`）：必须同时带 `sc=origin_cover` 与 `PackSourceEnum_AWEME_DETAIL`；`:766` 断言不会误选「相关推荐」（`RELATED_AWEME`）。
  - 首页推荐流无 id 时用 `lark:url:video_iframe_url` 里的 id 兜底（`:335-351`，实现在 `background.js:1415/1423/1451`）。
  - 静态接线检查（`:392-423`）：`await settleDouyinDom(tab, deadline);`、`const expectedId = isDouyinUrl(tab.url)`、`data.videoId !== expectedId`、`videoId: douyin?.readId`、`readId: document.querySelector` 必须都在；并断言 `probeDouyinFreshness` 自包含（不引用后台标识符，`:414-418`）。

### 7.2 `tests/metadata-extract.test.js`（805 行，23 个章节）

章节标题即站点清单（行号为 `console.log("=== …")` 所在行）：

- `:134` YouTube 站内跳转（og 停在首页）→ 断言 `i.ytimg.com/vi/CURRENT123/maxresdefault.jpg`（`:140`）与 `source === "YouTube"`（`:146`）。
- `:149` 整页直开；`:157` `/shorts/`；`:164` `youtu.be` 短链；`:170` YouTube 首页（标题须留空 `:175`，封面保留 `yt_1200.png` `:176`）。
- `:179` 普通网站回归（og:title/og:image/og:description/og:site_name）。
- `:188` 封面降级链 `maxresdefault → hq720 → hqdefault → mqdefault`（`:196-204`，这个链在展示端，`library.js`/`sidepanel.js` 里的 `COVER_CHAIN`，`:211` 静态断言）。
- `:215` 「只保留一份提取逻辑」：`library.js`/`sidepanel.js` 不得自带旧 `extractPageMetadata`，必须走 `EXTRACT_METADATA`（`:219-220`），后台只注册一处（`:222-223`）。
- `:227` 重复收藏时修补旧记录（`:251-254` 修好标题/封面/摘要，`:270` 正常的不要乱改）。
- `:319` **小红书型页面**（`:319-348`）：封面是 CSS 背景图，正文不在 `<p>` 里 → 断言 `imageFrom === "background"`（`:348`），且不能把 `avatar` 小图当封面（`:344`）。
- `:351` 视频笔记（封面在 `video[poster]`）。
- `:369` 懒加载站（真图在 `data-src`，`src` 是 `data:` 占位）。
- `:381` JSON-LD；`:393` 老式 `image_src` / `itemprop`。
- `:404` 不把平台 logo/占位图/雪碧图当封面 → 宁可不显示（`:415`），自检 `imageFrom === "generic-skipped"`（`:416`）。
- `:429` **跨站图片防盗链**：`library.html` / `sidepanel.html` 必须有 `<meta name="referrer" content="no-referrer">`（`:435`），且封面 `<img>` 设 `referrerPolicy = "no-referrer"`（`:439-440`）。**这是与内容脚本无关但会影响显示层的事实。**
- `:447` 标题抓取（og 缺失 / 陈旧 / 写成平台名）：`:458` 用实时 DOM 标题、`:469` 优先实时标题、`:477` 剥「- 站点名」、`:486` 叠两层后缀、`:493` 分隔符后不是站点名时保持原样（`React 18 发布 - 前端周刊`）。
- `:497` `<article><header><h1>` 合法、页面级 header 的 h1 跳过（`:503`/`:511`）、类名兜底（`:519`）、纯符号 h1 跳过（`:526`）、**实在没有标题时留空**（`:533`，不拿域名硬凑）。
- `:545` Wikipedia 无 `og:site_name` 时靠域名剥后缀；`:559`/`:570`/`:585` 小红书文案（`富贵少爷…`）、B 站（`哔哩哔哩_bilibili` 二层后缀）。
- `:609` 占位标题规则 `isPlaceholderText`；`:631-654` `titleHasSiteNoise`。
- `:752` **抖音：不给分享标签时也要抓到标题与封面**（`:757-772`）；`:775` 无简介时宁可留空（`:784`）；`:787` 抖音首页/feed 不乱抓（`:792`）；`:795` 普通网站不受抖音逻辑影响。

### 7.3 其它相关测试

- `tests/reading-position-content.test.js`（99 行）：`:43` 断言浮层样式里有 `right:28px;top:50%;transform:translateY(-50%)`；`:45` 断言 logo 是 `chrome-extension://lateron/icon128.png`；`:68` 断言消息字段恰好 `itemId,type,y`；`:80-81` 断言 context invalidated 后 `disposed === true` 且 `removeListener` 被调用；`:85-86` 断言重新注入建立新实例。
- `tests/topbook-modal.test.js`：`topbook.cc` 类站点「弹窗式」文章，网址靠 `pushState` 变、head 里 og 不更新 → 触发后台服务端兜底（对应 `background.js:1471-1476` 注释与 `:1479-1533` 实现）。
- `tests/picker-reinjection.test.js`：连续注入两次 `content-folder-picker.js` 不抛错、且两次都打开浮层。
- `tests/reading-position-background.test.js`、`tests/background-modules.test.js`：后台模块与 `importScripts` 的静态/接线检查。

---

## 8. 中文注释里的线索（浏览器差异 / CSP / 注入失败 / 已知限制）

**明确提到 Chrome 或 Chrome-only 能力**

- `content-translation.js:39`「当前 Chrome 不支持本机网页翻译，请升级浏览器」—— 整个功能是 Chrome 内建 AI（`Translator`/`LanguageDetector`）的封装，**Firefox 无对应 API**。
- `background.js:1322-1323`「在当前窗口的「活动标签页」上弹一条药丸通知。若当前停在 Chrome 内部页面（新标签页 / 设置页等）无法注入，则只保留角标提示。」
- `background.js:501`「Chrome 设置页等其它受保护页面收不到扩展页消息，仍保留角标兜底。」
- `background.js:1375`「抖音是单页应用。实测站内切换视频时各信号的更新时间线（**无头 Chrome**，逐 100ms 采样）」；`tests/douyin-spa.test.js:4` 同。
- `background.js:1472`「场景（topbook.cc 实测）」服务端兜底针对「pushState 弹窗 + og 不更新」。
- `manifest.json:6` `minimum_chrome_version: "121"`。

**注入失败 / 受保护页面 / 超时**

- `background.js:79`「页面受保护或已关闭，忽略即可。」
- `background.js:1131-1132`「页面正在跳转、冻结或渲染进程短暂无响应时，executeScript 可能一直不返回。选项目浮层不能跟着无限等待：到点就交回 false，让调用方重试网页内浮层。」
- `background.js:1232-1234`「executeScript 成功只代表文件执行完，不代表浮层一定留在页面上。页面恰好导航、DOM 被站点重建、共享 UI 初始化失败时，主动确认宿主确实存在；看不到就返回 false。」
- `background.js:1245`「页面受保护 / 权限不足 / 标签已关闭：返回失败，不创建其它形态的选择窗口。」
- `background.js:1333-1334`「executeScript 遇到卡死的页面（未加载完、被冻结、渲染进程无响应）可能长时间不返回，批量场景下只要有标签卡住，整个「一键收藏」就会石沉大海。」
- `background.js:1328`「内部页面不允许注入，忽略即可。」
- `background.js:1579-1581`「休眠（内存被回收）或从未加载过的标签，注入脚本注定要等到超时……就算注入失败，服务端兜底也还能补救。」
- `reading-position-background.js:32`「标签可能已关闭、正在跳转，或属于浏览器保护页面；都不影响正常浏览。」
- `background.js:612`「页面不支持注入时只保留角标提示。」

**扩展更新 / 重载导致上下文失效（Chrome MV3 SW 特有场景）**

- `content-reading-position.js:4-5`、`:48-49`、`:58-60`
- `content-folder-picker.js:10-11`、`:15-16`
- `picker-ui.js:21`「扩展更新后旧网页里的浮层可能还在；上下文失效时安静失败」
- `background.js:378-379`「不依赖 onInstalled —— 因为「重新加载扩展」不会触发 onInstalled」

**性能红线（影响注入策略）**

- `background.js:1698-1701`「⚠️ 性能红线：读 `naturalWidth/Height` 会触发布局重排，图片多的页面（信息流、图库）若遍历全部图片会把主线程卡到几十秒……所以这里一律「限量扫描」：图片最多看前 80 张，段落最多看前 200 个。」→ 实现在 `content-metadata.js:146-147`（`IMAGE_LIMIT = 80`、`PARAGRAPH_LIMIT = 200`）。
- `content-metadata.js:217-218`「行内 CSS 背景图：用属性选择器先筛一遍，比遍历所有元素算 computed style 快几个量级。」

**SPA / 时序**

- `background.js:1374-1382`（抖音时间线，已在上文引用）
- `background.js:1584-1585`「等待 + 事后复核共用同一个截止时间，所以最多只耽搁 DOUYIN_SETTLE_MS。」
- `content-metadata.js:1-7`（YouTube og 不更新）
- `content-metadata.js:61-62`「站内跳转后这份数据同样停留在上一个视频，所以必须 videoId 对得上才采用。」
- `content-metadata.js:632-635`「以前这里会退回域名，结果 JS 渲染站点会被存成「bilibili.com」这种无效标题，反而把浏览器本来正确的标题盖掉了。」

**没有找到的 TODO / FIXME**：对仓库 JS 全文 grep `TODO|FIXME|HACK|XXX` **无命中**——已知限制全部写在上述注释正文里，没有待办标记。

---

## 9. Firefox 移植影响最大的 5 个点（内容脚本层）

1. **`world: "MAIN"`（`background.js:567`）与它背后的 Chrome 内建 AI API（`content-translation.js:39/65/82/86`）**。Firefox 对 `executeScript` 的 `world` 选项支持起始版本晚于 Chrome，且**完全没有 `Translator` / `LanguageDetector`**（Firefox 的本地翻译走 UI 内置、不暴露给扩展）。结论：这个功能在 Firefox 上大概率要整体降级为「不支持」或改走外部翻译服务，而不是改一行参数。
2. **`files` 注入的返回值语义（`background.js:570` + `content-translation.js:162` + `background.js:1626` + `content-metadata.js:695`）**。当前依赖「文件最后一个表达式的完成值」被当作 `result` 返回（翻译返回对象、元数据直接 `extractPageMetadataForShortcut();` 的返回对象）。这属于最容易在跨浏览器时悄悄退化的地方——**必须实测 Firefox 是否照样把 `result` 填好**，否则 `injection[0]?.result?.ok === false`（`:570`）永远不等，错误提示不再出现；`:1626` 的 `injection?.[0]?.result || null` 永远为 null，元数据全退回标签页标题。
3. **`chrome.*` 命名空间 + Promise 的混用**。内容脚本里既有 Promise 式（`content-reading-position.js:53` 依赖 `chrome.runtime.sendMessage` 返回可 `.catch` 的 Promise；`content-folder-picker.js:18` `Promise.resolve(chrome.runtime.sendMessage(...))`）也有回调式（`reading-position-background.js:85-87` 的 `sendResponse` + `return true`）。Firefox 的 `chrome` 命名空间 Promise 支持是最需要逐个核对的移植风险（见 §11）。
4. **受保护页面判定完全依赖 `isWebUrl`（`background.js:1665-1667`）+ 静默 `try/catch`**。Firefox 另有硬性禁注页面（`about:*`、`addons.mozilla.org`、内置 PDF viewer 的 `resource://pdf.js/`）以及不同的报错，而当前代码在这些页面上只会「静默失败 + 角标」，**用户不会得到任何解释**。同时 `chrome.scripting.insertCSS` 与重注入策略在 Firefox 上的失败面更宽（`background.js:76`、`:85-88` 的 `injectedCssTabs` 复位逻辑需重验）。
5. **裸 DOM + `innerHTML` + 全属性 `!important` 的注入风格 vs Firefox 的 CSP / Trusted Types 处理差异**。药丸（`translation.css:41-115`，无 Shadow DOM）与翻译提示（`translation.css:13-38`）直接写页面 DOM；两个 Shadow DOM 浮层（`content-reading-position.js:120`、`picker-ui.js:77`）用的是 `innerHTML`（`content-reading-position.js:124`、`picker-ui.js:94/120`）。若站点启用 `require-trusted-types-for 'script'`，内容脚本对页面 DOM 的 `innerHTML` 写入会被拒；Firefox 对内容脚本 CSP 的处理与 Chrome 不同，需要逐站点实测。

（另有两个「内容脚本之外」但同样阻塞移植的点，仅记录：`manifest.json:34-36` 的 `side_panel` API 在 Firefox 不存在（对应 `sidebar_action`）；`background.js:38` 的 `service_worker` 在 Firefox 里是 event page，需重验 top-level `importScripts`（`background.js:1`）与 SW 重启语义。）

---

## 10. 复现/验证入口

- 单测（Node + jsdom + vm）：`tests/metadata-extract.test.js`、`tests/douyin-spa.test.js`、`tests/reading-position-content.test.js`、`tests/reading-position-background.test.js`、`tests/picker-reinjection.test.js`、`tests/topbook-modal.test.js`、`tests/background-modules.test.js`。
- 这些测试都**不加载真实浏览器**，靠 vm/JSDOM 伪造 `chrome` API，因此它们**无法验证** §11 里的 Firefox 行为差异。

---

## 11. 未证实 / 不确定

以下条目**没有**在仓库代码或测试中找到证据，属于需要实测或查文档确认的推测：

1. **`world: "MAIN"` 在 Firefox 的最低支持版本**——未查文档，仅知道它与 Chrome 不同期。同时不确定：Firefox 的 MAIN 世界注入是否要求扩展有额外权限，以及 MAIN 世界注入后 `files` 的返回值是否可用。
2. **`executeScript({files})` 的 `result` 是否等于文件末表达式的完成值**——这是 Chrome 的行为，代码在 `background.js:570`、`background.js:1626` 两处依赖它；**Firefox 行为未验证**。（仓内测试用 vm 直接调用函数，绕过了这一层。）
3. **`chrome.runtime.sendMessage` 在 Firefox 的 `chrome` 命名空间下是否返回 Promise**——`content-reading-position.js:53`、`content-folder-picker.js:18`、`picker-ui.js:20` 都依赖它。未验证。
4. **`chrome.scripting.insertCSS` 与 `chrome.storage.session`（`background.js:1271/1273/1278/1297/1299`）在 Firefox MV3 的可用性/版本门槛**——未查文档。
5. **`<script type="application/json">` 节点是否会在严格 CSP 站点上被拒**——未在真实站点验证；同时**页面 JS 能读写该 payload** 这一点是从代码推断（`background.js:1206-1210`），没有对应的防御代码，也没找到相关注释。
6. **Trusted Types 是否已经在真实站点上导致过注入失败**——仓库无任何 Trusted Types 处理或相关注释，无法判断是否已知问题。
7. **`background.js:1322` 的注释说「Chrome 内部页面收不到扩展页消息」**——这是注释的判断，未找到验证过的记录。
8. **`content-translation.js` 在 MAIN 世界执行时，`Translator` 下载进度回调（`:68-71`、`:88-92`）在 Firefox 上如何表现**——Firefox 无此 API，不适用，但若未来用替代方案（如外部翻译服务），`monitor` 语义需重新设计。
9. **`sidepanel.html` / `chrome.sidePanel` 相关内容脚本交互**（`background.js` 里对侧栏的消息）不在本次读取范围内，未评估；`manifest.json:34-36` 的 `side_panel` 在 Firefox 不存在，但具体影响面未展开。
10. **`chrome.tabs.sendMessage` 在 Firefox 中「脚本尚未注入时的即时失败」语义**——`reading-position-background.js:19` 依赖「此时脚本可能还没注入、`.catch` 吞掉」，Firefox 的错误时机是否有差异未验证。
