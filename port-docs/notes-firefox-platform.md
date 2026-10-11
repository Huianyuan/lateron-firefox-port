# LaterOn 1.66.1 → Firefox 平台能力核查笔记

- **核查日期**：2026-10-11（Asia/Shanghai）
- **被核查对象**：`repo/manifest.json`（78 行，git HEAD `00fde27`，工作树干净）。本笔记全程只读，**未改动仓库任何文件**；引用行号均为该文件真实行号。
- **Firefox 版本基准**（同日从 Mozilla 官方接口抓取）：release `157.0.1`、ESR `140.17.0esr`、ESR-next `153.4.0esr`、Dev Edition `158.0b5`、Nightly `160.0a1`；`LAST_RELEASE_DATE 2026-10-09`、`LAST_MERGE_DATE 2026-10-08`。来源：<https://product-details.mozilla.org/1.0/firefox_versions.json>
- **兼容数据来源**：`mdn/browser-compat-data` main 分支原始 JSON（2026-10-11 抓取）。仓库 <https://github.com/mdn/browser-compat-data>；下文凡写「BCD」处即指该仓库中对应的 `webextensions/**.json` 条目（如 <https://github.com/mdn/browser-compat-data/blob/main/webextensions/manifest/background.json>）。MDN 页面的 compat 表与这些 JSON 同源。
- **MDN 页面版本信息**：所有 MDN 页面抓取于 2026-10-11；已知页面「last modified」：CSP 指南 = 2026-08-21，`tabs.onReplaced` = 2025-07-17，`tabs.Tab` = 未见 frozen 相关修订记录。Extension Workshop 页面无逐页日期，抓取于同日。
- **结论标记**：`[不支持]` Firefox 完全没有该能力；`[写法不同]` 能力存在但 manifest/代码写法需改；`[需版本]` 需要不低于某版本；`[未证实]` 未找到权威来源（汇总见文末）。

---

## 0. 结论速览

| 项目 | Firefox | 最低版本 | 移植动作 |
|---|---|---|---|
| `manifest_version: 3` | 支持 | **109**（101 起 dev preview） | 保留 |
| `side_panel` / `sidePanel` / `chrome.sidePanel` | `[不支持]` | — | 换成 `sidebar_action` + `browser.sidebarAction` |
| `background.service_worker` | `[不支持]` | — | 加 `background.scripts`（事件页）；linter 会对「只有 service_worker」报 **error** |
| `chrome.*` 命名空间 | 支持（MV2 回调 / MV3 也支持 Promise） | 45+ | **不必**改成 `browser.*` |
| `browser.*` + Promise | 支持 | 45+（原生） | 可选 |
| `action` / `omnibox` / `contextMenus` / `commands` / `alarms` / `storage` / `tabs` / `windows` / `scripting` / `activeTab` | 支持 | 见 §4 | 少量参数/语义差异 |
| `unlimitedStorage`、`storage.session` | 支持 | 56 / 115 | `setAccessLevel` 不存在 |
| `web_accessible_resources`（MV3 形式） | 支持 | 109 | 需 `matches` 或 `extension_ids`；无 `use_dynamic_url` |
| MV3 默认 CSP | 支持 | 109 | 禁 eval/内联，wasm 需 `'wasm-unsafe-eval'` |
| `browser_specific_settings.gecko.id` | MV3 **必需**（签名用） | 42 | 必须新增 |

---

## 1. 侧栏：`side_panel` 不支持，改用 `sidebar_action`

### 1.1 `side_panel` 与 `sidePanel` API

- **`side_panel` manifest key：Firefox 完全不支持**。BCD `manifest/side_panel` 的 Firefox 列为 no support（Chrome 114+ / Edge 114+ / Opera 100+）；MDN 的 `manifest.json/side_panel` 页面也标注 Firefox 不支持。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/side_panel>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/manifest/side_panel.json>
- **`sidePanel` 权限：Firefox 不支持**。MDN `manifest.json/permissions` 的权限清单里 `sidePanel` 条目标注 Chrome 114+ / Edge 114+，Firefox 与 Firefox for Android 均为 no support。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/permissions>
- 因此 `chrome.sidePanel.*` / `browser.sidePanel.*` 在 Firefox 中不存在，`manifest.json:15` 的 `"sidePanel"` 权限与 `manifest.json:34-36` 的 `side_panel` 键都需要替换（`sidePanel` 权限在 Firefox 属未支持权限，见 §6 的 linter `MANIFEST_PERMISSION_UNSUPPORTED`）。

### 1.2 Firefox 的对等能力：`sidebar_action` + `browser.sidebarAction`

- `sidebar_action`（manifest key）自 **Firefox 54** 起支持，且在 **Manifest V2 and higher** 均可使用（MV3 可用）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/sidebar_action>
- MV3 下的 manifest 写法示例（可直接对应本仓库 `sidepanel.html`）：

```json
"sidebar_action": {
  "default_panel": "sidepanel.html",
  "default_title": "__MSG_extensionName__",
  "default_icon": { "16": "icon16.png", "32": "icon32.png" },
  "open_at_install": false
}
```

- 键语义（来源同上页面）：
  - `default_panel` **必填**，是本地化属性，可写 `__MSG_*__`；
  - `default_icon`、`default_title` 可选，用于浏览器侧栏 UI（「View > Sidebar」菜单等）中的标题与图标；
  - `open_at_install`（Boolean，**默认 true**）：安装完成时自动打开侧栏；BCD 记 `open_at_install` 从 **Firefox 62** 起支持；
  - `browser_style` 在 **MV3 已移除**：MV3 扩展从 **Firefox 118** 起不再支持设为 true（MV3 下默认 false）。
- **侧栏宽度由用户拖拽控制**：MDN 侧栏指南只描述用户通过浏览器 UI（View > Sidebar）选择要显示的侧栏、侧栏显示在窗口一侧、每个窗口一份实例；`sidebar_action` 与 `sidebarAction` 都没有宽度相关键。（MDN 未明文写「宽度只能由用户控制」，此为对文档「无宽度 API」的推断，见 §11-13。）来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/user_interface/Sidebars>
- **生命周期**：打开侧栏时把文档加载进每个已打开窗口，新窗口也会各自加载；**窗口关闭或用户关闭侧栏时侧栏文档被卸载**（不是常驻页面）。首次安装时侧栏自动打开（对应 `open_at_install` 默认 true）。来源同上。

### 1.3 `browser.sidebarAction.*` 各方法行为与限制

| 方法 | Firefox 最低版本 | 说明 |
|---|---|---|
| `setPanel` / `setTitle` / `setIcon` / `getPanel` / `getTitle` | 54 | 支持 `windowId` 参数（FF61 起），传 `null` 作用于所有窗口（FF59 起） |
| `open()` | **57** | 打开**当前活动窗口**的侧栏；**只能在 user action 的 handler 里调用** |
| `close()` | 57 | — |
| `toggle()` | 73 | — |
| `isOpen()` | 59 | — |
| badge 系列（`setBadgeText` 等） | `[不支持]` | sidebarAction 没有 badge API（Chrome 也无此 API） |

