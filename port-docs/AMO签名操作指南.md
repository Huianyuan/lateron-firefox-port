# LaterOn Firefox 移植版 · AMO 签名操作指南（可执行版）

> **文档版本**：v1.0（2026-10-12）
> **适用产物**：`dist/LaterOn-1.66.1-firefox-amo.xpi`（= AMO 目标变体：`strict_min_version 140.0` + `data_collection_permissions`）
> **目标**：拿到 Mozilla 已签名的 `.xpi`，放进 GitHub Release，让用户「下载 → 双击 → 正式版 Firefox 直接装上」。
> **本机实测依据**：web-ext 8.10.0 的参数表、`addons.mozilla.org` 网络可达性、web-ext 内部提交逻辑（详见附录 C）。
> **诚实声明**：**我没有 AMO 账号，第 3 步之后（真正提交、拿回签名包）本机未实测**；所有账号侧动作来自 Mozilla 官方文档与 web-ext 源码。第 1、2 步（准备包、命令行参数）已在本机验证。

---

## 0. 一页速览

| 决策点 | 结论 | 理由 |
|---|---|---|
| 用哪个包去签名 | **必须是 AMO 变体**（`--target firefox --amo`） | 2025-11-03 起 AMO 拒绝缺 `data_collection_permissions` 的新扩展提交签名 |
| 分发方式 | **unlisted（自行分发）** | 你的分发入口是 GitHub Release；listed 需要填一堆 AMO 元数据并过人工审核 |
| 网页上传 vs 命令行 | **命令行 `web-ext sign`（推荐）** | 一条命令完成「建条目 → 上传 → 等签名 → 落盘」；网页路线作为备选 |
| 要不要先改名 | **已经改完了**（2026-10-12 第八棒） | 扩展显示名现为「LaterOn 社区移植版 · 项目型网页管理」/「LaterOn Community Port · Project Web Manager」；改名必须早于签名，而 §3 解出来的包就是改名后的包 |
| 预期耗时 | 账号+2FA 5–10 分钟，签名 1–3 分钟（被人工审核则最长 24h+），Release 替换 5 分钟 | AMO 官方说明：签名「up to 24 hours … or longer if selected for manual review」 |
| 前置账号要求 | AMO 账号 + **强制 2FA** + API key（JWT issuer / JWT secret） | 2FA 是 2021-03-15 起的硬性要求，未开则拿不到 API key |

---

## 1. 前置 A：AMO 账号与 2FA（必做，否则拿不到 API key）

1. 打开 <https://addons.mozilla.org/>，用 Firefox 账号登录；没有就注册。
2. **开启双因素认证**：右上头像 → **Account（账户）** → **Security（安全）** → Two-factor authentication → 用任意验证器 App（如 Aegis / Google Authenticator）扫码并输入 6 位码。
   - 未开启 2FA 的账号**无法访问 API key 页面**（会直接拦住），这是 2021-03-15 起的强制策略。
3. 复核：`Account → Security` 页面显示 2FA 已启用 / 已绑定。

**完成判据**：第 2 步页面出现「已启用」标识。

---

## 2. 前置 B：取得 API key

1. 打开 <https://addons.mozilla.org/developers/addon/api/key/>。
2. 点击 **Generate new credentials**（如有旧凭据可先 revoke）。
3. 页面给出两项，**只显示这一次，务必立刻复制到密码管理器**：
   - **JWT issuer** → 对应 web-ext 的 `--api-key`
   - **JWT secret** → 对应 web-ext 的 `--api-secret`
4. **安全纪律**：这两个值是密码级凭据，**不要**贴进聊天窗口、**不要**写进仓库任何文件（`.gitignore` 也挡不住已提交的文件）。本机 `github/` 仓库不接受任何形如 `user:xxx` 的 key 文件。

**完成判据**：拿到 `JWT issuer`（形如 `user:12345678:123`）与一长串 `JWT secret`。

