# LaterOn · Firefox 适配版（非官方移植）

LaterOn 是一个「项目型网页管理」扩展：把浏览到的网页按项目收进侧栏库、读正文、记阅读位置、按项目分组。
本仓库是它的 **Firefox（Manifest V3）适配移植版**，基于上游公开版本 v1.66.1 改造。

| | |
|---|---|
| 本版基线 | LaterOn **v1.66.1**（上游 commit `00fde27be93656d650ac5c52adc2684d511adb53`） |
| 本版形态 | 未签名 XPI（WebExtension，Manifest V3，`strict_min_version: 115.0`） |
| 适配方式 | 用独立清单 `manifest.firefox.json` + 一个转接垫片 `ff-sidebar.js`，**不改 `background.js` 业务逻辑** |
| 移植前基线 | 原版测试 51/53 通过（2 个上游既有失败，见下）；addons-linter **0 error / 7 warning** |
| 已实测 | Firefox 157.0.1 真实装载（无头 `web-ext run`）：后台页与 3 个扩展页全部无 JS 报错 |

---

## ⚠️ 来源与授权（请先读）

- **上游项目**：<https://github.com/gaoyiiiii/LaterOn>（LaterOn，作者 gaoyiiiii）
- **本版基线**：上游 **v1.66.1**，commit `00fde27be93656d650ac5c52adc2684d511adb53`（branch `main`）
- **上游没有 LICENSE 文件**，GitHub 上的 license 字段为 `null`（即默认「保留所有权利」，未授予任何开源许可）。
- 因此：**本仓库是非官方个人移植，未获上游作者授权**，版权归上游作者。本仓库仅用于个人学习与自用；请勿商业使用、请勿再分发。若上游作者提出异议，本仓库将立即下架或转为私有。
- 本仓库**不是**上游官方仓库，也**不是** GitHub Fork 关系（虽然保留了上游的提交历史，方便逐行对照；网络图上不会显示 fork 关系）。
- 本仓库不含上游 `.git` 之外的任何第三方代码；运行时代码全部来自上游 v1.66.1。

---

## 与原版的差异

一句话：**运行时逻辑一致，只做「浏览器 API 与清单」层面的适配**。业务功能、界面、存储结构、i18n 文案键位全部保持原样，因此两版可以共用同一份用户数据。

### 差异总览

- **改动 8 个既有文件**，新增 6 项（`ff-sidebar.js`、`manifest.firefox.json`、`package.json`、`package-lock.json`、`README.upstream.md`、`port-docs/`）。
- **`background.js` 一个字节都没改**（上游最大的文件，1706 行）——Firefox 侧的兼容靠垫片在运行前注入，而不是改业务代码。
- 逐行差异可随时复查：

  ```bash
  git diff v1.66.1 HEAD -- . ':(exclude)port-docs'
  ```

### 逐文件差异

| 文件 | 改了什么 | 为什么 |
|---|---|---|
| `ff-sidebar.js` | **新增**。转接垫片（约 6.5 KB）：`importScripts` 空实现、`LaterOnSidePanel`（`isFirefoxSidebar` / `canOpen` / `canClose` / `setPanelBehavior` / `open` / `close`）、Firefox 下用 `action.onClicked` 开侧栏 | Firefox 没有 `chrome.sidePanel`；上游用 `sidePanel` 开合侧栏是唯一的强依赖。垫片把 Chrome 的 `sidePanel` 语义映射到 `sidebarAction`，让上层代码无需感知浏览器 |
| `manifest.firefox.json` | **新增**。Firefox 专用清单（构建时改名为 `manifest.json` 打进去） | 两版清单结构差异太大，用「一份源码、两份清单」而不是「一份清单塞满分支」 |
| `sidepanel.html` | 顶部插入 `<script src="ff-sidebar.js"></script>` | 垫片必须先于业务脚本执行 |
| `library.html` | 同上 | 同上 |
| `settings.html` | 同上；快捷键说明改为浏览器中立措辞 | 同上；且 Firefox 版移除了 `toggle-translation` 快捷键 |
| `library.js` | ① 顶部加垫片兜底（忠实转发，不改变 Chrome 行为，`canOpen` / `canClose` 用 getter）；② `openItem` 里做手势预热；③ `openSidePanel(windowId, earlyPanelOpen)` 支持「已提前打开」的分支 | Firefox 的 `sidebarAction.open()` 必须在用户手势的同步调用链里发起，而上游是在 `await` 之后才调用 → 需要在点击回调里提前把侧栏打开 |
| `sidepanel.js` | 关闭侧栏、跨窗口打开侧栏的路径改走垫片；保留 Chrome 原行为 | 同上 |
| `settings.js` / `i18n.js` | 内置翻译（Chrome 的 `Translator` / `LanguageDetector`）在缺 API 时**降级隐藏**而不是报错；文案改为浏览器中立 | Firefox 没有 Chrome 内置翻译 API |
| `scripts/build-release.py` | 加 `--target {chrome,firefox}`；Firefox 目标校验 Firefox 清单键 | 一个脚本出两种包，且拒绝把 Chrome 键打进 Firefox 包 |