- 版本数据来源：<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/sidebar_action.json>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/sidebarAction>
- **`open()` 的用户手势要求（关键坑）**：MDN 原文「**You can only call this function from inside the handler for a user action.**」（你只能从用户动作的 handler 内部调用），页面示例即在 `menus.onClicked` 里调用 `browser.sidebarAction.open()`。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/sidebarAction/open>
- 同一限制的强化说明：MDN *User actions* 明确警告——在 user action handler 中先 `await` 其它异步操作再调用受手势限制的 API 会失败，因为「user action handler 状态」已丢失。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/User_actions>
- **能否在后台脚本里调用 `open()`**：不能用于「程序化自动弹侧栏」。后台事件（如 alarm、消息）触发的调用不算 user action。Firefox 提供的对应手段是：
  - 安装即打开 → `sidebar_action.open_at_install: true`（默认值）；
  - 快捷键打开 → commands 里的特殊命令 **`_execute_sidebar_action`**（Firefox 54+，**Chrome 无此命令**）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/commands>
  - 点击工具栏按钮打开 → `action.onClicked` 的 handler 里**同步**调用 `browser.sidebarAction.open()`。
- 对照 Chrome：Chrome 的 `chrome.sidePanel.open()` 同样要求用户手势（Chrome 116+，BCD `sidePanel.open`），但 Chrome 另有 `sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` 之类「点图标即开」的行为设置；**Firefox 没有等价 API**（未找到权威说明，见 §11-13）。

---

## 2. 后台脚本：MV3 只有事件页，没有 service worker

- **`background.service_worker` 在 Firefox 不支持**。BCD `manifest/background.service_worker`：Firefox = no support，Chrome 88+。MDN `manifest.json/background` 页面明确「Firefox does not support `background.service_worker`」。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/manifest/background.json>
- **Firefox MV3 支持的是 `background.scripts`（事件页 / non-persistent background script）或 `background.page`**：「In Manifest V3, only non-persistent background scripts or a page are supported.」`background.persistent` 只在 MV2 有意义（MV3 不能设 true）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Background_scripts>
- **MDN 给出的跨浏览器写法**是同时声明两者：支持 service worker 的浏览器用 `service_worker`，其余用 `scripts`。`background.scripts` Firefox 48+；`background.page` Firefox 48+。来源见上两条。
- **Chrome 侧的兼容性**：Chrome 只支持 service worker；Chrome 121 之前，MV3 扩展里出现 `background.scripts` 会导致**加载被拒绝**，从 Chrome 121 起改为忽略该键。因此「双写」对本扩展（`minimum_chrome_version: 121`，`manifest.json:6`）是安全的。来源：MDN `manifest.json/background`（同上）。
- **addons-linter 会强制要求配对**（这是最容易踩的一条）：
  - `BACKGROUND_SERVICE_WORKER_NOFALLBACK` — **error**：「The /background/service_worker property must be paired with use of /background/scripts property for Firefox compatibility.」
  - `BACKGROUND_SERVICE_WORKER_IGNORED` — **warning**：「The /background/service_worker manifest property is unsupported and ignored on Firefox. Please make sure /background/scripts or /background/page properties are providing appropriate Firefox compatibility.」
  来源：<https://mozilla.github.io/addons-linter/>
- **SW 专有写法在事件页里的后果**：
  - `importScripts()`：事件页不是 Worker 环境，**没有 `importScripts`**。`repo/background.js:1` 现在用 `importScripts("url-utils.js", "reading-position-background.js")`，在 Firefox 事件页中会抛 `TypeError`。正确做法是把这些文件按顺序写进 `background.scripts` 数组（脚本按数组顺序加载并共享同一全局作用域），并给 `background.js` 的 `importScripts` 调用加环境判断（`if (typeof importScripts === "function")`）。来源：MDN `manifest.json/background`/`Background_scripts`（「scripts are loaded in order … they share the same global scope」）；`importScripts` 不存在于文档环境属 WorkerGlobalScope 语义推断，见 §11-7。
  - `self`：文档全局同样有 `self`（指向 window），一般可继续使用；属推断。
  - `addEventListener('fetch')` / `onfetch`：事件页没有 Service Worker 的 fetch 事件，这类代码在 Firefox 不会触发（替代方案是 `webRequest`，或改为扩展页面内的显式请求代理）。`[不支持]`，未找到直接权威表述，见 §11-7。
  - `postMessage`/`MessageChannel` 等 SW 专有全局：不要依赖。
- **事件页的 DOM 与生命周期差异**：
  - DOM 可用性：Firefox 的 `background.scripts` 以**普通文档环境**运行（MDN 的 `preferred_environment` 键即用于在 document 与 service_worker 之间选择，Chrome 忽略该键，Firefox/Safari 省略时按 document 运行，`preferred_environment` Firefox 136+）。因此 `document`、`DOMParser`、`Image`、`XMLHttpRequest` 等在事件页中可用，而 SW 里没有。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background>（BCD `background.preferred_environment`: FF=136 / CR=no support）
  - 生命周期：「事件页只在需要响应事件时被加载，并在空闲时被卸载」；「a background page does not unload until all visible views and message ports are closed. Opening a view does not cause the background page to load but does prevent it from closing.」来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Background_scripts>
  - 崩溃恢复：Firefox 中持久后台脚本会自动重载；**事件页不会自动重载，但 Firefox 在需要调用其 WebExtensions API 事件监听器时会自动重启它**（可用 about:crashextensions 测试）。来源同上。
  - 推论（对移植很重要）：**全局变量不保证跨唤醒存活**，状态必须写 `storage`；`alarms` 不跨浏览器会话持久（见 §4），需在后台顶层或 `runtime.onStartup`/`onInstalled` 重建。
- **最低版本**：MV3 在 Firefox **109** 正式可用（101–108 为 developer preview）。来源：<https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/>

---

## 3. API 命名空间与 Promise 语义

- **`chrome.*` 在 Firefox 可用，不必改成 `browser.*`**：
  - 「In Manifest V2, Firefox extensions support the use of the `chrome.*` namespace with APIs that provide asynchronous event handling using callbacks. **In Manifest V3, Firefox supports promises for asynchronous events in the `chrome.*` namespace.**」来源：<https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/>
  - 即：Firefox 的 `chrome.*` 同时接受回调与 Promise（MV3 下异步 API 返回 Promise）。因此本仓库全量 `chrome.*` 的代码在 Firefox MV3 下可以照用。