---

## 3. 准备「可签名源目录」（本机可立即执行，已实测）

web-ext 的 `sign` 命令要求源目录**只有扩展运行时文件**——绝不能直接指向 `work/`（那里有 `node_modules`、`package.json`，会被一起打包）。

```powershell
$topic = "F:\ALL_AI\小助理\open-source-collection\lateron-firefox-port"
$src   = "C:\Users\lhy\AppData\Local\Temp\lateron-amo-src"

Remove-Item -Recurse -Force $src -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $src | Out-Null

# 用 python 解包（Expand-Archive 只认 .zip 后缀，对 .xpi 会报错）
& "D:\ALL_Python\python312\python312.exe" -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$topic\dist\LaterOn-1.66.1-firefox-amo.xpi" $src

# 期望：37 个文件
& "D:\ALL_Python\python312\python312.exe" -c "import sys,os; print(sum(len(f) for _,_,f in os.walk(sys.argv[1])))" $src

# 复核 manifest 里 AMO 要求的两个键
Get-Content "$src\manifest.json" -Raw -Encoding utf8 | ConvertFrom-Json |
  ForEach-Object { $_.browser_specific_settings.gecko } | Format-List
```

**期望输出**：
```
37
id                             : lateron-ff-port-695d5826@lhy.local
strict_min_version             : 140.0
data_collection_permissions    : @{required=System.Object[]}
```

> 若 `dist/LaterOn-1.66.1-firefox-amo.xpi` 不存在或已过期，用下面命令重建（cwd 必须是 `work\`，python 用全路径）：
> ```powershell
> cd "$topic\work"
> & "D:\ALL_Python\python312\python312.exe" "scripts\build-release.py" --target firefox --amo
> # → dist/LaterOn-1.66.1-firefox-amo.zip（498924 字节，SHA256 4B2674AA…F8B6）
> ```
> 注意：**`python` 裸命令在本机不可用**（PATH 里的 shim 会报 `Unable to create process`），必须用 `D:\ALL_Python\python312\python312.exe`。

**完成判据**：目录里有 37 个文件，且 `manifest.json` 的 `strict_min_version` 是 `140.0`、存在 `data_collection_permissions`。

---

## 4. 改名（**已于 2026-10-12 第八棒完成**）

**这一步已经做完了**，下面保留操作过程与结果，供你日后需要再次区分版本时参考。改名前扩展显示名是上游的 `LaterOn · 项目型网页管理`，与官方版无法区分，于是改了 `_locales` 两个 JSON 各三处：

| 文件 | 键 | 改前 | 改后（现行） |
|---|---|---|---|
| `work\_locales\zh_CN\messages.json` | `extensionName.message` | `LaterOn · 项目型网页管理` | **`LaterOn 社区移植版 · 项目型网页管理`** |
| `work\_locales\en\messages.json` | `extensionName.message` | `LaterOn · Project Web Manager` | **`LaterOn Community Port · Project Web Manager`** |
| 同上两份 | `actionTitle.message` | `打开 LaterOn 侧栏` / `Open the LaterOn side panel` | **`打开 LaterOn 社区移植版侧栏`** / **`Open the LaterOn Community Port side panel`** |
| 同上两份 | `extensionDescription.message` | 上游原文 | 末尾追加「基于 gaoyiiiii/LaterOn 的非官方 Firefox 移植版（MIT 许可）。」/「 Unofficial Firefox port of gaoyiiiii/LaterOn (MIT).」 |

另外，上游测试 `work\tests\i18n-onboarding.test.js` 的断言里**写死了旧显示名**，改名后必须同步改（本移植版**第一次修改上游测试文件**）；改完 53 项测试仍是 **51/53**（2 个失败是上游 v1.66.1 自带的）。

改完**必须**重新打包两个 Firefox 变体（同一份 manifest 派生）并重跑 linter：

```powershell
cd "$topic\work"
& "D:\ALL_Python\python312\python312.exe" "scripts\build-release.py" --target firefox
& "D:\ALL_Python\python312\python312.exe" "scripts\build-release.py" --target firefox --amo
& "node_modules\.bin\addons-linter.cmd" "dist\LaterOn-1.66.1-firefox-amo.zip" -o json
```

**注意**：
- 只改文件**内容**，不新增文件；`scripts/build-release.py` 的 37 文件清单是白名单，多一个文件会被拒绝构建。
- 改名后 GitHub Release 里的两个附件**已一并换成改名后的包**（2026-10-12 第八棒）：`LaterOn-1.66.1-firefox.xpi` 498891 字节 / `CFE6333D…9F5F`、`LaterOn-1.66.1-firefox-amo.xpi` 498924 字节 / `4B2674AA…F8B6`（Chrome 对照包 498810 / `D2A10577…8C90`）。注意**旧包与新签名包仍然不一致**：签回来的包会再多一个 `META-INF/` 目录，字节数会增加。
- **签名后改名字 = 签名失效**，所以这一步不能后置。

**完成判据**：linter 仍是 `errors 0 / warnings 7`（`KEY_FIREFOX_ANDROID_UNSUPPORTED_BY_MIN_VERSION` + 4× `UNSAFE_VAR_ASSIGNMENT` + 2× `UNSUPPORTED_API sidePanel.setPanelBehavior`）。

---

## 5. 路线 B（推荐）：命令行 `web-ext sign`

### 5.1 一条命令

```powershell
$topic = "F:\ALL_AI\小助理\open-source-collection\lateron-firefox-port"
$src   = "C:\Users\lhy\AppData\Local\Temp\lateron-amo-src"

