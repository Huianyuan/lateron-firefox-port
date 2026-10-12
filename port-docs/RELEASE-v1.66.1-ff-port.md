# Release v1.66.1-ff-port · LaterOn Firefox 适配版

## 怎么装（先看这张表）

| 你的 Firefox | 下哪个附件 | 步骤 |
|---|---|---|
| **140 及以上**（正式版 / Beta / ESR） | **`LaterOn-1.66.1-firefox-amo.xpi`**（**AMO 已签名**，518829 B） | ① 下载（**不要解压**）② `about:addons` → 齿轮 ⚙ → 「从文件安装附加组件…」 ③ 确认权限与「不收集任何数据」提示 → **永久生效，重启仍在** |
| **115–139** | `LaterOn-1.66.1-firefox.xpi`（未签名，498891 B） | ① 解压到空目录 ② `about:debugging#/runtime/this-firefox` → 「临时载入附加组件…」 ③ 选目录里的 `manifest.json`（**重启失效**） |
| Nightly / Developer Edition / ESR | `LaterOn-1.66.1-firefox.xpi` | `about:config` → `xpinstall.signatures.required = false` → 拖入安装 |

> 用起来：点工具栏 LaterOn 图标 → 右侧打开侧栏 → 把当前页按项目收进库。**`.xpi` 就是一个 ZIP**，签名包的签名块在 `META-INF/mozilla.rsa`，改一个字节即失效，所以别解压着装。

> **2026-10-13 更新**：`LaterOn-1.66.1-firefox-amo.xpi` 已由 **AMO 签名（unlisted）**，包内带 `META-INF/mozilla.rsa`，**正式版 Firefox 可以「下载即永久安装」**；另一个 `LaterOn-1.66.1-firefox.xpi` 仍为未签名临时载入版。