### 清单（manifest）差异

| | 原版（Chrome） | 本版（Firefox） |
|---|---|---|
| `background` | `service_worker: "background.js"` | `scripts: [ff-sidebar.js, url-utils.js, reading-position-background.js, background.js]`（**不保留 `service_worker`**，否则 linter 直接报 `BACKGROUND_SERVICE_WORKER_NOFALLBACK` 错误） |
| 侧栏 | `side_panel.default_path` + `permissions: ["sidePanel"]` | `sidebar_action.default_panel`（`permissions` 里去掉 `sidePanel`） |
| 选项页 | `options_page: "settings.html"` | `options_ui: {page, open_in_tab: true}`（`options_page` 需要 Firefox 126+，`options_ui` 在 115 就能用） |
| 最低版本 | `minimum_chrome_version: "121"` | 删除；改用 `browser_specific_settings.gecko.strict_min_version: "115.0"` + 固定 add-on ID |
| 快捷键 | `quick-save` / `toggle-translation` / `save-all-tabs` | 去掉 `toggle-translation`（翻译功能在 Firefox 降级） |
| 数据收集声明 | 无 | 无（**尚未加** `data_collection_permissions`；这是 AMO 签名提交的硬性要求，自签名/临时装载不受影响） |

> `sidebar_action`、`commands`（`Alt+1` / `Alt+Shift+1`）、`omnibox`、`web_accessible_resources`、`_locales` 在 addons-linter 下零告警。

### 已知限制（未实测项）

1. Firefox 侧栏内调用 `sidebarAction.close()` 的行为（上游「面板内关闭」路径的替代表述）。
2. 侧栏在 Firefox 下的默认宽度与 620px 断点、顶栏 58px 兜底高度的实际观感。
3. `Alt+1` / `Alt+Shift+1` 与系统或浏览器既有快捷键的冲突情况。
4. `contextMenus` 的 `"action"` 上下文在 Firefox 中的呈现（Firefox 上可能表现为工具栏按钮菜单）。
5. Trusted Types 站点上 `innerHTML` 的 4 处告警（上游既有代码，非本次引入）。
6. Firefox MV3 后台是**会被唤醒、回收的事件页**：上游 `background.js` 有若干纯内存集合（如已注入 CSS 的标签页集合），事件页被回收后可能重复注入。本版未改业务逻辑，建议后续单独改成 `storage.session`。
7. 正式版 Firefox 永久安装需要 AMO 签名（见下）。

---

## 安装

### 方式一：临时装载（最快，适合自用试用）

1. 解压 `LaterOn-1.66.1-firefox.xpi`（它就是个 ZIP）到一个**空目录**，例如 `D:\LaterOn-ff`；
2. Firefox 地址栏打开 `about:debugging#/runtime/this-firefox`；
3. 点 **「临时载入附加组件…」** → 选中刚解压目录里的 **`manifest.json`**；
4. 看到 `LaterOn` 出现即成功；在工具栏点扩展图标即可打开侧栏（首次可能需要在扩展菜单里固定图标）。

> 临时载入的特性：**重启 Firefox 就消失**，每次重启都要重新载入；不影响观看，但也不适合长期用。`about:debugging` 里可以点「重新载入」快速应用新版。

### 方式二：永久安装（Firefox Developer Edition / ESR，关闭签名校验）

1. 地址栏打开 `about:config`，接受风险提示；
2. 把 `xpinstall.signatures.required` 改为 `false`；
3. 把 `LaterOn-1.66.1-firefox.xpi` 拖进 Firefox（或 `about:addons` → 齿轮 → 从文件安装附加组件）；
4. 重启后仍在。

> ⚠️ 仅 **Developer Edition / ESR / Nightly** 允许关闭签名校验。**Firefox 正式版（Release/Beta）即使改了 `xpinstall.signatures.required` 也会拒绝安装未签名 XPI**。

### 方式三：正式版永久安装（需要 AMO 签名）

正式版只认 Mozilla 签名的包，两条路（都需要 Mozilla 账号，且**必须开启 2FA**）：