& "$topic\work\node_modules\.bin\web-ext.cmd" sign `
    --source-dir      $src `
    --artifacts-dir   "$topic\work\web-ext-artifacts" `
    --channel         unlisted `
    --api-key         "<JWT issuer>" `
    --api-secret      "<JWT secret>" `
    --approval-timeout 300000 `
    --no-input `
    --verbose
```

### 5.2 参数表（web-ext 8.10.0 实测）

| 参数 | 必填 | 说明 |
|---|---|---|
| `-s/--source-dir` | ✅ | 第 3 步那个 37 文件目录 |
| `-a/--artifacts-dir` | ✅ | 签名包落盘位置（默认 `<cwd>\web-ext-artifacts`） |
| `--channel` | ✅ | `unlisted`（自行分发）或 `listed`（上架 AMO） |
| `--api-key` | ✅ | AMO 的 **JWT issuer** |
| `--api-secret` | ✅ | AMO 的 **JWT secret** |
| `--approval-timeout` | ❌ | 等签名结果的毫秒数；**设 0 = 提交后不等**；未设则回落 `--timeout` |
| `--timeout` | ❌ | 单次 HTTP 超时 |
| `--api-proxy` | ❌ | 走代理时填（本机实测 **AMO 直连可用，不需要代理**） |
| `--amo-base-url` | ❌ | 默认 `https://addons.mozilla.org/api/v5/`；（本机实测：直连与经代理均可访问） |
| `--amo-metadata` | ❌ | 仅 listed 需要的元数据 JSON |
| `--upload-source-code` | ❌ | 本扩展是**未压缩可读 JS**，不需要上传源码包 |
| `--no-input` | ❌ | 非交互（推荐，避免卡在提示） |
| `-i/--ignore-files` | ❌ | 源目录已干净，不需要 |

### 5.3 首次运行会发生什么（web-ext 源码行为，已核对）

1. 本地校验 manifest 并打成临时 zip；
2. `POST https://addons.mozilla.org/api/v5/addon/` —— **新扩展会被自动创建条目**（源码注释：`it's the indication that a new add-on should be created, rather than a new version`）；
   - 本机实测该 ID `lateron-ff-port-695d5826@lhy.local` 目前 **404 Not found**，即**尚未注册**，正是「新扩展」路径。
