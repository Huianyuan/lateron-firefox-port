# Release v1.66.1-ff-port · LaterOn Firefox 适配版（未签名）

基于上游 **LaterOn v1.66.1**（commit `00fde27be93656d650ac5c52adc2684d511adb53`）+ 上游 **`a1a5313`**（2026-10-12 采纳 MIT 协议、并在发行包里带上 `LICENSE`）的 Firefox（Manifest V3）社区移植版。
**上游已采用 [MIT License](https://github.com/gaoyiiiii/LaterOn/blob/main/LICENSE)**（`Copyright (c) 2026 yiiiii`），本仓库同样以 MIT 发布：两个包内都已包含 `LICENSE`，再分发时请保留该文件与版权声明，并注明这是基于 LaterOn 的**非官方社区移植版**（上游 README 的明文要求）。

## 附件（两个包，按用途选一个）

| 文件 | 用途 | 大小 | 最低 Firefox | SHA-256 |
|---|---|---|---|---|
| `LaterOn-1.66.1-firefox.xpi` | **日常用这个**：`about:debugging` 临时载入 | 498779 字节 | 115 | `C826F4F41508CB444BAC53454543D04E0B21B36A788C133756BFC5D16C5B19C8` |
| `LaterOn-1.66.1-firefox-amo.xpi` | **提交 AMO 签名用**（已声明 `data_collection_permissions`） | 498812 字节 | 140 | `6DCA6DEC48AB4FA3AFCE8DC316173DFA6069115D9E0D5FC82F455D79A6909C9E` |

两个包都是 **37 个文件**（含上游 `LICENSE`），除 `manifest.json` 里的 `strict_min_version` 与 `data_collection_permissions` 外内容完全相同。

> 2026-10-12 因上游改为 MIT 协议（提交 `a1a5313`）重新打包：文件数 36 → 37，两个附件均已**替换**，旧的大小与哈希已作废。

> `.xpi` 就是一个 ZIP，可以直接解压查看内容；`manifest.json` 里能看到 Firefox 专用键（`sidebar_action`、`browser_specific_settings.gecko`）。

## 临时使用方法（推荐，无需签名）

**准备**：Firefox 115 及以上（实测 157.0.1）；把 `LaterOn-1.66.1-firefox.xpi` 下载到本机。

1. 把 `.xpi` **解压到一个空目录**（右键 → 解压到 `LaterOn-ff\`）。解压后目录里应当直接看到 `manifest.json`，**不要**多一层文件夹。
2. Firefox 地址栏输入 `about:debugging#/runtime/this-firefox` 回车。
3. 点 **「临时载入附加组件…」**（Load Temporary Add-on…）。
4. 在弹出的文件选择框里，进入刚才的解压目录，选中 **`manifest.json`** 并打开。
5. 列表里出现 `LaterOn`（ID `lateron-ff-port-695d5826@lhy.local`）即装载成功。
6. 点工具栏的 LaterOn 图标 → 右侧弹出侧栏即为正常（若图标没显示，点扩展菜单的拼图图标把 LaterOn 固定到工具栏）。
7. 验证通过后，可以打开 `about:addons` → 扩展 → LaterOn 查看权限与选项页。

**注意**：临时载入的扩展 **重启 Firefox 后会消失**，需要重新执行一遍第 2–5 步。这是 Firefox 的设计，不是扩展的问题。

## 永久安装

- **Firefox Developer Edition / ESR**：`about:config` 把 `xpinstall.signatures.required` 设为 `false`，然后拖入 `.xpi` 安装。**Firefox 正式版不支持**这条路（Release/Beta 强制签名校验）。
- **正式版**：必须走 AMO 签名。用附件里的 `LaterOn-1.66.1-firefox-amo.xpi`（已按 2025-11-03 起的要求声明 `data_collection_permissions: {"required": ["none"]}`），两条路线：
  - **路线 A（网页）**：<https://addons.mozilla.org/developers/> → 提交新附加组件 → **On your own / unlisted** → 上传该 `.xpi` → 下载已签名包。
  - **路线 B（命令行）**：把该 `.xpi` 解压成目录后 `web-ext sign --source-dir <目录> --artifacts-dir dist\signed --channel unlisted --api-key <key> --api-secret <secret>`（**不要**直接用仓库根目录当 `--source-dir`，那会把 `node_modules` 打进去）。
  - **前置条件**：AMO 账号必须已开 **2FA**（否则拿不到 API key）；扩展 ID 已固定为 `lateron-ff-port-695d5826@lhy.local`，签名后不可更改。

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
- 原始报告：`port-docs/lint-firefox-115.json`、`port-docs/lint-firefox-amo.json`；测试逐项结果 `port-docs/baseline-amo.csv`。

## 已知限制

侧栏内 `close()` 行为、侧栏默认宽度观感、与系统快捷键冲突、`contextMenus` 的 `action` 上下文呈现、Trusted Types 站点上的 4 处 `innerHTML`、以及事件页被回收后可能重复注入 CSS（上游内存态问题）——详见仓库 `README.md` 的「已知限制」。
**这 7 项必须在有头浏览器里由真人点一遍**：逐条操作脚本、通过判据与记录模板见 [`UI-人工点验清单.md`](./UI-人工点验清单.md)，不要只看无头结果就当作验收完毕。
