# LaterOn · Firefox 适配版（非官方移植）

LaterOn 是一个「项目型网页管理」扩展：把浏览到的网页按项目收进侧栏库、读正文、记阅读位置、按项目分组。
本仓库是它的 **Firefox（Manifest V3）适配移植版**，基于上游公开版本 v1.66.1 改造。

| | |
|---|---|
| 本版基线 | LaterOn **v1.66.1**（上游 commit `00fde27be93656d650ac5c52adc2684d511adb53`）+ 上游 **`a1a5313`**（2026-10-12 采纳 MIT、打包含 LICENSE，已 merge 进本仓库） |
| 本版形态 | 未签名 XPI（WebExtension，Manifest V3），两个变体：**日常版** `strict_min_version: 115.0`；**AMO 签名版** `strict_min_version: 140.0` + `data_collection_permissions: {"required": ["none"]}` |
| 适配方式 | 用独立清单 `manifest.firefox.json` + 一个转接垫片 `ff-sidebar.js`，**不改 `background.js` 业务逻辑** |
| 移植前基线 | 原版测试 51/53 通过（2 个上游既有失败，见下）；addons-linter **0 error / 7 warning** |
| 已实测 | Firefox 157.0.1 真实装载（无头 `web-ext run`）：后台页与 3 个扩展页全部无 JS 报错；两个变体都过 addons-linter **0 error / 7 warning** |
| 仍需人工 | 7 项必须在有头浏览器里点一遍，逐条脚本见 [`port-docs/UI-人工点验清单.md`](port-docs/UI-人工点验清单.md) |

---

## 来源与授权（请先读）

- **上游项目**：<https://github.com/gaoyiiiii/LaterOn>（LaterOn，作者 gaoyiiiii，提交署名 yi <yi@jueji.me>）
- **本版基线**：上游 **v1.66.1**（commit `00fde27be93656d650ac5c52adc2684d511adb53`）+ 上游 license 提交 **`a1a5313`**（2026-10-12，其父提交就是 v1.66.1）
- **上游已采用 MIT 协议**：2026-10-12 上游推送 `a1a5313`「License LaterOn under MIT and include notice in release packages」，新增根目录 `LICENSE`（MIT，`Copyright (c) 2026 yiiiii`）、在 README 增加「开源协议」章节、并让打包脚本把 `LICENSE` 放进每个发行包。GitHub API 现在返回 `license.spdx_id = "MIT"`（此前为 `null`）。
- **本仓库已合并该提交**（merge commit `36f01c9`，用 merge 而非 rebase，见仓库 git 历史）：根目录 `LICENSE` 与上游**逐字节一致**，`scripts/build-release.py` 也已把 `LICENSE` 列为发行包必需文件 —— 三个产物均含 `LICENSE`。
- **上游明确欢迎社区移植**：其 README「开源协议」章节写明允许使用、修改、移植、再发布及商业使用，同时要求**注明原项目与修改内容、区分社区版与官方版**。本仓库正是照此做的。但它**不是**上游官方仓库，也**不是** GitHub Fork 关系（保留了上游提交历史便于逐行对照，网络图上不显示 fork 关系）。
- 本仓库的移植改动同样以 **MIT** 发布（见根目录 [`LICENSE`](LICENSE)）。MIT 不授予商标权，`LaterOn` 名称与图标权利仍属上游；`tests/fixtures/` 中的第三方网页内容仍归原权利人，不因 MIT 获得额外授权。
- 本仓库不含上游之外的任何第三方运行时代码。

---

## 与原版的差异

一句话：**运行时逻辑一致，只做「浏览器 API 与清单」层面的适配**。业务功能、界面、存储结构、i18n 文案键位全部保持原样，因此两版可以共用同一份用户数据。

### 差异总览