基于上游 **LaterOn v1.66.1**（commit `00fde27be93656d650ac5c52adc2684d511adb53`）+ 上游 **`a1a5313`**（2026-10-12 采纳 MIT 协议、并在发行包里带上 `LICENSE`）的 Firefox（Manifest V3）社区移植版。
**上游已采用 [MIT License](https://github.com/gaoyiiiii/LaterOn/blob/main/LICENSE)**（`Copyright (c) 2026 yiiiii`），本仓库同样以 MIT 发布：两个包内都已包含 `LICENSE`，再分发时请保留该文件与版权声明，并注明这是基于 LaterOn 的**非官方社区移植版**（上游 README 的明文要求）。

## 附件（两个包，按用途选一个）

| 文件 | 用途 | 大小 | 最低 Firefox | 文件数 | SHA-256 |
|---|---|---|---|---|---|
| `LaterOn-1.66.1-firefox.xpi` | **日常临时载入**：`about:debugging` 载入，重启即失效 | 498891 字节 | 115 | 37 | `CFE6333D43398E424CCABE57CAF42D2458F9D107D64BE971E182038EC0F49F5F` |
| `LaterOn-1.66.1-firefox-amo.xpi` | **AMO 已签名**：正式版**下载即永久安装** | 518829 字节 | 140 | 42 | `E154AC5A67B6F1123BB2473387C5CACC1C2115CE4539B2C0B05A81CAE8277524` |

- 签名包比未签名包多 5 个文件（`META-INF/`：`manifest.mf`、`mozilla.sf`、`mozilla.rsa`、`cose.manifest`、`cose.sig`），其余 37 个文件与 AMO 版一致；`META-INF/mozilla.rsa` 就是签名块。
- 除 `manifest.json` 里的 `strict_min_version`（115 / 140）与 `data_collection_permissions` 外，两个包内容相同；扩展显示名为 **`LaterOn 社区移植版 · 项目型网页管理`**（英文界面 `LaterOn Community Port · Project Web Manager`），与上游官方版区分。
- **未签名输入包**（重新签名时才需要）保留在仓库里：`dist/LaterOn-1.66.1-firefox-amo-unsigned.xpi`（498924 字节 / `4B2674AAC5DB40225E7AEFCF3531CE18292BB82E11E0F5034793A509A3BDF8B6`），不进 Release。

> 2026-10-12 两轮重打包：① 因上游改为 MIT 协议（提交 `a1a5313`）加 `LICENSE`，文件数 36 → 37；② 因**改名**（提交 `bd64e7d`，第八棒）内容变化。两次都**替换**了附件，**旧的大小与哈希全部作废**（含 498779 / `C826F4F4…19C8`、498812 / `6DCA6DEC…9C9E`）。
>
> 2026-10-13 签名：`LaterOn-1.66.1-firefox-amo.xpi` 换成 AMO 回签的包（498924 → 518829），未签名原件另存为 `…-amo-unsigned.xpi`；`LaterOn-1.66.1-firefox.xpi` **未变**（498891）。

> `.xpi` 就是一个 ZIP，可以直接解压查看内容；`manifest.json` 里能看到 Firefox 专用键（`sidebar_action`、`browser_specific_settings.gecko`）。

## 临时使用方法（推荐，无需签名）

**准备**：Firefox 115 及以上（实测 157.0.1）；把 `LaterOn-1.66.1-firefox.xpi` 下载到本机。

1. 把 `.xpi` **解压到一个空目录**（右键 → 解压到 `LaterOn-ff\`）。解压后目录里应当直接看到 `manifest.json`，**不要**多一层文件夹。
2. Firefox 地址栏输入 `about:debugging#/runtime/this-firefox` 回车。
3. 点 **「临时载入附加组件…」**（Load Temporary Add-on…）。
4. 在弹出的文件选择框里，进入刚才的解压目录，选中 **`manifest.json`** 并打开。
5. 列表里出现 `LaterOn 社区移植版 · 项目型网页管理`（ID `lateron-ff-port-695d5826@lhy.local`）即装载成功。
6. 点工具栏的 LaterOn 图标 → 右侧弹出侧栏即为正常（若图标没显示，点扩展菜单的拼图图标把 LaterOn 固定到工具栏）。
7. 验证通过后，可以打开 `about:addons` → 扩展 → LaterOn 查看权限与选项页。

**注意**：临时载入的扩展 **重启 Firefox 后会消失**，需要重新执行一遍第 2–5 步。这是 Firefox 的设计，不是扩展的问题。

## 永久安装

**正式版 Firefox（Release/Beta，强制签名校验）——用已签名的 `LaterOn-1.66.1-firefox-amo.xpi`：**

1. 下载 `LaterOn-1.66.1-firefox-amo.xpi`（**不要解压**，签名绑定在包上，改一个字节就失效）。
2. 地址栏输入 `about:addons` → 右上角齿轮 ⚙ → **「从文件安装附加组件…」** → 选中该 `.xpi`。
3. 出现权限与数据收集提示（本扩展声明 **不收集任何数据**）→ 确认安装。
4. 安装后是**永久生效**的，重启 Firefox 不会消失；卸载走 `about:addons`。

**要求 Firefox 140 及以上**：这个包声明了 `data_collection_permissions`（AMO 自 2025-11-03 起对新扩展的强制要求），而该键只有 Firefox 140+ 认；**115–139 的用户请用另一个包走下面的临时载入路线**。

**Developer Edition / Nightly / ESR**：`about:config` 里把 `xpinstall.signatures.required` 设为 `false`，之后未签名包也能装（正式版不支持这条路）。

**临时载入（任意版本，重启失效）**：用 `LaterOn-1.66.1-firefox.xpi`，见上一节。

**重新签名（版本更新时）**：用 `dist/LaterOn-1.66.1-firefox-amo-unsigned.xpi` 或 `python312 scripts/build-release.py --target firefox --amo` 重新构建，再按 [`port-docs/AMO签名操作指南.md`](./AMO签名操作指南.md) 执行；扩展的 ID 已固定为 `lateron-ff-port-695d5826@lhy.local`，**签名后不可更改**（改 ID 等于换一个扩展）。

## AMO 签名记录（2026-10-13）

| 项 | 值 |
|---|---|
| 通道 | `unlisted`（只签名、不上架 AMO 商店，由本仓库分发） |
| 工具 | `web-ext` 8.10.0：`web-ext sign --source-dir <解包目录> --artifacts-dir <输出目录> --channel unlisted --api-key <JWT issuer> --api-secret <JWT secret>` |
| 输入 | `LaterOn-1.66.1-firefox-amo-unsigned.xpi`（498924 字节，37 文件） |
| 输出 | AMO 回签包 518829 字节，42 文件，SHA-256 `E154AC5A67B6F1123BB2473387C5CACC1C2115CE4539B2C0B05A81CAE8277524` |
| 耗时 | 提交 2026-10-12 23:55 → 回签包下载完成 2026-10-13 00:01（约 6.5 分钟，自动校验通过，未进人工审核队列） |
| 校验 | 包内 `META-INF/mozilla.rsa`（4379 字节）+ `mozilla.sf` + `cose.sig`/`cose.manifest` 齐全；显示名、`gecko.id`、`strict_min_version 140.0`、`data_collection_permissions {"required":["none"]}` 与签名前一致 |
| 后续 | 首次签名时 AMO 自动建立了该扩展的条目（源码里对应 `POST addon/`），无需手工先建 |

> **凭据提醒**：用于本次签名的 AMO **API key（JWT issuer / secret）已经暴露在对话记录里**，请到 <https://addons.mozilla.org/developers/addon/api/key/> **Revoke 掉这一对、再 Generate new credentials**，之后用新凭据签名即可（扩展本身不受影响）。

## 本版做了什么

- 侧栏：`side_panel` / `chrome.sidePanel` → `sidebar_action` + `ff-sidebar.js` 垫片（含「点击图标开侧栏」与「必须用户手势内打开」的处理）。
- 后台：`service_worker` → 事件页 `background.scripts`（**`background.js` 业务逻辑一个字节没改**）。
- 选项页：`options_page` → `options_ui`（115 兼容）。
- 翻译：Chrome 内置 `Translator` / `LanguageDetector` 缺失 → 功能降级隐藏，不报错。
- 数据与界面逻辑、存储结构、i18n 键位与上游一致，两版可共用同一份数据。

## 验证状态

- 上游 53 项测试：**51 通过 / 2 失败**，与移植前基线**逐项一致**（2 个失败是上游自带的既有问题）。
- `addons-linter`（两版都是 **0 error / 7 warning**）：
  - 日常版：1 条未声明数据收集 + 4 条上游既有 `innerHTML` + 2 条已知 `sidePanel` 残留；
  - AMO 版：`MISSING_DATA_COLLECTION_PERMISSIONS` 已消除，改为 1 条「Android 不支持」（`sidebar_action` 是桌面专有，如实标注）+ 同样 4 条 + 2 条。
- 真机实测：Firefox 157.0.1 无头装载成功，后台页与 `sidepanel.html` / `settings.html` / `library.html` 三个扩展页**均无 JS 报错**。
- 签名验证：AMO 回签包内 5 个 `META-INF/` 文件齐全（`mozilla.rsa` 4379 字节），解包后 42 文件、显示名与 gecko 键与签名前逐字段一致；本 Release 附件下载后 SHA-256 与本地逐字节一致（`E154AC5A…7524`）。**在正式版"从文件安装"这一步仍需你自己点一遍确认**（无头环境无法替代）。
- 原始报告：`port-docs/lint-firefox-115.json`、`port-docs/lint-firefox-amo.json`（**均为改名后重跑**，两版仍是 0 error / 7 warning，告警条目与改名前逐条相同）；测试逐项结果 `port-docs/baseline-amo.csv`、改名后 `port-docs/baseline-rename.csv`。

## 已知限制

侧栏内 `close()` 行为、侧栏默认宽度观感、与系统快捷键冲突、`contextMenus` 的 `action` 上下文呈现、Trusted Types 站点上的 4 处 `innerHTML`、以及事件页被回收后可能重复注入 CSS（上游内存态问题）——详见仓库 `README.md` 的「已知限制」。
**这 7 项必须在有头浏览器里由真人点一遍**：逐条操作脚本、通过判据与记录模板见 [`UI-人工点验清单.md`](./UI-人工点验清单.md)，不要只看无头结果就当作验收完毕。