- **`browser.*` 是 Firefox 的原生 Promise 命名空间**：「Firefox and Safari have always used the `browser` namespace (with promises). Originally, Chromium-based browsers used the `chrome` namespace (with callbacks). **Starting with Chrome 148, Chrome also supports the `browser` namespace**, except in extensions that include a DevTools page; that limitation was removed in Chrome 152.」来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API>
- **移植建议（本仓库）**：保持 `chrome.*`。理由——把 `chrome.` 全量改成 `browser.` 反而会破坏 Chrome 121（`minimum_chrome_version`，`manifest.json:6`）与 Edge 的兼容性，因为 Chrome 要到 148/152 才支持 `browser.*`；而 Firefox 对 `chrome.*` 的支持是完整的。
- **反向场景**：若确实想在 Chrome 上用 `browser.*` 的 Promise 风格，需引入 `webextension-polyfill`；但该 polyfill **不支持 Firefox 独有 API**。来源：<https://extensionworkshop.com/documentation/develop/browser-compatibility/>
- **回调式代码的错误处理差异**：Chrome 用 `chrome.runtime.lastError`（回调式）报告失败；Firefox 的 Promise 风格会 reject。BCD `runtime.lastError` Firefox 47+，且 MDN 提示 Chrome 中它「not an Error object」。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/runtime/lastError>
- **`runtime.onMessage` 的异步响应语义（移植最常见的坑之一）**：
  - 两种异步响应方式：从监听器 `return true`（让 `sendResponse` 在监听器返回后仍有效），或 `return` 一个 Promise。
  - **返回 Promise 只有 Firefox 支持**：BCD `runtime.onMessage.return_promise`：Firefox ≤62 / Chrome = no support。所以想在 Chrome 上工作必须用 `return true`。
  - MDN 警告：「Do not prepend `async` to the function. Prepending `async` changes the meaning to sending an asynchronous response using a promise, which is effectively the same as `sendResponse(true)`.」
  来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/runtime/onMessage>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/runtime.json>
- **`runtime.getManifest()` 的行为**：MDN 注记「Returns `null` for missing values, and removes unsupported keys.」——即在 Firefox 上，Chrome 专有键（如 `minimum_chrome_version`、`side_panel`）不会出现在 `getManifest()` 结果里。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/runtime/getManifest>

---

## 4. 逐项能力核查

### 4.1 `action`（含 `onClicked`、badge/icon/title 系列）

- **支持**：manifest key 与 `action` API 均 **Firefox 109+**（MV3 起），`onClicked`、`setBadgeText`、`setIcon`、`setTitle`、`setBadgeBackgroundColor` 均为 109+。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/action>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/action.json>
- 差异：
  - Firefox 的 badge/icon/title 方法支持 **`details.windowId`** 参数（可只改某个窗口的显示），Chrome 无此参数；
  - `setBadgeText({ text: null })`：Firefox 一直支持，Chrome 从 116 起；
  - Firefox 独有 manifest 键 `action.default_area`（把按钮放到地址栏/菜单，Chrome 无）与 `action.theme_icons`；
  - `action.openPopup()` **Firefox 109+**，但 BCD 注记「**Before Firefox 149, a user gesture is required**」（FF149 之前必须在用户手势中调用）；
  - `getUserSettings`/`setUserSettings` Firefox 116+（Chrome 91+），`onUserSettingsChanged` Firefox 142+。
- 本扩展：`action` 无 `default_popup`（`manifest.json:22-30`），所以点击行为走 `action.onClicked`，Firefox 完全支持。

### 4.2 `omnibox`

- **支持**：Firefox **52+**（Chrome 9+）；`keyword: "lo"`（`manifest.json:31-33`）可直接用。`onInputChanged`/`onInputEntered`/`onInputStarted`/`onInputCancelled`/`setDefaultSuggestion` 均 52+。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/omnibox>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/omnibox.json>
- **重要写法差异**：`SuggestResult.description` 与 `setDefaultSuggestion({description})` 在 Firefox 中按**纯文本**处理，**不识别 XML 标记**；Chrome 使用 XML（`<match>`、`<dim>`、`<url>`）。因此 Chrome 里带高亮标记的建议文本在 Firefox 会把标签原样显示，需要改写。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/omnibox/SuggestResult>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/omnibox/setDefaultSuggestion>
- `deletable`（建议可否被删除）与 `onDeleteSuggestion` 需要 Firefox 109+；`onInputEntered` 触发的用户动作从 **Firefox 142** 起会授予 `activeTab`（见 §4.14）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/activeTab_permission>

### 4.3 `contextMenus`

- **支持**：`menus` Firefox 55+（`contextMenus` 是别名，Firefox 48+）；`onClicked`、`create`/`update`/`remove`/`removeAll` 均 55+。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/menus>
- **关键差异：菜单在 Firefox 中从不持久化。** MDN `menus.create` 注记：Chrome 中用持久后台页创建的菜单会被持久化（重启后仍在），**Firefox 从不持久化**，因此应在 `runtime.onInstalled` 里创建。Extension Workshop 补充：若只按 `onInstalled` 注册，**Firefox 105 及以前**重启浏览器后菜单会消失；变通做法是无条件调用 `contextMenus.create`，并在回调里读 `runtime.lastError` 以避免「ID already exists」告警。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/menus/create>、<https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/>
- `contexts` 差异：Firefox 支持 `bookmark`（59+）、`password`（53+）、`tools_menu`（56+）等 Chrome 没有的类型；`tab` 上下文 Chrome 要到 150 才支持（Firefox 53+）。`OnClickData` 的 `button`/`modifiers`/`linkText`/`targetElementId`/`bookmarkId` 为 Firefox 独有。
- `documentUrlPatterns` / `targetUrlPatterns`：MDN `menus.create` 文档中列出（BCD 未单独跟踪该子特性）→ 可用于按 URL 过滤菜单项。来源同上页面。
- Firefox 独有事件/方法：`onShown`、`onHidden`、`refresh()`、`getTargetElement()`、`overrideContext`。

### 4.4 `commands`（含 `Alt+1` / `Alt+2` / `Alt+Shift+1`）

- **支持**：`commands` Firefox **48+**；`suggested_key` 是生效的（支持 `default`/`mac`/`linux`/`windows`/`chromeos`/`android`/`ios`）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/commands>
- 合法组合规则：1 个必需修饰键（Ctrl/Alt/Command/MacCtrl）+ 可选第二修饰键（Shift，或 Firefox 63+ 的 Ctrl/Alt/Command/MacCtrl）+ 一个键（A–Z、0–9、F1–F12、Comma/Period/Home/End/PageUp/PageDown/Space/Insert/Delete/方向键）。因此 `Alt+1`、`Alt+2`、`Alt+Shift+1`（`manifest.json:42-58`）在**格式**上合法。`MoreSecondaryModifiers` = Firefox 63+；F1–F12 只有 Firefox 支持（Chrome 无此条目）。
- **冲突处理（官方规则）**：被浏览器或其它扩展占用的组合**无法覆盖**——扩展可以定义它，但 handler 不会被调用（静默失效）。来源同上页面。
- **`Alt+1` / `Alt+2` 是否被 Firefox 保留或与内置快捷键冲突：未找到权威来源**（support.mozilla.org 的 Firefox 快捷键页未列出 Alt+数字 组合，两种抓取方式均未取得相关文本）。移植时应在 Firefox 实测，或直接让用户改键。见 §11-2。
- **用户如何改键**：用户在 **about:addons → 该扩展 → Manage Extension Shortcuts（管理扩展快捷键）** 修改；Chrome 只能在 `chrome://extensions/shortcuts` 改。扩展侧还可以：
  - `commands.update()` **程序化改键**（Firefox 支持；Chrome 不能程序化改）；
  - `commands.openShortcutSettings()` 直接打开快捷键设置页（Firefox 支持，Chrome 无）。
  来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/commands>