3. 带 `channel=unlisted` 上传 XPI → 等待 AMO 签名；
4. 签名完成后把签名包写进 `--artifacts-dir`，文件名由 AMO 决定（形如 `<id>-1.66.1-an+fx.xpi`）；
5. 终端出现 `Your add-on has been submitted for signing.` / `Signed XPI downloaded to: …` 之类的成功行。

### 5.4 完成判据

`work\web-ext-artifacts\` 下出现一个**新**的 `.xpi`，且第 6 节校验通过。

---

## 6. 路线 A（备选）：网页上传签名

不装任何工具，全在浏览器里点：

1. 打开 <https://addons.mozilla.org/developers/> → **Submit a New Add-on**。
2. 选择 **On your own（self-distribution / unlisted）** —— 这一步决定「只签名，不上架」。
3. 上传第 3 步那个目录**重新打成的 zip**（或直接用 `dist/LaterOn-1.66.1-firefox-amo.zip`）。
   - ⚠️ 上传前**别解压后手动再压缩**并带上 `__MACOSX`/多一层目录；用现成的 zip 最稳。
4. AMO 先自动校验（addons-linter），失败会给出具体错误码 → 对照第 10 节处置。
5. 通过后进入签名等待；完成后在 **Developer Hub → 你的扩展 → 版本列表** 里下载已签名 `.xpi`。

**与路线 B 的差异**：网页路线的第一次提交仍需你手工选「self-distribution」；后续版本可直接在 Developer Hub 上传新版本，也可改回命令行。

---

## 7. 验证拿到的包确实是「签名包」

```powershell
$signed = "<web-ext-artifacts 或浏览器下载目录里的签名 xpi>"
& "D:\ALL_Python\python312\python312.exe" -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); print([n for n in z.namelist() if n.startswith('META-INF')])" $signed
```

**期望**：出现 `META-INF/manifest.mf`、`META-INF/mozilla.sf`、`META-INF/mozilla.rsa`（Mozilla 的 JAR 签名块）。未签名的包**没有 `META-INF/`**（当前 `dist/` 里两个 `.xpi` 都是未签名的）。

终局验证（唯一权威）：在**正式版 Firefox**（本机 `D:\Firefox\firefox.exe`）里 `about:addons` → 齿轮 → **从文件安装附加组件** → 选该 xpi：
- 签名有效：**不出现**「无法安装未签名附加组件」提示，直接装上，且不需要改任何 `about:config`；
- 未签名：正式版会拒绝安装（此前只能靠 `about:debugging` 临时装载或 `xpinstall.signatures.required=false` 绕过）。

---

## 8. 签名之后：更新 GitHub Release

Release：<https://github.com/Huianyuan/lateron-firefox-port/releases/tag/v1.66.1-ff-port>（release id `409797272`）
当前两个附件（**都是未签名包**）：

| 附件 | 字节 | 说明 |
|---|---|---|
| `LaterOn-1.66.1-firefox.xpi` | 498891 | min 115 直装变体；**永远只能临时装载**（FF 115–139 用户用它） |
| `LaterOn-1.66.1-firefox-amo.xpi` | 498924 | AMO 签名**输入**包（min 140 + dcp）；签名后建议替换为 AMO 回传的签名包 |

**网页操作（最简单）**：Release → `Edit` → 删除 `LaterOn-1.66.1-firefox-amo.xpi` → `Attach binaries` 上传签名包（建议重命名为 `LaterOn-1.66.1-firefox-signed.xpi`，**改文件名不影响签名**，改内容才失效）→ 正文里把该附件标成「Mozilla 已签名 · 下载即可永久安装」→ `Update release`。

**命令行/API 操作**（本仓库此前用过这条路，本机**没有 `gh` CLI**）：token 从 Windows 凭据管理器现取现用（只留在进程内，不打印、不落盘）：

```powershell
$env:GIT_TERMINAL_PROMPT = "0"
$cred = ("protocol=https`nhost=github.com`n`n" | git credential fill) | Out-String
$tok  = ($cred -split "`r?`n" | Where-Object { $_ -like "password=*" }) -replace "^password=", ""