- **改动 8 个既有文件**，新增 7 项（`ff-sidebar.js`、`manifest.firefox.json`、`package.json`、`package-lock.json`、`README.upstream.md`、`port-docs/`、`LICENSE` —— `LICENSE` 来自上游 `a1a5313`，不是本次移植写的）。
- **移植代码改动面**（对当前上游 `a1a5313`，不含对外 README 与工具链）：**10 文件 / +509 −44**，其中新增 2 个文件（`ff-sidebar.js` 127 行、`manifest.firefox.json` 92 行）。**`background.js` 一个字节都没改**（上游最大的文件，1706 行）——Firefox 侧的兼容靠垫片在运行前注入，而不是改业务代码。
- 逐行差异可随时复查（`a1a5313` = 当前上游 HEAD，含 MIT 协议提交；`v1.66.1` 是移植前的基线 tag）：

  ```bash
  git diff a1a5313 HEAD -- . ':(exclude)port-docs'    # 相对当前上游的全部差异
  git diff v1.66.1 HEAD -- . ':(exclude)port-docs'    # 相对移植前基线（含上游 LICENSE 提交）
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
| `scripts/build-release.py` | 加 `--target {chrome,firefox}` + `--amo`；Firefox 目标校验 Firefox 清单键；`RUNTIME_FILES` 首位加入 `"LICENSE"` | 一个脚本出两种包，且拒绝把 Chrome 键打进 Firefox 包；MIT 要求分发时携带协议全文 |
| `LICENSE` | **来自上游**（`git merge a1a5313`，非本次移植所写）；构建时进包 | 上游 2026-10-12 采纳 MIT，分发衍生版必须保留版权声明与协议全文 |

### 清单（manifest）差异

| | 原版（Chrome） | 本版（Firefox） |
|---|---|---|
| `background` | `service_worker: "background.js"` | `scripts: [ff-sidebar.js, url-utils.js, reading-position-background.js, background.js]`（**不保留 `service_worker`**，否则 linter 直接报 `BACKGROUND_SERVICE_WORKER_NOFALLBACK` 错误） |
| 侧栏 | `side_panel.default_path` + `permissions: ["sidePanel"]` | `sidebar_action.default_panel`（`permissions` 里去掉 `sidePanel`） |
| 选项页 | `options_page: "settings.html"` | `options_ui: {page, open_in_tab: true}`（`options_page` 需要 Firefox 126+，`options_ui` 在 115 就能用） |
| 最低版本 | `minimum_chrome_version: "121"` | 删除；改用 `browser_specific_settings.gecko.strict_min_version: "115.0"` + 固定 add-on ID |
| 快捷键 | `quick-save` / `toggle-translation` / `save-all-tabs` | 去掉 `toggle-translation`（翻译功能在 Firefox 降级） |
| 数据收集声明 | 无 | **日常构建不带**（`strict_min_version: 115.0`）；**AMO 签名构建带** `"data_collection_permissions": {"required": ["none"]}` 并把 `strict_min_version` 抬到 `140.0`（该键只有 Firefox 140+ 认，详下「方式三」） |

> `sidebar_action`、`commands`（`Alt+1` / `Alt+Shift+1`）、`omnibox`、`web_accessible_resources`、`_locales` 在 addons-linter 下零告警。

### 已知限制（未实测项）

1. Firefox 侧栏内调用 `sidebarAction.close()` 的行为（上游「面板内关闭」路径的替代表述）。
2. 侧栏在 Firefox 下的默认宽度与 620px 断点、顶栏 58px 兜底高度的实际观感。
3. `Alt+1` / `Alt+Shift+1` 与系统或浏览器既有快捷键的冲突情况。
4. `contextMenus` 的 `"action"` 上下文在 Firefox 中的呈现（Firefox 上可能表现为工具栏按钮菜单）。
5. Trusted Types 站点上 `innerHTML` 的 4 处告警（上游既有代码，非本次引入）。
6. Firefox MV3 后台是**会被唤醒、回收的事件页**：上游 `background.js` 有若干纯内存集合（如已注入 CSS 的标签页集合），事件页被回收后可能重复注入。本版未改业务逻辑，建议后续单独改成 `storage.session`。
7. 正式版 Firefox 永久安装需要 AMO 签名（见「安装 · 方式三」，签名专用包已内置可一键产出）。

> 上面 1–7 项**不是"还没查"，而是"无头环境查不了"**：它们要么取决于真实的侧栏宽度与渲染，要么取决于真人点击产生的手势与系统级上下文。逐条操作步骤、代码行号、通过判据与记录模板见 [`port-docs/UI-人工点验清单.md`](port-docs/UI-人工点验清单.md)。

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

正式版只认 Mozilla 签名的包。**不需要手改清单** —— 本仓库的打包脚本已经能直接产出「签名专用包」`dist/LaterOn-1.66.1-firefox-amo.zip`（= Release 附件 `LaterOn-1.66.1-firefox-amo.xpi`，498812 字节，37 文件，含上游 `LICENSE`），它已声明 `"data_collection_permissions": {"required": ["none"]}` 并把 `strict_min_version` 设为 `140.0`：

```bash
python scripts/build-release.py --target firefox --amo   # → dist/LaterOn-1.66.1-firefox-amo.zip
```

> 为什么不把 dcp 直接写进 `manifest.firefox.json`？因为该键**只有 Firefox 140+ 才认**，写进主清单就必须放弃 Firefox 115–139 的用户。所以采用「一份源码、两个产物」：日常版保 115，签名版走 140。

两条签名路线（都需要 Mozilla 账号，且**必须开启 2FA**）：

- **网页**：<https://addons.mozilla.org/developers/> → 提交新附加组件 → 选 **「On your own / 自托管（unlisted）」** → 上传 `LaterOn-1.66.1-firefox-amo.xpi` → 下载签名的 `.xpi`；
- **命令行**（把 `-s` 指向**解包后的 37 文件干净目录**，不要指向仓库根目录，否则 `node_modules` 会被一起打包）：

  ```bash
  unzip -o dist/LaterOn-1.66.1-firefox-amo.zip -d /tmp/lateron-amo
  npx web-ext sign -s /tmp/lateron-amo -a dist/signed \
      --channel unlisted --api-key <KEY> --api-secret <SECRET>
  ```

  成功后 `dist/signed/` 里会出现已签名的 `.xpi`，可直接在正式版 Firefox 永久安装。扩展 ID 固定为 `lateron-ff-port-695d5826@lhy.local`，**签名后不可更改**。

签名前建议先自查：`npx addons-linter dist/LaterOn-1.66.1-firefox-amo.zip` 应为 **0 error / 7 warning**（那 7 条见下「构建与测试」）。

---

## 构建与测试

需要 Node.js（≥ 18）与 Python 3。

```bash
npm install                 # 只为测试/lint 工具链（jsdom、web-ext、addons-linter）；扩展本身零依赖