- **特殊命令**：MV3 建议用 **`_execute_action`**（Firefox 91+）替代已废弃的 `_execute_browser_action`/`_execute_page_action`（仅 MV2）；**`_execute_sidebar_action` 为 Firefox 独有（54+）**，可用于「一键开侧栏」。
- Firefox 135 起用户还可指定 F13–F19 作为快捷键。

### 4.5 `alarms`

- **支持**：Firefox **45+**。`create`/`clear`/`clearAll`/`get`/`getAll`/`onAlarm` 均可用。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/alarms>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/alarms.json>
- 差异：
  - MDN `alarms.create` 记录的**最小周期限制是 Chrome 专有**：Chrome 中（非 unpacked 加载的）扩展不能比每 30 秒更频繁，传入小于 0.5 分钟会按 30 秒处理并给出告警（Chrome 120 之前该下限是 1 分钟）。**Firefox 的最小延迟未找到权威说明**（见 §11-1）。
  - Chrome 117+ 最多 500 个 alarm；Chrome 150+ alarm 名字超过 1024 字节会被拒绝（Firefox 无对应条目）。
  - `alarms.clearAll()` 的返回值：BCD 注记「**Until Firefox 156, returned a boolean rather than undefined**」（Chrome 157 之前同样返回 true）——不要依赖返回 `undefined`。
  - **alarms 不跨浏览器会话持久**（重启后丢失），需要在后台脚本顶层或 `runtime.onStartup`/`onInstalled` 重建。来源同上。
  - alarms 是全扩展共享的：后台创建的 alarm 会在选项页/弹窗/扩展页面中触发，反之亦然。
- 本扩展用途：`background.js:348-353` 用 `periodInMinutes: 720`（12 小时）做清理，Firefox 下无最小周期风险。

### 4.6 `storage.local` 与 `unlimitedStorage`

- **支持**：`storage` 权限 Firefox 48+，`storage.local` Firefox 45+（内容脚本中 48+）；`unlimitedStorage` 作为普通权限 Firefox **56+**（Chrome 20+）。注：`unlimitedStorage` **不能**放进 `optional_permissions`（BCD optional_permissions 中 `unlimitedStorage` 两端都是 no support）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/permissions>
- 配额差异：
  - Chrome：没有 `unlimitedStorage` 时 `storage.local` 上限为 **5MB**（MDN 原文如此），有则不受限。
  - Firefox：`storage.local` 受**与 IndexedDB 相同的存储配额**约束；需要 `unlimitedStorage` 才能超出，但**即使有 `unlimitedStorage`，超过全局磁盘配额时仍可能报 quota exceeded**。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/local>
  - Firefox 的具体数值：best-effort 模式下单个 origin 上限 = 取较小者——profile 所在磁盘总容量的 **10%**，或 **10 GiB**（Firefox 对同一 site 下所有 origin 施加的 group limit）；获得 persistent 授权的 origin 可到磁盘总容量的 **50%**（上限 8 TiB）且不受 group limit 约束。Web Storage（localStorage/sessionStorage）每 origin 各 5 MiB，最多 10 MiB。来源：<https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria>
- Firefox 独有的 `unlimitedStorage` 效果：「**In Firefox, enables extensions to create a "persistent" IndexedDB database without the browser prompting the user for permission at the time the database is created.**」（还能让 `storage.local` 突破配额）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/permissions>
- 本扩展：`permissions` 已有 `storage` + `unlimitedStorage`（`manifest.json:10-11`），Firefox 下需保留 `unlimitedStorage`（FF56+，不构成版本门槛）。

### 4.7 `storage.session`

- **支持**：Firefox **115+**（Chrome 102+）；`session.QUOTA_BYTES` Firefox 131+。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/session>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/storage.json>
- 语义：只存内存、不落盘，浏览器会话期间有效（Firefox 115+ 支持）。
- **关键差异：`storage.session.setAccessLevel()` 在 Firefox 不存在**（BCD `StorageArea.setAccessLevel`：Firefox = no support / Chrome 96+）。MDN 说明 `storage.session` **默认不对内容脚本暴露**，要用 `setAccessLevel()` 才能改变——因此在 Firefox 中**内容脚本无法访问 `storage.session`**。移植时若内容脚本需要读到会话状态，必须改走 `storage.local` 或由后台经 `runtime.sendMessage` 转发。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/session>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/StorageArea/setAccessLevel>
- 其他：`getBytesInUse` 对 `session` 需 Firefox 131+；`onChanged` Firefox 101+（Chrome 73+）。

### 4.8 `tabs`

- **支持**但有若干缺失/差异（来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/tabs.json>）：

| 特性 | Firefox | Chrome | 备注 |
|---|---|---|---|
| `tabs.onReplaced` | **`[不支持]`（no support）** | 26+ | MDN：「may not be relevant for or supported by browsers other than Chrome」（prerendering/instant 专用） |
| `tabs.hide` / `tabs.show` | **61+**（需 `tabHide` 权限） | no support | Firefox 独有 |
| `Tab.discarded` | 57+ | 54+ | 可用 |
| `Tab.autoDiscardable` | 116+ | 54+ | 低版本 Firefox 无 |
| `Tab.frozen` | **BCD 无条目、MDN `tabs.Tab` 全文未提** | Chrome 专有 | 视为 Chrome 专有（见 §11-3） |
| `Tab.groupId` | 138+ | 88+ | 低版本 Firefox 无标签组 |
| `Tab.lastAccessed` | 56+ | 121+ | — |
| `Tab.cookieStoreId` | 52+ | no support | Firefox 独有（容器标签页） |
| `tabs.captureTab` | 59+ | no support | Firefox 独有 |
| `tabs.captureVisibleTab` | 47+ | — | FF125 及以前需要 `<all_urls>`；FF126 起 `<all_urls>` 或 `activeTab` 均可 |
| `tabs.create({discarded:true})` | 63+ | no support | — |
| `tabs.executeScript` | 仅 MV2 | 仅 MV2 | MV3 用 `scripting.executeScript` |
| `tabs.onUpdated` 的 `filter`/`properties` | Firefox 独有 | — | 只在 Firefox 生效 |

- **`tabs` 权限本身**：Firefox 48+（Chrome 20+）。`captureVisibleTab` 的权限要求在 Firefox 侧比 Chrome 宽松（FF126 起 `activeTab` 也够）。

### 4.9 `windows.create({type:'popup'})`

