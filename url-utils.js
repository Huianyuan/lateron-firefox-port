// Shared URL canonicalization for matching the active tab with saved items.
(function () {
  function normalize(url) {
    try {
      const parsed = new URL(url);
      // 同一 YouTube 视频可能来自稍后观看、播放列表、短链接或移动端。
      // 用视频 ID 匹配；保留原始网址用于实际打开，不改变播放时间或列表。
      const hostname = parsed.hostname.toLowerCase();
      const youtube = ["youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"].includes(hostname);
      let videoId = "";
      if (["http:", "https:"].includes(parsed.protocol) && !parsed.port) {
        if (["youtu.be", "www.youtu.be"].includes(hostname)) {
          videoId = parsed.pathname.match(/^\/([^/]+)\/?$/)?.[1] || "";
        } else if (youtube) {
          videoId = /^\/watch\/?$/.test(parsed.pathname)
            ? parsed.searchParams.get("v") || ""
            : parsed.pathname.match(/^\/(?:shorts|embed|live)\/([^/]+)\/?$/)?.[1] || "";
        }
      }
      if (/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
        return `https://youtube.com/watch?v=${videoId}`;
      }
      const host = parsed.host.toLowerCase().replace(/^www\./, "");
      const path = parsed.pathname.replace(/\/+$/, "") || "/";
      const keep = [...parsed.searchParams.entries()]
        .filter(([key]) => !/^(utm_|fbclid|gclid|mc_|ref|spm|igshid)/i.test(key))
        .sort(([a], [b]) => a.localeCompare(b));
      const search = keep.length
        ? "?" + keep.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join("&")
        : "";
      return `${parsed.protocol}//${host}${path}${search}`;
    } catch {
      return String(url || "").trim().toLowerCase();
    }
  }

  globalThis.LaterOnUrl = { normalize };
})();