# 1) 删掉旧的未签名 amo 附件（id 634104772）
Invoke-RestMethod -Method Delete -Headers @{ Authorization = "token $tok" } `
  -Uri "https://api.github.com/repos/Huianyuan/lateron-firefox-port/releases/assets/634104772"

# 2) 上传签名包
Invoke-RestMethod -Method Post -Headers @{ Authorization = "token $tok" } `
  -ContentType "application/xpi" -InFile "<签名包路径>" `
  -Uri "https://uploads.github.com/repos/Huianyuan/lateron-firefox-port/releases/409797272/assets?name=LaterOn-1.66.1-firefox-signed.xpi"
```

（`api.github.com` 与 `uploads.github.com` 本机直连可用；若某步报连接重置，加 `-Proxy http://127.0.0.1:7897`。）

**git 侧不需要改代码**：签名包是产物，`*.xpi` 已在 `.gitignore` 里；只有正文/附件变化，不需要提交。

---

## 9. 变更管理（签名后的长期纪律）

| 场景 | 做法 |
|---|---|
| 以后出新版本 | 改 `work\manifest.firefox.json` 的 `version`（必须**递增**），重跑 `--target firefox --amo`，再签一次；同一 ID 同版本号不能重复提交 |
| `data_collection_permissions` | **一旦用过就必须一直用**，后续版本删掉会被 AMO 拒 |
| 改了任何字节 | 必须**重新签名**（签名覆盖全部文件内容） |
| 想让 unlisted 包自动更新 | AMO 不推送更新；需要额外在 `gecko` 里加 `update_url` 指向自建 update.json |
| 想上架 AMO（listed） | 需补名称/简介/分类/协议等元数据并过人工审核；签名效力与 unlisted **完全相同** |
| ID | `lateron-ff-port-695d5826@lhy.local` 签名后**不可更改**；若要换 ID，必须在**这次签名之前**决定 |

---

## 10. 故障排查（按报错对照）