- **支持**：`windows.create` Firefox **45+**；`createData.type` 45+；类型取值 `popup`/`panel`/`detached_panel`/`app`/`devtools` 均可用。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/windows/create>
- **差异 1（易踩）：`createData.focused` Firefox 不支持**（BCD `createData.focused`: Firefox = no support / Chrome 12+）。MDN 页面本身仍写着 `focused` 默认 true——以 BCD/MDN compat 表为准。需要把新窗口置前时，可靠做法是在用户手势内创建（或创建后 `windows.update({focused:true})`）。
- **差异 2**：`type: "panel"` 是 Firefox 独有（无地址栏/工具栏的窗口）；`type: "detached_panel"` 亦为 Firefox 独有。
- **差异 3**：`left`/`top` 定位在 **Firefox 108 及以前**对 `panel`/`popup` 类型被忽略（可用 `windows.update()` 绕过）。来源同上。
- 其他：`WindowState.docked` Firefox 不支持；`windows.get`/`getCurrent` 的 `getInfo.windowTypes` Firefox 不支持（`getAll` 的 `windowTypes` Firefox 58+）。

### 4.10 `scripting.executeScript`

- **支持**：`scripting` 权限与 API Firefox **102+**（MV3 下 Chrome 与 Firefox 101 起可用；MV2 下 Safari 与 Firefox 102+ 也可用）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/scripting/executeScript>
- **`world: 'MAIN'` 需要 Firefox 128+**（Chrome 102+）。这是本次核查里最容易造成「最低版本被抬高」的一项：BCD `ExecutionWorld.MAIN`：FF=128 / CR=102；`RegisteredContentScript.world` 同样 FF=128。来源：<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/scripting.json>
- `files` 注入：支持（可注入多文件）；`allFrames`：支持；`injectImmediately`：102+。
- 语义差异（重要）：
  - **权限不足时的行为不同**：Firefox/Safari 在只缺少部分 host 权限时**仍会执行并返回部分结果**（partial results）；**Chrome 只要缺权限就完全不执行**。来源：MDN `scripting.executeScript`（同上）。
  - `func` 会被序列化再反序列化：**对象字面量或类里的方法无法序列化**，此时 **Firefox 返回 `SyntaxError`，Chrome 只在目标标签页控制台报错**。来源同上。
  - `InjectionResult.error` 只有 Firefox 有（Chrome 未实现，issue 1271527）。
- `persistAcrossSessions`：Firefox 105 起为可选，**105 之前必须传且只接受 `false`**；`matchOriginAsFallback` FF128+；`documentIds` FF153+。

### 4.11 `activeTab`

- **支持**：Firefox **48+**（Chrome 26+）；它是 API 权限而非主机权限。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/activeTab_permission>
- 语义：授予对「用户当前正在操作的标签页」的**临时**访问，由显式用户动作触发，**持续到用户导航离开该页**；用 `"permissions": ["activeTab"]` 申请，也可放进 `optional_permissions` 并在运行时请求（`permissions.request()`），且是**静默授予、不弹提示**的权限之一。
- **它本身不授予任何 API**：例如要注入脚本仍需 `scripting` 权限，要读 `tabs` 的敏感字段仍需 `tabs` 权限。来源同上。
- 授予 activeTab 的用户动作（Firefox 官方列表）：
  1. 点击扩展的工具栏按钮 / 页面动作；
  2. 选择扩展的上下文菜单项（触发 `menus.onClicked`）；
  3. **激活 commands API 定义的键盘快捷键（触发 `commands.onCommand`）**；
  4. 点击地址栏中的扩展建议（触发 `omnibox.onInputEntered`，**从 Firefox 142 起**）。
- 例外：作用于「标签栏右键菜单」的菜单项会把 activeTab 授予**被右击的那个标签页**（即使它不是当前活动标签页）。来源同上。
- 本扩展：`manifest.json:9` 已有 `activeTab`；`quick-save`(Alt+1) 走 commands → 可自动获得 activeTab（Firefox 支持）。

---

## 5. `host_permissions` 与用户授权模型

- **写法**：MV3 的主机权限放 `host_permissions`（Firefox 109+ / Chrome 88+）；运行时追加用 `optional_host_permissions`（MV2 时代才写在 `permissions` 里）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/permissions>
- **安装时是否显示/授予（版本分水岭 FF127）**：
  - MDN：「Until Firefox 126, a Manifest V3 extension's requested host permissions weren't displayed in the install prompt. **From Firefox 127, host permissions listed in the manifest are displayed in the install prompt and granted on installation.**」
  - Extension Workshop：FF126 及以前安装时**既不显示也不授予**，FF127 起显示并授予。
  来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/host_permissions>、<https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/>
- **用户可以 ad hoc 授予/撤销**（about:addons → 权限）；扩展更新时**新增的主机权限不会向用户展示**（Firefox bug 1893232），因此扩展应自行用 `permissions.contains()` 检查并按需 `permissions.request()`。来源同上。
- **未授予时 `scripting.executeScript` 的表现**：不会注入。MDN Content scripts：「content scripts can only access page content when host permissions for the web page's origin are granted」；「To inject scripts programmatically, the extension needs **either the `activeTab` permission or host permissions**. The `scripting` permission is required to use methods from the `scripting` API」；「Registered content scripts are only executed if the extension is granted host permissions for the domain」。而 `executeScript` 在 Firefox/Safari 中是**部分结果**语义（缺部分权限仍可能成功）。**具体报错文本/错误码未找到权威来源**（见 §11-6）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_scripts>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/scripting/executeScript>
- **`activeTab` 能否覆盖**：能，但只覆盖「用户动作发生的那一个标签页，且到导航为止」——不能覆盖「任意标签页、任意时刻」的注入需求。
- **`browser.permissions.request()` 在 MV3 可用**：Firefox **55+**（Chrome 16+），必须在用户手势中调用。已知限制：无法在 DevTools 中请求权限（bug 1796933）；**Firefox 101 之前无法从侧栏（sidebar）文档请求**（bug 1493396）——侧栏即 `sidebar_action` 面板，移植后要注意这条历史限制。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/permissions/request>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/permissions.json>
- 本扩展：`host_permissions: ["http://*/*", "https://*/*"]`（`manifest.json:18-21`）在 Firefox 127+ 会在安装提示中列出并要求授予；在 109–126 上安装后不会自动获得，需要代码里做 `permissions.contains` + 引导用户授权。

---

## 6. 打包与签名

