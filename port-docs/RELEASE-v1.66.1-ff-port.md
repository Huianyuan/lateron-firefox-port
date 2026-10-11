# Release v1.66.1-ff-port · LaterOn Firefox 适配版（未签名）

基于上游 **LaterOn v1.66.1**（commit `00fde27be93656d650ac5c52adc2684d511adb53`）的 Firefox（Manifest V3）个人移植版。
**非官方、未获上游授权**（上游无 LICENSE）。仅个人自用，请勿再分发。

## 附件

| 文件 | 大小 | 文件数 | SHA-256 |
|---|---|---|---|
| `LaterOn-1.66.1-firefox.xpi` | 498065 字节 | 36 | `F2A5D3CC5F31B08228DF71D18795B0370024FE8993EDD1C49AA268C629423046` |

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
- **正式版**：必须将源码提交 AMO 获取签名后安装（Mozilla 账号需开 2FA；2025-11-03 起新扩展还须在清单里声明 `data_collection_permissions`，本包尚未加）。

## 本版做了什么

- 侧栏：`side_panel` / `chrome.sidePanel` → `sidebar_action` + `ff-sidebar.js` 垫片（含「点击图标开侧栏」与「必须用户手势内打开」的处理）。
- 后台：`service_worker` → 事件页 `background.scripts`（**`background.js` 业务逻辑一个字节没改**）。
- 选项页：`options_page` → `options_ui`（115 兼容）。
- 翻译：Chrome 内置 `Translator` / `LanguageDetector` 缺失 → 功能降级隐藏，不报错。
- 数据与界面逻辑、存储结构、i18n 键位与上游一致，两版可共用同一份数据。

## 验证状态

- 上游 53 项测试：**51 通过 / 2 失败**，与移植前基线**逐项一致**（2 个失败是上游自带的既有问题）。
- `addons-linter`：**0 error / 7 warning**（1 条未声明数据收集 + 4 条上游既有 `innerHTML` + 2 条已知 `sidePanel` 残留）。
- 真机实测：Firefox 157.0.1 无头装载成功，后台页与 `sidepanel.html` / `settings.html` / `library.html` 三个扩展页**均无 JS 报错**。

## 已知限制

侧栏内 `close()` 行为、侧栏默认宽度观感、与系统快捷键冲突、`contextMenus` 的 `action` 上下文呈现、Trusted Types 站点上的 4 处 `innerHTML`、以及事件页被回收后可能重复注入 CSS（上游内存态问题）——详见仓库 `README.md` 的「已知限制」。这些均未在真实交互场景中穷尽验证。