- **网页**：<https://addons.mozilla.org/developers/> → 提交新附加组件 → 选 **「On your own / 自托管（unlisted）」** → 上传 `.xpi` → 下载签名的 `.xpi`；
- **命令行**：

  ```bash
  npx web-ext sign -s <解包后的36文件目录> -a web-ext-artifacts \
      --channel unlisted --api-key <KEY> --api-secret <SECRET>
  ```

  注意 `-s` 必须指向**解包后的干净目录**（36 个文件），不要指向仓库根目录，否则 `node_modules` 会被一起打包。

  另外，**2025-11-03 起 AMO 拒绝没有声明 `browser_specific_settings.gecko.data_collection_permissions` 的新扩展** —— 届时需在 `manifest.firefox.json` 的 `browser_specific_settings.gecko` 里加上：

  ```json
  "data_collection_permissions": { "required": ["none"] }
  ```

  （LaterOn 不上传任何用户数据，故为 `none`。加上后本机 addons-linter 结果仍是 0 error，只多一条「该键需要 Firefox 140+」的提示。）

---

## 构建与测试

需要 Node.js（≥ 18）与 Python 3。

```bash
npm install                 # 只为测试/lint 工具链（jsdom、web-ext、addons-linter）；扩展本身零依赖

# 跑上游自带的 53 个测试（每个都是独立 Node 脚本）
node tests/<name>.test.js

# 打两种包 → dist/
python scripts/build-release.py --target firefox   # dist/LaterOn-1.66.1-firefox.zip（= .xpi）
python scripts/build-release.py --target chrome    # dist/LaterOn-1.66.1.zip

# 静态检查 / 真机装载
npx addons-linter dist/LaterOn-1.66.1-firefox.zip
npx web-ext run --source-dir <解包目录> --firefox <firefox 可执行文件> --args=-headless
```

**基线（上游 v1.66.1，未移植前）**：53 个测试 51 通过、2 个失败：
`tests/background-modules.test.js`（上游自带的「`background.js` 体积 < 80000 字节」守卫，而它自己有 81138 字节）与 `tests/edit-item.test.js`（「编辑后立刻重画卡片」一项）。这两个失败**上游原本就有**，本版原样保留未修。

**本版结果**：测试仍为 **51/53（与基线逐项一致）**；`addons-linter` **0 error / 7 warning**（1 条缺数据收集声明 + 4 条上游既有 `innerHTML` + 2 条 `sidePanel.setPanelBehavior` 的已知残留，原始 JSON 见 `port-docs/lint-firefox-final.json`）。

---

## 目录结构

```
.
├── manifest.json              # Chrome 清单（原样保留，打 Chrome 包时用）
├── manifest.firefox.json      # Firefox 清单（打 Firefox 包时改名为 manifest.json）
├── ff-sidebar.js              # ★ 唯一的 Firefox 专有运行时文件：sidePanel → sidebarAction 垫片
├── background.js              # 事件/后台页（未改）
├── sidepanel.html/.css/.js    # 侧栏界面（HTML/JS 有适配改动）
├── library.html/.css/.js      # 库界面（HTML/JS 有适配改动）
├── settings.html/.css/.js     # 选项页（有适配改动）
├── i18n.js                    # 文案（翻译降级改动）
├── content-*.js, dialog.js, picker-ui.js, theme.js, boot.js, url-utils.js, tab-navigation.js
├── _locales/{en,zh_CN}/       # i18n 资源
├── docs/                      # 上游自带截图资源
├── scripts/build-release.py   # 打包脚本（新增 --target）
├── tests/                     # 上游自带 53 个测试
├── port-docs/                 # ★ 移植文档与实测证据（见下）
├── README.upstream.md         # 上游原 README（原样保留）
└── package.json               # 仅测试/lint 工具链
```

### port-docs/（移植文档与证据）

| 文件 | 内容 |
|---|---|
| `Firefox-适配技术方案.md` | **施工级技术方案**（3300+ 行）：可行性论证、逐文件改动设计、12 个清单变体的 addons-linter 实测矩阵、验收清单、附录 F 施工实测记录 |
| `Firefox-适配方案.md` | 早期可行性分析（工作量与风险清单） |
| `LaterOn-项目分析.md` | 上游项目结构/架构分析 |
| `notes-background.md`、`notes-content-scripts.md`、`notes-ui.md`、`notes-firefox-platform.md` | 上游源码阅读笔记 + Firefox 平台差异考证（逐条引用 MDN / BCD / Extension Workshop） |
| `lint-firefox-final.json` | 本版 XPI 的 addons-linter 原始输出 |
| `baseline-before.csv`、`baseline-after.csv`、`baseline-before-failures.txt` | 移植前/后的 53 项测试逐项结果对照 |

> 文档路径映射：方案与笔记里写的 `repo/` = 上游原版快照（本仓库不含，可用 `git checkout v1.66.1` 得到），`work/` = 本仓库根目录。

---

## 版本与更新

- 上游 CHANGELOG 原样保留在 [`CHANGELOG.md`](CHANGELOG.md)；上游 README 保留在 [`README.upstream.md`](README.upstream.md)。
- 本移植版号沿用上游：`1.66.1`。二进制工件见本仓库 **Releases**。