- **临时安装（开发用）**：about:debugging → **This Firefox** → **Load Temporary Add-on** → 选择扩展目录里的任一文件或打包的 `.zip`；**一直保持安装直到手动移除或重启 Firefox**；点击 **Reload** 会重新加载持久脚本并**重新解析 `manifest.json`**（权限、`content_scripts` 等改动生效）。来源：<https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/>
- **正式安装必须签名**：扩展与主题必须由 Mozilla 签名才能在 Firefox release/beta 安装；签名统一经 addons.mozilla.org（无论是否在 AMO 上架自分发）。来源：<https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/>
- **未签名扩展的安装路径**：只能在 **Developer Edition / Nightly / ESR** 中安装，方法是先在 `about:config` 把 `xpinstall.signatures.required` 切为 false，**且该功能要求扩展必须带一个 add-on ID**。字典（dictionaries）无需签名。来源同上。
- **`browser_specific_settings.gecko.id` 是否必需**：**MV3 下必需**——「In Manifest V3, this property is required for signing (both AMO and self-distribution) to provide an extension ID；MV2 非必需但推荐」。MV2 不给 ID 时 AMO 会自动分配 GUID；**MV3 AMO 不再分配 ID，必须自己提供**。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/browser_specific_settings>
- **ID 格式**：推荐 ≤80 字符、形如邮箱的 `something@something`（正则 `^[a-zA-Z0-9-._]*@[a-zA-Z0-9-._]+$`，官方示例 `great_app@developers.company`），或 GUID 形式 `{8-4-4-4-12 hex}`；**可以用真实邮箱但官方提示可能招致垃圾邮件**（因此建议用自有域名的「假邮箱」而非个人真实邮箱）。来源同上。
- **AMO 的新强制项**：自 **2025-11-03** 起，提交到 AMO 的**新扩展**必须在 `browser_specific_settings.gecko` 中提供 `data_collection_permissions`（Firefox 140+ 的 manifest 能力）。addons-linter 会以 `MISSING_DATA_COLLECTION_PERMISSIONS`（warning）提示，未来对新版本也会强制。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/browser_specific_settings>、<https://mozilla.github.io/addons-linter/>（注意该规则表内部存在一处表述冲突，见 §11-11）
- **AMO 对 MV3 扩展的审核要点**（来源：<https://extensionworkshop.com/documentation/publish/add-on-policies/>）：
  - 扩展必须自包含，**不得加载/执行远程代码**（远程脚本、`eval` 远程串都属违规）；
  - 不得包含混淆代码或隐藏功能意图；为减小体积的压缩/打包允许，但必须向 Mozilla 提供可审查源码与可复现的构建说明（本仓库有 `scripts/build-release.py`，移植时需保留该可复现路径）;
  - 「Add-ons must only request those permissions that are necessary」——最小权限；移植时应删掉不再需要的 `sidePanel` 等；
  - 不得放宽网页的安全头（CSP）；
  - 远程传输用户数据必须加密；
  - 关于 `wasm-unsafe-eval`：**带 `'unsafe-eval'`、远程脚本、blob 或远程源的扩展不符合 AMO 政策，不允许上架**；WebAssembly 需要显式加 `'wasm-unsafe-eval'`（Firefox 102+），并可能触发人工审核。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/content_security_policy>
- **`minimum_chrome_version` 这类 Chrome 专有 key**：addons-linter 有一条**通用**规则 `MANIFEST_FIELD_UNSUPPORTED`（**warning**）——「A manifest field is not supported (or not supported for the extension manifest_version)」；同时 `runtime.getManifest()` 会「remove unsupported keys」。**是否有专门针对 `minimum_chrome_version` 的条目、是 warning 还是 error：未找到权威来源**（见 §11-4）。保守做法：Firefox 构建产物里删掉它，或接受 linter 告警。
- **MV3 扩展在 Firefox 的最低版本**：**109**（101 起为 developer preview）。来源：<https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/>

---

## 7. `web_accessible_resources`

- **支持**：`web_accessible_resources` Firefox 48+；MV3 形式（对象数组、`resources`/`matches`/`extension_ids` 三个子键）**均为 Firefox 109+**。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/web_accessible_resources>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/manifest/web_accessible_resources.json>
- **MV3 的结构要求**：每个对象**必须有 `resources`，并且必须有 `matches` 或 `extension_ids` 之一**。本仓库当前写法（`manifest.json:67-77` = `resources: ["icon128.png"]` + `matches: ["http://*/*","https://*/*"]`）**合法**。
- 差异：
  - `matches` 只按 **origin** 匹配；**Firefox 与 Safari 允许路径部分带通配以外的写法，Chrome 的路径部分必须是 `/*`**。本扩展用的 `http://*/*` 两端都合法。
  - **`use_dynamic_url` Firefox 不支持**（BCD: FF=no support / Chrome 130+）。若 Chrome 侧依赖它做随机 URL，需要移植时剔除。
  - **`extension_ids` Firefox 支持**（BCD FF=109）。
  - 从 **Firefox 105** 起，其它扩展要访问本扩展的资源，必须把它明确列进本键（以前默认允许）；内容脚本访问本扩展资源**不需要**列进 WAR。
  - URL 协议：Chrome 是 `chrome-extension://`，Firefox 是 `moz-extension://`——代码里若有硬编码需用 `runtime.getURL()` 生成。
- 注意 `minimum_chrome_version`/`side_panel` 等无关；但 `icon128.png` 若被网页 `<img>` 引用（本扩展的封面/占位图场景），Firefox 侧仍需保持 WAR 条目。

---

## 8. CSP 差异

- **MV3 默认 CSP**：`script-src 'self'; upgrade-insecure-requests;`（MV2 是 `script-src 'self'; object-src 'self';`）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/content_security_policy>
- 默认策略下（Firefox 与 Chrome 一致）：
  - **不能 `eval()` 字符串**，不能用 `new Function()`，不能用字符串形式的 `setTimeout`；
  - **内联脚本不执行**（`<script>…</script>`、`onclick=` 等）；
  - **默认不能用 WebAssembly**；需要把 `'wasm-unsafe-eval'` 加入 `script-src`（**Firefox 102+ / Chrome 103+** 支持该关键字；Firefox 的 MV2 扩展无需该关键字即可用 wasm）；
  - MV3 的 script 类指令只允许 `'self'`、`'none'`、`'wasm-unsafe-eval'` 等**静态源**，**禁止远程源与 blob**。
- 开发便利（仅开发期）：Chrome 110 的 unpacked 扩展、**Firefox 147 的临时加载扩展**可在 `extension_pages` 里指定 `http://localhost:3000` 之类的源。
- `sandbox` 键可用于沙箱化页面（BCD: Firefox 154+ / Chrome 88+）——这是想在扩展页面里跑 `eval`/内联脚本的唯一合规途径。
  来源均同上页面。
- **内容脚本受不受页面 CSP 限制**（这是第 8 项的核心，MDN 原文明说两端不同）：
  > 「In Manifest V2, content scripts have no CSP. As of Manifest V3, content scripts share the default CSP as extensions. It is currently not possible to specify a separate CSP for content scripts. The extent to which the CSP controls loads from content scripts varies by browser. **In Firefox, JavaScript features such as `eval` are restricted by the extension CSP. Generally, most DOM-based APIs are subjected to the CSP of the web page. In Chrome, many DOM APIs are covered by the extension CSP instead of the web page's CSP (crbug 896041).**」
  来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy>（页面 last modified 2026-08-21）