| 现象 | 原因 | 处置 |
|---|---|---|
| `Version 1.66.1 already exists` | 同 ID 同版本号已提交过 | 递增 `manifest.firefox.json` 的 `version`，重打包再签 |
| `401 Invalid API key` / `JWT authentication failed` | key/secret 抄错、账号未开 2FA、或 key 已被 revoke | 重开 API key 页面（确认 2FA 已启用）重新生成 |
| `403` / 提示缺 `data_collection_permissions` | 提交了 **115 变体**（无 dcp） | 用 `--target firefox --amo` 的包（第 3 步） |
| `Add-on not found` / `404` | **listed** 通道要求先在 AMO 建条目 | 改用 `--channel unlisted`（web-ext 会自动建），或先在网页创建条目 |
| 卡住不动 / `Approval timeout` | 被抽到人工审核（最长 24h+） | 加大 `--approval-timeout`，或稍后到 Developer Hub 看状态；`--approval-timeout 0` 时命令会直接返回，需自行回网页取件 |
| TLS/连接失败 | 走了不通的代理 | 去掉代理（**AMO 直连可用**）；必须走代理时加 `--api-proxy http://127.0.0.1:7897` |
| linter 报 `UNSAFE_VAR_ASSIGNMENT` | 上游 4 处 `innerHTML` | 与本流程无关，AMO 视为 warning，不阻断签名 |
| 上传包里有 `node_modules` | `-s` 指到了 `work\` | 必须指向第 3 步那个 37 文件目录 |

---

## 11. 本指南未覆盖 / 未知项

- 我**没有 AMO 账号**，第 2 步之后的真实页面文案、按钮位置可能随 AMO 改版变化；以实际页面为准，卡住把报错原文贴给我。
- **改名已执行**（第 4 节，2026-10-12 第八棒）——显示名已与上游官方版区分；代价是三个构建产物的旧哈希全部作废，文档与 Release 附件已同步。
- 签名需要 **min 140**，意味着 **FF 115–139 用户永远只能用临时装载的 115 包**；这是 dcp 政策的直接后果，无法绕过。
- 7 项有头人工点验（见 `UI-人工点验清单.md`）与签名相互独立，签名不替代点验。

---

## 附录 A · 关键路径速查

| 用途 | 值 |
|---|---|
| AMO API key 页面 | <https://addons.mozilla.org/developers/addon/api/key/> |
| AMO 开发者后台 | <https://addons.mozilla.org/developers/> |
| 签名 API 基址 | `https://addons.mozilla.org/api/v5/` |
| 本扩展 ID 查询（实测 404 = 未注册） | `https://addons.mozilla.org/api/v5/addons/addon/lateron-ff-port-695d5826@lhy.local/` |
| 源目录 | `C:\Users\lhy\AppData\Local\Temp\lateron-amo-src`（37 文件） |
| 待签包 | `dist\LaterOn-1.66.1-firefox-amo.xpi`（498924 B / `4B2674AAC5DB40225E7AEFCF3531CE18292BB82E11E0F5034793A509A3BDF8B6`；改名后的现行值，**签名输入就是它**） |
| web-ext | `work\node_modules\.bin\web-ext.cmd`（8.10.0） |
| 签名产物落盘 | `work\web-ext-artifacts\` |

## 附录 B · 官方依据

- 数据收集声明（2025-11-03 起新扩展强制）：<https://blog.mozilla.org/addons/2025/10/23/data-collection-consent-changes-for-new-firefox-extensions/>
- 签名与分发总览：<https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/>
- 自行分发（self-distribution）：<https://extensionworkshop.com/documentation/publish/self-distribution/>
- 内置数据同意调研（dcp 细节）：<https://extensionworkshop.com/documentation/develop/firefox-builtin-data-consent/>
- 未上架扩展的审核与签名解耦：<https://blog.mozilla.org/addons/2015/12/01/de-coupling-reviews-from-signing-unlisted-add-ons/>
- `browser_specific_settings`（含 dcp）：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/browser_specific_settings>
- 2FA 强制：<https://blog.mozilla.org/addons/2021/03/11/two-factor-authentication-required-for-extension-developers/>
- 未签名扩展在正式版被拒：<https://support.mozilla.org/en-US/kb/add-on-signing-in-firefox>

## 附录 C · 本机实测证据（本轮）

| 项 | 结果 |
|---|---|
| `web-ext sign --help` | 8.10.0：`-s`/`-a`/`--api-key`/`--api-secret`/`--channel` 必填；有 `--approval-timeout`（0 = 不等）；**没有** `--headless` |
| `addons.mozilla.org:443` 直连 | `Test-NetConnection` = True；`/api/v5/` 与扩展查询均返回 404（根路径无内容属正常；我们的 ID 404 = 未注册） |
| 经代理 `127.0.0.1:7897` | 同样 404 ⇒ AMO 通道**不需要代理** |
| web-ext 提交逻辑 | `work\node_modules\web-ext\lib\util\submit-addon.js`：`:169 POST addon/`（新建条目）、`:180 PUT addon/{id}/`、`:191 PATCH addon/{id}/versions/{versionId}/`；`:428` 注释确认「新扩展走创建分支」 |
| web-ext 包结构 | 只有 `bin/` + `lib/`，**没有 `dist/`**（查源码别去 `dist\web-ext.js`） |
| 现有两个 Release 附件 | 498891 / 498924 字节（改名后），**均无 `META-INF/`，都是未签名包** |