# 跑上游自带的 53 个测试（每个都是独立 Node 脚本）
node tests/<name>.test.js

# 打两种包 → dist/
python scripts/build-release.py                            # dist/LaterOn-1.66.1.zip（Chrome，默认）
python scripts/build-release.py --target firefox           # dist/LaterOn-1.66.1-firefox.zip（= .xpi，min 115）
python scripts/build-release.py --target firefox --amo     # dist/LaterOn-1.66.1-firefox-amo.zip（min 140 + dcp，签名用）

# 静态检查 / 真机装载
npx addons-linter dist/LaterOn-1.66.1-firefox.zip
npx web-ext run --source-dir <解包目录> --firefox <firefox 可执行文件> --args=-headless
```

`--amo` 会走两道额外闸门（缺 `data_collection_permissions`、`strict_min_version < 140.0`、或清单里混入 `side_panel` 等 Chrome 专有键，都会直接构建失败），构建完还会回读归档里的 `manifest.json` 打印 `gecko.id / strict_min_version / data_collection_permissions`。

**基线（上游 v1.66.1，未移植前）**：53 个测试 51 通过、2 个失败：
`tests/background-modules.test.js`（上游自带的「`background.js` 体积 < 80000 字节」守卫，而它自己有 81138 字节）与 `tests/edit-item.test.js`（「编辑后立刻重画卡片」一项）。这两个失败**上游原本就有**，本版原样保留未修。

**本版结果**：测试仍为 **51/53（与基线逐项一致，逐项结果见 `port-docs/baseline-amo.csv`）**；

`addons-linter` 两个变体都是 **0 error / 7 warning**：

| 变体 | 7 条 warning 是什么 | 原始报告 |
|---|---|---|
| 日常版（min 115） | 1 条未声明数据收集 + 4 条上游既有 `innerHTML`（`content-reading-position.js:124`、`dialog.js:117`、`dialog.js:534`、`picker-ui.js:94`）+ 2 条 `sidePanel.setPanelBehavior` 残留（`background.js:266`、`:268`） | `port-docs/lint-firefox-115.json` |
| AMO 版（min 140 + dcp） | 未声明数据收集 → 换成 1 条「Android 不支持」（`sidebar_action` 是桌面专有，如实标注）+ 同样 6 条 | `port-docs/lint-firefox-amo.json` |

---

## 目录结构

```
.
├── LICENSE                    # 上游 MIT 协议全文（来自上游 a1a5313，随每个发行包分发）
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
├── scripts/build-release.py   # 打包脚本（--target {chrome,firefox} + --amo）
├── tests/                     # 上游自带 53 个测试
├── port-docs/                 # ★ 移植文档与实测证据（见下）
├── README.upstream.md         # 上游原 README（原样保留）
└── package.json               # 仅测试/lint 工具链
```

### port-docs/（移植文档与证据）

| 文件 | 内容 |
|---|---|
| `Firefox-适配技术方案.md` | **施工级技术方案**（3496 行）：可行性论证、逐文件改动设计、12 个清单变体的 addons-linter 实测矩阵、验收清单、附录 **F** 施工实测记录、附录 **G** AMO 签名版（dcp）实现与签名两条路线 |
| `UI-人工点验清单.md` | **有头人工点验的操作脚本**：附录 F.6 那 7 项逐条给出「为什么无头测不了 / 代码位置 / 操作 / 通过判据 / 失败特征 / 记录字段」，含前置命令与记录模板 |
| `Firefox-适配方案.md` | 早期可行性分析（工作量与风险清单） |
| `LaterOn-项目分析.md` | 上游项目结构/架构分析 |
| `notes-background.md`、`notes-content-scripts.md`、`notes-ui.md`、`notes-firefox-platform.md` | 上游源码阅读笔记 + Firefox 平台差异考证（逐条引用 MDN / BCD / Extension Workshop） |
| `lint-firefox-final.json`、`lint-firefox-115.json`、`lint-firefox-amo.json` | addons-linter 原始输出（移植完成时 / 日常版 / AMO 签名版） |
| `baseline-before.csv`、`baseline-after.csv`、`baseline-amo.csv`、`baseline-before-failures.txt` | 移植前 / 移植后 / 加 `--amo` 后的 53 项测试逐项结果对照 |

> 文档路径映射：方案与笔记里写的 `repo/` = 上游原版快照（本仓库不含，可用 `git checkout v1.66.1` 得到），`work/` = 本仓库根目录。

---

## 版本与更新

- 上游 CHANGELOG 原样保留在 [`CHANGELOG.md`](CHANGELOG.md)；上游 README 保留在 [`README.upstream.md`](README.upstream.md)。
- 本移植版号沿用上游：`1.66.1`。二进制工件见本仓库 **Releases**。