- **`<script src="chrome.runtime.getURL(...)">` 注入网页是否被页面 CSP 拦截**：按上面的一般性划分，在 Firefox 中这类**通过 DOM 插入的 script 元素**受**网页** CSP 管辖（Chrome 中很多同类 DOM API 反而受扩展 CSP 管辖）。因此同一段「把扩展资源当脚本塞进页面」的代码在两端行为可能不同：在 Firefox 上，若目标页面的 CSP 不允许该源，脚本会被拦。**该具体场景没有 MDN 明文**，属基于上述划分的推断（见 §11-9）。实践建议：不要用注入 `<script>` 执行扩展代码；用 `scripting.executeScript({ world: 'MAIN' })`（需 FF128+）或让内容脚本用 `runtime.sendMessage` 回后台。
- 其他 CSP 相关：
  - 默认 CSP 含 `upgrade-insecure-requests`（HTTP/WS 请求会被升级为 HTTPS/WSS）；如需 `http:`/`ws:` 必须在 `content_security_policy.extension_pages` 里覆盖该指令，但 AMO 要求所有用户数据安全传输，实际上等于不允许降级；
  - 含 `'unsafe-eval'`、远程脚本、blob 或远程源的扩展**不符合 AMO 政策，不能上架**（见 §6）。

---

## 9. 「Chrome MV3 扩展移植到 Firefox」常见坑清单

1. **`background.service_worker` 被忽略**：必须补 `background.scripts`（事件页），否则 addons-linter 报 `BACKGROUND_SERVICE_WORKER_NOFALLBACK` **error**（不是 warning）。来源：<https://mozilla.github.io/addons-linter/>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background>
2. **`importScripts()` 在事件页里不存在**：`background.js:1` 的调用会抛错；改为 `background.scripts` 数组（按顺序加载）并加 `typeof importScripts === "function"` 判断。
3. **事件页会被回收**：全局变量不保证存活，状态必须落 `storage`；`alarms` 不跨浏览器会话持久，需重建；事件页崩溃后不会自动重载（但下次事件会自动重启它）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Background_scripts>
4. **`sendResponse` 的异步语义**：Firefox 可以 `return` Promise，Chrome 必须 `return true`；不要给监听器加 `async`（会被当成「已用 Promise 响应」）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/runtime/onMessage>
5. **`sidePanel` → `sidebar_action`**：`chrome.sidePanel` 全部不可用；`sidebarAction.open()` 只能在 user action handler 内、且**不能在 `await` 之后**调用；「安装即开」靠 `open_at_install`，「点按钮开」靠 `action.onClicked` 内同步调用或 `_execute_sidebar_action`。侧栏宽度不能由扩展控制。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/sidebarAction/open>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/User_actions>
6. **storage 配额口径不同**：Chrome 无 `unlimitedStorage` 时 `storage.local` 5MB；Firefox 按 IndexedDB 配额（min(磁盘 10%, 10 GiB)）并且即使有 `unlimitedStorage` 仍可能撞全局磁盘配额。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/local>
7. **`storage.session.setAccessLevel` 不存在** → `storage.session` 在 Firefox 中对内容脚本不可见，需改用 `storage.local` 或消息转发。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/session>
8. **`chrome.i18n` 的 `_locales` 目录名**：语言+地区变体必须用**下划线**（如 `en_US`，不是 `en-US`）；只要存在 `_locales` 就必须提供 `default_locale`（本仓库已是 `zh_CN`，`manifest.json:5`，与目录名一致）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Internationalization>、<https://mozilla.github.io/addons-linter/>（`MISSING_DEFAULT_LOCALE` / `NO_DEFAULT_LOCALE`）
9. **快捷键可能静默失效**：`Alt+1` / `Alt+2` / `Alt+Shift+1` 若与浏览器或其它扩展冲突，handler **不会触发**（可定义但无效）；用户需到 about:addons → Manage Extension Shortcuts 改键，扩展可用 `commands.update()`（Firefox 支持程序化改键）或 `commands.openShortcutSettings()`。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/commands>
10. **`contextMenus` 不持久化**：菜单必须在 `runtime.onInstalled` 里创建（Chrome 的持久后台页会保留）；Firefox 105 及以前重启后菜单会消失，变通做法是无条件 `create` 并读 `runtime.lastError`。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/menus/create>
11. **受限页面/域名无法注入**：Firefox 中内容脚本被禁止在 `accounts.firefox.com`、`addons.mozilla.org`、`api.accounts.firefox.com`、`discovery.addons.mozilla.org`、`install.mozilla.org`、`oauth.accounts.firefox.com`、`profile.accounts.firefox.com`、`support.mozilla.org` 执行；也无法注入特权浏览器 UI 页（about:debugging、about:addons、阅读模式、view-source、PDF 查看器）与扩展页面。企业策略 `restricted_domains` 还能再加限制。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_scripts>
12. **`omnibox` 建议描述不解析 XML**：`setDefaultSuggestion`/`SuggestResult.description` 在 Firefox 里是纯文本，`<match>`/`<dim>` 会原样显示。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/omnibox/SuggestResult>
13. **`scripting.executeScript({world:'MAIN'})` 需要 FF128+**；且 `func` 不能是对象字面量/类里的方法（Firefox 直接 `SyntaxError`）；缺主机权限时 Firefox 可能「部分执行成功」而 Chrome 完全不执行。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/scripting/executeScript>、<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/scripting.json>
14. **`windows.create` 的 `focused` 参数无效**（Firefox no support）；`left/top` 在 FF108 及以前对 popup/panel 被忽略。来源：<https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/windows.json>
15. **`tabs.onReplaced` 不存在**（no support），`tabs.hide/show`、`tabs.captureTab`、`Tab.cookieStoreId` 反而是 Firefox 独有。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs/onReplaced>
16. **`chrome.*` 不用改 `browser.*`**，但反向（在 Chrome 上写 `browser.`）要等 Chrome 148/152 或上 polyfill。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API>

---

## 10. 移植所需的最低 Firefox 版本与 manifest 改动清单

### 10.1 最低版本

- **MV3 的硬底线：Firefox 109**（101–108 为 developer preview）。来源：<https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/>
- 按用到的能力上调：
  - 若保留 `storage.session` → **115+**；
  - 若需要 `scripting.executeScript({world:'MAIN'})` → **128+**；
  - 若使用 `browser_specific_settings.gecko.data_collection_permissions`（2025-11-03 后 AMO 新提交必需）→ 该 manifest 能力 Firefox 140+；
  - 若使用 CSP 的 `sandbox` 键 → 154+；
  - `preferred_environment`（可选优化）→ 136+。
- 建议在 manifest 里写 `"strict_min_version": "109.0"`（如用到 MAIN world 注入则写 `"128.0"`）。

### 10.2 改动清单（针对本仓库 `manifest.json`）

