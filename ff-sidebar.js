// ff-sidebar.js —— LaterOn 的 Firefox 适配垫片
//
// 作用：把上游对 Chrome 专有 chrome.sidePanel.* 的调用，统一收敛到本模块，
//       在 Firefox 下转成 browser.sidebarAction.*。
//
// 载入位置（三处，缺一不可）：
//   1. manifest.firefox.json → background.scripts 首项
//   2. sidepanel.html 的 <script> 列表首位
//   3. library.html 的 <script> 列表首位
//
// 设计约束：
//   * 不去给 chrome 对象挂属性 —— Firefox 的 chrome/browser 是受管代理，写新属性不可靠。
//     所以统一走"显式改调用点"的路线。
//   * 在 Chrome 里也安全：检测到 chrome.sidePanel 就用它，行为与上游逐字节等价。
//   * 本文件不依赖任何其它模块，可以放在最前面。
//
// 证据档：据官方文档推断（sidebarAction 三方法见 notes-firefox-platform.md），
//         行为项标为"待施工者实测"，见第 12.4 节 A-02 / A-03 / A-04 / A-05。

// ── Firefox 后台兼容：importScripts 守卫（见第 6.3 节方案 A）────────────
// Chrome 的 MV3 后台是 Service Worker，有 importScripts，background.js:1 用它同步加载前置模块。
// Firefox 的 MV3 后台是扩展页文档（background.scripts 按序在同一全局作用域执行），
// 文档上下文没有 importScripts，background.js:1 会直接抛 ReferenceError，整个后台脚本中断。
// 这里在文档上下文里补一个空实现：那两个模块已由 manifest.background.scripts 加载过，
// 再执行一次会让 reading-position-background.js 重复注册监听器。
// 若某种实现把后台跑在 Worker 里（有 importScripts 且没有 document），本段自动跳过。
if (typeof document !== "undefined") {
  globalThis.importScripts = function () {
    /* no-op：前置脚本已由 manifest 的 background.scripts 按序加载 */
  };
}

(function () {
  const api = globalThis.browser ?? globalThis.chrome ?? {};
  const hasChromeSidePanel = typeof api.sidePanel?.open === "function";
  const sidebar = api.sidebarAction;              // Firefox: SidebarAction；Chrome: undefined

  function warnIgnoredWindowId(method, windowId) {
    if (windowId == null) return;
    // Firefox 的 sidebarAction.open/close 只作用于当前窗口，没有 windowId 参数。
    // 不抛错：抛错会让 library.js 的整条"侧栏阅读"链路退化到"在新标签页里打开"。
    console.warn(
      "[LaterOn] Firefox 的 sidebarAction." + method + "() 不支持指定 windowId，已忽略：",
      windowId
    );
  }

  const LaterOnSidePanel = {
    // 是否正在用 Firefox 的侧栏实现（调用点用它做分支判断）
    get isFirefoxSidebar() { return !hasChromeSidePanel && !!sidebar; },

    // 能不能真的打开/关闭（调用点用它替代原来对 chrome.sidePanel?.open 的 typeof 判断）
    get canOpen() {
      return hasChromeSidePanel
        ? typeof api.sidePanel.open === "function"
        : typeof sidebar?.open === "function";
    },
    get canClose() {
      return hasChromeSidePanel
        ? typeof api.sidePanel.close === "function"
        : typeof sidebar?.close === "function";
    },

    // Chrome: 交给浏览器保存这个偏好（工具栏左键＝切换侧栏）。
    // Firefox: 没有 openPanelOnActionClick。等价物是下面注册的 action.onClicked，
    //          它满足 sidebarAction.open() 对用户手势的要求。
    //          openPanelOnActionClick === false 在 Firefox 无法表达 —— 登记为能力缺口 R-06。
    async setPanelBehavior(options) {
      const openPanelOnActionClick = options?.openPanelOnActionClick;
      if (hasChromeSidePanel && typeof api.sidePanel.setPanelBehavior === "function") {
        return api.sidePanel.setPanelBehavior({ openPanelOnActionClick: !!openPanelOnActionClick });
      }
      if (openPanelOnActionClick === false) return false;   // 表达不了，如实返回 false
      return true;                                          // 空操作成功
    },

    // 打开侧栏。Chrome 支持指定窗口；Firefox 只能开当前窗口。
    async open(options) {
      const windowId = options?.windowId ?? null;
      if (hasChromeSidePanel && typeof api.sidePanel.open === "function") {
        return api.sidePanel.open(windowId == null ? undefined : { windowId });
      }
      if (typeof sidebar?.open !== "function") {
        throw new Error("Firefox 的 sidebarAction.open 不可用");
      }
      warnIgnoredWindowId("open", windowId);
      await sidebar.open();
      return undefined;
    },

    // 关闭侧栏。返回 true 表示"确实调用了关闭"。
    // 返回 false 表示当前环境没有关闭能力 —— 调用点必须自己准备退路（见 7.5 节）。
    async close(options) {
      const windowId = options?.windowId ?? null;
      if (hasChromeSidePanel && typeof api.sidePanel.close === "function") {
        await api.sidePanel.close(windowId == null ? undefined : { windowId });
        return true;
      }
      if (typeof sidebar?.close !== "function") return false;
      warnIgnoredWindowId("close", windowId);
      await sidebar.close();
      return true;
    }
  };

  globalThis.LaterOnSidePanel = LaterOnSidePanel;

  // ── Firefox：把工具栏图标左键接到侧栏上 ─────────────────────────────
  // 上游 background.js:261-273 + :374-375 的做法是让浏览器原生处理图标左键
  // （setPanelBehavior({openPanelOnActionClick:true})）。Firefox 没这个开关，
  // 于是图标点了没反应 —— 这里显式补上，action.onClicked 本身就是用户手势，
  // 正好满足 sidebarAction.open() 的手势要求。
  // 只在没有 chrome.sidePanel 时注册（Chrome 交给 setPanelBehavior，避免两套逻辑打架）。
  if (!hasChromeSidePanel && api.action?.onClicked?.addListener) {
    api.action.onClicked.addListener(async () => {
      try {
        await LaterOnSidePanel.open();
      } catch (error) {
        // 退路：侧栏开不了就退到全屏收藏库，至少不让这次点击落空。
        console.warn("[LaterOn] 打开 Firefox 侧栏失败，改为打开收藏库：", error);
        try {
          await api.tabs.create({ url: api.runtime.getURL("library.html") });
        } catch { /* 连标签页都开不了就放弃，用户还能用快捷键 */ }
      }
    });
  }
})();