| # | 行号 | 现状 | Firefox 侧改动 |
|---|---|---|---|
| 1 | `manifest.json:6` | `minimum_chrome_version: "121"` | Chrome 专有；Firefox 会忽略（linter 通用 warning）。可保留（双目标共用一份 manifest），或在 Firefox 构建产物中删除 |
| 2 | `manifest.json:15` | `permissions` 含 `"sidePanel"` | **删除**（Firefox 无此权限，列为未支持） |
| 3 | `manifest.json:34-36` | `side_panel.default_path` | **新增** `sidebar_action`（`default_panel` = `sidepanel.html`；可选 `default_title`/`default_icon`/`open_at_install`），`side_panel` 可保留给 Chrome |
| 4 | `manifest.json:37-39` | 只有 `background.service_worker` | **新增** `background.scripts`（事件页）：`["url-utils.js", "reading-position-background.js", "background.js"]`；`service_worker` 保留给 Chrome。注意 addons-linter 要求两者配对 |
| 5 | `repo/background.js:1` | `importScripts("url-utils.js", "reading-position-background.js")` | 事件页无 `importScripts`：加 `if (typeof importScripts === "function")` 包裹（或改由 `background.scripts` 顺序加载并删除该行） |
| 6 | 新增 | — | `browser_specific_settings.gecko.id`（MV3 签名必需，形如 `lateron@<your-domain>`）+ `strict_min_version`（≥`"109.0"`）；AMO 新提交还需 `gecko.data_collection_permissions` |
| 7 | `manifest.json:40-59` | `commands` 三条 `Alt+1`/`Alt+2`/`Alt+Shift+1` | 格式合法，保留；但需实测是否被 Firefox 占用（§11-2），必要时换键或用 `commands.update()` |
| 8 | `manifest.json:67-77` | `web_accessible_resources`（`resources` + `matches`） | **无需改**（Firefox 109+ 支持该 MV3 形式）；若引入 `use_dynamic_url` 需剔除 |
| 9 | 代码层 | `chrome.sidePanel.*` 调用（若有） | 改为 `browser.sidebarAction.*`（`open()` 只能在用户手势内同步调用）；`chrome.*` 其它调用**不必改写** |
| 10 | 代码层 | 依赖 `tabs.onReplaced`、`Tab.frozen`、`windows.create({focused})` 的逻辑 | Firefox 无这些能力，需降级或删除 |
| 11 | 构建 | `scripts/build-release.py`（1 个产物） | 建议出两个 manifest 变体（Chrome 保留 `side_panel`/`sidePanel`/`minimum_chrome_version`；Firefox 删 Chrome 专有键、加 `sidebar_action`/`browser_specific_settings`），避免 linter warning 与权限冗余 |

---

## 11. 未证实 / 不确定

1. **Firefox 的 alarms 最小周期/延迟下限**：未找到权威来源。MDN `alarms.create` 只记载了 Chrome 的限制（非 unpacked 扩展最短 30 秒；传入小于 0.5 分钟按 30 秒处理并告警；Chrome 120 前该下限为 1 分钟）。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/alarms/create>
2. **`Alt+1` / `Alt+2` / `Alt+Shift+1` 是否被 Firefox 保留或与内置快捷键冲突**：未找到权威来源。support.mozilla.org 的 Firefox 键盘快捷键页未列出 Alt+数字 组合，且两种抓取方式（去标签后按正则取上下文、按行过滤）都没取到相关文本；MDN commands 页只说「被占用的组合无法覆盖、handler 不会触发」。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/commands>
3. **`tabs.Tab.frozen`**：BCD 无该条目，MDN `tabs.Tab` 全文未提 `frozen`（只有 `discarded`/`autoDiscardable`），因此「Firefox 不支持」是**推断**，未找到 Firefox 官方的明确否定表述。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs/Tab>
4. **`minimum_chrome_version` 在 addons-linter 中的确切处理**：只找到通用规则 `MANIFEST_FIELD_UNSUPPORTED`（warning）「A manifest field is not supported (or not supported for the extension manifest_version)」；没有专门针对该键的规则条目，也无法确认它是否升级为 error。来源：<https://mozilla.github.io/addons-linter/>
5. **Firefox 忽略未知 manifest 键的明文**：只找到 Chrome 侧的说法（w3c/webextensions issue #14：「Chrome's manifest validation … default behavior is to ignore unknown properties」）；Firefox 侧未找到权威表述（`runtime.getManifest()` 会「remove unsupported keys」可作旁证，但不等于加载时不报错）。来源：<https://github.com/w3c/webextensions/issues/14>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/runtime/getManifest>
6. **`scripting.executeScript` 在缺少主机权限时的确切报错文本/错误码**：未找到权威来源。文档只说明行为（Firefox/Safari 可能返回 partial results；Chrome 完全不执行），未给错误串。
7. **事件页中的 `importScripts` / `self` / `addEventListener('fetch')` 行为**：MDN 未逐条说明。本笔记的结论（`importScripts` 未定义会抛错、无 fetch 事件）基于「事件页是普通文档环境、不是 Worker/ServiceWorker 全局」这一事实推断。来源（父事实）：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Background_scripts>、<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background>
8. **`_locales` 目录名的大小写敏感性**：MDN 只规定「语言+地区变体用下划线分隔（`en_US`）」，未说明目录名大小写与 `default_locale` 不一致时 Firefox 是否报错/回退。未找到权威来源。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Internationalization>
9. **`<script src="moz-extension://…">` 注入网页是否被页面 CSP 拦截**：MDN 只有一般性划分（Firefox 中「most DOM-based APIs are subjected to the CSP of the web page」），没有这一具体场景的明文，属推断。来源：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy>
10. **Firefox MV3 下 `chrome.*` 是否对「所有」异步 API 返回 Promise**：Extension Workshop 只给出一句总述（「In Manifest V3, Firefox supports promises for asynchronous events in the `chrome.*` namespace」），没有逐 API 例外清单。按此总述，回调式代码在 Firefox 仍可用，但「哪些 API 在 `chrome.*` 下没有 Promise」未能核实。来源：<https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/>
11. **`data_collection_permissions` 的 linter 规则自相矛盾**：规则表里同时有 `MISSING_DATA_COLLECTION_PERMISSIONS`（warning：「新扩展必须提供，未来新版也强制」）与 `DATA_COLLECTION_PERMISSIONS_PROP_RESERVED`（**error**：「reserved for future usage and cannot be used … at the moment」）。两处表述冲突，无法判断最终该不该写这个键。来源：<https://mozilla.github.io/addons-linter/>
12. **Firefox 126 及以前的 MV3 主机权限到底「不显示」还是「不显示也不授予」**：MDN 只写「weren't displayed in the install prompt」；Extension Workshop 写「既不显示也不授予」。两者不完全一致，本笔记在 §5 中并列了两处说法。
13. **Firefox 是否有与 Chrome `sidePanel.setPanelBehavior` 等价的「点图标自动开侧栏」API**：未找到权威来源。已核实的替代手段是 `open_at_install` 与 `_execute_sidebar_action` 特殊快捷键；「侧栏宽度只能由用户拖拽」也是基于「文档中不存在宽度 API」的推断。
14. **`permissions.request()` 从侧栏文档调用的现状**：BCD 只记「FF101 之前无法从 sidebar 文档请求（bug 1493396）」，未说明之后是否完全修复（当前 FF157 应已可用，但未找到明文确认）。
15. **Chrome 侧 `background.scripts` 被忽略的起点**：MDN 说 Chrome 121 之前会拒绝加载 MV3 扩展、121 起忽略；本仓库 `minimum_chrome_version: "121"` 恰好落在边界上，Edge 对应版本未核实。
